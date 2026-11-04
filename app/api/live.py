"""What Exasol is doing right now, read from its own system tables and the run log.

Read-only and on its own connection, so a poll never waits for the pool or touches the pipeline. Nothing is calculated
here: statements, operators, row counts and timings are shown as Exasol and the runner recorded them.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta, timezone

from scripts.audit import now, pipeline_files
from scripts.db import connect, schemas
from scripts.sqlrun import header, render, statements

S = schemas()
OUT = S["OUT"]
STALE_AFTER = timedelta(hours=1)  # a RUNNING row this old means the runner was killed before it could mark the run
CACHE_S = 0.3  # several open tabs share one read

_lock = threading.Lock()
_conn = None
_cached: tuple[float, dict] | None = None
_pipeline: list[dict] | None = None
_lookup: tuple[str, dict[str, str]] | None = None


def pipeline() -> list[dict]:
    global _pipeline
    if _pipeline is None:
        _pipeline = []
        for path in pipeline_files():
            meta = header(path)
            _pipeline.append({"step_id": meta.get("step", path.stem.upper()), "file_path": f"sql/{path.name}",
                              "purpose": meta.get("purpose", "")})
    return _pipeline


def _prefix(sql: str) -> str:
    return " ".join(sql.split())[:160]


def statement_steps(run_id: str) -> dict[str, str]:
    """Which pipeline step each statement of this run belongs to, from the SQL files themselves.

    Timing cannot say this reliably: a poll can read the run log just before a step ends and the session just after.
    The runner's own bookkeeping statements are in no file, so they map to no step.
    """
    global _lookup
    if _lookup is None or _lookup[0] != run_id:
        found = {}
        for path in pipeline_files():
            step_id = header(path).get("step", path.stem.upper())
            for stmt in statements(render(path.read_text(), run_id)):
                found[_prefix(stmt)] = step_id
        _lookup = (run_id, found)
    return _lookup[1]


def step_states(steps: list[dict], timings: dict[str, dict], status: str | None) -> list[dict]:
    """Done steps are in the run log. The first step without a timing is the one running, or the one that failed."""
    out = []
    pending = {"RUNNING": "running", "FAILED": "failed"}.get(status or "")
    for step in steps:
        t = timings.get(step["step_id"])
        state = "done" if t else (pending or "waiting")
        if not t:
            pending = None
        out.append({**step, "state": state, "duration_ms": t["duration_ms"] if t else None,
                    "rows_out": t["rows_out"] if t else None})
    return out


def is_audit_write(session: dict) -> bool:
    """A statement writing to the run's working or output tables, as opposed to a screen reading results."""
    sql = (session.get("sql_text") or "").upper()
    return session["command_name"] not in ("SELECT", "COMMIT") and any(f"{S[k]}." in sql for k in ("WORK", "OUT"))


def is_book_write(session: dict) -> bool:
    """A statement loading a loan book."""
    sql = (session.get("sql_text") or "").upper()
    return session["command_name"] not in ("SELECT", "COMMIT") and any(f"{S[k]}." in sql for k in ("RAW", "TRUTH"))


def pick_current(sessions: list[dict]) -> dict | None:
    """The statement to feature: the audit's own if there is one, then a book load, then anything but a commit."""
    def rank(s: dict) -> int:
        if is_audit_write(s):
            return 0
        if is_book_write(s):
            return 1
        return 3 if s["command_name"] == "COMMIT" else 2
    return min(sessions, key=rank, default=None)


def _mask(sql: str | None) -> str | None:
    return re.sub(r"(?i)(IDENTIFIED\s+BY\s+)\S+", r"\1***", sql) if sql else sql


def _fetch(c, sql: str, params: dict | None = None) -> list[dict]:
    st = c.execute(sql, params or {})
    cols = [x.lower() for x in st.column_names()]
    return [dict(zip(cols, r)) for r in st.fetchall()]


def _read(c) -> dict:
    run = next(iter(_fetch(c, f"SELECT run_id, dataset_id, status, label, started_at, duration_ms FROM {OUT}.audit_runs "
                              f"ORDER BY started_at DESC LIMIT 1")), None)
    status = run["status"] if run else None
    if run and status == "RUNNING":
        cutoff = (datetime.now(timezone.utc) - STALE_AFTER).strftime("%Y-%m-%d %H:%M:%S")
        if run["started_at"] < cutoff:
            status = run["status"] = "FAILED"
    timings = {}
    if run:
        timings = {r["sql_step_id"]: r for r in _fetch(
            c, f"SELECT sql_step_id, duration_ms, rows_out FROM {OUT}.step_timings WHERE run_id = {{r}}", {"r": run["run_id"]})}
    sessions = _fetch(c, """SELECT session_id, user_name, status, command_name, stmt_id, duration, activity, temp_db_ram,
                                   SUBSTR(sql_text, 1, 4000) AS sql_text
                            FROM EXA_DBA_SESSIONS
                            WHERE session_id <> CURRENT_SESSION AND status <> 'IDLE' AND sql_text IS NOT NULL""")
    for s in sessions:
        s["sql_text"] = _mask(s["sql_text"])
    current = pick_current(sessions)
    operators = []
    if current:
        current["audit"] = is_audit_write(current)
        current["step_id"] = statement_steps(run["run_id"]).get(_prefix(current["sql_text"] or "")) if run else None
        operators = _fetch(c, """SELECT part_id, part_name, part_info, part_finished, object_schema, object_name,
                                        object_rows, out_rows, duration, cpu, temp_db_ram_peak
                                 FROM EXA_DBA_PROFILE_RUNNING
                                 WHERE session_id = {s!d} AND stmt_id = {t!d} ORDER BY part_id LIMIT 60""",
                           {"s": current["session_id"], "t": current["stmt_id"]})
    return {
        "polled_at": now(),
        "version": c.execute("SELECT param_value FROM EXA_METADATA WHERE param_name = 'databaseProductVersion'").fetchval(),
        "open_sessions": c.execute("SELECT COUNT(*) FROM EXA_DBA_SESSIONS WHERE client NOT LIKE 'LogServer%'").fetchval(),
        "run": run,
        "running": status == "RUNNING",
        "steps": step_states(pipeline(), timings, status),
        "current": current,
        "operators": operators,
        "others": [s for s in sessions if s is not current and s["command_name"] != "COMMIT"],
    }


def snapshot() -> dict:
    global _conn, _cached
    with _lock:
        if _cached and time.monotonic() - _cached[0] < CACHE_S:
            return _cached[1]
        try:
            if _conn is None:
                _conn = connect()
            data = _read(_conn)
        except Exception:
            try:
                if _conn is not None:
                    _conn.close()
            finally:
                _conn = None
            raise
        _cached = (time.monotonic(), data)
        return data

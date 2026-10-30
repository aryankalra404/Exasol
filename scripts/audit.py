"""Run the Sahi Byaaj audit pipeline inside Exasol.

Every figure is computed by the numbered SQL files in sql/. This script only orders them, records the run
(run id, policy snapshot, per-step timings) and the lineage (step id, file, SHA-256 of the SQL text).

Usage: python -m scripts.audit [--label "text"]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone

from scripts.db import ROOT, connect, schemas
from scripts.sqlrun import SQL_DIR, header, run_file, sha

PIPELINE_MIN_STEP = 10  # files below this create schemas and are run by the loader


def pipeline_files():
    files = sorted(p for p in SQL_DIR.glob("*.sql") if int(p.name.split("_")[0]) >= PIPELINE_MIN_STEP)
    return files


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def run_audit(label: str = "", conn=None) -> dict:
    s = schemas()
    own = conn is None
    conn = conn or connect()
    run_file(conn, SQL_DIR / "05_policy_and_out_schema.sql")
    run_id = str(uuid.uuid4())
    settings = conn.execute(f"SELECT setting_key, setting_value FROM {s['POLICY']}.settings ORDER BY 1").fetchall()
    precedence = conn.execute(f"SELECT payment_mode, rank, evidence_source, rule FROM {s['POLICY']}.date_precedence "
                              f"ORDER BY 1, 2").fetchall()
    snapshot = json.dumps({"settings": dict(settings),
                           "date_precedence": [dict(zip(["payment_mode", "rank", "evidence_source", "rule"],
                                                        [str(v) for v in r])) for r in precedence]})
    dataset_id = conn.execute(f"SELECT MAX(dataset_id) FROM {s['RAW']}.dataset_info").fetchval()
    started = now()
    conn.execute(f"INSERT INTO {s['OUT']}.audit_runs (run_id, dataset_id, started_at, git_sha, policy_snapshot, status, label) "
                 f"VALUES ({{r}}, {{d}}, {{t}}, {{g}}, {{p}}, 'RUNNING', {{l}})",
                 {"r": run_id, "d": dataset_id, "t": started, "g": git_sha(), "p": snapshot, "l": label[:200]})
    t0 = time.perf_counter()
    steps = []
    try:
        for path in pipeline_files():
            meta = header(path)
            step_id = meta.get("step", path.stem.upper())
            step_start = now()
            ms, rows = run_file(conn, path, run_id)
            conn.execute(f"INSERT INTO {s['OUT']}.step_timings VALUES ({{r}}, {{s}}, {{t}}, {{ms}}, {{rows}})",
                         {"r": run_id, "s": step_id, "t": step_start, "ms": ms, "rows": rows})
            conn.execute(f"MERGE INTO {s['OUT']}.lineage l USING (SELECT {{s}} AS sql_step_id, {{f}} AS file_path, "
                         f"{{d}} AS description, {{h}} AS statement_sha FROM DUAL) n ON l.sql_step_id = n.sql_step_id "
                         f"WHEN MATCHED THEN UPDATE SET file_path = n.file_path, description = n.description, "
                         f"statement_sha = n.statement_sha "
                         f"WHEN NOT MATCHED THEN INSERT VALUES (n.sql_step_id, n.file_path, n.description, n.statement_sha)",
                         {"s": step_id, "f": f"sql/{path.name}", "d": meta.get("purpose", "")[:500], "h": sha(path)})
            steps.append({"step": step_id, "ms": ms})
        total = int((time.perf_counter() - t0) * 1000)
        conn.execute(f"UPDATE {s['OUT']}.audit_runs SET status = 'DONE', finished_at = {{t}}, duration_ms = {{ms}}, "
                     f"loan_count = (SELECT loans_audited FROM {s['OUT']}.run_summary WHERE run_id = {{r}}), "
                     f"posting_count = (SELECT posting_rows FROM {s['OUT']}.run_summary WHERE run_id = {{r}}) "
                     f"WHERE run_id = {{r}}", {"t": now(), "ms": total, "r": run_id})
    except Exception:
        conn.execute(f"UPDATE {s['OUT']}.audit_runs SET status = 'FAILED', finished_at = {{t}} WHERE run_id = {{r}}",
                     {"t": now(), "r": run_id})
        raise
    finally:
        if own:
            conn.close()
    return {"run_id": run_id, "dataset_id": dataset_id, "duration_ms": total, "steps": steps}


def main() -> None:
    p = argparse.ArgumentParser(description="Run the audit pipeline in Exasol")
    p.add_argument("--label", default="")
    a = p.parse_args()
    print(json.dumps(run_audit(a.label), indent=2))


if __name__ == "__main__":
    main()

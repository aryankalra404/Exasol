"""Sahi Byaaj API. Reads result tables in Exasol; never computes an interest or refund figure itself.

Writes are limited to policy settings, starting a new audit run (which runs the SQL pipeline in Exasol), replacing
the loaded loan book with a validated extract or the synthetic sample (Data page), and the human review log
(decisions, policy changes, released letters), which the pipeline never reads.
"""

from __future__ import annotations

import csv
import io
import queue
import re
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api import live as live_view
from app.api import review as rv
from app.api.book_io import inspection_pack, templates_zip, validate_extract, write_book
from letters.letter import check, render
from scripts.audit import now, run_audit
from scripts.db import ROOT, connect, schemas
from scripts.sqlrun import SQL_DIR, run_file

S = schemas()
RAW, POL, OUT = S["RAW"], S["POLICY"], S["OUT"]
app = FastAPI(title="Sahi Byaaj", version="0.1.0")

# Exasol Personal allows 20 connections; keep a small pool
_pool: queue.Queue = queue.Queue()
_pool_size = 4
_pool_lock = threading.Lock()
_created = 0
_run_lock = threading.Lock()


@contextmanager
def db():
    global _created
    try:
        conn = _pool.get_nowait()
    except queue.Empty:
        with _pool_lock:
            if _created < _pool_size:
                _created += 1
                conn = connect()
                run_file(conn, SQL_DIR / "06_review_schema.sql")
            else:
                conn = None
        if conn is None:
            conn = _pool.get(timeout=30)
    try:
        yield conn
    except Exception:
        try:
            conn.close()
        finally:
            with _pool_lock:
                _created -= 1
        raise
    else:
        _pool.put(conn)


def _val(v):
    # paise arrive as strings for wide decimals; send integers when they fit safely in JSON
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v):
        n = int(v)
        return n if abs(n) < 2**53 else v
    return v


def rows(sql: str, params: dict | None = None) -> list[dict]:
    with db() as c:
        st = c.execute(sql, params or {})
        cols = [x.lower() for x in st.column_names()]
        return [{k: _val(v) for k, v in zip(cols, r)} for r in st.fetchall()]


def one(sql: str, params: dict | None = None) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


def resolve_run(run_id: str) -> str:
    if run_id == "latest":
        r = one(f"SELECT run_id FROM {OUT}.audit_runs WHERE status = 'DONE' AND dataset_id = "
                f"(SELECT MAX(dataset_id) FROM {RAW}.dataset_info) ORDER BY started_at DESC LIMIT 1")
        if not r:
            raise HTTPException(404, "No audit has been run on the loaded book yet. Run `make demo` (or `make audit`) and refresh.")
        return r["run_id"]
    if not re.fullmatch(r"[0-9a-f-]{36}", run_id):
        raise HTTPException(400, "bad run id")
    return run_id


@app.get("/api/runs")
def runs():
    return rows(f"""SELECT r.run_id, r.dataset_id, r.started_at, r.duration_ms, r.status, r.label, r.loan_count,
                           r.posting_count, r.policy_snapshot, s.refund_paise, s.refund_loans
                    FROM {OUT}.audit_runs r LEFT JOIN {OUT}.run_summary s ON s.run_id = r.run_id
                    -- only runs over the dataset currently loaded; older datasets' loans are no longer in RAW
                    WHERE r.dataset_id = (SELECT MAX(dataset_id) FROM {RAW}.dataset_info)
                    ORDER BY r.started_at DESC LIMIT 50""")


@app.get("/api/runs/{run_id}/summary")
def summary(run_id: str):
    rid = resolve_run(run_id)
    run = one(f"SELECT * FROM {OUT}.audit_runs WHERE run_id = {{r}}", {"r": rid})
    return {
        "run": run,
        "summary": one(f"SELECT * FROM {OUT}.run_summary WHERE run_id = {{r}}", {"r": rid}),
        "steps": rows(f"""SELECT t.sql_step_id, t.duration_ms, t.rows_out, l.file_path, l.description, l.statement_sha
                          FROM {OUT}.step_timings t LEFT JOIN {OUT}.lineage l ON l.sql_step_id = t.sql_step_id
                          WHERE t.run_id = {{r}} ORDER BY t.started_at""", {"r": rid}),
        "rollups": rows(f"SELECT dimension, dim_value, status, loans, findings, excess_paise FROM {OUT}.rollups "
                        f"WHERE run_id = {{r}} ORDER BY dimension, dim_value", {"r": rid}),
        "root_causes": rows(f"""SELECT rc.*, b.branch_name FROM {OUT}.root_causes rc
                                JOIN {RAW}.branches b ON b.branch_id = rc.branch_id
                                WHERE rc.run_id = {{r}} ORDER BY rc.excess_paise DESC""", {"r": rid}),
        "practices": rows(f"SELECT practice_code, title, rbi_reference FROM {POL}.practices ORDER BY 1"),
        "branches": rows(f"SELECT branch_id, branch_name, state_name, region FROM {RAW}.branches ORDER BY 1"),
        "dataset": one(f"SELECT * FROM {RAW}.dataset_info"),
    }


_LEDGER_STATE = rv.state_case("l.excess_paise")
LEDGER_SQL = f"""
    SELECT l.loan_id, l.borrower_id, b.display_name, l.branch_id, br.branch_name, l.product, l.practice_code,
           l.periods, l.days_affected, l.excess_paise, l.first_period, l.last_period, {_LEDGER_STATE} AS review_state,
           d.decided_by, d.reason AS review_reason, d.decided_at, fc.conventions, {rv.CERTAINTY_CASE} AS certainty,
           CASE WHEN d.review_decision = 'HOLD' AND d.figure_paise = l.excess_paise
                THEN GREATEST(DAYS_BETWEEN(CAST({{today}} AS DATE), CAST(d.decided_at AS DATE)), 0) END AS held_days
    FROM {OUT}.refund_ledger l
    JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
    JOIN {RAW}.branches br ON br.branch_id = l.branch_id
    LEFT JOIN ({rv.latest_decisions_sql(OUT, POL, 'LEDGER')}) d
      ON d.loan_id = l.loan_id AND d.practice_code = l.practice_code AND d.rn = 1
    {rv.certainty_joins_sql(OUT)}
    WHERE l.run_id = {{r}}
      AND ({{review}} IS NULL OR {_LEDGER_STATE} = {{review}})
      AND ({{certainty}} IS NULL OR {rv.CERTAINTY_CASE} = {{certainty}})
      AND ({{convention}} IS NULL OR INSTR(',' || fc.conventions || ',', ',' || {{convention}} || ',') > 0)
      AND ({{practice}} IS NULL OR l.practice_code = {{practice}})
      AND ({{branch}} IS NULL OR l.branch_id = {{branch}})
      AND ({{product}} IS NULL OR l.product = {{product}})
      AND ({{q}} IS NULL OR UPPER(l.loan_id) LIKE {{q}} OR UPPER(b.display_name) LIKE {{q}})
"""


def _ledger_params(rid, practice, branch, product, q, review="", certainty="", convention=""):
    return {"r": rid, "practice": practice or None, "branch": branch or None, "product": product or None,
            "q": f"%{q.upper()}%" if q else None, "review": review or None, "certainty": certainty or None,
            "convention": convention or None, "today": now()[:10]}  # the app's clock: the database VM's can lag after sleep


@app.get("/api/runs/{run_id}/ledger")
def ledger(run_id: str, practice: str = "", branch: str = "", product: str = "", q: str = "", review: str = "",
           certainty: str = "", convention: str = "", sort: str = "excess", page: int = Query(1, ge=1), size: int = Query(50, le=500)):
    rid = resolve_run(run_id)
    order = {"excess": "l.excess_paise DESC", "loan": "l.loan_id", "days": "l.days_affected DESC",
             "period": "l.first_period"}.get(sort, "l.excess_paise DESC")
    p = _ledger_params(rid, practice, branch, product, q, review, certainty, convention)
    total = one(f"SELECT COUNT(*) AS n, COALESCE(SUM(excess_paise), 0) AS excess_paise, "
                f"COUNT(DISTINCT loan_id) AS loans FROM ({LEDGER_SQL}) x", p)
    data = rows(f"{LEDGER_SQL} ORDER BY {order}, l.loan_id, l.practice_code LIMIT {size} OFFSET {(page - 1) * size}", p)
    return {"run_id": rid, "total": total, "rows": data, "page": page, "size": size}


@app.get("/api/runs/{run_id}/ledger.csv")
def ledger_csv(run_id: str, practice: str = "", branch: str = "", product: str = "", q: str = ""):
    rid = resolve_run(run_id)
    data = rows(f"{LEDGER_SQL} ORDER BY l.loan_id, l.practice_code", _ledger_params(rid, practice, branch, product, q))
    buf = io.StringIO()
    if data:
        w = csv.DictWriter(buf, fieldnames=list(data[0].keys()) + ["run_id"])
        w.writeheader()
        for r in data:
            w.writerow({**r, "run_id": rid})
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=refund_ledger_{rid[:8]}.csv"})


@app.get("/api/runs/{run_id}/queue/{status}")
def work_queue(run_id: str, status: str, page: int = Query(1, ge=1), size: int = Query(50, le=500)):
    rid = resolve_run(run_id)
    if status not in ("UNEXPLAINED", "AMBIGUOUS", "PERMITTED", "UNDERCHARGE", "EVIDENCE_GAP"):
        raise HTTPException(400, "unknown queue")
    return rows(f"""SELECT f.run_id, f.loan_id, b.display_name, f.branch_id, f.product, f.period_start, f.practice_code,
                           f.excess_paise, f.days_affected, f.reason, fp.posted_paise, fp.fair_paise,
                           fp.closest_convention_id, fp.closest_diff_paise, fp.tied_convention_ids, fp.has_manual,
                           {rv.state_case('fp.excess_paise')} AS review_state, d.decided_by, d.reason AS review_reason,
                           COUNT(*) OVER () AS total_rows
                    FROM {OUT}.findings f
                    JOIN {RAW}.borrowers b ON b.borrower_id = f.borrower_id
                    JOIN {OUT}.fingerprints fp ON fp.run_id = f.run_id AND fp.loan_id = f.loan_id
                                               AND fp.period_start = f.period_start
                    LEFT JOIN ({rv.latest_decisions_sql(OUT, POL, 'UNEXPLAINED')}) d
                      ON d.loan_id = f.loan_id AND d.period_start = f.period_start AND d.rn = 1
                    WHERE f.run_id = {{r}} AND f.status = {{s}}
                    ORDER BY ABS(f.excess_paise) DESC, f.loan_id, f.period_start
                    LIMIT {size} OFFSET {(page - 1) * size}""", {"r": rid, "s": status})


@app.get("/api/runs/{run_id}/gaps")
def gaps(run_id: str):
    rid = resolve_run(run_id)
    return rows(f"""SELECT g.*, br.branch_name, b.display_name FROM {OUT}.evidence_gaps g
                    JOIN {RAW}.branches br ON br.branch_id = g.branch_id
                    JOIN {RAW}.loans l ON l.loan_id = g.loan_id
                    JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
                    WHERE g.run_id = {{r}} ORDER BY g.posted_paise_at_stake DESC""", {"r": rid})


@app.get("/api/runs/{run_id}/cohorts")
def cohorts(run_id: str, branch: str):
    rid = resolve_run(run_id)
    return rows(f"SELECT sanction_quarter, period_quarter, loans_in_cohort, loans_overcharged, excess_paise "
                f"FROM {OUT}.cohorts WHERE run_id = {{r}} AND branch_id = {{b}} ORDER BY 1, 2", {"r": rid, "b": branch})


@app.get("/api/runs/{run_id}/loans/{loan_id}")
def loan(run_id: str, loan_id: str):
    rid = resolve_run(run_id)
    p = {"r": rid, "l": loan_id}
    head = one(f"""SELECT l.*, b.display_name, b.preferred_language, br.branch_name, br.state_name,
                          k.annual_rate_pct, k.day_count_basis, k.commitment_fee_rate_pct, k.disclosed_emi_paise
                   FROM {RAW}.loans l JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
                   JOIN {RAW}.branches br ON br.branch_id = l.branch_id JOIN {RAW}.kfs k ON k.loan_id = l.loan_id
                   WHERE l.loan_id = {{l}}""", p)
    if not head:
        raise HTTPException(404, "loan not found")
    return {
        "run_id": rid,
        "review": rows(f"SELECT * FROM ({rv.ledger_review_sql(OUT, POL)}) x WHERE x.loan_id = {{l}} ORDER BY x.practice_code", p),
        "review_history": rows(f"""SELECT practice_code, period_start, figure_paise, review_decision, decided_by, reason, decided_at
                                   FROM {POL}.review_decisions
                                   WHERE loan_id = {{l}} AND dataset_id = (SELECT dataset_id FROM {OUT}.audit_runs WHERE run_id = {{r}})
                                   ORDER BY decision_seq DESC""", p),
        "letter": one(f"SELECT * FROM ({rv.loan_states_sql(OUT, POL)}) x WHERE x.loan_id = {{l}}", p),
        "loan": head,
        "tranches": rows(f"""SELECT m.*, t.payee_type FROM {OUT}.money_in_hand m
                             JOIN {RAW}.tranches t ON t.loan_id = m.loan_id AND t.tranche_no = m.tranche_no
                             WHERE m.run_id = {{r}} AND m.loan_id = {{l}} ORDER BY m.tranche_no""", p),
        "evidence": rows(f"""SELECT evidence_id, loan_id, tranche_no, evidence_source, event_date, reference, recorded_in FROM {RAW}.disbursement_evidence
                             WHERE loan_id = {{l}}
                             UNION ALL
                             SELECT a.evidence_id, a.loan_id, a.tranche_no, a.evidence_source, a.event_date, a.reference, 'REVIEWER'
                             FROM {POL}.evidence_additions a JOIN {OUT}.audit_runs r ON r.run_id = {{r}} AND r.dataset_id = a.dataset_id
                             WHERE a.loan_id = {{l}} AND a.added_at <= r.started_at AND (a.withdrawn_at IS NULL OR a.withdrawn_at > r.started_at)
                             ORDER BY 3, 5""", p),
        "rates": rows(f"SELECT effective_date, annual_rate_pct FROM {RAW}.rate_history WHERE loan_id = {{l}} ORDER BY 1", p),
        "periods": rows(f"SELECT * FROM {OUT}.fingerprints WHERE run_id = {{r}} AND loan_id = {{l}} ORDER BY period_start", p),
        "findings": rows(f"SELECT * FROM {OUT}.findings WHERE run_id = {{r}} AND loan_id = {{l}} ORDER BY period_start, practice_code", p),
        "ledger": rows(f"SELECT * FROM {OUT}.refund_ledger WHERE run_id = {{r}} AND loan_id = {{l}} ORDER BY practice_code", p),
        "ledger_total": one(f"SELECT COALESCE(SUM(excess_paise), 0) AS excess_paise, COUNT(DISTINCT practice_code) AS practices "
                            f"FROM {OUT}.refund_ledger WHERE run_id = {{r}} AND loan_id = {{l}}", p),
        "receipts": rows(f"SELECT * FROM {RAW}.receipts WHERE loan_id = {{l}} AND kind IN ('ADVANCE_EMI', 'CLOSURE') ORDER BY value_date", p),
        "conventions": rows(f"SELECT convention_id, start_basis, principal_basis, advance_treatment, month_rounding, "
                            f"practice_codes FROM {POL}.conventions"),
    }


@app.get("/api/runs/{run_id}/loans/{loan_id}/proof/{period}")
def proof(run_id: str, loan_id: str, period: str):
    """Interval-level working for one billing period: the fair path and the extra balance that was charged."""
    rid = resolve_run(run_id)
    p = {"r": rid, "l": loan_id, "p": period}
    den = one(f"SELECT CASE WHEN day_count_basis = '30E_360' THEN 360 ELSE 365 END AS divisor FROM {RAW}.kfs WHERE loan_id = {{l}}", p)
    divisor = den["divisor"] if den else 365
    # unrounded interval amounts are computed by Exasol here, for display; the period total is rounded once in S50
    fair = rows(f"""SELECT interval_start, interval_end, balance_paise, annual_rate_pct, days, numerator,
                           CAST(CAST(numerator AS DECIMAL(36,0)) / CAST({100000000 * divisor} AS DECIMAL(18,0)) AS DECIMAL(30,4)) AS interest_paise_exact
                    FROM {OUT}.balance_intervals WHERE run_id = {{r}} AND loan_id = {{l}} AND period_start = {{p}}
                    ORDER BY interval_start""", p)
    extra = rows(f"""SELECT convention_id, interval_start, interval_end, extra_balance_paise, fee_balance_paise,
                            annual_rate_pct, fee_rate_pct, days, numerator,
                            CAST(CAST(numerator AS DECIMAL(36,0)) / CAST({100000000 * divisor} AS DECIMAL(18,0)) AS DECIMAL(30,4)) AS interest_paise_exact
                     FROM {OUT}.excess_intervals WHERE run_id = {{r}} AND loan_id = {{l}} AND period_start = {{p}}
                     ORDER BY interval_start""", p)
    fp = one(f"SELECT * FROM {OUT}.fingerprints WHERE run_id = {{r}} AND loan_id = {{l}} AND period_start = {{p}}", p)
    postings = rows(f"SELECT * FROM {RAW}.interest_postings WHERE loan_id = {{l}} AND period_start = {{p}} ORDER BY posted_on, posting_id", p)
    return {"divisor": divisor, "fair_intervals": fair, "extra_intervals": extra, "fingerprint": fp, "postings": postings}


@app.get("/api/runs/{run_id}/letters/{loan_id}")
def letter(run_id: str, loan_id: str, lang: str = ""):
    rid = resolve_run(run_id)
    q = f"SELECT * FROM {OUT}.letter_figures WHERE run_id = {{r}} AND loan_id = {{l}}"
    figs = rows(q, {"r": rid, "l": loan_id})
    if not figs:
        raise HTTPException(404, "no refundable findings for this loan in this run")
    for f in figs:
        for k in ("first_period", "last_period"):
            from datetime import date as _d
            f[k] = _d.fromisoformat(str(f[k]))
    lang = lang or next(f["preferred_language"] for f in figs)
    lt = render(figs, lang)
    # the checker re-reads the ledger on its own, not the rows used to render
    result = check(lt, rows(q, {"r": rid, "l": loan_id}))
    state = one(f"SELECT * FROM ({rv.loan_states_sql(OUT, POL)}) x WHERE x.loan_id = {{l}}", {"r": rid, "l": loan_id})
    return {"run_id": rid, "loan_id": loan_id, "lang": lt.lang, "requested_lang": lang, "text": lt.text, "check": result,
            "state": state}


@app.get("/api/lineage")
def lineage():
    return rows(f"SELECT * FROM {OUT}.lineage ORDER BY sql_step_id")


@app.get("/api/lineage/{step_id}")
def lineage_step(step_id: str):
    r = one(f"SELECT * FROM {OUT}.lineage WHERE sql_step_id = {{s}}", {"s": step_id})
    if not r:
        raise HTTPException(404, "unknown step")
    r["sql"] = (ROOT / r["file_path"]).read_text()
    return r


def _actor(name: str, reason: str) -> tuple[str, str]:
    try:
        return rv.clean_actor(name, reason)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/policy/settings")
def get_settings():
    return {"settings": rows(f"SELECT * FROM {POL}.settings ORDER BY setting_key"),
            "date_precedence": rows(f"SELECT * FROM {POL}.date_precedence ORDER BY payment_mode, rank"),
            "changes": rows(f"SELECT setting_key, old_value, new_value, changed_by, reason, changed_at "
                            f"FROM {POL}.policy_changes ORDER BY change_seq DESC LIMIT 50")}


class SettingIn(BaseModel):
    setting_key: str
    setting_value: str
    changed_by: str
    reason: str


@app.put("/api/policy/settings")
def put_setting(s: SettingIn):
    if not one(f"SELECT 1 AS x FROM {POL}.settings WHERE setting_key = {{k}}", {"k": s.setting_key}):
        raise HTTPException(404, "unknown setting")
    if not re.fullmatch(r"true|false|\d{1,6}", s.setting_value):
        raise HTTPException(400, "value must be true, false or a whole number")
    who, why = _actor(s.changed_by, s.reason)
    with db() as c:
        p = {"v": s.setting_value, "k": s.setting_key, "who": who, "why": why, "at": now()}
        c.execute(f"""INSERT INTO {POL}.policy_changes (setting_key, old_value, new_value, changed_by, reason, changed_at)
                      SELECT setting_key, setting_value, {{v}}, {{who}}, {{why}}, {{at}} FROM {POL}.settings
                      WHERE setting_key = {{k}} AND setting_value <> {{v}}""", p)
        c.execute(f"UPDATE {POL}.settings SET setting_value = {{v}} WHERE setting_key = {{k}}", p)
    return get_settings()


class RunIn(BaseModel):
    label: str = ""


@app.post("/api/runs")
def start_run(body: RunIn):
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "an audit run is already in progress")
    try:
        with db() as c:
            return run_audit(body.label or "re-run from app", conn=c)
    finally:
        _run_lock.release()


@app.get("/api/live")
def live():
    """What Exasol is executing now and how far the latest run has got. System tables and the run log only."""
    try:
        return live_view.snapshot()
    except Exception as exc:
        raise HTTPException(503, f"Cannot read Exasol: {exc}")


@app.get("/api/compare/{a}/{b}")
def compare(a: str, b: str):
    """What changed between two runs: totals per status and practice, and loans whose refund changed."""
    ra, rb = resolve_run(a), resolve_run(b)
    p = {"a": ra, "b": rb}
    by = rows(f"""SELECT COALESCE(x.status, y.status) AS status, COALESCE(x.practice_code, y.practice_code) AS practice_code,
                         COALESCE(x.excess_paise, 0) AS a_paise, COALESCE(y.excess_paise, 0) AS b_paise,
                         COALESCE(y.excess_paise, 0) - COALESCE(x.excess_paise, 0) AS delta_paise,
                         COALESCE(x.loans, 0) AS a_loans, COALESCE(y.loans, 0) AS b_loans
                  FROM (SELECT status, practice_code, SUM(excess_paise) excess_paise, COUNT(DISTINCT loan_id) loans
                        FROM {OUT}.findings WHERE run_id = {{a}} GROUP BY 1, 2) x
                  FULL OUTER JOIN (SELECT status, practice_code, SUM(excess_paise) excess_paise, COUNT(DISTINCT loan_id) loans
                        FROM {OUT}.findings WHERE run_id = {{b}} GROUP BY 1, 2) y
                    ON x.status = y.status AND COALESCE(x.practice_code, '-') = COALESCE(y.practice_code, '-')
                  ORDER BY 1, 2""", p)
    loans = rows(f"""SELECT COALESCE(x.loan_id, y.loan_id) AS loan_id, COALESCE(x.refund, 0) AS a_paise,
                            COALESCE(y.refund, 0) AS b_paise, COALESCE(y.refund, 0) - COALESCE(x.refund, 0) AS delta_paise,
                            x.statuses AS a_status, y.statuses AS b_status
                     FROM (SELECT loan_id, SUM(CASE WHEN status IN ('REFUND','AMBIGUOUS') THEN excess_paise ELSE 0 END) refund,
                                  GROUP_CONCAT(DISTINCT status ORDER BY status SEPARATOR ',') statuses
                           FROM {OUT}.findings WHERE run_id = {{a}} GROUP BY 1) x
                     FULL OUTER JOIN (SELECT loan_id, SUM(CASE WHEN status IN ('REFUND','AMBIGUOUS') THEN excess_paise ELSE 0 END) refund,
                                  GROUP_CONCAT(DISTINCT status ORDER BY status SEPARATOR ',') statuses
                           FROM {OUT}.findings WHERE run_id = {{b}} GROUP BY 1) y ON x.loan_id = y.loan_id
                     WHERE COALESCE(x.refund, 0) <> COALESCE(y.refund, 0) OR COALESCE(x.statuses, '') <> COALESCE(y.statuses, '')
                     ORDER BY ABS(COALESCE(y.refund, 0) - COALESCE(x.refund, 0)) DESC LIMIT 200""", p)
    totals = one(f"""SELECT a.refund_paise AS a_refund, b.refund_paise AS b_refund, b.refund_paise - a.refund_paise AS delta_refund,
                             a.refund_loans AS a_loans, b.refund_loans AS b_loans, b.refund_loans - a.refund_loans AS delta_loans,
                             a.permitted_paise AS a_permitted, b.permitted_paise AS b_permitted
                      FROM {OUT}.run_summary a, {OUT}.run_summary b WHERE a.run_id = {{a}} AND b.run_id = {{b}}""", p)
    return {"a": ra, "b": rb, "totals": totals, "by_status_practice": by, "loans": loans}


@app.get("/api/search")
def search(q: str):
    qq = f"%{q.upper()}%"
    return rows(f"""SELECT l.loan_id, b.display_name, l.branch_id, l.product FROM {RAW}.loans l
                    JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
                    WHERE UPPER(l.loan_id) LIKE {{q}} OR UPPER(b.display_name) LIKE {{q}}
                    ORDER BY b.display_name, l.loan_id LIMIT 12""", {"q": qq})


# ---------- data: what is loaded, templates, import, sample, inspection pack ----------
SAMPLE = ("s42_n10000", 42, 10000)
MAX_UPLOAD = 512 * 2**20


@app.get("/api/data/status")
def data_status():
    try:
        info = one(f"SELECT dataset_id, seed, loans, as_of, generator_version FROM {RAW}.dataset_info")
    except Exception:
        info = None
    if not info:
        return {"loaded": False}
    counts = rows("SELECT LOWER(table_name) AS table_name, table_row_count AS n FROM EXA_ALL_TABLES "
                  "WHERE table_schema = {s} AND table_name <> 'DATASET_INFO' ORDER BY 1", {"s": RAW})
    run = one(f"SELECT run_id, started_at, duration_ms, label FROM {OUT}.audit_runs WHERE status = 'DONE' "
              f"AND dataset_id = {{d}} ORDER BY started_at DESC LIMIT 1", {"d": info["dataset_id"]})
    return {"loaded": True, "dataset": info, "synthetic": info["generator_version"] != "upload",
            "tables": counts, "latest_run": run}


@app.get("/api/data/templates.zip")
def data_templates():
    return Response(templates_zip(), media_type="application/zip",
                    headers={"Content-Disposition": "attachment; filename=sahi_byaaj_extract_templates.zip"})


def _replace_book(path: Path, label: str) -> dict:
    """Load a dataset folder into Exasol and audit it. On a failed load, put the previous book back."""
    from scripts.load import load
    try:
        prev = one(f"SELECT dataset_id FROM {RAW}.dataset_info")
    except Exception:
        prev = None
    try:
        loaded = load(path)
    except Exception as e:
        for cand in ([ROOT / "data" / prev["dataset_id"], ROOT / "data" / "uploads" / prev["dataset_id"]] if prev else []):
            if cand.exists():
                load(cand)
                break
        raise HTTPException(422, f"Exasol rejected the extract during load, so the previous book was kept. Detail: {str(e)[:300]}")
    run = run_audit(label)
    return {"dataset_id": loaded["dataset_id"], "load_ms": loaded["load_ms"], "run": run}


@app.post("/api/data/upload")
async def data_upload(request: Request):
    body = await request.body()
    if len(body) > MAX_UPLOAD:
        raise HTTPException(413, "The ZIP is larger than 512 MB. Load large books with `make load` instead.")
    tables, errors, counts = validate_extract(body)
    if errors:
        return {"ok": False, "errors": errors, "counts": counts}
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "An audit run is already in progress. Try again when it finishes.")
    try:
        path = write_book(tables, ROOT / "data" / "uploads")
        return {"ok": True, "counts": counts, **_replace_book(path, "Uploaded book")}
    finally:
        _run_lock.release()


@app.post("/api/data/sample")
def data_sample():
    from datetime import date as _date

    from generator.generate import generate
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "An audit run is already in progress. Try again when it finishes.")
    try:
        name, seed, loans = SAMPLE
        path = ROOT / "data" / name
        if not (path / "manifest.json").exists():
            path = generate(seed, loans, _date(2026, 10, 1), 1.0, ROOT / "data")
        return {"ok": True, **_replace_book(path, "Baseline audit")}
    finally:
        _run_lock.release()


@app.get("/api/runs/{run_id}/inspection-pack.zip")
def run_inspection_pack(run_id: str):
    rid = resolve_run(run_id)
    if not one(f"SELECT run_id FROM {OUT}.run_summary WHERE run_id = {{r}}", {"r": rid}):
        raise HTTPException(404, "no such completed run")
    data = inspection_pack(rid, rows, OUT, RAW, POL)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=inspection_pack_{rid[:8]}.zip"})


# ---------- review: human decisions and letter release; no figure is written from the browser ----------
def _writable_run(run_id: str) -> str:
    """Review actions apply to the latest run only, and not while a new run is being written."""
    if _run_lock.locked():
        raise HTTPException(409, "An audit run is in progress. Try again when it finishes.")
    rid = resolve_run(run_id)
    if rid != resolve_run("latest"):
        raise HTTPException(409, "This is an older run. Switch to the latest run to review or release.")
    return rid


_DECISION_INSERT = f"""INSERT INTO {POL}.review_decisions (action_id, dataset_id, run_id, item_kind, loan_id, practice_code,
                           period_start, figure_paise, review_decision, decided_by, reason, decided_at)"""


@app.get("/api/runs/{run_id}/outcomes")
def loan_outcomes(run_id: str):
    """Where every audited loan landed. Each loan has exactly one outcome, so the counts add up to the book."""
    rid = resolve_run(run_id)
    return {"run_id": rid, "outcomes": rows(f"""SELECT outcome, COUNT(*) AS loans, SUM(refund_paise) AS refund_paise
                                               FROM ({rv.loan_outcomes_sql(OUT)}) x GROUP BY outcome""", {"r": rid})}


@app.get("/api/runs/{run_id}/outcomes/{outcome}")
def loans_with_outcome(run_id: str, outcome: str, branch: str = "", page: int = Query(1, ge=1), size: int = Query(50, le=500)):
    rid = resolve_run(run_id)
    if outcome not in ("FAIR", "REFUND", "EVIDENCE_GAP", "UNEXPLAINED", "PERMITTED", "UNDERCHARGE"):
        raise HTTPException(400, "unknown outcome")
    return rows(f"""SELECT x.loan_id, b.display_name, l.branch_id, br.branch_name, l.product, x.months, x.posted_paise, x.fair_paise,
                           x.refund_paise, COUNT(*) OVER () AS total_rows
                    FROM ({rv.loan_outcomes_sql(OUT)}) x
                    JOIN {RAW}.loans l ON l.loan_id = x.loan_id
                    JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
                    JOIN {RAW}.branches br ON br.branch_id = l.branch_id
                    WHERE x.outcome = {{o}} AND ({{b}} IS NULL OR l.branch_id = {{b}})
                    ORDER BY x.loan_id LIMIT {size} OFFSET {(page - 1) * size}""", {"r": rid, "o": outcome, "b": branch or None})


@app.get("/api/runs/{run_id}/review/summary")
def review_summary(run_id: str):
    rid = resolve_run(run_id)
    p = {"r": rid}
    return {
        "run_id": rid,
        "is_latest": rid == resolve_run("latest"),
        "by_certainty": rows(f"""SELECT certainty, COUNT(*) AS row_count, COUNT(DISTINCT loan_id) AS loans, SUM(excess_paise) AS excess_paise
                                 FROM ({LEDGER_SQL}) x GROUP BY certainty""", _ledger_params(rid, "", "", "", "")),
        "ledger_total": one(f"SELECT COALESCE(SUM(excess_paise), 0) AS v FROM {OUT}.refund_ledger WHERE run_id = {{r}}", p)["v"],
        "by_state": rows(f"""SELECT review_state, COUNT(*) AS row_count, COUNT(DISTINCT loan_id) AS loans,
                                    SUM(excess_paise) AS excess_paise
                             FROM ({rv.ledger_review_sql(OUT, POL)}) x GROUP BY review_state""", p),
        "letters": rows(f"""SELECT letter_state, COUNT(*) AS loans, SUM(total_paise) AS total_paise
                            FROM ({rv.loan_states_sql(OUT, POL)}) x GROUP BY letter_state""", p),
        "changed_releases": rows(rv.changed_releases_sql(OUT, POL), p),
        "unexplained": rows(f"""SELECT {rv.state_case('fp.excess_paise')} AS review_state, COUNT(*) AS periods
                                FROM {OUT}.fingerprints fp
                                LEFT JOIN ({rv.latest_decisions_sql(OUT, POL, 'UNEXPLAINED')}) d
                                  ON d.loan_id = fp.loan_id AND d.period_start = fp.period_start AND d.rn = 1
                                WHERE fp.run_id = {{r}} AND fp.match_status = 'UNEXPLAINED'
                                GROUP BY 1""", p),
        "batches": rows(f"""SELECT batch_id, run_id, released_by, batch_note, released_at, letter_count, total_paise
                            FROM {POL}.release_batches
                            WHERE dataset_id = (SELECT dataset_id FROM {OUT}.audit_runs WHERE run_id = {{r}})
                            ORDER BY released_at DESC""", p),
    }


class DecisionIn(BaseModel):
    loan_id: str
    practice_code: str
    decision: str
    reviewer: str
    reason: str


@app.post("/api/runs/{run_id}/review/decisions")
def review_decision(run_id: str, body: DecisionIn):
    rid = _writable_run(run_id)
    if body.decision not in rv.LEDGER_DECISIONS:
        raise HTTPException(400, "decision must be APPROVED or HOLD")
    who, why = _actor(body.reviewer, body.reason)
    with db() as c:
        st = c.execute(f"""{_DECISION_INSERT}
                           SELECT {{a}}, r.dataset_id, l.run_id, 'LEDGER', l.loan_id, l.practice_code, CAST(NULL AS DATE),
                                  l.excess_paise, {{d}}, {{who}}, {{why}}, {{at}}
                           FROM {OUT}.refund_ledger l JOIN {OUT}.audit_runs r ON r.run_id = l.run_id
                           WHERE l.run_id = {{r}} AND l.loan_id = {{l}} AND l.practice_code = {{p}}""",
                       {"a": str(uuid.uuid4()), "d": body.decision, "who": who, "why": why, "at": now(), "r": rid,
                        "l": body.loan_id, "p": body.practice_code})
        if not st.rowcount():
            raise HTTPException(404, "This row is not in the refund ledger of the latest run.")
    return {"ok": True}


class BulkApproveIn(BaseModel):
    practice: str = ""
    branch: str = ""
    product: str = ""
    q: str = ""
    certainty: str = ""
    convention: str = ""
    reviewer: str
    reason: str


@app.post("/api/runs/{run_id}/review/approve-filtered")
def review_approve_filtered(run_id: str, body: BulkApproveIn):
    """Approve the not-yet-reviewed rows matching a filter, so one reason covers one root cause. Rows on hold or
    with a changed figure are left alone; they need looking at one by one."""
    rid = _writable_run(run_id)
    if not (body.practice or body.branch or body.product or body.q or body.certainty or body.convention):
        raise HTTPException(400, "Filter first, for example by root cause, practice or branch. The whole book cannot be approved in one click.")
    who, why = _actor(body.reviewer, body.reason)
    action = str(uuid.uuid4())
    p = {**_ledger_params(rid, body.practice, body.branch, body.product, body.q, "UNREVIEWED", body.certainty, body.convention),
         "a": action, "who": who, "why": why, "at": now()}
    with db() as c:
        c.execute(f"""{_DECISION_INSERT}
                      SELECT {{a}}, r.dataset_id, l.run_id, 'LEDGER', l.loan_id, l.practice_code, CAST(NULL AS DATE),
                             l.excess_paise, 'APPROVED', {{who}}, {{why}}, {{at}}
                      FROM {OUT}.refund_ledger l JOIN {OUT}.audit_runs r ON r.run_id = l.run_id
                      JOIN ({LEDGER_SQL}) t ON t.loan_id = l.loan_id AND t.practice_code = l.practice_code
                      WHERE l.run_id = {{r}}""", p)
    return one(f"""SELECT COUNT(*) AS row_count, COALESCE(SUM(figure_paise), 0) AS excess_paise
                   FROM {POL}.review_decisions WHERE action_id = {{a}}""", {"a": action})


class QueueDecisionIn(BaseModel):
    loan_id: str
    period_start: str
    decision: str
    reviewer: str
    reason: str


@app.post("/api/runs/{run_id}/review/unexplained")
def review_unexplained(run_id: str, body: QueueDecisionIn):
    """Record the outcome of a manual look at an unexplained month. It moves no money: to change a refund, fix the
    evidence or the policy and re-run."""
    rid = _writable_run(run_id)
    if body.decision not in rv.QUEUE_DECISIONS:
        raise HTTPException(400, "decision must be CLEARED or HOLD")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", body.period_start):
        raise HTTPException(400, "bad period")
    who, why = _actor(body.reviewer, body.reason)
    with db() as c:
        st = c.execute(f"""{_DECISION_INSERT}
                           SELECT {{a}}, r.dataset_id, f.run_id, 'UNEXPLAINED', f.loan_id, CAST(NULL AS VARCHAR(3)), f.period_start,
                                  f.excess_paise, {{d}}, {{who}}, {{why}}, {{at}}
                           FROM {OUT}.fingerprints f JOIN {OUT}.audit_runs r ON r.run_id = f.run_id
                           WHERE f.run_id = {{r}} AND f.loan_id = {{l}} AND f.period_start = {{p}}
                             AND f.match_status = 'UNEXPLAINED'""",
                       {"a": str(uuid.uuid4()), "d": body.decision, "who": who, "why": why, "at": now(), "r": rid,
                        "l": body.loan_id, "p": body.period_start})
        if not st.rowcount():
            raise HTTPException(404, "This month is not in the unexplained queue of the latest run.")
    return {"ok": True}


# ---------- evidence: a date a person enters from a branch reply; the next run decides what it means ----------
@app.get("/api/runs/{run_id}/evidence")
def evidence_entries(run_id: str):
    rid = resolve_run(run_id)
    return rows(f"""SELECT a.evidence_id, a.loan_id, b.display_name, a.tranche_no, a.evidence_source, a.event_date, a.reference,
                           a.added_by, a.reason, a.added_at, a.withdrawn_by, a.withdrawn_reason, a.withdrawn_at,
                           CASE WHEN a.withdrawn_at IS NOT NULL AND a.added_at > r.started_at THEN 'NEVER_USED'
                                WHEN a.withdrawn_at > r.started_at THEN 'WITHDRAWN_PENDING'
                                WHEN a.withdrawn_at IS NOT NULL THEN 'WITHDRAWN'
                                WHEN a.added_at > r.started_at THEN 'PENDING'
                                ELSE 'IN_RUN' END AS entry_state,
                           COALESCE(led.refund_paise, 0) AS loan_refund_paise, fnd.statuses AS loan_statuses
                    FROM {POL}.evidence_additions a
                    JOIN {OUT}.audit_runs r ON r.run_id = {{r}} AND r.dataset_id = a.dataset_id
                    LEFT JOIN (SELECT loan_id, SUM(excess_paise) AS refund_paise FROM {OUT}.refund_ledger
                               WHERE run_id = {{r}} GROUP BY loan_id) led ON led.loan_id = a.loan_id
                    LEFT JOIN (SELECT loan_id, GROUP_CONCAT(DISTINCT status ORDER BY status SEPARATOR ',') AS statuses
                               FROM {OUT}.findings WHERE run_id = {{r}} GROUP BY loan_id) fnd ON fnd.loan_id = a.loan_id
                    LEFT JOIN {RAW}.loans l ON l.loan_id = a.loan_id
                    LEFT JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
                    ORDER BY a.added_at DESC""", {"r": rid})


class EvidenceIn(BaseModel):
    loan_id: str
    tranche_no: int
    event_date: str
    reference: str
    reviewer: str
    reason: str


@app.post("/api/runs/{run_id}/evidence")
def evidence_add(run_id: str, body: EvidenceIn):
    """Record the date a branch supplied for a tranche in the gap queue. No figure is entered: re-run the audit and
    the same SQL rules decide what this date means."""
    rid = _writable_run(run_id)
    who, why = _actor(body.reviewer, body.reason)
    reference = " ".join(body.reference.split())
    if not reference:
        raise HTTPException(400, "Enter the document reference from the branch's reply.")
    if len(reference) > 50:
        raise HTTPException(400, "Document reference is too long (50 characters at most).")
    p = {"r": rid, "l": body.loan_id, "t": body.tranche_no}
    gap = one(f"SELECT missing_source FROM {OUT}.evidence_gaps WHERE run_id = {{r}} AND loan_id = {{l}} AND tranche_no = {{t}}", p)
    if not gap:
        raise HTTPException(404, "This tranche is not in the evidence-gap queue of the latest run.")
    info = one(f"SELECT dataset_id, as_of FROM {RAW}.dataset_info")
    try:
        when = rv.clean_evidence_date(body.event_date, info["as_of"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    source = str(gap["missing_source"]).split(",")[0]  # the first record the precedence rules look for
    if one(f"""SELECT 1 AS x FROM {POL}.evidence_additions WHERE dataset_id = {{d}} AND loan_id = {{l}} AND tranche_no = {{t}}
               AND evidence_source = {{s}} AND withdrawn_at IS NULL""", {**p, "d": info["dataset_id"], "s": source}):
        raise HTTPException(409, "A date is already entered for this tranche. Withdraw it first if it was wrong.")
    with db() as c:
        c.execute(f"""INSERT INTO {POL}.evidence_additions (evidence_id, dataset_id, loan_id, tranche_no, evidence_source, event_date,
                                                            reference, added_by, reason, added_at)
                      VALUES ({{i}}, {{d}}, {{l}}, {{t}}, {{s}}, {{w}}, {{ref}}, {{who}}, {{why}}, {{at}})""",
                  {**p, "i": f"RV{uuid.uuid4().hex[:12].upper()}", "d": info["dataset_id"], "s": source, "w": when,
                   "ref": reference, "who": who, "why": why, "at": now()})
    return evidence_entries(rid)


class WithdrawIn(BaseModel):
    reviewer: str
    reason: str


@app.post("/api/runs/{run_id}/evidence/{evidence_id}/withdraw")
def evidence_withdraw(run_id: str, evidence_id: str, body: WithdrawIn):
    """A wrong entry is withdrawn, never erased. The next run stops using it."""
    rid = _writable_run(run_id)
    who, why = _actor(body.reviewer, body.reason)
    with db() as c:
        st = c.execute(f"""UPDATE {POL}.evidence_additions SET withdrawn_by = {{who}}, withdrawn_reason = {{why}}, withdrawn_at = {{at}}
                           WHERE evidence_id = {{i}} AND withdrawn_at IS NULL""",
                       {"who": who, "why": why, "at": now(), "i": evidence_id})
        if not st.rowcount():
            raise HTTPException(404, "No active entry with this id.")
    return evidence_entries(rid)


class ReleaseIn(BaseModel):
    reviewer: str
    reason: str
    loan_ids: list[str] | None = None  # None releases every approved letter
    lang: str = ""


@app.post("/api/runs/{run_id}/releases")
def release_letters(run_id: str, body: ReleaseIn):
    """Hand approved letters over for dispatch. The checker runs again here; one failure stops the whole batch."""
    rid = _writable_run(run_id)
    who, why = _actor(body.reviewer, body.reason)
    if body.lang and body.lang not in rv.LETTER_LANGS:
        raise HTTPException(400, "unknown language")
    states = {s["loan_id"]: s for s in rows(rv.loan_states_sql(OUT, POL), {"r": rid})}
    if body.loan_ids is None:
        ids = [k for k, s in states.items() if s["letter_state"] == "APPROVED"]
    else:
        ids = body.loan_ids
        blocked = [i for i in ids if states.get(i, {}).get("letter_state") != "APPROVED"]
        if blocked:
            words = {"DRAFT": "it is still a draft: every refund row must be approved at its current figure first",
                     "RELEASED": "this letter has already been released at this figure"}
            why_blocked = words.get(states.get(blocked[0], {}).get("letter_state"), "it has no refund in this run")
            raise HTTPException(409, f"Cannot release {blocked[0]}: {why_blocked}.")
    if not ids:
        raise HTTPException(409, "No approved letters are waiting to be released.")
    wanted = set(ids)
    q = f"SELECT * FROM {OUT}.letter_figures WHERE run_id = {{r}}"
    figs = [f for f in rows(q, {"r": rid}) if f["loan_id"] in wanted]
    recheck = [f for f in rows(q, {"r": rid}) if f["loan_id"] in wanted]  # separate read, as in the letter screen
    letters, failed = rv.build_letters(figs, recheck, body.lang)
    if failed:
        raise HTTPException(409, f"Nothing was released. The checker rejected {len(failed)} letter(s), first {failed[0]}.")
    mismatch = [x["loan_id"] for x in letters if str(x["excess_paise"]) != str(states[x["loan_id"]]["total_paise"])]
    if mismatch or len(letters) != len(wanted):
        raise HTTPException(409, "Nothing was released. The letter figures do not match the refund ledger for this run.")
    batch, at = str(uuid.uuid4()), now()
    dataset = one(f"SELECT dataset_id FROM {OUT}.audit_runs WHERE run_id = {{r}}", {"r": rid})["dataset_id"]
    data = [(batch, dataset, rid, x["loan_id"], x["letter_lang"], x["excess_paise"], states[x["loan_id"]]["approved_by"],
             who, at, x["text_sha256"], x["letter_text"]) for x in letters]
    with db() as c:
        c.set_autocommit(False)  # the letters and their batch row land together or not at all
        c.import_from_iterable(data, (POL, "LETTER_RELEASES"), import_params={"columns": [
            "BATCH_ID", "DATASET_ID", "RUN_ID", "LOAN_ID", "LETTER_LANG", "EXCESS_PAISE", "APPROVED_BY", "RELEASED_BY",
            "RELEASED_AT", "TEXT_SHA256", "LETTER_TEXT"]})
        c.execute(f"""INSERT INTO {POL}.release_batches (batch_id, dataset_id, run_id, released_by, batch_note, released_at,
                                                         letter_count, total_paise)
                      SELECT {{b}}, {{d}}, {{r}}, {{who}}, {{why}}, {{at}}, COUNT(*), SUM(excess_paise)
                      FROM {POL}.letter_releases WHERE batch_id = {{b}}""",
                  {"b": batch, "d": dataset, "r": rid, "who": who, "why": why, "at": at})
        c.commit()
        c.set_autocommit(True)
    return one(f"SELECT * FROM {POL}.release_batches WHERE batch_id = {{b}}", {"b": batch})


@app.get("/api/releases/{batch_id}/letters.zip")
def release_download(batch_id: str):
    if not re.fullmatch(r"[0-9a-f-]{36}", batch_id):
        raise HTTPException(400, "bad batch id")
    batch = one(f"SELECT * FROM {POL}.release_batches WHERE batch_id = {{b}}", {"b": batch_id})
    if not batch:
        raise HTTPException(404, "no such batch")
    letters = rows(f"""SELECT r.loan_id, b.display_name, r.letter_lang, r.excess_paise, r.approved_by, r.released_by,
                              r.released_at, r.text_sha256, r.letter_text
                       FROM {POL}.letter_releases r
                       LEFT JOIN {RAW}.loans l ON l.loan_id = r.loan_id
                       LEFT JOIN {RAW}.borrowers b ON b.borrower_id = l.borrower_id
                       WHERE r.batch_id = {{b}} ORDER BY r.loan_id""", {"b": batch_id})
    return Response(rv.release_zip(batch, letters), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=letter_release_{batch_id[:8]}.zip"})


@app.get("/api/health")
def health():
    return PlainTextResponse("ok")


DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")

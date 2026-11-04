"""The rows behind one audited month, exactly as they sit in Exasol, for the Show source records panel.

Read-only. Nothing is calculated here: raw rows come back as stored, and figures in the decision come from result
tables. The only logic is naming which stored row set a date the run already resolved, and comparing stored values.
"""

from __future__ import annotations

import json
from textwrap import dedent

from scripts.db import schemas

S = schemas()
RAW, POL, OUT = S["RAW"], S["POLICY"], S["OUT"]
JSON_SAFE = 2**53


def _q(sql: str) -> str:
    return dedent(sql).strip()


RECORDS: tuple[tuple[str, str, str], ...] = (
    ("evidence", f"{RAW}.disbursement_evidence", _q(f"""
        SELECT evidence_id, tranche_no, evidence_source, event_date, reference, recorded_in
        FROM {RAW}.disbursement_evidence
        WHERE loan_id = {{l}}
        ORDER BY tranche_no, event_date, evidence_id""")),
    # a date from a branch reply counts only for runs that started after it was entered and before it was withdrawn
    ("entered_evidence", f"{POL}.evidence_additions", _q(f"""
        SELECT a.evidence_id, a.tranche_no, a.evidence_source, a.event_date, a.reference, a.added_by, a.reason
        FROM {POL}.evidence_additions a
        JOIN {OUT}.audit_runs r ON r.run_id = {{r}} AND r.dataset_id = a.dataset_id
        WHERE a.loan_id = {{l}} AND a.added_at <= r.started_at
          AND (a.withdrawn_at IS NULL OR a.withdrawn_at > r.started_at)
        ORDER BY a.tranche_no, a.event_date, a.evidence_id""")),
    ("postings", f"{RAW}.interest_postings", _q(f"""
        SELECT posting_id, period_start, period_end, posted_paise, posted_on, reverses_posting_id, is_manual
        FROM {RAW}.interest_postings
        WHERE loan_id = {{l}} AND period_start = CAST({{p}} AS DATE)
        ORDER BY posted_on, posting_id""")),
    ("tranches", f"{RAW}.tranches", _q(f"""
        SELECT tranche_no, amount_paise, payment_mode, payee_type
        FROM {RAW}.tranches
        WHERE loan_id = {{l}}
        ORDER BY tranche_no""")),
    ("rates", f"{RAW}.rate_history", _q(f"""
        SELECT effective_date, annual_rate_pct
        FROM {RAW}.rate_history
        WHERE loan_id = {{l}} AND effective_date < ADD_MONTHS(CAST({{p}} AS DATE), 1)
        ORDER BY effective_date""")),
    ("kfs", f"{RAW}.kfs", _q(f"""
        SELECT issued_date, annual_rate_pct, day_count_basis, commitment_fee_rate_pct, broken_period_disclosed,
               disclosed_emi_paise, disclosed_apr_pct
        FROM {RAW}.kfs
        WHERE loan_id = {{l}}""")),
    ("loan", f"{RAW}.loans", _q(f"""
        SELECT loan_id, product, sanction_date, agreement_date, sanctioned_paise, tenure_months, status, closed_date
        FROM {RAW}.loans
        WHERE loan_id = {{l}}""")),
    ("receipts", f"{RAW}.receipts", _q(f"""
        SELECT receipt_id, value_date, kind, amount_paise, principal_paise, due_date
        FROM {RAW}.receipts
        WHERE loan_id = {{l}}
          AND ((value_date >= CAST({{p}} AS DATE) AND value_date < ADD_MONTHS(CAST({{p}} AS DATE), 1))
               OR kind = 'ADVANCE_EMI')
        ORDER BY value_date, receipt_id""")),
)

EARLIER_RECEIPTS = f"""SELECT COUNT(*) AS receipts, COALESCE(SUM(principal_paise), 0) AS principal_paise
                       FROM {RAW}.receipts WHERE loan_id = {{l}} AND value_date < CAST({{p}} AS DATE)"""
POSTED_NOW = f"""SELECT COALESCE(SUM(posted_paise), 0) AS posted_now
                 FROM {RAW}.interest_postings WHERE loan_id = {{l}} AND period_start = CAST({{p}} AS DATE)"""
REFUND = f"""SELECT COALESCE(SUM(excess_paise), 0) AS refund_paise FROM {OUT}.findings
             WHERE run_id = {{r}} AND loan_id = {{l}} AND period_start = CAST({{p}} AS DATE) AND status = 'REFUND'"""


def cell(value):
    """A stored value as it is, except an integer JSON cannot carry exactly goes as a string."""
    return str(value) if isinstance(value, int) and not isinstance(value, bool) and abs(value) >= JSON_SAFE else value


def as_dicts(record: dict) -> list[dict]:
    return [dict(zip(record["columns"], row)) for row in record["rows"]]


def deciding_ids(evidence: list[dict], tranches: list[dict]) -> list[str]:
    """Which rows set each tranche's resolved date. A cheque handed over before its date resolves to the cheque date."""
    out: list[str] = []
    for t in tranches:
        if not t.get("resolved_date"):
            continue
        same = [e for e in evidence if e["tranche_no"] == t["tranche_no"] and e["event_date"] == t["resolved_date"]]
        hits = [e for e in same if e["evidence_source"] == t["resolved_source"]]
        if not hits and t["resolved_source"] == "HANDOVER_ACK":
            hits = [e for e in same if e["evidence_source"] == "CHEQUE_DATE"]
        out += [e["evidence_id"] for e in hits]
    return out


def precedence(policy_snapshot: str | None, payment_mode: str) -> list[dict]:
    """The date rule this run used for a payment mode, from its own policy snapshot, not today's settings."""
    snap = json.loads(policy_snapshot or "{}")
    use_fallback = str(snap.get("settings", {}).get("allow_lms_fallback_electronic", "true")).lower() == "true"
    ranked = sorted((p for p in snap.get("date_precedence", []) if p["payment_mode"] == payment_mode),
                    key=lambda p: int(p["rank"]))
    return [{"evidence_source": p["evidence_source"], "rule": p["rule"]} for p in ranked
            if p["rule"] != "FALLBACK" or use_fallback]


def freshness(run_dataset: str | None, loaded_dataset: str | None, posted_in_run, posted_now) -> dict:
    """Raw tables hold the loaded extract, not a copy per run, so say when they no longer match what the run audited."""
    return {"same_extract": run_dataset == loaded_dataset, "posted_in_run": posted_in_run, "posted_now": posted_now,
            "posted_matches": str(posted_in_run) == str(posted_now)}

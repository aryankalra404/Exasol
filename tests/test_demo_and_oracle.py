"""Acceptance tests for the demo loans (docs/SPEC.md) and the oracle-agreement check.

Oracle-only tests need just the generated CSVs. Tests marked `db` need Exasol with a loaded dataset and a
completed audit run (make demo).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from generator.generate import generate
from oracle.oracle import audit

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def small_book(tmp_path_factory) -> Path:
    return generate(seed=11, loans=150, as_of=date(2026, 10, 1), defect_scale=1.0,
                    out_root=tmp_path_factory.mktemp("data"))


def by_period(results, loan_id):
    return {r.period_start: r for r in results if r.loan_id == loan_id}


def test_meena_cheque_date_eight_days(small_book):
    res = by_period(audit(small_book, ["LDM0001"]), "LDM0001")
    march = res[date(2025, 3, 1)]
    assert march.status == "MATCHED"
    assert march.convention == "CHQ|DIS|NET|EXACT"
    # 12,00,000 x 8.75% x 8 / 365 = 2,301.3698... -> Rs 2,301.37
    assert march.posted - march.fair == 230137
    assert all(r.status == "FAIR" for p, r in res.items() if p != date(2025, 3, 1))


def test_raghav_disclosed_commitment_fee_is_permitted(small_book):
    res = by_period(audit(small_book, ["LDM0002"]), "LDM0002")
    flagged = {p: r for p, r in res.items() if r.status != "FAIR"}
    assert flagged and all(r.status == "PERMITTED" and r.convention == "CFEE" for r in flagged.values())


def test_asha_missing_handover_is_evidence_gap(small_book):
    res = by_period(audit(small_book, ["LDM0003"]), "LDM0003")
    assert res[date(2025, 6, 1)].status == "EVIDENCE_GAP"


def test_generator_is_deterministic(tmp_path):
    a = generate(5, 40, date(2026, 10, 1), 1.0, tmp_path / "a")
    b = generate(5, 40, date(2026, 10, 1), 1.0, tmp_path / "b")
    for f in (a / "raw").glob("*.csv"):
        assert f.read_bytes() == (b / "raw" / f.name).read_bytes()


def test_no_defects_means_no_unexplained(tmp_path):
    book = generate(3, 120, date(2026, 10, 1), 0.0, tmp_path)
    statuses = {r.status for r in audit(book) if not r.loan_id.startswith("LDM")}  # Asha's gap is deliberate
    assert "UNEXPLAINED" not in statuses and "EVIDENCE_GAP" not in statuses


needs_db = pytest.mark.skipif(not (ROOT / ".env").exists() or os.environ.get("SKIP_DB") == "1",
                              reason="needs Exasol (.env) and a completed audit run")


@needs_db
def test_sql_demo_loans_match_spec():
    from scripts.db import connect, schemas
    s = schemas()
    conn = connect()
    run = conn.execute(f"SELECT run_id FROM {s['OUT']}.audit_runs WHERE status = 'DONE' "
                       f"ORDER BY started_at DESC LIMIT 1").fetchval()
    rows = conn.execute(f"SELECT loan_id, TO_CHAR(period_start, 'YYYY-MM'), practice_code, status, days_affected, "
                        f"excess_paise FROM {s['OUT']}.findings WHERE run_id = {{r}} AND loan_id LIKE 'LDM%'",
                        {"r": run}).fetchall()
    meena = [r for r in rows if r[0] == "LDM0001"]
    assert meena == [("LDM0001", "2025-03", "P2", "REFUND", 8, 230137)] or \
        [(a, b, c, d, int(e), int(f)) for a, b, c, d, e, f in meena] == [("LDM0001", "2025-03", "P2", "REFUND", 8, 230137)]
    assert {r[3] for r in rows if r[0] == "LDM0002"} == {"PERMITTED"}
    assert {r[3] for r in rows if r[0] == "LDM0003"} == {"EVIDENCE_GAP"}
    gap = conn.execute(f"SELECT suggested_query FROM {s['OUT']}.evidence_gaps WHERE run_id = {{r}} AND loan_id = 'LDM0003'",
                       {"r": run}).fetchval()
    assert "handover ack" in gap


@needs_db
def test_sql_agrees_with_oracle():
    from eval.oracle_agreement import compare
    info = conn_dataset()
    report = compare(ROOT / "data" / info, sample=400)
    assert report["periods_only_in_sql"] == 0
    assert report["largest_fair_deviation_paise"] == 0
    assert report["fair_exact"] == report["periods_compared"]
    assert report["status_agree"] == report["periods_compared"]
    assert report["matched_convention_agree"] == report["periods_compared"]


def conn_dataset() -> str:
    from scripts.db import connect, schemas
    return connect().execute(f"SELECT MAX(dataset_id) FROM {schemas()['RAW']}.dataset_info").fetchval()

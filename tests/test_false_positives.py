"""False-positive suite: loans that look unfair but are disclosed or fair must never reach the refund ledger.

Cases (docs/SPEC.md, docs/DOMAIN.md):
- KFS discloses a commitment fee from sanction (BR008): periods charged under it are PERMITTED, never MATCHED
- KFS discloses 30E/360 and the LMS uses it: fair under the disclosed basis, never flagged
- Every period the hidden LMS posted fairly, on loans with no planted defect: FAIR

Expected labels come from the generator's truth tables, which tests may read. The audit side is the
independent oracle here, and the SQL output in the db test at the bottom.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from generator.generate import generate
from oracle.oracle import audit
from tests.test_demo_and_oracle import conn_dataset, needs_db

ROOT = Path(__file__).resolve().parent.parent
FAIR = "MIH|DIS|NET|EXACT"
FLAGGED = {"MATCHED", "AMBIGUOUS", "UNEXPLAINED"}  # anything that is, or could become, a refund


def rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def truth(book: Path) -> dict[tuple[str, str], str]:
    return {(r["loan_id"], r["period_start"]): r["true_convention_id"] for r in rows(book / "truth" / "expected.csv")}


def kfs(book: Path) -> dict[str, dict]:
    return {r["loan_id"]: r for r in rows(book / "raw" / "kfs.csv")}


@pytest.fixture(scope="module")
def clean_book(tmp_path_factory) -> Path:
    return generate(seed=23, loans=1200, as_of=date(2026, 10, 1), defect_scale=0.0,
                    out_root=tmp_path_factory.mktemp("fp"))


@pytest.fixture(scope="module")
def clean_results(clean_book):
    return {(r.loan_id, r.period_start.isoformat()): r for r in audit(clean_book)}


def test_disclosed_commitment_fee_is_permitted_not_refunded(clean_book, clean_results):
    fee_loans = {k for k, v in kfs(clean_book).items() if v["commitment_fee_rate_pct"]}
    periods = [k for k, conv in truth(clean_book).items() if conv == "CFEE" and k[0] in fee_loans and k in clean_results]
    assert len(fee_loans) >= 5 and periods, "book too small to contain disclosed commitment fees"
    statuses = Counter(clean_results[k].status for k in periods)
    assert statuses["PERMITTED"] > 0
    assert set(statuses) <= {"PERMITTED", "FAIR"}, statuses  # FAIR once fully disbursed: fee is then zero


def test_disclosed_30e_360_is_fair(clean_book, clean_results):
    loans = {k for k, v in kfs(clean_book).items() if v["day_count_basis"] == "30E_360"}
    periods = [k for k, conv in truth(clean_book).items() if conv == FAIR and k[0] in loans and k in clean_results]
    assert loans and periods, "book too small to contain a disclosed 30E/360 loan"
    wrong = [k for k in periods if clean_results[k].status != "FAIR"]
    assert wrong == []


def test_fairly_posted_periods_are_never_flagged(clean_book, clean_results):
    periods = [k for k, conv in truth(clean_book).items() if conv == FAIR and not k[0].startswith("LDM") and k in clean_results]
    statuses = Counter(clean_results[k].status for k in periods)
    assert len(periods) > 10000
    assert not (set(statuses) & FLAGGED), statuses


@needs_db
def test_sql_flags_no_disclosed_or_fair_period():
    """Same checks against the SQL pipeline's latest run on the loaded dataset, skipping loans with planted defects."""
    from scripts.db import connect, schemas
    s = schemas()
    book = ROOT / "data" / conn_dataset()
    defective = {r["loan_id"] for r in rows(book / "truth" / "planted_defects.csv")}
    conn = connect()
    run = conn.execute(f"SELECT run_id FROM {s['OUT']}.audit_runs WHERE status = 'DONE' "
                       f"ORDER BY started_at DESC LIMIT 1").fetchval()
    found = conn.execute(f"SELECT loan_id, TO_CHAR(period_start, 'YYYY-MM-DD'), status FROM {s['OUT']}.findings "
                         f"WHERE run_id = {{r}}", {"r": run}).fetchall()  # findings hold every non-FAIR period
    expected = truth(book)
    checked = [((loan, ps), st) for loan, ps, st in found if loan not in defective and expected.get((loan, ps)) in (FAIR, "CFEE")]
    assert any(st == "PERMITTED" for _, st in checked)
    assert [k for k, st in checked if st != "PERMITTED"] == []

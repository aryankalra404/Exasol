"""Public anchor: RBI's own worked example, run through the oracle and the SQL pipeline.

RBI's illustrative Key Facts Statement (digital lending guidelines, Sep 2022, Annex II; reused in the KFS
circular of 15 Apr 2024) shows a loan of Rs 20,000 over 24 monthly instalments of Rs 969.73 (rounded to
Rs 970), total interest Rs 3,274, an upfront charge of Rs 400 and an APR of 17.07%. The rate is not quoted
in the excerpts we could read; 15% p.a. on a monthly reducing balance is the rate that reproduces all of
those figures together, which the first test checks.

The fixture book holds that one loan: disbursed on the 1st, KFS discloses 30E/360 (so each whole month is
balance x rate / 12, as in RBI's schedule), EMIs on the 1st, and the lender posts exactly RBI's schedule.
The audit must call every month FAIR and reproduce the schedule's interest to the paisa.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, getcontext
from pathlib import Path

from oracle.oracle import audit
from tests.test_demo_and_oracle import needs_db

getcontext().prec = 50

# RBI's published figures
RBI_PRINCIPAL = 2000000  # paise, Rs 20,000
RBI_MONTHS = 24
RBI_EMI = 96973  # paise, Rs 969.73
RBI_EMI_ROUNDED_RUPEES = 970
RBI_TOTAL_INTEREST_RUPEES = 3274
RBI_FEE = 40000  # paise, Rs 400
RBI_APR = Decimal("17.07")

RATE = Decimal(15)
LOAN = "LRBI0001"
START = date(2024, 1, 1)


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def schedule() -> list[tuple[date, int, int]]:
    """RBI-style schedule from the published EMI: (due date, interest, principal) per instalment, in paise."""
    r = RATE / 1200
    bal, rows = RBI_PRINCIPAL, []
    for k in range(1, RBI_MONTHS + 1):
        interest = int((bal * r).quantize(Decimal(1), ROUND_HALF_UP))
        principal = RBI_EMI - interest if k < RBI_MONTHS else bal
        bal -= principal
        rows.append((add_months(START, k), interest, principal))
    assert bal == 0
    return rows


def apr(instalment: int, net: int) -> Decimal:
    """Nominal annual IRR, in percent, of receiving `net` and paying `instalment` for RBI_MONTHS months."""
    lo, hi = Decimal(0), Decimal("0.1")
    for _ in range(200):
        m = (lo + hi) / 2
        pv = sum(Decimal(instalment) / (1 + m) ** k for k in range(1, RBI_MONTHS + 1))
        lo, hi = (m, hi) if pv > net else (lo, m)
    return (lo * 1200).quantize(Decimal("0.01"), ROUND_HALF_UP)


def write(path: Path, cols: list[str], rows: list[list]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)


def build_book(root: Path) -> Path:
    from generator.generate import COLUMNS

    out = root / "rbi_kfs"
    (out / "raw").mkdir(parents=True)
    (out / "truth").mkdir()
    sched = schedule()
    sanction = date(2023, 12, 15)
    tables = {
        "branches": [["BR009", "Vadodara Alkapuri", "Gujarat", "WEST"]],
        "borrowers": [["BRBI0001", "RBI Illustration (synthetic)", "en", "Gujarat"]],
        "loans": [[LOAN, "BRBI0001", "BR009", "PERSONAL", sanction, sanction, RBI_PRINCIPAL, RBI_MONTHS, sched[0][0], "CLOSED", sched[-1][0]]],
        "kfs": [[LOAN, sanction, RATE, "30E_360", "", "TRUE", RBI_EMI, RBI_APR]],
        "kfs_disbursal_schedule": [[LOAN, 1, START, RBI_PRINCIPAL]],
        "rate_history": [[LOAN, sanction, RATE]],
        "tranches": [[LOAN, 1, RBI_PRINCIPAL, "NEFT", "BORROWER"]],
        "disbursement_evidence": [["ERBI00011", LOAN, 1, "LMS_DISB", START, "LMSRBI1", "LMS"],
                                  ["ERBI00012", LOAN, 1, "RAIL_CREDIT", START, "UTRRBI1", "PAYMENTS"]],
        "demands": [[LOAN, due, k, "EMI", i + p] for k, (due, i, p) in enumerate(sched, 1)],
        "receipts": [[f"RRBI{k:03d}", LOAN, due, "EMI", i + p, p, due] for k, (due, i, p) in enumerate(sched, 1)],
        "interest_postings": [[f"PRBI{k:03d}", LOAN, add_months(START, k - 1), due, i, due, "", "FALSE"]
                              for k, (due, i, _) in enumerate(sched, 1)],
    }
    for name, rows in tables.items():
        write(out / "raw" / f"{name}.csv", COLUMNS[name], rows)
    for name in ("lms_config", "planted_defects", "expected"):
        write(out / "truth" / f"{name}.csv", COLUMNS[name], [])
    (out / "manifest.json").write_text(json.dumps(dict(dataset_id="rbi_kfs", seed=0, loans=1, bulk_loans=0, as_of="2026-01-01",
                                                       defect_scale=0, generator_version="fixture")))
    return out


def test_fixture_reproduces_rbi_figures():
    sched = schedule()
    assert sched[0][1] + sched[0][2] == RBI_EMI
    assert int((Decimal(RBI_EMI) / 100).quantize(Decimal(1), ROUND_HALF_UP)) == RBI_EMI_ROUNDED_RUPEES
    total = sum(i for _, i, _ in sched)
    assert total == 327358  # Rs 3,273.58
    assert int((Decimal(total) / 100).quantize(Decimal(1), ROUND_HALF_UP)) == RBI_TOTAL_INTEREST_RUPEES
    assert apr(RBI_EMI, RBI_PRINCIPAL - RBI_FEE) == RBI_APR


def test_oracle_reproduces_rbi_schedule(tmp_path):
    book = build_book(tmp_path)
    res = sorted(audit(book, [LOAN]), key=lambda r: r.period_start)
    assert [r.period_start for r in res] == [add_months(START, k) for k in range(RBI_MONTHS)]
    assert [r.fair for r in res] == [i for _, i, _ in schedule()]
    assert {r.status for r in res} == {"FAIR"}


@needs_db
def test_sql_reproduces_rbi_schedule(tmp_path, monkeypatch):
    """Load the one-loan book into separate schemas and run the full pipeline; the demo schemas are not touched."""
    from scripts.audit import run_audit
    from scripts.db import connect, schemas
    from scripts.load import load

    keys = ("RAW", "POLICY", "OUT", "TRUTH", "WORK")
    for key in keys:
        monkeypatch.setenv(f"EXASOL_SCHEMA_{key}", f"RBIFIX_{key}")
    s = schemas()
    load(build_book(tmp_path))
    run = run_audit("rbi fixture")["run_id"]
    conn = connect()
    try:
        rows = conn.execute(f"SELECT period_start, fair_paise, posted_paise, match_status FROM {s['OUT']}.fingerprints "
                            f"WHERE run_id = {{r}} AND loan_id = {{l}} ORDER BY period_start", {"r": run, "l": LOAN}).fetchall()
        findings = conn.execute(f"SELECT COUNT(*) FROM {s['OUT']}.findings WHERE run_id = {{r}}", {"r": run}).fetchval()
    finally:
        for key in keys:
            conn.execute(f"DROP SCHEMA IF EXISTS {s[key]} CASCADE")
        conn.close()
    assert [int(f) for _, f, _, _ in rows] == [i for _, i, _ in schedule()]
    assert sum(int(f) for _, f, _, _ in rows) == 327358
    assert {st for *_, st in rows} == {"FAIR"}
    assert int(findings) == 0


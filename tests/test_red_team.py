"""The red-team harness must report disagreements, and must run without touching the demo schemas."""

from __future__ import annotations

import csv
import io
import zipfile

import pytest

from app.api.book_io import templates_zip
from eval.red_team import EXPECTED_COLUMNS, compare, read_expected, run
from tests.test_demo_and_oracle import needs_db


def row(loan="X1", period="2025-03-01", status="REFUND", fair="100", excess="50", why=""):
    return dict(zip(EXPECTED_COLUMNS, [loan, period, status, fair, excess, why]))


def audit(loan="X1", period="2025-03-01", status="MATCHED", fair=100, excess=50):
    return {"loan_id": loan, "period_start": period, "match_status": status, "fair_paise": fair, "excess_paise": excess}


def test_agreeing_month_passes_and_matched_means_refund():
    r = compare([row()], [audit()], {"X1": 50})
    assert r["months_disagreeing"] == 0 and r["loan_refund_totals"][0]["agrees"]


def test_each_kind_of_disagreement_is_reported():
    assert "status" in compare([row(status="FAIR")], [audit()], {})["cases"][0]["problems"][0]
    assert "fair" in compare([row(fair="99")], [audit()], {})["cases"][0]["problems"][0]
    assert "excess" in compare([row(excess="49")], [audit()], {})["cases"][0]["problems"][0]
    assert compare([row()], [], {})["cases"][0]["problems"] == ["month not audited"]
    assert not compare([row()], [audit()], {"X1": 49})["loan_refund_totals"][0]["agrees"]


def test_flagged_month_nobody_expected_is_reported():
    r = compare([row()], [audit(), audit(period="2025-04-01", status="UNEXPLAINED", excess=7), audit(loan="OTHER")], {"X1": 50})
    assert [u["period_start"] for u in r["unlisted_flagged_months"]] == ["2025-04-01"]


def test_expected_file_problems_are_named(tmp_path):
    path = tmp_path / "expected.csv"
    assert "missing" in read_expected(path)[1][0]
    path.write_text("loan_id,period_start\nX1,2025-03-01\n")
    assert "missing column" in read_expected(path)[1][0]
    path.write_text(",".join(EXPECTED_COLUMNS) + "\nX1,March,MAYBE,1.5,,\nX1,March,FAIR,,,\n")
    problems = "\n".join(read_expected(path)[1])
    assert "status must be" in problems and "YYYY-MM-DD" in problems and "whole paise" in problems and "listed twice" in problems


@pytest.fixture
def template_book(tmp_path):
    with zipfile.ZipFile(io.BytesIO(templates_zip())) as z:
        for name in z.namelist():
            if name.endswith(".csv"):
                (tmp_path / name.split("/")[-1]).write_bytes(z.read(name))
    return tmp_path


def write_expected(book, rows):
    with (book / "expected.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(EXPECTED_COLUMNS)
        w.writerows(rows)


@needs_db
def test_end_to_end_on_known_loans_and_demo_book_untouched(template_book):
    from scripts.db import connect

    def demo_state():
        c = connect()
        state = (c.execute("SELECT dataset_id FROM SAHI_RAW.dataset_info").fetchval(),
                 c.execute("SELECT MAX(started_at), COUNT(*) FROM SAHI_OUT.audit_runs").fetchone())
        c.close()
        return state

    before = demo_state()
    write_expected(template_book, [["LDM0001", "2025-03-01", "REFUND", "", "230137", "cheque date"],
                                   ["LDM0003", "2025-06-01", "EVIDENCE_GAP", "", "", "no handover record"]])
    good = run(template_book)
    assert good["months_disagreeing"] == 0, good["cases"]
    assert good["loan_refund_totals"][0] == {"loan_id": "LDM0001", "expected_refund_paise": 230137,
                                             "ledger_refund_paise": 230137, "agrees": True}

    # one paisa off must be caught
    write_expected(template_book, [["LDM0001", "2025-03-01", "REFUND", "", "230138", "wrong on purpose"]])
    bad = run(template_book)
    assert bad["months_disagreeing"] == 1 and "excess" in bad["cases"][0]["problems"][0]
    assert demo_state() == before


def test_refuses_to_run_without_written_answers(template_book):
    write_expected(template_book, [])
    with pytest.raises(ValueError, match="write the expected answers"):
        run(template_book)


def _oracle_results():
    """The oracle on the frozen blind book, read straight from the CSVs."""
    import shutil
    import tempfile
    from pathlib import Path

    from eval.red_team import BOOK
    from oracle.oracle import audit

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "raw").mkdir()
        for f in BOOK.glob("*.csv"):
            if f.name != "expected.csv":
                shutil.copy(f, Path(tmp) / "raw" / f.name)
        return {(r.loan_id, str(r.period_start)): r for r in audit(Path(tmp))}


def test_oracle_audits_a_posting_before_the_sanction_month():
    result = _oracle_results()[("RT003", "2023-12-01")]
    assert result.status == "FAIR" and result.fair == 9315


@needs_db
def test_frozen_blind_book_agrees_and_no_posting_is_left_out():
    from eval.red_team import BOOK

    report = run(BOOK)
    assert report["months_disagreeing"] == 0, [c for c in report["cases"] if c["problems"]]
    assert all(t["agrees"] for t in report["loan_refund_totals"])
    # months after a test loan stopped posting are undercharges, never refunds
    assert {u["audit_status"] for u in report["unlisted_flagged_months"]} <= {"UNDERCHARGE"}


@needs_db
def test_every_posting_on_the_demo_book_is_audited():
    from scripts.audit import postings_outside_audit
    from scripts.db import connect, schemas

    conn = connect()
    run_id = conn.execute(f"SELECT run_id FROM {schemas()['OUT']}.audit_runs WHERE status = 'DONE' "
                          f"ORDER BY started_at DESC LIMIT 1").fetchval()
    assert postings_outside_audit(conn, run_id) == []
    conn.close()

"""Loan-book import checks and the inspection pack (app/api/book_io.py)."""

from __future__ import annotations

import csv
import io
import zipfile

from app.api.book_io import templates_zip, validate_extract
from tests.test_demo_and_oracle import needs_db


def rezip(src: bytes, edit) -> bytes:
    """Copy a ZIP, letting `edit(name, text)` return new text, or None to drop the file."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src)) as zin, zipfile.ZipFile(out, "w") as zout:
        for name in zin.namelist():
            text = edit(name.split("/")[-1], zin.read(name).decode())
            if text is not None:
                zout.writestr(name, text)
    return out.getvalue()


def test_template_is_a_valid_extract():
    tables, errors, counts = validate_extract(templates_zip())
    assert errors == []
    assert counts["loans"] == 3 and counts["interest_postings"] > 0


def test_posting_not_on_the_first_of_a_month_is_refused():
    def edit(name, text):
        if name != "interest_postings.csv":
            return text
        lines = text.splitlines()
        i = lines[0].split(",").index("period_start")
        cells = lines[1].split(",")
        cells[i] = cells[i][:-2] + "15"
        lines[1] = ",".join(cells)
        return "\n".join(lines) + "\n"
    assert any("1st of a month" in e for e in validate_extract(rezip(templates_zip(), edit))[1])


def test_not_a_zip_is_refused():
    assert "not a ZIP" in validate_extract(b"hello")[1][0]


def test_missing_file_bad_value_and_missing_column_are_reported():
    def edit(name, text):
        if name == "receipts.csv":
            return None
        if name == "tranches.csv":
            return text.replace("payment_mode", "pay_mode", 1)
        if name == "loans.csv":
            lines = text.splitlines()
            lines[1] = lines[1].replace("2024-05-20", "20/05/2024")
            return "\n".join(lines) + "\n"
        return text
    errors = validate_extract(rezip(templates_zip(), edit))[1]
    assert "receipts.csv is missing." in errors
    assert any("tranches.csv: missing column payment_mode" in e for e in errors)
    assert any("loans.csv line 2, sanction_date" in e and "YYYY-MM-DD" in e for e in errors)


def test_columns_in_any_order_are_accepted_and_reordered():
    def edit(name, text):
        if name != "kfs.csv":
            return text
        rows = list(csv.reader(io.StringIO(text)))
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows([list(reversed(r)) for r in rows])
        return buf.getvalue()
    tables, errors, _ = validate_extract(rezip(templates_zip(), edit))
    assert errors == []
    assert tables["kfs"][0][0].startswith("LDM")  # loan_id back in first position


def test_unknown_loan_reference_is_reported():
    def edit(name, text):
        return text + "PX,LZZ9999,2025-01-01,2025-02-01,100,2025-02-01,,FALSE\n" if name == "interest_postings.csv" else text
    errors = validate_extract(rezip(templates_zip(), edit))[1]
    assert any("interest_postings.csv refers to 1 loan(s) not in loans.csv, e.g. LZZ9999" in e for e in errors)


@needs_db
def test_inspection_pack_matches_run_summary():
    from app.api.book_io import inspection_pack
    from app.api.main import OUT, RAW, resolve_run, rows
    rid = resolve_run("latest")
    pack = zipfile.ZipFile(io.BytesIO(inspection_pack(rid, rows, OUT, RAW)))
    names = {n.split("/", 1)[1] for n in pack.namelist()}
    assert {"README.md", "refund_ledger.csv", "findings.csv", "evidence_gaps.csv", "policy_snapshot.json", "lineage.csv"} <= names
    ledger = list(csv.DictReader(io.StringIO(pack.read(next(n for n in pack.namelist() if n.endswith("refund_ledger.csv"))).decode())))
    total = rows(f"SELECT refund_paise FROM {OUT}.run_summary WHERE run_id = {{r}}", {"r": rid})[0]["refund_paise"]
    assert sum(int(r["excess_paise"]) for r in ledger) == int(total)

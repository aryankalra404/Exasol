"""Blind red team: loans and expected answers written by someone who did not build the system, scored against the audit.

The book goes through the same checks as a lender's upload, is loaded into separate schemas (RT_*) with default
policy, and audited in Exasol. Every month in expected.csv is then compared with the result, and any other flagged
month on those loans is reported. Demo schemas are not touched. See docs/RED_TEAM.md.

Usage: python -m eval.red_team --template    write blank-format CSVs to fill in
       python -m eval.red_team               audit the book and write eval/reports/red_team.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import zipfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from app.api.book_io import templates_zip, validate_extract, write_book
from scripts.audit import run_audit
from scripts.db import connect, schemas
from scripts.load import load

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "tests" / "fixtures" / "red_team"
REPORT = ROOT / "eval" / "reports" / "red_team.json"
PREFIX = "RT_"
KEYS = ("RAW", "POLICY", "OUT", "TRUTH", "WORK")
EXPECTED_COLUMNS = ["loan_id", "period_start", "expected_status", "expected_fair_paise", "expected_excess_paise", "why"]
STATUSES = {"FAIR", "REFUND", "PERMITTED", "AMBIGUOUS", "EVIDENCE_GAP", "UNEXPLAINED", "UNDERCHARGE"}
REFUNDABLE = {"REFUND", "AMBIGUOUS"}


def read_expected(path: Path) -> tuple[list[dict], list[str]]:
    """Return (rows, problems). Amounts are optional, but a given amount must be whole paise."""
    if not path.exists():
        return [], [f"{path.name} is missing."]
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in EXPECTED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return [], [f"{path.name}: missing column {', '.join(missing)}."]
        rows = [r for r in reader if (r["loan_id"] or "").strip()]
    problems = []
    seen = set()
    for i, r in enumerate(rows, start=2):
        key = (r["loan_id"].strip(), r["period_start"].strip())
        if key in seen:
            problems.append(f"{path.name} line {i}: {key[0]} {key[1]} is listed twice.")
        seen.add(key)
        if r["expected_status"].strip() not in STATUSES:
            problems.append(f"{path.name} line {i}: status must be one of {', '.join(sorted(STATUSES))}.")
        try:
            date.fromisoformat(key[1])
        except ValueError:
            problems.append(f"{path.name} line {i}: period_start must be YYYY-MM-DD, the first of the month.")
        for c in ("expected_fair_paise", "expected_excess_paise"):
            v = (r[c] or "").strip()
            if v and not v.lstrip("-").isdigit():
                problems.append(f"{path.name} line {i}: {c} must be whole paise.")
    return rows, problems


def compare(expected: list[dict], actual: list[dict], ledger: dict[str, int]) -> dict:
    """Score the written answers against the audit. A disagreement is reported, never resolved here: the expected
    answer or the audit may be the wrong one, and a person decides which."""
    by_key = {(a["loan_id"], a["period_start"]): a for a in actual}
    loans = {e["loan_id"].strip() for e in expected}
    cases = []
    listed = set()
    for e in expected:
        key = (e["loan_id"].strip(), e["period_start"].strip())
        listed.add(key)
        a = by_key.get(key)
        case = {"loan_id": key[0], "period_start": key[1], "why": (e["why"] or "").strip(),
                "expected_status": e["expected_status"].strip(), "problems": []}
        if a is None:
            case["problems"].append("month not audited")
            cases.append(case)
            continue
        got = "REFUND" if a["match_status"] == "MATCHED" else a["match_status"]
        case.update(audit_status=got, audit_fair_paise=int(a["fair_paise"]), audit_excess_paise=int(a["excess_paise"]))
        if got != case["expected_status"]:
            case["problems"].append(f"status: expected {case['expected_status']}, audit says {got}")
        for col, audit_value, label in (("expected_fair_paise", case["audit_fair_paise"], "fair"),
                                        ("expected_excess_paise", case["audit_excess_paise"], "excess")):
            want = (e[col] or "").strip()
            if want and int(want) != audit_value:
                case["problems"].append(f"{label}: expected {want} paise, audit says {audit_value}")
        cases.append(case)
    unlisted = [{"loan_id": a["loan_id"], "period_start": a["period_start"], "audit_status": a["match_status"],
                 "audit_excess_paise": int(a["excess_paise"])}
                for a in actual if a["loan_id"] in loans and a["match_status"] != "FAIR"
                and (a["loan_id"], a["period_start"]) not in listed]
    totals = []
    for loan in sorted(loans):
        rows = [e for e in expected if e["loan_id"].strip() == loan and e["expected_status"].strip() in REFUNDABLE]
        if all((e["expected_excess_paise"] or "").strip() for e in rows):
            want = sum(int(e["expected_excess_paise"]) for e in rows)
            totals.append({"loan_id": loan, "expected_refund_paise": want, "ledger_refund_paise": ledger.get(loan, 0),
                           "agrees": want == ledger.get(loan, 0)})
    disagreements = sum(1 for c in cases if c["problems"])
    return {"months_checked": len(cases), "months_agreeing": len(cases) - disagreements, "months_disagreeing": disagreements,
            "unlisted_flagged_months": unlisted, "loan_refund_totals": totals, "cases": cases}


@contextmanager
def _red_team_schemas():
    """RT_* for the audit, restoring the environment after so nothing else in the process is redirected."""
    saved = {k: os.environ.get(f"EXASOL_SCHEMA_{k}") for k in KEYS}
    for k in KEYS:
        os.environ[f"EXASOL_SCHEMA_{k}"] = f"{PREFIX}{k}"
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(f"EXASOL_SCHEMA_{k}", None)
            else:
                os.environ[f"EXASOL_SCHEMA_{k}"] = v


def _zip_csvs(book: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for path in sorted(book.glob("*.csv")):
            if path.name != "expected.csv":
                z.write(path, path.name)
    return buf.getvalue()


def run(book: Path = BOOK) -> dict:
    expected, problems = read_expected(book / "expected.csv")
    if not expected and not problems:
        problems = ["expected.csv has no rows: write the expected answers before running anything."]
    tables, errors, _ = validate_extract(_zip_csvs(book))
    if problems or errors:
        raise ValueError("\n".join(problems + errors))
    with _red_team_schemas():
        s = schemas()
        conn = connect()
        for k in KEYS:  # default policy and no earlier results, every run
            conn.execute(f"DROP SCHEMA IF EXISTS {s[k]} CASCADE")
        conn.close()
        dataset = write_book(tables, ROOT / "data" / "red_team")
        load(dataset)
        audit = run_audit("red team")
        conn = connect()
        cols = ["loan_id", "period_start", "match_status", "fair_paise", "excess_paise"]
        actual = [dict(zip(cols, r)) for r in conn.execute(
            f"SELECT loan_id, TO_CHAR(period_start, 'YYYY-MM-DD'), match_status, fair_paise, excess_paise "
            f"FROM {s['OUT']}.fingerprints WHERE run_id = {{r}}", {"r": audit["run_id"]}).fetchall()]
        ledger = {r[0]: int(r[1]) for r in conn.execute(
            f"SELECT loan_id, SUM(excess_paise) FROM {s['OUT']}.refund_ledger WHERE run_id = {{r}} GROUP BY loan_id",
            {"r": audit["run_id"]}).fetchall()}
        conn.close()
    return {"date": date.today().isoformat(), "run_id": audit["run_id"], "audit_ms": audit["duration_ms"],
            "loans": len(tables["loans"]), **compare(expected, actual, ledger)}


def write_template(book: Path = BOOK) -> None:
    book.mkdir(parents=True, exist_ok=True)
    if any(book.glob("*.csv")):
        sys.exit(f"{book} already has CSVs. Nothing was overwritten.")
    with zipfile.ZipFile(io.BytesIO(templates_zip())) as z:
        for name in z.namelist():
            if name.endswith(".csv"):
                (book / Path(name).name).write_bytes(z.read(name))
    with (book / "expected.csv").open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow(EXPECTED_COLUMNS)
    print(f"Templates written to {book}. Replace the three example loans with your own, then fill in expected.csv.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--template", action="store_true", help="write blank-format CSVs to fill in")
    p.add_argument("--book", default=str(BOOK))
    p.add_argument("--out", default=str(REPORT))
    a = p.parse_args()
    if a.template:
        write_template(Path(a.book))
        return
    try:
        report = run(Path(a.book))
    except ValueError as e:
        sys.exit(str(e))
    Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['months_agreeing']} of {report['months_checked']} months agree, "
          f"{len(report['unlisted_flagged_months'])} flagged months not in expected.csv. Report: {a.out}")
    for c in report["cases"]:
        if c["problems"]:
            print(f"  {c['loan_id']} {c['period_start']}: {'; '.join(c['problems'])}")
    for u in report["unlisted_flagged_months"]:
        print(f"  {u['loan_id']} {u['period_start']}: flagged {u['audit_status']}, not in expected.csv")
    for t in report["loan_refund_totals"]:
        if not t["agrees"]:
            print(f"  {t['loan_id']}: expected refund {t['expected_refund_paise']} paise, ledger says {t['ledger_refund_paise']}")


if __name__ == "__main__":
    main()

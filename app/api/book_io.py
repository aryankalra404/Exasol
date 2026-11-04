"""Loan-book import, extract templates and the inspection pack.

Import: a ZIP of extract CSVs (one per SAHI_RAW table) is checked against the table definitions in
sql/01_raw_schema.sql before anything touches Exasol: every required file present, the expected columns,
dates as YYYY-MM-DD, whole paise, booleans as TRUE/FALSE, text within column widths, and every loan referenced
by another file present in loans.csv. Columns may come in any order; they are rewritten in table order.

Nothing here computes an interest or refund figure. The inspection pack copies result tables out of Exasol.
"""

from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from app.api.review import ledger_review_sql
from generator.generate import COLUMNS, generate
from scripts.db import ROOT
from scripts.load import RAW_TABLES, TRUTH_TABLES

SQL_DIR = ROOT / "sql"
# a lender may have no demand schedule or KFS disbursal plan in its extract; every other table is needed
OPTIONAL = {"demands", "kfs_disbursal_schedule"}
MAX_ERRORS = 25


def raw_types() -> dict[str, dict[str, tuple[str, int | None]]]:
    """{table: {column: (kind, width)}} parsed from the RAW schema DDL. kind: text, date, int, dec, bool."""
    ddl = (SQL_DIR / "01_raw_schema.sql").read_text()
    out: dict[str, dict[str, tuple[str, int | None]]] = {}
    for table, body in re.findall(r"CREATE (?:OR REPLACE )?TABLE \{RAW\}\.(\w+) \((.*?)\);", ddl, re.S):
        cols: dict[str, tuple[str, int | None]] = {}
        for name, typ, a, b in re.findall(r"(\w+) (VARCHAR\((\d+)\)|DATE|BOOLEAN|DECIMAL\((\d+),\d+\))", body):
            if typ.startswith("VARCHAR"):
                cols[name] = ("text", int(a))
            elif typ == "DATE":
                cols[name] = ("date", None)
            elif typ == "BOOLEAN":
                cols[name] = ("bool", None)
            else:
                cols[name] = ("int", None) if typ.endswith(",0)") else ("dec", None)
        out[table] = cols
    return out


def _check_value(kind: str, width: int | None, v: str) -> str | None:
    if v == "":
        return None
    if kind == "text" and width and len(v) > width:
        return f"longer than {width} characters"
    if kind == "date":
        try:
            date.fromisoformat(v)
        except ValueError:
            return "not a date in YYYY-MM-DD form"
    if kind == "int" and not re.fullmatch(r"-?\d+", v):
        return "not a whole number (amounts are in paise)"
    if kind == "dec" and not re.fullmatch(r"-?\d+(\.\d+)?", v):
        return "not a number"
    if kind == "bool" and v.upper() not in ("TRUE", "FALSE"):
        return "not TRUE or FALSE"
    return None


def validate_extract(zip_bytes: bytes) -> tuple[dict[str, list[list[str]]], list[str], dict[str, int]]:
    """Return (rows per table in table column order, errors, row counts). Rows exclude the header."""
    errors: list[str] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return {}, ["The file is not a ZIP archive. Put one CSV per table in a ZIP and upload that."], {}
    files = {Path(n).name.lower(): n for n in zf.namelist() if n.lower().endswith(".csv") and not Path(n).name.startswith(".")}
    types = raw_types()
    tables: dict[str, list[list[str]]] = {}
    counts: dict[str, int] = {}

    def err(msg: str) -> bool:
        errors.append(msg)
        return len(errors) < MAX_ERRORS

    for table in RAW_TABLES:
        cols = COLUMNS[table]
        name = f"{table}.csv"
        if name not in files:
            if table not in OPTIONAL:
                err(f"{name} is missing.")
            tables[table], counts[table] = [], 0
            continue
        text = zf.read(files[name]).decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = [h.strip().lower() for h in next(reader, [])]
        missing = [c for c in cols if c not in header]
        if missing:
            err(f"{name}: missing column{'s' if len(missing) > 1 else ''} {', '.join(missing)}.")
            continue
        idx = [header.index(c) for c in cols]
        out: list[list[str]] = []
        for line_no, rec in enumerate(reader, start=2):
            if not rec or all(not x.strip() for x in rec):
                continue
            if len(rec) < len(header):
                if not err(f"{name} line {line_no}: {len(rec)} values, expected {len(header)}."):
                    break
                continue
            row = [rec[i].strip() for i in idx]
            for c, v in zip(cols, row):
                kind, width = types[table][c]
                problem = _check_value(kind, width, v)
                if problem and not err(f"{name} line {line_no}, {c} = '{v[:30]}': {problem}."):
                    break
            out.append(row)
            if len(errors) >= MAX_ERRORS:
                break
        tables[table], counts[table] = out, len(out)

    if not errors:
        loans = {r[0] for r in tables["loans"]}
        if not loans:
            err("loans.csv has no rows.")
        dup = len(loans) != len(tables["loans"])
        if dup:
            err("loans.csv has the same loan_id more than once.")
        branches = {r[0] for r in tables["branches"]}
        for r in tables["loans"]:
            if r[2] not in branches and not err(f"loans.csv: loan {r[0]} refers to branch {r[2]}, which is not in branches.csv."):
                break
        for table in RAW_TABLES:
            if table in ("loans", "branches", "borrowers") or "loan_id" not in COLUMNS[table]:
                continue
            i = COLUMNS[table].index("loan_id")
            unknown = sorted({r[i] for r in tables[table]} - loans)
            if unknown and not err(f"{table}.csv refers to {len(unknown)} loan(s) not in loans.csv, e.g. {', '.join(unknown[:3])}."):
                break
        if not tables["interest_postings"]:
            err("interest_postings.csv has no rows: there is nothing to audit.")
    return tables, errors, counts


def write_book(tables: dict[str, list[list[str]]], out_root: Path) -> Path:
    """Write a validated extract as a dataset folder the loader understands. Truth tables stay empty."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dataset_id = f"upload_{stamp}"
    out = out_root / dataset_id
    (out / "raw").mkdir(parents=True)
    (out / "truth").mkdir()
    for table in RAW_TABLES:
        with open(out / "raw" / f"{table}.csv", "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(COLUMNS[table])
            w.writerows(tables[table])
    for table in TRUTH_TABLES:
        with open(out / "truth" / f"{table}.csv", "w", newline="") as fh:
            csv.writer(fh, lineterminator="\n").writerow(COLUMNS[table])
    ends = [r[COLUMNS["interest_postings"].index("period_end")] for r in tables["interest_postings"]]
    manifest = dict(dataset_id=dataset_id, seed=0, loans=len(tables["loans"]), bulk_loans=len(tables["loans"]),
                    as_of=max(ends), defect_scale=0, generator_version="upload",
                    row_counts={t: len(tables[t]) for t in RAW_TABLES}, generated_at=stamp)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out


TEMPLATE_README = """Sahi Byaaj loan-book extract

One CSV per table, first line = column names (any order). Zip the CSVs together and upload the ZIP on the
Data page, or place them in data/<name>/raw/ and run `make load` then `make audit`.

Formats
- Money: whole paise (Rs 12,00,000 = 120000000). Rates: percent a year (8.75).
- Dates: YYYY-MM-DD. Booleans: TRUE or FALSE. Empty cell = not known.
- day_count_basis: ACT_365 or 30E_360. payment_mode: CHEQUE, DD, NEFT, RTGS, IMPS.
- evidence_source: LMS_DISB, CHEQUE_DATE, HANDOVER_ACK, RAIL_CREDIT.
- receipts.kind: EMI, PRE_EMI, ADVANCE_EMI, CLOSURE. demands.kind: EMI, PRE_EMI.
- interest_postings: one row per posting; a reversal has a negative amount and reverses_posting_id set.

Optional files: demands.csv, kfs_disbursal_schedule.csv. Every other file is required.
The example rows are three synthetic loans (Meena, Raghav, Asha). This ZIP can be uploaded as it is.
Full definitions: docs/CONTRACT.md in the repository.
"""


def templates_zip() -> bytes:
    """Blank-format templates with the three synthetic demo loans as example rows."""
    with tempfile.TemporaryDirectory() as tmp:
        book = generate(seed=1, loans=0, as_of=date(2026, 10, 1), defect_scale=0.0, out_root=Path(tmp))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("README.txt", TEMPLATE_README)
            for table in RAW_TABLES:
                z.write(book / "raw" / f"{table}.csv", f"sahi_byaaj_extract/{table}.csv")
        return buf.getvalue()


def _csv(data: list[dict]) -> str:
    buf = io.StringIO()
    if data:
        w = csv.DictWriter(buf, fieldnames=list(data[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(data)
    return buf.getvalue()


def inspection_pack(rid: str, rows, out_schema: str, raw_schema: str, policy_schema: str | None = None) -> bytes:
    """Everything an inspector needs for one run, copied out of Exasol as it stands. `rows(sql, params)` reads."""
    p = {"r": rid}
    run = rows(f"SELECT * FROM {out_schema}.audit_runs WHERE run_id = {{r}}", p)[0]
    summary = rows(f"SELECT * FROM {out_schema}.run_summary WHERE run_id = {{r}}", p)[0]
    ledger = rows(f"SELECT l.*, b.display_name FROM {out_schema}.refund_ledger l "
                  f"JOIN {raw_schema}.borrowers b ON b.borrower_id = l.borrower_id WHERE l.run_id = {{r}} "
                  f"ORDER BY l.loan_id, l.practice_code", p)
    findings = rows(f"SELECT * FROM {out_schema}.findings WHERE run_id = {{r}} ORDER BY loan_id, period_start, practice_code", p)
    gaps = rows(f"SELECT * FROM {out_schema}.evidence_gaps WHERE run_id = {{r}} ORDER BY branch_id, loan_id, tranche_no", p)
    timings = rows(f"SELECT * FROM {out_schema}.step_timings WHERE run_id = {{r}} ORDER BY started_at", p)
    lineage = rows(f"SELECT * FROM {out_schema}.lineage ORDER BY sql_step_id")
    review_files: dict[str, list[dict]] = {}
    if policy_schema:
        scope = f"WHERE dataset_id = (SELECT dataset_id FROM {out_schema}.audit_runs WHERE run_id = {{r}})"
        review_files = {
            "review_decisions.csv": rows(f"SELECT decision_seq, run_id, item_kind, loan_id, practice_code, period_start, figure_paise, "
                                         f"review_decision, decided_by, reason, decided_at FROM {policy_schema}.review_decisions "
                                         f"{scope} ORDER BY decision_seq", p),
            "policy_changes.csv": rows(f"SELECT setting_key, old_value, new_value, changed_by, reason, changed_at "
                                       f"FROM {policy_schema}.policy_changes ORDER BY change_seq"),
            "release_batches.csv": rows(f"SELECT batch_id, run_id, released_by, batch_note, released_at, letter_count, total_paise "
                                        f"FROM {policy_schema}.release_batches {scope} ORDER BY released_at", p),
            "letter_releases.csv": rows(f"SELECT batch_id, run_id, loan_id, letter_lang, excess_paise, approved_by, released_by, "
                                        f"released_at, text_sha256 FROM {policy_schema}.letter_releases {scope} ORDER BY release_seq", p),
        }

    def rupees(paise) -> str:
        s = str(paise)
        neg = s.startswith("-")
        s = s.lstrip("-").rjust(3, "0")
        whole, frac = s[:-2], s[-2:]
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        return f"{'-' if neg else ''}Rs {','.join(groups + [tail]) if groups else tail}.{frac}"

    review_note = ""
    if policy_schema:
        states = rows(f"SELECT review_state, COUNT(*) AS row_count, SUM(excess_paise) AS excess_paise "
                      f"FROM ({ledger_review_sql(out_schema, policy_schema)}) x GROUP BY review_state ORDER BY 1", p)
        review_note = "\n## Human review of this ledger (names are self-declared)\n\n" + "".join(
            f"- {s['review_state']}: {s['row_count']} rows, {rupees(s['excess_paise'])}\n" for s in states)

    note = f"""# Inspection pack

Run {rid}, dataset {run['dataset_id']}, label "{run['label']}"
Started {run['started_at']} UTC, {run['duration_ms']} ms inside Exasol, code version {run['git_sha']}

## Totals for this run (copied from SAHI_OUT.run_summary)

- Refund owed: {rupees(summary['refund_paise'])} to {summary['refund_loans']} loans ({summary['refund_findings']} findings)
- Permitted, not refunded: {rupees(summary['permitted_paise'])} on {summary['permitted_loans']} loans
- Evidence gaps (not in the total): {summary['gap_tranches']} tranches on {summary['gap_loans']} loans
- Unexplained postings (not in the total): {summary['unexplained_periods']} billing months on {summary['unexplained_loans']} loans
- Loans audited: {summary['loans_audited']}; billing months recomputed: {summary['periods_audited']}
{review_note}
## Files

- refund_ledger.csv: one row per loan and RBI practice; finding_ids link to findings.csv
- findings.csv: every billing month that differs from fair interest, with status, reason and evidence ids
- evidence_gaps.csv: tranches that could not be decided, with the query drafted to each branch
- policy_snapshot.json: the interpretation settings and date-precedence rules this run used
- step_timings.csv and lineage.csv: each SQL step, its time, its file and the SHA-256 of that file
- review_decisions.csv: every approve, hold or clear, with who, why and the figure they saw; re-reviews add rows
- policy_changes.csv: every change to a policy setting, with who and why
- release_batches.csv and letter_releases.csv: letters handed over for dispatch; this tool does not send them
- sql/: the SQL files as they are in this copy of the code; compare their SHA-256 with lineage.csv

Every figure was computed by SQL inside Exasol. This pack is a copy; nothing in it was recalculated.
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        base = f"inspection_pack_{rid[:8]}/"
        z.writestr(base + "README.md", note)
        z.writestr(base + "refund_ledger.csv", _csv(ledger))
        z.writestr(base + "findings.csv", _csv(findings))
        z.writestr(base + "evidence_gaps.csv", _csv(gaps))
        z.writestr(base + "step_timings.csv", _csv(timings))
        z.writestr(base + "lineage.csv", _csv(lineage))
        z.writestr(base + "run_summary.csv", _csv([summary]))
        for name, data in review_files.items():
            z.writestr(base + name, _csv(data))
        try:
            z.writestr(base + "policy_snapshot.json", json.dumps(json.loads(run["policy_snapshot"]), indent=2))
        except (TypeError, ValueError):
            z.writestr(base + "policy_snapshot.json", str(run["policy_snapshot"]))
        for f in sorted(SQL_DIR.glob("*.sql")):
            z.write(f, base + "sql/" + f.name)
    return buf.getvalue()

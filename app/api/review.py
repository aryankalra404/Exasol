"""Human review and letter release.

People decide; Exasol keeps the figures. A decision records who, why and the figure they saw, and that figure is
copied from the result tables by the INSERT itself, never sent by the browser. If a later run changes the figure,
the old decision no longer counts and the row needs a fresh review. Releasing hands approved letters to the lender;
this tool never contacts a borrower, so the record says "released", not "sent".
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from datetime import date

from letters.letter import check, inr, render

LEDGER_DECISIONS = ("APPROVED", "HOLD")
QUEUE_DECISIONS = ("CLEARED", "HOLD")
LETTER_LANGS = ("en", "hi", "ta")


def clean_actor(name: str, reason: str) -> tuple[str, str]:
    """Both are required on every human action. Raises ValueError with a message fit to show."""
    name, reason = " ".join(name.split()), " ".join(reason.split())
    if not name:
        raise ValueError("Enter your name. Every review action records who took it.")
    if not reason:
        raise ValueError("Enter a reason. Every review action records why it was taken.")
    if len(name) > 100:
        raise ValueError("Name is too long (100 characters at most).")
    if len(reason) > 500:
        raise ValueError("Reason is too long (500 characters at most).")
    return name, reason


def clean_evidence_date(event_date: str, as_of: str) -> str:
    """A real calendar date, not after the book's as-of date. Raises ValueError with a message fit to show."""
    try:
        when = date.fromisoformat(event_date.strip())
    except ValueError:
        raise ValueError("Enter the date from the branch's reply.") from None
    if when > date.fromisoformat(str(as_of)):
        raise ValueError(f"That date is after this book's as-of date, {as_of}.")
    return when.isoformat()


def latest_decisions_sql(out: str, pol: str, kind: str) -> str:
    """The most recent decision per item for the dataset of run {r}. Earlier decisions stay in the log."""
    return f"""SELECT loan_id, practice_code, period_start, figure_paise, review_decision, decided_by, reason, decided_at,
                      ROW_NUMBER() OVER (PARTITION BY loan_id, practice_code, period_start ORDER BY decision_seq DESC) AS rn
               FROM {pol}.review_decisions
               WHERE item_kind = '{kind}' AND dataset_id = (SELECT dataset_id FROM {out}.audit_runs WHERE run_id = {{r}})"""


def state_case(figure_col: str) -> str:
    return (f"CASE WHEN d.review_decision IS NULL THEN 'UNREVIEWED' WHEN d.figure_paise <> {figure_col} THEN 'STALE' "
            f"ELSE d.review_decision END")


def ledger_review_sql(out: str, pol: str) -> str:
    """Every ledger row of run {r} with its review state."""
    return f"""SELECT l.loan_id, l.practice_code, l.excess_paise, {state_case('l.excess_paise')} AS review_state,
                      d.figure_paise AS reviewed_paise, d.decided_by, d.reason AS review_reason, d.decided_at
               FROM {out}.refund_ledger l
               LEFT JOIN ({latest_decisions_sql(out, pol, 'LEDGER')}) d
                 ON d.loan_id = l.loan_id AND d.practice_code = l.practice_code AND d.rn = 1
               WHERE l.run_id = {{r}}"""


def latest_releases_sql(out: str, pol: str) -> str:
    return f"""SELECT loan_id, batch_id, excess_paise, released_at, released_by,
                      ROW_NUMBER() OVER (PARTITION BY loan_id ORDER BY release_seq DESC) AS rn
               FROM {pol}.letter_releases
               WHERE dataset_id = (SELECT dataset_id FROM {out}.audit_runs WHERE run_id = {{r}})"""


def loan_states_sql(out: str, pol: str) -> str:
    """One row per refundable loan of run {r}: DRAFT until every row is approved at its current figure, then
    APPROVED, then RELEASED once a letter for this exact total has been released."""
    return f"""SELECT s.loan_id, s.total_paise, s.pending_rows, s.approved_by, rel.excess_paise AS released_paise,
                      rel.released_at, rel.released_by, rel.batch_id,
                      CASE WHEN rel.excess_paise = s.total_paise THEN 'RELEASED'
                           WHEN s.pending_rows = 0 THEN 'APPROVED' ELSE 'DRAFT' END AS letter_state
               FROM (SELECT loan_id, SUM(excess_paise) AS total_paise,
                            SUM(CASE WHEN review_state = 'APPROVED' THEN 0 ELSE 1 END) AS pending_rows,
                            GROUP_CONCAT(DISTINCT decided_by ORDER BY decided_by SEPARATOR ', ') AS approved_by
                     FROM ({ledger_review_sql(out, pol)}) lr GROUP BY loan_id) s
               LEFT JOIN ({latest_releases_sql(out, pol)}) rel ON rel.loan_id = s.loan_id AND rel.rn = 1"""


def changed_releases_sql(out: str, pol: str) -> str:
    """Letters already released whose figure no longer matches run {r}, including loans now owed nothing."""
    return f"""SELECT rel.loan_id, rel.batch_id, rel.released_at, rel.excess_paise AS released_paise,
                      COALESCE(s.total_paise, 0) AS current_paise
               FROM ({latest_releases_sql(out, pol)}) rel
               LEFT JOIN (SELECT loan_id, SUM(excess_paise) AS total_paise FROM {out}.refund_ledger
                          WHERE run_id = {{r}} GROUP BY loan_id) s ON s.loan_id = rel.loan_id
               WHERE rel.rn = 1 AND COALESCE(s.total_paise, 0) <> rel.excess_paise
               ORDER BY rel.loan_id"""


def _with_dates(figs: list[dict]) -> list[dict]:
    return [{**f, "first_period": date.fromisoformat(str(f["first_period"])),
             "last_period": date.fromisoformat(str(f["last_period"]))} for f in figs]


def _by_loan(figs: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in figs:
        out.setdefault(f["loan_id"], []).append(f)
    return out


def build_letters(figs: list[dict], recheck: list[dict], lang: str = "") -> tuple[list[dict], list[str]]:
    """Render and check each loan's letter. `recheck` must be a separate read of the ledger, as in the letter
    screen. Returns (letters, loan ids that failed the checker)."""
    fresh = _by_loan(recheck)
    letters, failed = [], []
    for loan_id, loan_figs in sorted(_by_loan(_with_dates(figs)).items()):
        total = next(f for f in loan_figs if f["line_key"] == "TOTAL")
        lt = render(loan_figs, lang or total["preferred_language"])
        if loan_id not in fresh or not check(lt, fresh[loan_id])["ok"]:
            failed.append(loan_id)
            continue
        letters.append({"loan_id": loan_id, "display_name": total["display_name"], "letter_lang": lt.lang,
                        "excess_paise": total["excess_paise"], "letter_text": lt.text,
                        "text_sha256": hashlib.sha256(lt.text.encode()).hexdigest()})
    return letters, failed


def release_zip(batch: dict, letters: list[dict]) -> bytes:
    """Letters exactly as stored at release, a manifest, and a note saying what this batch is and is not."""
    base = f"letter_release_{batch['batch_id'][:8]}/"
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["file", "loan_id", "borrower", "language", "refund", "excess_paise", "approved_by", "released_by",
                "released_at", "sha256"])
    with io.BytesIO() as raw, zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as z:
        for r in letters:
            name = f"letters/{re.sub(r'[^A-Za-z0-9_-]', '_', r['loan_id'])}_{r['letter_lang']}.txt"
            z.writestr(base + name, r["letter_text"])
            w.writerow([name, r["loan_id"], r["display_name"], r["letter_lang"], inr(int(r["excess_paise"])),
                        r["excess_paise"], r["approved_by"], r["released_by"], r["released_at"], r["text_sha256"]])
        z.writestr(base + "manifest.csv", buf.getvalue())
        z.writestr(base + "README.txt", f"""Letter release batch {batch['batch_id']}

Released by {batch['released_by']} at {batch['released_at']} UTC
Run {batch['run_id']}, dataset {batch['dataset_id']}
Letters: {batch['letter_count']}. Total refund: {inr(int(batch['total_paise']))}
Note: {batch['batch_note']}

These letters were approved and handed over for dispatch through the lender's own channels. This tool does not
send anything, so being in this batch does not mean a borrower has received a letter.

manifest.csv lists each letter with who approved it, who released it and the SHA-256 of its text.
""")
        z.close()
        return raw.getvalue()

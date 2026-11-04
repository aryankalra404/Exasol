# Blind red team

Goal: test the audit on loans its authors did not design. All loans are synthetic and made up by you. Use obviously fake names.

Expect about 2 to 3 hours for 10 short loans. Finding a problem is a good result, not a failure.

## Rules

**You may read**

- RBI text on charging of interest
- `docs/DOMAIN.md`, for the interest rules the tool claims to follow
- `README.txt` in the template (Data page), for the file formats

**Do not read until your answers are written**

- `generator/`, `sql/`, `oracle/`, `tests/`
- `docs/STATUS.md`, `docs/LIMITS.md`
- Any audit result for your loans

**The one rule that matters:** write `expected.csv` by hand before the first run. Do not change an answer after seeing a result. If you find your own mistake later, add a note in `why` and keep the original in the report.

## Steps

1. `make red-team-template` writes the CSVs to `tests/fixtures/red_team/`
2. Delete the three example loans (`LDM...`) from every file
3. Add about 10 loans of 3 to 6 months. Keep them short, as you work each month out by hand
4. For each loan, write what the lender's system posted in `interest_postings.csv`
5. For each month that matters, write your answer in `expected.csv`, and check it by hand or in a spreadsheet
6. `make red-team`, then read the result. Results go to `eval/reports/red_team.json`

The run uses separate `RT_*` schemas with default policy. It does not touch the demo book. It keeps nothing between runs.

## expected.csv

| Column | Meaning |
|---|---|
| `loan_id` | Your loan |
| `period_start` | First of the month, `YYYY-MM-DD` |
| `expected_status` | `FAIR`, `REFUND`, `PERMITTED`, `AMBIGUOUS`, `EVIDENCE_GAP`, `UNEXPLAINED` or `UNDERCHARGE` |
| `expected_fair_paise` | Interest that should have been charged. Blank to skip the check |
| `expected_excess_paise` | Posted minus fair. Blank to skip the check |
| `why` | One line on what this case tests, with the RBI wording it relies on |

## What to try

Aim for cases that might break it, not cases that show it working. Some areas to start from:

- Dates that disagree, or arrive in an unusual order
- Several tranches or repayments close together, or in one month
- Rate changes
- Month and year edges
- Something that looks unfair but was disclosed, so no refund is due
- Records that are missing, duplicated, reversed or entered by hand
- A posting that follows no rule you can name

## After the run

Every disagreement goes in the table, including the ones that look bad. For each, decide who was wrong, with a second person where possible.

| Outcome | What to do |
|---|---|
| The audit is wrong | Fix the SQL and the oracle, add a test, re-run |
| The expected answer is wrong | Keep it in the table, with the reason |
| `DOMAIN.md` is unclear | Fix the doc and record the choice in `DECISIONS.md` |
| The tool does not cover the case by design | Add it to `LIMITS.md` |

Then record the counts in `docs/STATUS.md` "Measured results".

## Results

| Builder | Date | Loans | Months checked | Agree | Audit wrong | Answer wrong | Not covered |
|---|---|---|---|---|---|---|---|
| Machine-written, given only `DOMAIN.md`, the file formats and this brief, in a folder with no code. Not a person | 4 Nov 2026 | 12 | 60 | First run 59. After the fix 60 | 1 | 0 | 0 |
| A person who has not read the code | | | | | | | |

Answers were frozen before the first run and never edited: `tests/fixtures/red_team/expected.csv`, SHA-256 starting `002b41b75410e939`.

**What the first run found:** a posting in a month before the loan's sanction month was never audited (RT003, Dec 2023, ₹93.15). It appeared nowhere, and no check noticed. The SQL and the oracle both started each loan at its sanction month, so they agreed with each other and neither could catch it. This is the risk of one author writing both. Fixed in both, separately, and uploads now refuse postings that do not start on the 1st. No demo figure changed: the demo book has no such posting.

**What this does not prove:** the rules still come from our own `DOMAIN.md`, so a mistaken rule would pass. A person's review of the RBI text is still needed.

Also reported: 54 months flagged Undercharge that were not in `expected.csv`, all after a test loan stopped posting while the book ran on. `DOMAIN.md` treats a missing posting as an undercharge, and none is refunded, so this is expected. A real extract with missing months would show the same.

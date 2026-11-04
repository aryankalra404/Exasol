# Why Exasol

What Exasol Personal does in Sahi Byaaj, step by step, and what deliberately stays outside it. Judges: every refund figure in the app is produced by the SQL files below.

## Step map

Rows out are from the 10,003-loan demo book (seed 42), run on 30 Oct 2026; see `STATUS.md` "Measured results".

| Step | What it does | SQL file | Exasol features used |
|---|---|---|---|
| Load | Create schemas, import synthetic extracts | `sql/01_raw_schema.sql`, `scripts/load.py` | `IMPORT ... FROM CSV` via pyexasol |
| Policy seed | Settings, precedence, practices, 33 conventions (as a cross join of four value lists) | `sql/05_policy_and_out_schema.sql` | `VALUES` tables, `CROSS JOIN`, idempotent seeding |
| Entered evidence | A date from a branch reply joins the evidence that S20 resolves; the re-run decides the result. No amount is entered | `sql/06_review_schema.sql`, `sql/20_money_in_hand.sql` | `UNION ALL` into the same set-based resolution |
| Review log | Tables for human decisions, policy changes and released letters; review states and approved totals are computed by SQL from them. Not an audit step: the pipeline never reads these | `sql/06_review_schema.sql`, `app/api/review.py` | `IDENTITY` columns, window functions, `INSERT ... SELECT` so figures come from result tables |
| S10 Run setup | Snapshot policy, find the audit window from the data, months, rate spans, loan facts | `sql/10_run_setup.sql` | `CONNECT BY` number generator, `LEAD`, `ROW_NUMBER` |
| S20 Money-in-hand | Resolve the real disbursement date per tranche from conflicting evidence using the precedence table; flag conflicts and gaps | `sql/20_money_in_hand.sql` | window functions over evidence, `GROUP_CONCAT` |
| S30 Balance events | Fair balance events; each candidate convention stored only as its difference from fair | `sql/30_balance_events.sql` | set-based per-convention events for every loan at once |
| S40 Intervals | Constant-balance, constant-rate intervals clipped to billing months, with exact integer numerators | `sql/40_balance_intervals.sql` | running `SUM ... OVER`, `LEAD`, range joins, `DECIMAL(36,0)` |
| S50 Period interest | Fair interest per month, rounded half up once; net postings after reversals | `sql/50_period_interest.sql` | exact `DIV` rounding on integers |
| S60 Candidates | Every differing month recomputed under all candidate conventions side by side | `sql/60_candidate_conventions.sql` | one join, all conventions at once |
| S70 Fingerprint + permitted check | Which convention reproduces each posting to the paisa; loan-history tie-break; KFS commitment fee permitted by policy | `sql/70_fingerprint.sql` | `DENSE_RANK`, `REGEXP_SUBSTR` |
| S80 Findings | Status per month, excess split across practices so the parts sum exactly, evidence ids, step id | `sql/80_findings.sql` | telescoping attribution in one statement |
| S90 Ledger | Refund ledger, gap queue with drafted queries, rollups, root causes, cohorts, letter figures, interval proof, run summary | `sql/90_ledger_and_rollups.sql` | `GROUPING SETS`, string building in SQL |
| Lineage | Step id, file, SHA-256 of each SQL file; per-step timings; policy snapshot per run | `scripts/audit.py` writes `SAHI_OUT.lineage`, `step_timings`, `audit_runs` | `MERGE` |
| Ask the book | Latest-run views and a read-only user for Exasol's MCP server | `sql/ask/ask_views.sql`, `scripts/ask_setup.py` | views with owner rights, `GRANT SELECT ON SCHEMA`, `exasol-mcp-server` |

The runner (`scripts/audit.py`) only orders the files and records timings. It does no arithmetic.

## Measured

See `STATUS.md` "Measured results" for every figure, with dataset, hardware and date.

Headline: the full audit of a 500,003-loan book (11.7M interest postings, 11.6M billing periods recomputed under 33 conventions, 56.5M difference intervals) runs inside Exasol Personal in 479.0 s on a MacBook Air M4 with a 2 vCPU / 12 GB VM, and agrees with the independent oracle to the paisa on a random 3,003-loan sample. `make scale LOANS=500000` reproduces it; `eval/reports/scale_s7_n500000.json` has every step

## Why this shape suits Exasol

- **No row per day.** A loan's balance changes a few dozen times; billing months and rate changes split those into intervals. That is ~42 fair intervals per loan instead of ~1,000 day rows
- **All 33 conventions at once, cheaply.** Interest is linear in the balance, so a convention is stored as its difference from the fair path (often two rows: +amount on the cheque date, -amount on the handover date). Exact candidate figures come from fair numerator + difference numerator
- **Exact by construction.** Numerators are integers (`balance * rate_micro * days`); one `DIV` per month does the rounding. The independent oracle reproduces every month to the paisa
- **Re-runnable.** Every run gets an id, a policy snapshot and its own result rows, so policy changes and loan-system configuration changes can be diffed run against run

## What stays outside Exasol, and why

| Piece | Where | Why |
|---|---|---|
| Synthetic data generation | Python | Test fixture production, not analysis |
| Independent oracle | Python | Must not share code with the SQL it checks |
| Letter wording | Templates in `letters/letter.py` | Text only; every number is substituted from `SAHI_OUT.letter_figures` and checked against a second read of it |
| UI | React + Vite static build served by FastAPI | Presentation only; formats paise as rupees with string operations |

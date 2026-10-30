# Why Exasol

What Exasol Personal does in Sahi Byaaj, step by step, and what deliberately stays outside it. Judges: every refund figure in the app is produced by the SQL files below.

## Step map

Fill in as files land. One row per pipeline step.

| Step | What it does | SQL file | Exasol features used | Rows out (measured) |
|---|---|---|---|---|
| Load | Import synthetic extracts | `scripts/load` | `IMPORT` | |
| Policy seed | Precedence, settings, practices, 33 conventions | | | |
| Money-in-hand | Resolve the real disbursement date per tranche, flag conflicts and gaps | | window functions over evidence | |
| Balance events | Disbursements, repayments, advance EMIs, rate resets under each convention | | | |
| Intervals | Constant-balance, constant-rate intervals | | `LEAD`/`LAG` | |
| Period interest | Fair and candidate interest per billing period, exact decimals | | `DECIMAL(36,12)` | |
| Fingerprint | Which convention reproduces each posting to the paisa | | set-based join across 33 candidates | |
| Permitted check | KFS and policy-driven exceptions | | | |
| Findings | Status, attribution by practice, evidence ids | | | |
| Ledger and rollups | Refund ledger, gaps, rollups | | | |
| Lineage | Step ids and statement hashes | | | |

## Measured

From `STATUS.md` "Measured results". Hardware, dataset size, end-to-end runtime, per-step timings. Nothing here that we did not run.

## What stays outside Exasol, and why

| Piece | Where | Why |
|---|---|---|
| Synthetic data generation | Python | Test fixture production, not analysis |
| Independent oracle | Python | Must not share code with the SQL it checks |
| Letter wording | Templates (+ optional LLM phrasing) | Text only; every number is substituted from SAHI_OUT and checked |
| UI | Next.js | Presentation only |

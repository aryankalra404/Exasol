# Ask the book

An audit committee member asks a plain question, an assistant answers it with SQL against the audit's result
views, and shows the SQL it ran. Built on Exasol's own MCP server (`exasol-mcp-server`).

All figures below are synthetic, from the demo book (`s42_n10000`), recorded by `eval/ask_smoke.py` on 31 Oct 2026.

## What the assistant can and cannot touch

| | |
|---|---|
| Logs in as | `ASK_READER`, a dedicated database user |
| Can read | the `SAHI_ASK` views only: each pinned to the latest completed audit run, no borrower names |
| Cannot read | `SAHI_TRUTH`, `SAHI_RAW` evidence and borrower names, raw `SAHI_OUT` (refused by Exasol: `insufficient privileges`) |
| Cannot write | anything: the user has only `CREATE SESSION` plus `SELECT` on `SAHI_ASK`; the server's write tool is off |
| Decides | which SQL to run. Exasol computes every number; the refund ledger stays the record |

The limit is enforced by Exasol privileges, not by the prompt. `make ask-smoke` proves it each time: a read of
`SAHI_TRUTH` through the MCP server comes back `insufficient privileges`. Exasol stores names in uppercase, so a client that quotes `"SAHI_TRUTH"."expected"` gets "not found" instead; use `SAHI_TRUTH.EXPECTED` to show the refusal.

## Set up

```bash
make ask-setup     # SAHI_ASK views + ASK_READER user; password generated into .env (gitignored)
make ask-smoke     # starts the MCP server, lists its tools, runs the examples below, checks the boundary
```

**Connect an MCP client.** The repo's `.mcp.json` registers the server as `sahi-byaaj-ask` for clients that
read project MCP config; approve it when the client asks. For any other client, add a stdio server:

```json
{ "command": "/path/to/sahi-byaaj/.venv/bin/python", "args": ["-m", "scripts.ask_mcp"], "cwd": "/path/to/sahi-byaaj" }
```

`scripts/ask_mcp.py` reads the connection from `.env`, so no password sits in a client config file. Re-run
`make ask-setup` after recreating the database.

## Examples (as run)

| Question | SQL (abridged) | Answer |
|---|---|---|
| How much do we owe borrowers in total, and how many loans? | `SELECT refund_rupees, refund_loans, gap_loans, unexplained_loans FROM SAHI_ASK.run_summary` | ₹8,83,23,995.69 to 3,063 loans; 232 loans wait on evidence, 81 unexplained |
| How much do we owe borrowers disbursed by cheque in 2024? | `SUM(excess_paise)` from `refund_ledger` for loans with a `CHEQUE` tranche resolved in 2024 (`money_in_hand`) | ₹2,23,61,602.76, 555 loans |
| Which RBI practice accounts for the most refund? | `refund_ledger` grouped by `practice_code`, joined to `practices` | P5 EMI on sanctioned amount ₹5,50,16,055.06 (303 loans), then P1 sanction date ₹1,55,58,505.21 (1,203 loans) |
| At BR001, are loans sanctioned after the July 2024 fix still overcharged? | `cohorts` for BR001 from 2024-Q3, split by sanction quarter | Before the fix: 38 loan-quarters, ₹92,754.07. From Jul 2024: 0, ₹0 |
| How much posted interest is waiting on evidence? | `COUNT(*)`, `SUM(posted_paise_at_stake)` from `evidence_gaps` | 234 tranches, ₹54,86,201.28 of posted interest at stake |

Full SQL and raw results: `eval/ask_smoke.py`, `eval/reports/ask_smoke.json`.

## Views

`latest_run`, `run_summary`, `refund_ledger`, `findings`, `money_in_hand`, `evidence_gaps`, `rollups`,
`root_causes`, `cohorts`, `loans` (no names), `practices`, `policy_settings`. Definitions and comments:
`sql/ask/ask_views.sql`. The only arithmetic in them is paise to rupees.

# CLAUDE.md

Instructions for any AI coding agent (and human) working in this repo. Read this first, every session.

## What we are building

**Sahi Byaaj** ("correct interest"): a full-book interest audit for Indian lenders, built on Exasol Personal for ExaThon India 2026, Track 01 (Money, Risk & Regulation).

For every loan and every tranche it finds the day the borrower's money actually reached them, recomputes the interest they should have paid from that day, names the convention the lender's system actually applied, separates unfair practice from disclosed permitted terms, and produces a paisa-exact refund ledger with evidence behind every rupee.

- Submission deadline: **Sat 31 Oct 2026, 11:59 pm IST**
- Top 5 announced: Wed 4 Nov 2026. Live demo day: Fri 6 Nov 2026
- Full context: `docs/PROBLEM.md`. Scope: `docs/SPEC.md`. Interest rules: `docs/DOMAIN.md`

## Start of every session

1. `git pull --rebase`
2. Read `docs/STATUS.md` (what is done, what is claimed, what is next)
3. Read `docs/CONTRACT.md` if you touch data, SQL, the app or the generator
4. Read the doc for the area you are touching (table below)
5. Claim your task in `docs/STATUS.md`, commit and push that claim before starting real work

## Non-negotiables

Breaking any of these loses points or credibility. Do not trade them for speed.

- **Every number is computed by SQL inside Exasol.** The app, letters and AI only read result tables. No interest, refund or rollup math in Python/JS on the product path
- **The Python oracle is the only exception**, and it is test code. It must never import from `sql/` or share logic with it. It exists to disagree with the SQL
- **Money is integer paise** (`DECIMAL(18,0)`) at rest. Intermediates use `DECIMAL(36,12)`. Never floats, anywhere, including Python (`Decimal` only) and JSON (send paise as integers or strings)
- **Rounding:** half up to the paisa, once per posting period. See `docs/DOMAIN.md`
- **AI never decides a date, classifies a practice or produces an amount.** It may phrase text whose numbers are substituted from the ledger and verified by the checker
- **The audit pipeline never reads the truth schema** (`SAHI_TRUTH`). Only `tests/` and `eval/` may read it
- **Synthetic data only.** Obviously fake names and IDs. No employer data, nothing proprietary, no real people
- **No secrets in git.** Credentials live in `.env` (gitignored). `.env.example` holds placeholders
- **Measured numbers only.** Never write a runtime, row count, accuracy or prevalence figure we did not run and record. Never claim "first" or "only". Never state how many real borrowers are affected

## Keep docs in sync (part of "done")

A change is not finished until the matching doc is updated in the same commit or the one right after.

| If you change... | Update |
|---|---|
| Any table, column, type, enum or file layout shared between components | `docs/CONTRACT.md` (bump version + changelog line) |
| An interest rule, convention, precedence rule or rounding | `docs/DOMAIN.md` and the oracle |
| A pipeline step or SQL file | `docs/WHY_EXASOL.md` step map, `docs/ARCHITECTURE.md` if the flow changed |
| Scope (add, cut or defer a feature) | `docs/SPEC.md` and `docs/STATUS.md` |
| A non-obvious choice (tool, library, trade-off, interpretation) | New entry in `docs/DECISIONS.md` |
| Something we cannot do, assume, or got wrong | `docs/LIMITS.md` |
| Setup, commands, env vars | `README.md` and the Commands section below |
| Demo flow or demo data (Meena, Raghav, Asha) | `docs/DEMO.md` |
| Finishing or starting any task | `docs/STATUS.md` |
| A measured result (timing, oracle agreement, test counts) | `docs/STATUS.md` "Measured results", then README/WHY_EXASOL |

If you notice a doc is wrong or stale, fix it now. Do not leave it for later.

## Working with other contributors

The team size and number of parallel agents can change at any time (one, two, three or more). These rules make that safe.

- **`docs/CONTRACT.md` is the interface.** Components talk only through the tables and files it defines. Build against the contract, not against someone else's code
- **Changing the contract:** edit `CONTRACT.md`, bump the version, add a changelog line saying what changed and who it affects, list it under "Contract changes" in `STATUS.md`, then commit and push immediately, before the code that depends on it. Additive changes (new nullable column, new table) are fine to make alone. Breaking changes (rename, remove, retype, change meaning) need the affected task owners told in `STATUS.md`
- **Claim before you build.** Put your name or session label next to the task in `STATUS.md`. Do not start a task someone else has claimed. If a claim looks abandoned, note it in STATUS rather than silently taking over
- **Stay in your lane.** Edit files that belong to your task. If you must change another area, keep it minimal and mention it in the commit message
- **Pull often, push often.** `git pull --rebase` before starting and before every push. Small commits keep merges trivial
- **Working solo?** Same rules, just less coordination. Still update STATUS, the contract and the docs, because the next session (or a new teammate) starts cold

## Commits

- **Commit regularly.** Every working unit: a passing test, a finished SQL step, a screen that renders, a doc update. Do not sit on large uncommitted changes. Push after committing
- **Message: one line, plain, human.** Write it like a teammate would. Lowercase start is fine, no trailing period, under ~72 characters
  - Good: `resolve money-in-hand date per tranche with conflict flag`
  - Good: `fix off-by-one in pre-emi interval end`
  - Good: `update contract: add evidence_gaps.suggested_query`
  - Bad: `feat(sql): Implement comprehensive evidence resolution module.`
  - Bad: multi-paragraph bodies, bullet lists, emoji
- **No AI attribution of any kind.** No `Co-Authored-By` trailers, no "Generated with", no mention of Claude, AI or agents in commits, PRs, code comments or docs
- Never commit `.env`, data dumps, generated Parquet/CSV, `node_modules`, or anything over a few MB
- Never force-push `main`. Never rewrite pushed history
- Before committing code: run the relevant tests (see Commands). Do not commit a red build to `main` knowingly; if you must, say so in the message (`wip: ...`) and fix it next

## Definition of done

- Works end to end for its part, against the contract
- Tests added or updated and passing (oracle agreement for any interest logic)
- Docs updated per the sync table
- `STATUS.md` updated
- Committed and pushed

## Repo layout

```
CLAUDE.md            this file
README.md            overview, setup, usage (judges read this)
LICENSE              MIT
CONTRIBUTING.md      how to contribute
docs/
  PROBLEM.md         problem statement, users, evidence, sources
  SPEC.md            scope: in, stretch, out
  DOMAIN.md          interest rules, conventions, practices, rounding (source of truth)
  ARCHITECTURE.md    components and data flow
  CONTRACT.md        tables, columns, enums, files (the interface)
  STATUS.md          task board, claims, measured results
  DECISIONS.md       decision log
  WHY_EXASOL.md      pipeline step -> SQL file map, what stays outside Exasol and why
  LIMITS.md          limitations, assumptions, known gaps
  DEMO.md            3-min video script and live demo plan
  SUBMISSION.md      submission checklist
generator/           synthetic loan book (Python, fixed seeds)
sql/                 numbered pipeline steps, one step per file
oracle/              independent Python recompute (exact Decimal)
app/                 API + web UI (reads result tables only)
agent/               ask-the-book assistant via Exasol MCP (read-only)
letters/             borrower letter templates + number checker
tests/               unit, oracle agreement, fixtures, false positives
eval/                fingerprint accuracy, red team, scale runs
scripts/             setup, load, run, demo helpers
data/                generated data (gitignored)
```

Folders are created when first needed. Update this tree if you add a top-level folder.

## Conventions

**SQL (Exasol)**
- One pipeline step per file, numbered: `sql/20_money_in_hand.sql`
- Header comment in every file: step id, purpose, inputs, outputs
- Uppercase keywords, snake_case identifiers, explicit column lists (no `SELECT *` in pipeline steps)
- Every output row carries `run_id`. Every finding carries `sql_step_id` for lineage
- Set-based only. No day-by-day row explosion: use balance intervals
- Re-runnable: each step can be dropped and rebuilt from its inputs

**Python**
- 3.11+. Type hints. `Decimal` for all money and rates. `ruff` for lint/format
- Generator uses fixed seeds and is deterministic for a given seed and size
- `pyexasol` for DB access. Connection settings from `.env`

**Writing (docs, UI copy, letters, deck)**
- Concise. Bullets over prose. No em dashes
- Indian number formatting in UI and letters (₹12,00,000)
- All personas and figures are synthetic and labelled as such

## Commands

Fill these in as they come to exist. Keep them accurate.

```
# setup                     TBD (scripts/setup.sh)
# generate data             TBD
# load into Exasol          TBD
# run audit                 TBD
# run tests                 TBD
# run oracle agreement      TBD
# start app                 TBD
```

## Environment

- Exasol Personal runs locally (macOS Apple Silicon, single node). Connection in `.env` (see `.env.example`): `EXASOL_DSN`, `EXASOL_USER`, `EXASOL_PASSWORD`, plus one `EXASOL_SCHEMA_*` per schema
- Exasol Personal allows 20 connections. Use a small pool in the app
- Python UDFs locally need the script language container installed first (`exasol slc install python3`). Prefer plain SQL; UDFs only where justified (see `docs/DECISIONS.md`)

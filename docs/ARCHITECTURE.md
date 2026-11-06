# Architecture

## One line

Synthetic extracts go into Exasol; a numbered chain of SQL steps turns them into money-in-hand dates, fair and candidate interest, fingerprints, findings and a refund ledger; everything else (app, letters, assistant) only reads those result tables.

## Flow

```
generator/ (Python, fixed seed, simulated LMS posts interest under a hidden per-branch config)
   │  CSV per table + manifest
   ▼
scripts/load ──IMPORT──►  SAHI_RAW            SAHI_TRUTH (eval only)
                              │                      ▲
                              ▼                      │
                    sql/ pipeline in Exasol      eval/, tests/
                    (scripts/audit orders it)        │
                      10 run setup, windows          │
                      20 money-in-hand               │
                      30 balance events (fair + diffs per convention)
                      40 intervals, exact numerators │
                      50 fair interest, net postings │ compare
                      60 candidate conventions       │
                      70 fingerprint + permitted     │
                      80 findings + attribution      │
                      90 ledger, gaps, rollups,      │
                         root causes, cohorts, fix   │
                         coverage,                   │
                         letter figures, proof       │
                              │   (SAHI_WORK holds   │
                              ▼    intermediates)    │
                          SAHI_OUT  ─────────────────┘
                     │                 │
                     ▼                 ▼
               app/api (FastAPI)   letters/ (template + checker)
               app/web (React UI)

 SAHI_OUT ──views──► SAHI_ASK ──(ASK_READER, read-only)──► exasol-mcp-server ──► any MCP client

oracle/ (Python, day-by-day, independent) ──► eval/oracle_agreement compares with SAHI_OUT
```

The step map with files and Exasol features is in `WHY_EXASOL.md`.

## Components

| Component | Does | Reads | Writes |
|---|---|---|---|
| generator | Builds a synthetic loan book with hidden LMS config and planted defects | nothing | `data/<dataset_id>/raw`, `truth` |
| loader | Creates schemas, imports CSVs | `data/` | `SAHI_RAW`, `SAHI_TRUTH` |
| pipeline | All audit logic, including dates entered from branch replies (`SAHI_POLICY.evidence_additions`) | `SAHI_RAW`, `SAHI_POLICY` | `SAHI_OUT` |
| runner | Runs pipeline steps in order, records `audit_runs` and `step_timings`, snapshots policy | `sql/` | `SAHI_OUT.audit_runs` |
| oracle | Recomputes fair interest and fingerprints per loan in Python | CSVs in `data/` | test reports |
| app | API + web UI for the auditor; Data page loads a checked extract or the sample; inspection pack export; live view of Exasol during a run | `SAHI_OUT`, `SAHI_POLICY`, `SAHI_RAW`, Exasol system tables (live view) | `SAHI_POLICY.settings`, triggers runs, replaces `SAHI_RAW` through the loader on upload |
| review | People approve or hold refunds, clear unexplained months, release approved letters, and sign policy changes. Append-only; the pipeline never reads it | `SAHI_OUT` | `SAHI_POLICY.review_decisions`, `policy_changes`, `letter_releases`, `release_batches` |
| letters | Renders refund letters and checks every figure | `SAHI_OUT` | `letters/out/` |
| ask | Read-only views and MCP server for plain-language questions (`ASK.md`) | `SAHI_OUT` via `SAHI_ASK` views | nothing |
| eval | Fingerprint accuracy, robustness, red team, scale | `SAHI_OUT`, `SAHI_TRUTH` | `eval/reports/` |

## Design principles

- **Database does the work.** Set-based SQL, exact decimals, no row explosion. If a step needs logic SQL cannot express well, write it down in `DECISIONS.md` before reaching for a UDF
- **Re-runnable and idempotent.** Each run gets a `run_id`. Steps rebuild their outputs from inputs. Policy is snapshotted per run so runs can be diffed
- **Evidence over assertion.** Every finding links to source rows (`evidence_ids`) and the step that produced it (`sql_step_id`)
- **Honest uncertainty.** `EVIDENCE_GAP` and `UNEXPLAINED` are first-class outputs, never forced into a category
- **Independent verification.** The oracle shares no code with the pipeline

## Stack (see `DECISIONS.md` for why)

- Exasol Personal, local on macOS Apple Silicon (single node)
- Python 3.11+, `pyexasol`, `decimal`
- API: FastAPI (Python, `pyexasol` pool, read-mostly)
- UI: React + TypeScript + Vite, built to static files served by the API, so one process runs the demo (D19)
- Tests: `pytest` (oracle-only tests need no database; `db` tests skip without `.env`)

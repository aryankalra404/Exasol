# Architecture

## One line

Synthetic extracts go into Exasol; a numbered chain of SQL steps turns them into money-in-hand dates, fair and candidate interest, fingerprints, findings and a refund ledger; everything else (app, letters, assistant) only reads those result tables.

## Flow

```
generator/ (Python, fixed seed)
   │  CSV per table + manifest
   ▼
scripts/load  ──IMPORT──►  SAHI_RAW            SAHI_TRUTH (eval only)
                              │                      ▲
                              ▼                      │
                      sql/ pipeline (Exasol)     eval/, tests/
                        10 schema + policy seed      │
                        20 money-in-hand             │ compare
                        30 balance events            │
                        40 balance intervals         │
                        50 period interest (fair)    │
                        60 candidate conventions     │
                        70 fingerprint               │
                        80 permitted check           │
                        90 findings + attribution    │
                        95 ledger, gaps, rollups     │
                              │                      │
                              ▼                      │
                          SAHI_OUT  ─────────────────┘
                     │        │         │
                     ▼        ▼         ▼
                   app/    letters/   agent/ (MCP, read-only)
                (API + UI) (template   (Tier 2)
                           + checker)

oracle/ (Python Decimal, independent) ──► compared with SAHI_OUT in tests/
```

Step numbers are indicative. The real map lives in `WHY_EXASOL.md` and is updated as files land.

## Components

| Component | Does | Reads | Writes |
|---|---|---|---|
| generator | Builds a synthetic loan book with hidden LMS config and planted defects | nothing | `data/<dataset_id>/raw`, `truth` |
| loader | Creates schemas, imports CSVs | `data/` | `SAHI_RAW`, `SAHI_TRUTH` |
| pipeline | All audit logic | `SAHI_RAW`, `SAHI_POLICY` | `SAHI_OUT` |
| runner | Runs pipeline steps in order, records `audit_runs` and `step_timings`, snapshots policy | `sql/` | `SAHI_OUT.audit_runs` |
| oracle | Recomputes fair interest and fingerprints per loan in Python | CSVs in `data/` | test reports |
| app | API + web UI for the auditor | `SAHI_OUT`, `SAHI_POLICY` | `SAHI_POLICY.settings`, triggers runs |
| letters | Renders refund letters and checks every figure | `SAHI_OUT` | `letters/out/` |
| agent | Answers questions over results via Exasol MCP, shows its SQL | `SAHI_OUT` (read-only user) | nothing |
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
- UI: Next.js + TypeScript, built to static files served by the API, so one process runs the demo
- Tests: `pytest`; CI on GitHub Actions for the Python parts that do not need Exasol

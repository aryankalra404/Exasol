# Status

Live task board. Update it when you start, finish, block or cut something. Keep it short and current; history lives in git.

**Deadline: Sat 31 Oct 2026, 11:59 pm IST.** Target: submit by 10:00 pm.

## How to use

- Claim a task by writing your name or session label in **Owner** and setting **State** to `doing`. Commit and push the claim
- States: `todo`, `doing`, `blocked`, `done`, `cut`
- One owner per task. Split big tasks rather than sharing them
- When done: set `done`, add a short note (what landed, where), push

## Contract changes

Breaking or notable changes to `CONTRACT.md` that others must react to. Newest first.

- (none yet)

## Tasks

### Foundation
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| F1 | Pre-build docs, CLAUDE.md, licence | | done | this commit |
| F2 | Exasol Personal running locally, connection in `.env`, smoke query | | todo | starter kit already present on the main laptop; verify version and creds |
| F3 | Repo scaffold: folders, `pyproject`, ruff, pytest, `.env.example`, Makefile or scripts | | todo | |

### Data
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| D1 | Generator: loans, KFS, tranches, evidence, receipts, rate history | | todo | contract tables in SAHI_RAW |
| D2 | Generator: hidden LMS config + interest postings under that config | | todo | includes mid-2024 "fixed for new loans only" story |
| D3 | Generator: planted defects + truth tables | | todo | |
| D4 | Demo fixtures: Meena, Raghav, Asha exactly as in SPEC | | todo | |
| D5 | Loader: create schemas, import CSVs | | todo | |

### Engine (SQL)
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| E1 | Policy seed: precedence, settings, practices, 33 conventions | | todo | |
| E2 | Money-in-hand resolution | | todo | |
| E3 | Balance events + intervals per convention | | todo | |
| E4 | Period interest (fair + candidates) | | todo | |
| E5 | Fingerprint + permitted check | | todo | |
| E6 | Findings, attribution, refund ledger, gaps, rollups | | todo | |
| E7 | Lineage + runner (audit_runs, step_timings) | | todo | |

### Proof
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| T1 | Oracle (independent Decimal recompute + fingerprint) | | todo | must not import from sql/ |
| T2 | Oracle agreement test on 10k+ loans | | todo | |
| T3 | RBI worked-example fixtures | | todo | |
| T4 | False-positive suite | | todo | |
| T5 | Fingerprint accuracy vs truth | | todo | |
| T6 | Scale run, measured | | todo | |

### App
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| A1 | API (FastAPI) per contract | | todo | |
| A2 | Book overview | | todo | |
| A3 | Loan timeline + fingerprint panel + lineage | | todo | |
| A4 | Ledger + export, evidence-gap queue | | todo | |
| A5 | Policy toggle + re-run (Tier 1) | | todo | |
| A6 | Config regression view (Tier 1) | | todo | |

### Letters, agent
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| L1 | English letter template + checker | | todo | |
| L2 | Hindi + Tamil (Tier 1) | | todo | |
| G1 | Ask-the-book via Exasol MCP (Tier 2) | | todo | |

### Submission
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| S1 | README final, run guide, deployment instructions | | todo | |
| S2 | WHY_EXASOL, LIMITS, DECISIONS final | | todo | |
| S3 | Cold-start install test on a second machine | | todo | |
| S4 | Pitch deck (PDF) | | todo | |
| S5 | Demo video under 3 min | | todo | |
| S6 | Submit form, repo public, licence present | | todo | see SUBMISSION.md |

## Measured results

Only numbers we actually ran. Include date, dataset, hardware.

| What | Value | Dataset | Hardware | Date |
|---|---|---|---|---|
| | | | | |

## Blockers and open questions

- Exasol Personal local: confirm version, connection details, and whether Python UDF container is needed (only for Tier 2 APR)

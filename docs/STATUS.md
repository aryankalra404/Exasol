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

- 0.3.0 (31 Oct): additive, `SAHI_ASK` views + `ASK_READER` user for ask-the-book. No action needed
- 0.2.0 (30 Oct): reserved-word renames (`state_name`, `evidence_source`), `SAHI_WORK`, new OUT tables. See CONTRACT changelog

## Tasks

### Foundation
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| F1 | Pre-build docs, CLAUDE.md, licence | | done | |
| F2 | Exasol Personal running locally, connection in `.env`, smoke query | Aashman | done | `exasol install local`, Exasol 2026.2.0-dev.0, VM 2 vCPU / 8 GB |
| F3 | Repo scaffold: folders, `pyproject`, ruff, pytest, Makefile | Aashman | done | |

### Data
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| D1 | Generator: loans, KFS, tranches, evidence, receipts, rate history | Aashman | done | `generator/generate.py` |
| D2 | Generator: hidden LMS config + interest postings under that config | Aashman | done | `generator/lms.py`; BR001-BR003 fixed for new loans only in Jul 2024 |
| D3 | Generator: planted defects + truth tables | Aashman | done | missing/duplicate acks, missing rail credit, reversals, manual journals, wrong day count |
| D4 | Demo fixtures: Meena, Raghav, Asha exactly as in SPEC | Aashman | done | `LDM0001`-`LDM0003`, tested |
| D5 | Loader: create schemas, import CSVs | Aashman | done | `scripts/load.py` |

### Engine (SQL)
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| E1 | Policy seed: precedence, settings, practices, 33 conventions | Aashman | done | `sql/05` |
| E2 | Money-in-hand resolution | Aashman | done | `sql/20` |
| E3 | Balance events + intervals per convention | Aashman | done | `sql/30`, `sql/40`; conventions as differences from fair |
| E4 | Period interest (fair + candidates) | Aashman | done | `sql/50`, `sql/60` |
| E5 | Fingerprint + permitted check | Aashman | done | `sql/70`, loan-history tie-break |
| E6 | Findings, attribution, refund ledger, gaps, rollups | Aashman | done | `sql/80`, `sql/90`, plus root causes, cohorts, letter figures |
| E7 | Lineage + runner (audit_runs, step_timings) | Aashman | done | `scripts/audit.py` |

### Proof
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| T1 | Oracle (independent recompute + fingerprint) | Aashman | done | `oracle/oracle.py`, day by day, no shared code. Ideally re-reviewed by a teammate who did not write the SQL |
| T2 | Oracle agreement test on 10k+ loans | Aashman | done | 232,890 / 232,890 periods |
| T3 | RBI worked-example fixtures | Aryan | done | `tests/test_rbi_fixtures.py`: RBI's Rs 20,000 / 24-month illustration through oracle and full SQL pipeline (separate schemas) |
| T4 | False-positive suite | Aryan | done | `tests/test_false_positives.py`: disclosed commitment fee, disclosed 30E/360, fairly posted periods; oracle on a clean book plus SQL on the loaded run |
| T5 | Fingerprint accuracy vs truth | Aashman | done | measured below; script still inline, move to `eval/` |
| T6 | Scale run, measured | Aashman | done | 100k loans |
| T7 | CI (ruff + db-free tests) and README badge | Aryan | done | `.github/workflows/ci.yml`: ruff, pytest without Exasol, web build |
| T8 | Robustness: defect levels none to heavy | Aryan | done | `eval/robustness.py`, `make robustness`, report in `eval/reports/robustness.json` |
| T9 | Larger scale run (up to 1M loans) | Aryan | todo | |

### App
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| A1 | API (FastAPI) per contract | Aashman | done | `app/api/main.py` |
| A2 | Book overview | Aashman | done | |
| A3 | Loan timeline + fingerprint panel + lineage | Aashman | done | |
| A4 | Ledger + export, evidence-gap queue | Aashman | done | |
| A5 | Policy toggle + re-run (Tier 1) | Aashman | done | with run compare |
| A6 | Config regression view (Tier 1) | Aashman | done | cohort heatmap |

### Letters, agent
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| L1 | English letter template + checker | Aashman | done | `letters/letter.py`, tests in `tests/test_letters.py` |
| L2 | Hindi + Tamil (Tier 1) | Aryan | done | Tamil template, UI toggle, checker test in `tests/test_letters.py` |
| G1 | Ask-the-book via Exasol MCP (Tier 2) | Aryan | done | `docs/ASK.md`: `SAHI_ASK` views, read-only `ASK_READER`, `scripts/ask_mcp.py`, `.mcp.json`, `make ask-smoke` |

### Submission
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| S1 | README final, run guide, deployment instructions | Aashman | done | |
| S2 | WHY_EXASOL, LIMITS, DECISIONS final | Aashman | done | |
| S3 | Cold-start install test (fresh clone) | Aryan | doing | |
| S4 | Pitch deck (PDF) | | todo | |
| S5 | Demo video under 3 min | | todo | |
| S6 | Submit form, repo public, licence present | | todo | see SUBMISSION.md |

## Measured results

Only numbers we actually ran. Hardware for all rows: Exasol Personal local, VM 2 vCPU / 8 GB RAM, on an Apple M4 MacBook with 16 GB.

| What | Value | Dataset | Date |
|---|---|---|---|
| Generate book | 9.7 s (10k), 111 s (100k) | s42_n10000, s7_n100000 | 30 Oct 2026 |
| Load (IMPORT, all tables) | 6.0 s (10k), 10.4 s (100k) | same | 30 Oct 2026 |
| Full audit inside Exasol | 16.2 to 17.4 s over four runs | s42_n10000 (10,003 loans, 234,195 postings) | 30 Oct 2026 |
| Full audit inside Exasol | 120.6 s | s7_n100000 (100,003 loans, 2,342,745 postings) | 30 Oct 2026 |
| Slowest steps at 100k | S40 intervals 26.5 s, S90 ledger 20.0 s, S30 events 19.4 s, S60 candidates 18.4 s | s7_n100000 | 30 Oct 2026 |
| Intermediate rows at 100k | 4.2M fair intervals, 11.3M difference intervals, 3.5M candidate figures | s7_n100000 | 30 Oct 2026 |
| Oracle agreement | 232,890 / 232,890 periods (fair figure, status, matched convention), largest deviation 0 paise | s42_n10000, all loans | 30 Oct 2026 |
| Oracle agreement | 70,361 / 70,361 periods, largest deviation 0 paise | s7_n100000, random 3,003 loans | 30 Oct 2026 |
| Fingerprint accuracy | MATCHED 7,535: 6,612 exact hidden convention + 923 numerically identical; PERMITTED 2,072 exact | s42_n10000 | 30 Oct 2026 |
| Undecided, held out | EVIDENCE_GAP 252 periods, UNEXPLAINED 454, AMBIGUOUS 385 (counted by default), UNDERCHARGE 577 | s42_n10000 | 30 Oct 2026 |
| Policy flip (commitment fee not permitted) | refund +₹30,68,322.19, 250 more borrowers; re-run 16.5 s | s42_n10000 | 30 Oct 2026 |
| False positives (oracle, clean book) | 0 wrongly flagged: 519 disclosed-fee periods (151 PERMITTED, 368 FAIR), 131 disclosed 30E/360 periods FAIR, 13,632 fairly posted periods FAIR | s23_n1200, defect scale 0 | 31 Oct 2026 |
| False positives (SQL) | 0 wrongly flagged: 1,826 disclosed-fee periods on loans without planted defects all PERMITTED, no fairly posted period in findings | s42_n10000 | 31 Oct 2026 |
| RBI worked example | pass: EMI Rs 969.73 (Rs 970), total interest Rs 3,273.58 (Rs 3,274), APR 17.07% on Rs 19,600 net; oracle and SQL reproduce all 24 months to the paisa, all FAIR, 0 findings | fixture `rbi_kfs` | 31 Oct 2026 |
| Robustness, defects none (0) | refund ₹9,29,48,965.45 = 100.00% of true unfair excess, 0 wrongly refunded, 0 unexplained, 1 gap (Asha, deliberate) | s42_n10000, MacBook Air M4 24 GB, Exasol VM 2 vCPU / 12 GB | 31 Oct 2026 |
| Robustness, defects default (1) | 1,338 planted defects: refund 98.37% of true unfair excess, 0 wrongly refunded, 234 gap tranches, 454 unexplained, 577 undercharge | same | 31 Oct 2026 |
| Robustness, defects heavy (3) | 4,057 planted defects: refund 96.82% of true unfair excess, 0 wrongly refunded, 683 gap tranches, 1,786 unexplained, 2,410 undercharge | same | 31 Oct 2026 |
| Full audit inside Exasol, second machine | 7.1 to 7.2 s per run | s42_n10000 at defect levels 0/1/3, MacBook Air M4 24 GB, Exasol VM 2 vCPU / 12 GB | 31 Oct 2026 |
| Ask-the-book over MCP | 5 of 5 example questions answered through `exasol-mcp-server` 2.3.0 as `ASK_READER`; read of `SAHI_TRUTH` refused by Exasol (insufficient privileges); no write tool exposed | s42_n10000 | 31 Oct 2026 |
| Tests | 19 passed locally with Exasol; CI runs 16 (db tests skip) | | 31 Oct 2026 |

## Blockers and open questions

- Python UDF container not installed (only needed for the Tier 2 APR check)
- Risk 1 (how auditors test interest today) still unvalidated: talk to two practitioners before the deck

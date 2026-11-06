# Status

Live task board. Update it when you start, finish, block or cut something. Keep it short and current; history lives in git.

**In the top 5. Live demo day: Fri 6 Nov 2026, 10:00 am IST.** Submission closed 31 Oct.

## How to use

- Claim a task by writing your name or session label in **Owner** and setting **State** to `doing`. Commit and push the claim
- States: `todo`, `doing`, `blocked`, `done`, `cut`
- One owner per task. Split big tasks rather than sharing them
- When done: set `done`, add a short note (what landed, where), push

## Contract changes

Breaking or notable changes to `CONTRACT.md` that others must react to. Newest first.

- 0.10.0 (6 Nov): additive, `fix_coverage`, `fix_coverage_grid`, `fix_loans`, three endpoints. Re-run the audit and restart the app. Refund figures unchanged
- 0.9.0 (5 Nov): additive, `GET /api/runs/{run_id}/loans/{loan_id}/source/{period_start}`. No table changes
- 0.8.1 (5 Nov): additive, `current.step_id` on `GET /api/live`. No table changes
- 0.8.0 (5 Nov): additive, `GET /api/live`. No table changes
- 0.7.0 (4 Nov): loan outcomes, evidence level, refund instructions. No table changes
- 0.6.0 (4 Nov): `SAHI_POLICY.evidence_additions`, new input to S20 and the oracle. No action needed
- 0.5.0 (4 Nov): review log and release endpoints; `PUT /api/policy/settings` now requires `changed_by` and `reason`. App only
- 0.4.0 (31 Oct): additive, data and inspection-pack endpoints, uploaded books. No action needed
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
| T9 | Larger scale run | Aryan | done | 500k loans, `eval/scale.py`, report `eval/reports/scale_s7_n500000.json` |

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

### Finale (demo day Fri 6 Nov 2026, 10:00 am IST)
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| R1 | Human review layer + letter release | Aryan | done | `sql/06`, `app/api/review.py`, Review & release page, `tests/test_review.py`. Run on Exasol through the API and through the real buttons in headless Chrome |
| R3 | Blind red team | | doing | machine-written round done, found and fixed 1 real bug, see `docs/RED_TEAM.md`. Still wanted: a person who has not read the generator or SQL |
| R4 | Close the evidence gap: enter branch replies, re-run | Aryan | done | `evidence_additions`, S20, oracle, Work queues, `tests/test_evidence.py` |
| R5 | Usable review: loan outcomes, review by root cause, evidence level, refund instructions | Aryan | done | Overview, All loans, Review & release, `tests/test_review.py` |
| R2 | Human checks: letters, oracle, auditor, RBI text | | todo | sheets in `docs/HUMAN_CHECKS.md`; only people can do these |
| R6 | Exasol live view: running SQL, operators and step progress during a run | Aryan | done | `app/api/live.py`, live panel on Policy that opens on a re-run, then walks through the finished run step by step (arrows, left and right keys, or clicking a step), the same panel on Data for a load and audit, step strip on Work queues, `tests/test_live.py`. Read-only, no pipeline change. Run through the real buttons in headless Chrome |
| R7 | Show source records: the raw rows and decision path behind one month | Aryan | done | `app/api/source.py`, panel on the loan page, `make tamper` and `make tamper-undo`, `tests/test_source_records.py`. Read-only, no pipeline change. Run through the real button in headless Chrome for refund, permitted, gap, fair, changed and unexplained months |
| R8 | Pre-rehearsal fixes: review state, app restart, refusal prompt, deck figures | Aryan | done | Slides 9 and 14 patched in the PDF, as the deck source is not in the repo. Exasol status and standby laptop still open, see Blockers |
| R9 | Fix coverage from test months: judge a fix only on months the old rule and fair differ | Aryan | done | S90, `app/api/main.py`, Fix coverage page, `tests/test_fix_coverage.py`. Verdicts agree with the generator's hidden config at all 8 branches with a refundable main rule. 500k scale run not repeated with this step |

### Submission
| # | Task | Owner | State | Notes |
|---|---|---|---|---|
| S1 | README final, run guide, deployment instructions | Aashman | done | |
| A7 | Data page (load your own book, templates, sample reload), first-run screen, inspection pack | Aryan | done | `app/api/book_io.py`, `tests/test_book_io.py`; upload of the template book and sample reload tested end to end |
| S7 | UI copy and polish pass (every screen) | Aryan | done | plain words instead of codes, plurals, letter reflow, readable branch queries, timeline label overlap, Method panel overflow, grouped nav, paged work queues with branch filter, no demo-specific defaults |
| S2 | WHY_EXASOL, LIMITS, DECISIONS final | Aashman | done | |
| S3 | Cold-start install test (fresh clone) | Aryan | done | fresh GitHub clone on a second laptop (MacBook Air M4): setup, demo, test, oracle from the README, separate `COLD_*` schemas |
| S4 | Pitch deck (PDF) | Aryan | done | `docs/Sahi-Byaaj-pitch.pdf`, 16 slides (flowchart added as slide 8); RBI quote and KFS annex figures checked in a browser |
| S5 | Demo video under 3 min | | done | linked at the top of `README.md` |
| S6 | Submit form, repo public, licence present | | done | see SUBMISSION.md |

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
| Full audit inside Exasol | 479.0 s (generate 248.4 s, load 22.3 s) | s7_n500000 (500,003 loans, 785,974 tranches, 11,702,698 postings, 11,639,169 periods), MacBook Air M4 24 GB, Exasol VM 2 vCPU / 12 GB | 31 Oct 2026 |
| Steps at 500k | S30 events 146.8 s, S40 intervals 93.1 s, S60 candidates 85.7 s, S90 ledger 56.7 s, S70 fingerprint 37.7 s, S50 34.4 s, S80 13.4 s, S20 7.2 s, S10 3.3 s | s7_n500000 | 31 Oct 2026 |
| Intermediate rows at 500k | 21.1M fair intervals, 56.5M difference intervals, 17.5M candidate figures | s7_n500000 | 31 Oct 2026 |
| Oracle agreement | 69,895 / 69,895 periods (fair figure, status, matched convention), largest deviation 0 paise | s7_n500000, random 3,003 loans | 31 Oct 2026 |
| Cold start from a fresh clone | `make setup`, `make demo LOANS=10000` (19.9 s), `make test` 20 passed, `make oracle` 232,890 / 232,890, 0 paise; refund total identical to the paisa to the original machine's run; working tree clean | s42_n10000, MacBook Air M4 24 GB | 31 Oct 2026 |
| Letter release, whole book | 3,062 letters checked and stored in 0.48 s, ZIP of the batch in 0.18 s; 3,075 ledger rows approved by filter in 0.2 s | s42_n10000, MacBook Exasol VM 2 vCPU / 12 GB | 4 Nov 2026 |
| Stale approvals | All rows approved and released, then LMS fallback off and re-run: 41 rows needed re-review, 72 released letters flagged. Commitment fee off instead: 0 stale, 250 new draft letters | s42_n10000 | 4 Nov 2026 |
| Entered evidence, whole book | Handover dates entered for all 234 gaps, re-run: gaps 0, refund ₹8,83,23,995.69 to ₹8,89,23,632.85; oracle 232,890 / 232,890, largest deviation 0 paise; entries removed and re-run: original total exactly. The months resolved to 91 refund, 48 unexplained, 47 fair, 47 undercharge, 15 ambiguous, 4 permitted. Dates were test values at the end of each window, so these are not findings | s42_n10000 | 4 Nov 2026 |
| Blind red team, machine-written | 12 loans, 60 months, answers frozen first. First run 59 of 60; 1 real bug fixed (postings before the sanction month were not audited). After the fix 60 of 60, all 12 loan refund totals agree. 54 further months flagged Undercharge, none refunded. Demo book unchanged, oracle 232,890 / 232,890 | `tests/fixtures/red_team` | 4 Nov 2026 |
| Loan outcomes | 10,003 audited: 6,400 correct, 3,063 refund owed, 230 permitted, 171 waiting on evidence, 61 needs investigation, 78 undercharged. Refund rows by evidence: 2,560 exact match and confirmed date, 92 fallback date, 70 other months open, 353 rule not unique | s42_n10000 | 4 Nov 2026 |
| Live view polling | Audit 7.6, 7.7, 8.0 s without polling; 8.1, 8.2, 8.4 s with `/api/live` polled twice a second. Three runs each, so a small sample. Slowest poll 0.10 s | s42_n10000 in separate schemas | 5 Nov 2026 |
| Load and audit from the Data page | Sample reload: load 1.4 to 1.6 s, audit 8.2 to 9.2 s. Three-loan template upload: load 0.8 s, audit 1.1 to 1.5 s. Slowest live poll during an upload 0.14 s | s42_n10000 and the template book, separate schemas | 5 Nov 2026 |
| One paisa added to one posting (`PDM0001010`), re-run | Meena's March 2025 goes from Refund to Unexplained (closest rule off by 1 paisa); refund total ₹8,83,23,995.69 to ₹8,83,21,694.32, down exactly ₹2,301.37; refund loans 3,063 to 3,062; unexplained months 454 to 455; her approved letter leaves the book. Paisa taken back, re-run: total, loans and unexplained restored exactly and the approval counts again. Re-runs 7.4 to 8.4 s | s42_n10000, separate schemas | 5 Nov 2026 |
| Tests | 72 passed, 1 skipped locally with Exasol | separate schemas | 5 Nov 2026 |
| Fix coverage, test months at BR001 from Jul 2024 | Sanctioned before: 40 old rule, 0 fair. Sanctioned from: 0 old rule, 144 fair. 8 undecided over the branch's whole history. Verdicts match the hidden config at 8 of 8 branches. Refund total and oracle (232,890 / 232,890, 0 paise) unchanged. Tests 79 passed. S90 about 1.0 s to 1.25 s, audit 9.1 s, one run | s42_n10000 | 6 Nov 2026 |
| Unseen seed, generate + load + audit | 15.9 s (audit 8.3 s); refund ₹8,94,88,373.53, 3,102 loans; Meena ₹2,301.37 | s1107_n10000, MacBook Air M4 24 GB, separate schemas, no screen share | 5 Nov 2026 |
| Oracle agreement, unseen seed | 38.2 s, largest deviation 0 paise, no disagreements | s1107_n10000, all loans | 5 Nov 2026 |

## Blockers and open questions

- `exasol status` says `deployment_failed` on the demo laptop while the database serves queries normally; cause unknown. Set up a standby laptop before testing a restart here, and do not run `exasol deploy` or `destroy` until then
- Python UDF container not installed (only needed for the Tier 2 APR check)
- Risk 1 (how auditors test interest today) still unvalidated: talk to two practitioners before the deck

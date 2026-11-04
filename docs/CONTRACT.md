# Contract

**Version 0.8.0** (5 Nov 2026)

The interface between components. Generator, SQL pipeline, oracle, app, letters and agent talk only through what is defined here. Build against this, not against each other's code.

## Change rules

- **Additive** (new table, new nullable column, new enum value nobody branches on): bump minor version, add a changelog line, push. No sign-off needed
- **Breaking** (rename, remove, retype, change meaning or units): bump major-ish (0.x → 0.x+1.0 while in draft), changelog line naming who is affected, add it under "Contract changes" in `STATUS.md`, push this doc **before** the code that depends on it
- Interest semantics live in `DOMAIN.md`, not here. This doc is about shapes

## Global conventions

- Schemas: `SAHI_RAW` (loaded extracts), `SAHI_POLICY` (editable rules), `SAHI_OUT` (pipeline results), `SAHI_TRUTH` (hidden generator truth, eval only), `SAHI_WORK` (pipeline intermediates, rebuilt every run, latest run only), `SAHI_ASK` (read-only views for ask-the-book, latest completed run)
- Column names avoid Exasol reserved words (`STATE`, `SOURCE`, `VALUE`): hence `state_name` and `evidence_source`
- Identifiers: uppercase in Exasol, documented here in lowercase for readability
- Money: `*_paise DECIMAL(18,0)`. Rates: `*_rate_pct DECIMAL(9,6)`. Dates: `DATE`. Timestamps: `TIMESTAMP` (UTC)
- IDs are strings with obviously fake prefixes: `L000001`, `B000001`, `BR001`. The three demo loans are `LDM0001` (Meena), `LDM0002` (Raghav), `LDM0003` (Asha), present in every dataset
- Enums are `VARCHAR` with the exact values listed. Unknown values are a bug
- Every `SAHI_OUT` table has `run_id VARCHAR(36)` as its first column

## Generator output (files)

- Location: `data/<dataset_id>/` where `dataset_id = s<seed>_n<loans>` (for example `data/s42_n10000/`)
- One CSV per table: UTF-8, header row, comma separated, `YYYY-MM-DD` dates, integer paise, empty field = NULL
- `data/<dataset_id>/raw/*.csv` → `SAHI_RAW`; `data/<dataset_id>/truth/*.csv` → `SAHI_TRUTH`
- `data/<dataset_id>/manifest.json`: seed, loan count, generator version, row counts per file, generation timestamp

## SAHI_RAW (what a lender extract would contain)

**branches**: `branch_id VARCHAR(10) PK`, `branch_name VARCHAR(100)`, `state_name VARCHAR(50)`, `region VARCHAR(20)`

**borrowers**: `borrower_id VARCHAR(10) PK`, `display_name VARCHAR(100)`, `preferred_language VARCHAR(5)` (`en`, `hi`, `ta`), `state_name VARCHAR(50)`

**dataset_info** (written by the loader): `dataset_id`, `seed`, `loans`, `as_of DATE`, `generator_version`

**loans**
| column | type | notes |
|---|---|---|
| loan_id | VARCHAR(10) PK | |
| borrower_id | VARCHAR(10) | |
| branch_id | VARCHAR(10) | |
| product | VARCHAR(10) | `HOME`, `PERSONAL`, `LAP` |
| sanction_date | DATE | |
| agreement_date | DATE | |
| sanctioned_paise | DECIMAL(18,0) | |
| tenure_months | DECIMAL(4,0) | |
| emi_start_date | DATE | first full EMI due date |
| status | VARCHAR(10) | `ACTIVE`, `CLOSED` |
| closed_date | DATE | nullable |

**kfs**
| column | type | notes |
|---|---|---|
| loan_id | VARCHAR(10) PK | |
| issued_date | DATE | |
| annual_rate_pct | DECIMAL(9,6) | initial rate |
| day_count_basis | VARCHAR(10) | `ACT_365`, `30E_360` |
| commitment_fee_rate_pct | DECIMAL(9,6) | nullable; annual rate on undisbursed amount, sanction to disbursal |
| broken_period_disclosed | BOOLEAN | |
| disclosed_emi_paise | DECIMAL(18,0) | |
| disclosed_apr_pct | DECIMAL(9,6) | |

**kfs_disbursal_schedule**: `loan_id`, `tranche_no DECIMAL(3,0)`, `expected_date DATE`, `expected_paise DECIMAL(18,0)`. PK (loan_id, tranche_no)

**kfs_amortisation** (Tier 1, P6): `loan_id`, `instalment_no DECIMAL(4,0)`, `due_date`, `emi_paise`, `principal_paise`, `interest_paise`, `opening_balance_paise`

**rate_history**: `loan_id`, `effective_date DATE`, `annual_rate_pct DECIMAL(9,6)`. Includes the initial rate row. PK (loan_id, effective_date)

**tranches**
| column | type | notes |
|---|---|---|
| loan_id | VARCHAR(10) | |
| tranche_no | DECIMAL(3,0) | 1-based |
| amount_paise | DECIMAL(18,0) | |
| payment_mode | VARCHAR(10) | `NEFT`, `RTGS`, `IMPS`, `CHEQUE`, `DD` |
| payee_type | VARCHAR(10) | `BORROWER`, `BUILDER`, `SELLER` |

PK (loan_id, tranche_no)

**disbursement_evidence** (long format, one row per source per tranche)
| column | type | notes |
|---|---|---|
| evidence_id | VARCHAR(20) PK | |
| loan_id | VARCHAR(10) | |
| tranche_no | DECIMAL(3,0) | |
| evidence_source | VARCHAR(15) | `LMS_DISB`, `CHEQUE_DATE`, `HANDOVER_ACK`, `RAIL_CREDIT` |
| event_date | DATE | |
| reference | VARCHAR(50) | cheque no, UTR, ack no (fake) |
| recorded_in | VARCHAR(20) | `LMS`, `PAYMENTS`, `BRANCH_REGISTER` |

Sanction and agreement dates are read from `loans`, not duplicated here. A source may be missing (defect) or duplicated with different dates (defect).

**demands**: `loan_id`, `due_date`, `instalment_no DECIMAL(4,0)`, `kind VARCHAR(10)` (`PRE_EMI`, `EMI`), `demand_paise DECIMAL(18,0)`

**receipts**
| column | type | notes |
|---|---|---|
| receipt_id | VARCHAR(20) PK | |
| loan_id | VARCHAR(10) | |
| value_date | DATE | |
| kind | VARCHAR(12) | `EMI`, `PRE_EMI`, `ADVANCE_EMI`, `PREPAYMENT`, `CLOSURE` |
| amount_paise | DECIMAL(18,0) | |
| principal_paise | DECIMAL(18,0) | principal component as recorded by the LMS |
| due_date | DATE | for `ADVANCE_EMI`: the instalment it pre-pays |

**interest_postings**
| column | type | notes |
|---|---|---|
| posting_id | VARCHAR(20) PK | |
| loan_id | VARCHAR(10) | |
| period_start | DATE | 1st of month |
| period_end | DATE | 1st of next month (exclusive) |
| posted_paise | DECIMAL(18,0) | negative for reversals |
| posted_on | DATE | |
| reverses_posting_id | VARCHAR(20) | nullable |
| is_manual | BOOLEAN | manual journal adjustment |

The audit compares the **net** posted amount per (loan, period) after reversals.

**communications** (Tier 1, P6): `loan_id`, `comm_date`, `kind VARCHAR(20)` (`REVISED_SCHEDULE`, `KFS`, `OTHER`), `reference`

## SAHI_POLICY (editable, versioned per run)

**date_precedence**: `payment_mode`, `rank DECIMAL(2,0)`, `evidence_source`, `rule VARCHAR(20)` (`USE`, `MAX_WITH_CHEQUE_DATE`, `FALLBACK`). PK (payment_mode, rank)

**settings**: `setting_key VARCHAR(50) PK`, `setting_value VARCHAR(100)`, `description VARCHAR(500)`. Keys and defaults in `DOMAIN.md`

**practices**: `practice_code VARCHAR(3) PK`, `title VARCHAR(200)`, `rbi_reference VARCHAR(200)`, `introduced DATE`

**conventions**: `convention_id VARCHAR(40) PK`, `start_basis`, `principal_basis`, `advance_treatment`, `month_rounding`, `is_fair BOOLEAN`, `unfair_dimension_count DECIMAL(1,0)`, `is_permitted_variant BOOLEAN`, `practice_codes VARCHAR(20)` (e.g. `P2,P3`). Rebuilt by `sql/05`, 33 rows. `convention_id` = start (`MIH`, `CHQ`, `SNC`, `AGR`) `|` principal (`DIS`, `SAN`) `|` advance (`NET`, `IGN`) `|` month (`EXACT`, `FULL`); fair is `MIH|DIS|NET|EXACT`; the commitment fee variant is `CFEE`

## SAHI_POLICY: human review log (`sql/06_review_schema.sql`)

Append-only records of what people decided, kept across re-runs and scoped by `dataset_id`. The app writes them; the audit pipeline never reads them, so they cannot change a computed figure. Figures are copied from `SAHI_OUT` by the INSERT, never sent by the browser.

**review_decisions**: `decision_seq IDENTITY`, `action_id VARCHAR(36)` (shared by a filtered approval), `dataset_id`, `run_id`, `item_kind` (`LEDGER`, `UNEXPLAINED`), `loan_id`, `practice_code` (LEDGER), `period_start` (UNEXPLAINED), `figure_paise DECIMAL(18,0)` (the figure the reviewer saw), `review_decision` (`APPROVED`, `HOLD` for LEDGER; `CLEARED`, `HOLD` for UNEXPLAINED), `decided_by`, `reason`, `decided_at`. The latest row per item counts. Review state: `UNREVIEWED` with no decision, `STALE` when `figure_paise` differs from the run's figure, otherwise the decision

**evidence_additions**: `evidence_id` (`RV...`), `dataset_id`, `loan_id`, `tranche_no`, `evidence_source`, `event_date`, `reference`, `added_by`, `reason`, `added_at`, `withdrawn_by`, `withdrawn_reason`, `withdrawn_at`. A date a person entered from a branch reply. Unlike the rest of this log, this is a **pipeline input**: S20 reads it alongside `SAHI_RAW.disbursement_evidence`, unless withdrawn. It holds a date and never an amount. A wrong entry is withdrawn, never deleted. Each run lists the entries it used in `policy_snapshot`

**policy_changes**: `change_seq IDENTITY`, `setting_key`, `old_value`, `new_value`, `changed_by`, `reason`, `changed_at`

**letter_releases**: `release_seq IDENTITY`, `batch_id`, `dataset_id`, `run_id`, `loan_id`, `letter_lang`, `excess_paise`, `approved_by`, `released_by`, `released_at`, `text_sha256`, `letter_text VARCHAR(20000)`

**release_batches**: `batch_id`, `dataset_id`, `run_id`, `released_by`, `batch_note`, `released_at`, `letter_count`, `total_paise`

Letter state per refundable loan: `DRAFT` until every ledger row of the loan is `APPROVED`, then `APPROVED`, then `RELEASED` once a letter for this exact total has been released. Released means handed over for dispatch, not delivered.

## SAHI_OUT (pipeline results; the app reads only these, SAHI_POLICY and SAHI_RAW)

Every table has `run_id` first. DDL lives in the SQL step that fills the table.

**audit_runs**: `run_id PK`, `dataset_id`, `started_at`, `finished_at`, `duration_ms`, `git_sha`, `policy_snapshot` (JSON), `loan_count`, `posting_count`, `status` (`RUNNING`, `DONE`, `FAILED`), `label`

**step_timings**: `run_id`, `sql_step_id`, `started_at`, `duration_ms`, `rows_out`

**lineage**: `sql_step_id PK`, `file_path`, `description`, `statement_sha` (SHA-256 of the SQL file)

**money_in_hand** (S20): `loan_id`, `tranche_no`, `amount_paise`, `payment_mode`, `resolved_date` (NULL when GAP), `resolved_source`, `confidence` (`CONFIRMED`, `FALLBACK`, `GAP`), `conflict_flag`, `max_spread_days`, `missing_sources`, `effective_date` (resolved, or provisional for GAP), `gap_window_start`, `gap_window_end`, `evidence_ids`, `available_sources`

**fingerprints** (S70), one row per (loan, period) audited: `posted_paise` (net of reversals), `fair_paise`, `excess_paise` (posted - fair), `match_status` (`FAIR`, `PERMITTED`, `MATCHED`, `AMBIGUOUS`, `UNEXPLAINED`, `UNDERCHARGE`, `EVIDENCE_GAP`), `matched_convention_id`, `tied_convention_ids`, `closest_convention_id`, `closest_diff_paise`, `posting_ids`, `has_manual`, `gap_tranches`

**findings** (S80), one row per loan, period and practice, non-FAIR periods only: `finding_id`, `loan_id`, `borrower_id`, `branch_id`, `product`, `period_start`, `tranche_no` (currently NULL), `practice_code` (`P1`..`P5`, `AMB` for AMBIGUOUS, `P1` for PERMITTED, NULL for other statuses), `status` (`REFUND`, `AMBIGUOUS`, `PERMITTED`, `EVIDENCE_GAP`, `UNEXPLAINED`, `UNDERCHARGE`), `days_affected`, `excess_paise` (attributed share), `matched_convention_id`, `reason`, `evidence_ids`, `sql_step_id`

**refund_ledger** (S90), one row per loan + practice, `REFUND` (and `AMBIGUOUS` when the setting is on): `borrower_id`, `loan_id`, `branch_id`, `product`, `practice_code`, `periods`, `days_affected`, `excess_paise`, `first_period`, `last_period`, `finding_ids`, `sql_step_id`

**evidence_gaps** (S90): `loan_id`, `tranche_no`, `branch_id`, `payment_mode`, `amount_paise`, `missing_source`, `available_sources`, `window_start`, `window_end`, `periods_affected`, `posted_paise_at_stake`, `suggested_query`

**rollups** (S90): `dimension` (`practice`, `branch`, `product`, `period`), `dim_value`, `status`, `loans`, `findings`, `excess_paise`

**root_causes** (S90), REFUND findings by branch and matched convention: `branch_id`, `convention_id`, `practice_codes`, `loans`, `periods`, `excess_paise`, `first_period`, `last_period`, `earliest_sanction`, `latest_sanction`

**cohorts** (S90): `branch_id`, `sanction_quarter` (`YYYY-Qn`), `period_quarter`, `loans_in_cohort`, `loans_overcharged`, `excess_paise`

**letter_figures** (S90), per refundable loan: one row per practice plus `line_key = 'TOTAL'`: `loan_id`, `borrower_id`, `display_name`, `preferred_language`, `product`, `branch_name`, `line_key`, `periods`, `days_affected`, `excess_paise`, `first_period`, `last_period`

**balance_intervals** (S90), fair path for loans with any finding: `loan_id`, `period_start`, `interval_start`, `interval_end`, `balance_paise`, `annual_rate_pct`, `days`, `numerator`

**excess_intervals** (S90), the extra balance the matched convention charged on: `loan_id`, `period_start`, `convention_id`, `interval_start`, `interval_end`, `extra_balance_paise`, `fee_balance_paise`, `annual_rate_pct`, `fee_rate_pct`, `days`, `numerator`

**run_summary** (S90), one row per run: loans, tranches, periods, postings, posted and fair totals, refund total and loans, ambiguous, permitted, gap, unexplained, undercharge, conflict and fallback counts

Per-convention period interest is not persisted (it lives in `SAHI_WORK.candidates` for the latest run only); `excess_intervals` carries the proof for every finding.

## SAHI_ASK (views for ask-the-book over MCP)

Created by `sql/ask/ask_views.sql` (`make ask-setup`), not a pipeline step. Every view except `loans`, `practices` and `policy_settings` is filtered to `latest_run`. Columns are the `SAHI_OUT` columns of the same name without `run_id`, plus `*_rupees DECIMAL(18,2)` where noted. Readable only by user `ASK_READER` (`CREATE SESSION`, `SELECT ON SCHEMA SAHI_ASK`).

`latest_run`, `run_summary` (+ `refund_rupees`), `refund_ledger` (+ `excess_rupees`), `findings`, `money_in_hand`, `evidence_gaps`, `rollups`, `root_causes`, `cohorts`, `loans` (RAW loans + branch name, state, region; no borrower names), `practices`, `policy_settings`

## SAHI_TRUTH (eval only, the pipeline must never read it)

**lms_config**: `branch_id`, `valid_from DATE`, `valid_to DATE`, `applies_to VARCHAR(20)` (`NEW_LOANS`, `ALL_LOANS`), `convention_id`

**planted_defects**: `defect_id`, `loan_id`, `tranche_no`, `kind VARCHAR(30)`, `detail VARCHAR(500)`

**expected**: `loan_id`, `period_start`, `true_convention_id`, `true_fair_paise`, `true_posted_paise`

## Letters

- Input: one `refund_ledger` loan group + borrower + loan rows
- Output: `letters/out/<run_id>/<loan_id>_<lang>.md` (and `.pdf` if rendered)
- Every number in a letter is wrapped as `{{figure:<key>}}` in the template and substituted from the ledger. The checker parses the rendered letter and compares each figure to the ledger. Any mismatch fails the letter

## App API (as built, `app/api/main.py`)

`run_id` may be `latest`. Money in JSON: integer paise as JSON numbers if under 2^53, otherwise strings.

- `GET /api/runs`, `GET /api/runs/{run_id}/summary` (run, summary, steps, rollups, root causes, practices, branches)
- `GET /api/runs/{run_id}/ledger?practice=&branch=&product=&q=&sort=&page=&size=` and `/ledger.csv`
- `GET /api/runs/{run_id}/queue/{status}?page=&size=` for `UNEXPLAINED`, `AMBIGUOUS`, `PERMITTED`, `UNDERCHARGE`, `EVIDENCE_GAP`; each row carries `total_rows`
- `GET /api/runs/{run_id}/gaps`, `GET /api/runs/{run_id}/cohorts?branch=`
- `GET /api/runs/{run_id}/loans/{loan_id}` and `/loans/{loan_id}/proof/{period_start}`
- `GET /api/runs/{run_id}/letters/{loan_id}?lang=en|hi|ta` (rendered letter + checker result)
- `GET /api/runs/{run_id}/inspection-pack.zip`: README with totals, refund_ledger, findings, evidence_gaps, run_summary, step_timings, lineage CSVs, policy_snapshot.json and the SQL files
- `GET /api/data/status` (loaded dataset, synthetic or uploaded, row counts, latest run), `GET /api/data/templates.zip`
- `POST /api/data/upload` (body: a ZIP of one CSV per `SAHI_RAW` table, header row, any column order; checked against `sql/01_raw_schema.sql` before loading; returns `{ok:false, errors}` or loads, audits and returns the run), `POST /api/data/sample` (reload the synthetic sample)
- `GET /api/runs/{run_id}/review/summary`; `POST /api/runs/{run_id}/review/decisions`, `/review/approve-filtered` (needs a filter; touches `UNREVIEWED` rows only), `/review/unexplained`, `/releases` (409 on any draft or checker failure, nothing released); `GET /api/releases/{batch_id}/letters.zip`. Writes need `reviewer` and `reason`, and apply to the latest run only (409 otherwise). Ledger rows gain `review_state`, `decided_by`, `review_reason`, `decided_at`, and the ledger takes `review=`; loan and letter responses gain `run_id` and review state; the inspection pack gains `review_decisions.csv`, `policy_changes.csv`, `release_batches.csv`, `letter_releases.csv`
- `GET /api/runs/{run_id}/evidence`, `POST /api/runs/{run_id}/evidence` (only for a tranche in the gap queue; needs date, reference, reviewer, reason; moves nothing until a re-run), `POST /api/runs/{run_id}/evidence/{evidence_id}/withdraw`. Loan responses list entered evidence with `recorded_in = REVIEWER`; the inspection pack gains `evidence_additions.csv`
- `GET /api/runs/{run_id}/outcomes` (one outcome per audited loan: `REFUND`, `EVIDENCE_GAP`, `UNEXPLAINED`, `PERMITTED`, `UNDERCHARGE`, `FAIR`, in that order of strength), `GET /api/runs/{run_id}/outcomes/{outcome}?branch=&page=&size=`. Ledger rows gain `conventions`, `certainty` (`EXACT_CONFIRMED`, `FALLBACK_DATE`, `OPEN_MONTHS`, `NOT_UNIQUE`) and `held_days`, and the ledger and filtered approval take `certainty=` and `convention=`. Release ZIPs gain `refund_instructions.csv`
- `GET /api/live`: read-only view of what Exasol is doing, from `EXA_DBA_SESSIONS`, `EXA_DBA_PROFILE_RUNNING`, `audit_runs` and `step_timings`. Returns `version`, `open_sessions`, `run`, `running`, `steps` (`state`: `done`, `running`, `failed`, `waiting`), `current` (statement, SQL text up to 4,000 characters), `operators`, `others`. 503 if Exasol cannot be read
- `GET /api/lineage`, `GET /api/lineage/{sql_step_id}` (includes the SQL text)
- `GET/PUT /api/policy/settings` (PUT requires `changed_by` and `reason`; GET adds `changes`), `POST /api/runs` (re-run the pipeline), `GET /api/compare/{a}/{b}`, `GET /api/search?q=`

## Changelog

- 0.1.0 (30 Oct 2026): first draft
- 0.2.0 (30 Oct 2026): renamed reserved-word columns (`state` → `state_name`, `source` → `evidence_source`); added `SAHI_WORK`, `RAW.dataset_info`, `conventions.practice_codes`, `audit_runs.label`; fingerprints gain `UNDERCHARGE`, `posting_ids`, `has_manual`, `gap_tranches`; findings gain `matched_convention_id` and use `AMB` for ambiguous; new OUT tables `root_causes`, `cohorts`, `letter_figures`, `excess_intervals`, `run_summary`; `period_interest` not persisted. Affects generator, loader, app
- 0.3.0 (31 Oct 2026): additive. New schema `SAHI_ASK` (views, latest run) and user `ASK_READER`; env `EXASOL_SCHEMA_ASK`, `EXASOL_ASK_USER`, `EXASOL_ASK_PASSWORD`. Affects nobody else
- 0.3.1 (31 Oct 2026): additive. Work-queue API takes `page` and `size` (replaces `limit`) and returns `total_rows`. Affects app only
- 0.4.0 (31 Oct 2026): additive. Data and inspection-pack endpoints. An uploaded book gets `dataset_id = upload_<UTC timestamp>`, `generator_version = 'upload'`, empty truth tables, and is stored under `data/uploads/`. Affects app only
- 0.8.0 (5 Nov 2026): additive. `GET /api/live`. No table changes. Affects app only
- 0.7.0 (4 Nov 2026): additive. Loan outcomes, evidence level on ledger rows, refund instructions in release ZIPs. No table changes. Affects app only
- 0.6.0 (4 Nov 2026): additive. `SAHI_POLICY.evidence_additions`, a new input to S20 and the oracle; evidence endpoints. A book with no entries audits exactly as before. Affects pipeline, oracle, app
- 0.5.0 (4 Nov 2026): breaking for `PUT /api/policy/settings` callers (now requires `changed_by`, `reason`); otherwise additive. Human review log in `SAHI_POLICY`, review and release endpoints. Pipeline, oracle and generator unaffected. Affects app only

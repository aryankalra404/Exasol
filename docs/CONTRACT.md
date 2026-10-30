# Contract

**Version 0.1.0** (draft, 30 Oct 2026)

The interface between components. Generator, SQL pipeline, oracle, app, letters and agent talk only through what is defined here. Build against this, not against each other's code.

## Change rules

- **Additive** (new table, new nullable column, new enum value nobody branches on): bump minor version, add a changelog line, push. No sign-off needed
- **Breaking** (rename, remove, retype, change meaning or units): bump major-ish (0.x → 0.x+1.0 while in draft), changelog line naming who is affected, add it under "Contract changes" in `STATUS.md`, push this doc **before** the code that depends on it
- Interest semantics live in `DOMAIN.md`, not here. This doc is about shapes

## Global conventions

- Schemas: `SAHI_RAW` (loaded extracts), `SAHI_POLICY` (editable rules), `SAHI_OUT` (pipeline results), `SAHI_TRUTH` (hidden generator truth, eval only)
- Identifiers: uppercase in Exasol, documented here in lowercase for readability
- Money: `*_paise DECIMAL(18,0)`. Rates: `*_rate_pct DECIMAL(9,6)`. Dates: `DATE`. Timestamps: `TIMESTAMP` (UTC)
- IDs are strings with obviously fake prefixes: `L000001`, `B000001`, `BR001`
- Enums are `VARCHAR` with the exact values listed. Unknown values are a bug
- Every `SAHI_OUT` table has `run_id VARCHAR(36)` as its first column

## Generator output (files)

- Location: `data/<dataset_id>/` where `dataset_id = s<seed>_n<loans>` (for example `data/s42_n10000/`)
- One CSV per table: UTF-8, header row, comma separated, `YYYY-MM-DD` dates, integer paise, empty field = NULL
- `data/<dataset_id>/raw/*.csv` → `SAHI_RAW`; `data/<dataset_id>/truth/*.csv` → `SAHI_TRUTH`
- `data/<dataset_id>/manifest.json`: seed, loan count, generator version, row counts per file, generation timestamp

## SAHI_RAW (what a lender extract would contain)

**branches**: `branch_id VARCHAR(10) PK`, `branch_name VARCHAR(100)`, `state VARCHAR(50)`, `region VARCHAR(20)`

**borrowers**: `borrower_id VARCHAR(10) PK`, `display_name VARCHAR(100)`, `preferred_language VARCHAR(5)` (`en`, `hi`, `ta`), `state VARCHAR(50)`

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
| source | VARCHAR(15) | `LMS_DISB`, `CHEQUE_DATE`, `HANDOVER_ACK`, `RAIL_CREDIT` |
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

**date_precedence**: `payment_mode`, `rank DECIMAL(2,0)`, `source`, `rule VARCHAR(20)` (`USE`, `MAX_WITH_CHEQUE_DATE`, `FALLBACK`). PK (payment_mode, rank)

**settings**: `setting_key VARCHAR(50) PK`, `setting_value VARCHAR(100)`, `description VARCHAR(500)`. Keys and defaults in `DOMAIN.md`

**practices**: `practice_code VARCHAR(3) PK`, `title VARCHAR(200)`, `rbi_reference VARCHAR(200)`, `introduced DATE`

**conventions**: `convention_id VARCHAR(40) PK`, `start_basis`, `principal_basis`, `advance_treatment`, `month_rounding`, `is_fair BOOLEAN`, `unfair_dimension_count DECIMAL(1,0)`, `is_permitted_variant BOOLEAN`. Generated once, 33 rows. `convention_id` format: `MIH|DIS|NET|EXACT` style codes, defined by the SQL step that seeds it

## SAHI_OUT (pipeline results; the app reads only these and SAHI_POLICY)

**audit_runs**: `run_id PK`, `dataset_id`, `started_at`, `finished_at`, `duration_ms DECIMAL(12,0)`, `git_sha VARCHAR(40)`, `policy_snapshot VARCHAR(20000)` (JSON), `loan_count`, `posting_count`, `status VARCHAR(10)` (`RUNNING`, `DONE`, `FAILED`)

**step_timings**: `run_id`, `sql_step_id VARCHAR(40)`, `started_at`, `duration_ms`, `rows_out DECIMAL(18,0)`

**money_in_hand**
| column | type |
|---|---|
| run_id | VARCHAR(36) |
| loan_id, tranche_no | |
| resolved_date | DATE, nullable when GAP |
| resolved_source | VARCHAR(15) |
| confidence | VARCHAR(10): `CONFIRMED`, `FALLBACK`, `GAP` |
| conflict_flag | BOOLEAN |
| max_spread_days | DECIMAL(5,0) |
| missing_sources | VARCHAR(100), comma separated |

**balance_intervals**: `run_id`, `loan_id`, `convention_id`, `interval_start DATE`, `interval_end DATE` (exclusive), `balance_paise`, `annual_rate_pct`. Optional to persist for all conventions; persist at least fair + matched for lineage

**period_interest**: `run_id`, `loan_id`, `period_start`, `convention_id`, `interest_paise`

**fingerprints**
| column | type |
|---|---|
| run_id, loan_id, period_start | |
| posted_paise | DECIMAL(18,0), net of reversals |
| fair_paise | DECIMAL(18,0) |
| excess_paise | DECIMAL(18,0), posted - fair |
| match_status | `FAIR`, `PERMITTED`, `MATCHED`, `AMBIGUOUS`, `UNEXPLAINED`, `EVIDENCE_GAP` |
| matched_convention_id | nullable |
| tied_convention_ids | VARCHAR(2000), nullable |
| closest_convention_id | for UNEXPLAINED |
| closest_diff_paise | for UNEXPLAINED |

**findings** (one row per loan, period, practice)
| column | type |
|---|---|
| run_id | |
| finding_id | VARCHAR(60) |
| loan_id, borrower_id, branch_id, product | |
| period_start | DATE |
| tranche_no | nullable when not tranche-specific |
| practice_code | `P1`..`P6`, or NULL for non-practice statuses |
| status | `REFUND`, `AMBIGUOUS`, `PERMITTED`, `EVIDENCE_GAP`, `UNEXPLAINED`, `UNDERCHARGE` |
| days_affected | DECIMAL(5,0) |
| excess_paise | DECIMAL(18,0), attributed share for this practice |
| reason | VARCHAR(500), human readable, for PERMITTED / GAP / UNEXPLAINED |
| evidence_ids | VARCHAR(2000), comma separated `evidence_id` and `posting_id` values |
| sql_step_id | VARCHAR(40) |

**refund_ledger** (one row per loan + practice, refundable statuses only): `run_id`, `borrower_id`, `loan_id`, `practice_code`, `periods DECIMAL(5,0)`, `days_affected`, `excess_paise`, `first_period`, `last_period`, `finding_ids VARCHAR(20000)`

**evidence_gaps**: `run_id`, `loan_id`, `tranche_no`, `branch_id`, `missing_source`, `available_sources`, `posted_paise_at_stake`, `suggested_query VARCHAR(1000)`

**rollups** (views are fine): by `practice_code`, `branch_id`, `product`, `origination_month`, `period_start`, each with `loans`, `findings`, `excess_paise`

**lineage**: `sql_step_id PK`, `file_path VARCHAR(200)`, `description VARCHAR(500)`, `statement_sha VARCHAR(64)`

## SAHI_TRUTH (eval only, the pipeline must never read it)

**lms_config**: `branch_id`, `valid_from DATE`, `valid_to DATE`, `applies_to VARCHAR(20)` (`NEW_LOANS`, `ALL_LOANS`), `convention_id`

**planted_defects**: `defect_id`, `loan_id`, `tranche_no`, `kind VARCHAR(30)`, `detail VARCHAR(500)`

**expected**: `loan_id`, `period_start`, `true_convention_id`, `true_fair_paise`, `true_posted_paise`

## Letters

- Input: one `refund_ledger` loan group + borrower + loan rows
- Output: `letters/out/<run_id>/<loan_id>_<lang>.md` (and `.pdf` if rendered)
- Every number in a letter is wrapped as `{{figure:<key>}}` in the template and substituted from the ledger. The checker parses the rendered letter and compares each figure to the ledger. Any mismatch fails the letter

## App API (draft, the API owner may extend additively)

- `GET /api/runs`, `GET /api/runs/{run_id}/summary`
- `GET /api/runs/{run_id}/loans/{loan_id}` (timeline, evidence, money-in-hand, fingerprints, findings)
- `GET /api/runs/{run_id}/ledger?practice=&branch=&product=&page=`
- `GET /api/runs/{run_id}/gaps`
- `GET /api/lineage/{sql_step_id}`
- `POST /api/runs` (start an audit run with the current policy)
- `GET/PUT /api/policy/settings`
- Money in JSON: integer paise as JSON numbers if under 2^53, otherwise strings

## Changelog

- 0.1.0 (30 Oct 2026): first draft

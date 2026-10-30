-- step: S01_RAW_SCHEMA
-- purpose: (re)create the raw extract tables and the eval-only truth tables before a load
-- inputs: none
-- outputs: {RAW}.*, {TRUTH}.*

CREATE SCHEMA IF NOT EXISTS {RAW};
CREATE SCHEMA IF NOT EXISTS {TRUTH};

CREATE OR REPLACE TABLE {RAW}.branches (
    branch_id VARCHAR(10) PRIMARY KEY, branch_name VARCHAR(100), state_name VARCHAR(50), region VARCHAR(20));

CREATE OR REPLACE TABLE {RAW}.borrowers (
    borrower_id VARCHAR(10) PRIMARY KEY, display_name VARCHAR(100), preferred_language VARCHAR(5), state_name VARCHAR(50));

CREATE OR REPLACE TABLE {RAW}.loans (
    loan_id VARCHAR(10) PRIMARY KEY, borrower_id VARCHAR(10), branch_id VARCHAR(10), product VARCHAR(10),
    sanction_date DATE, agreement_date DATE, sanctioned_paise DECIMAL(18,0), tenure_months DECIMAL(4,0),
    emi_start_date DATE, status VARCHAR(10), closed_date DATE);

CREATE OR REPLACE TABLE {RAW}.kfs (
    loan_id VARCHAR(10) PRIMARY KEY, issued_date DATE, annual_rate_pct DECIMAL(9,6), day_count_basis VARCHAR(10),
    commitment_fee_rate_pct DECIMAL(9,6), broken_period_disclosed BOOLEAN, disclosed_emi_paise DECIMAL(18,0),
    disclosed_apr_pct DECIMAL(9,6));

CREATE OR REPLACE TABLE {RAW}.kfs_disbursal_schedule (
    loan_id VARCHAR(10), tranche_no DECIMAL(3,0), expected_date DATE, expected_paise DECIMAL(18,0));

CREATE OR REPLACE TABLE {RAW}.rate_history (
    loan_id VARCHAR(10), effective_date DATE, annual_rate_pct DECIMAL(9,6));

CREATE OR REPLACE TABLE {RAW}.tranches (
    loan_id VARCHAR(10), tranche_no DECIMAL(3,0), amount_paise DECIMAL(18,0), payment_mode VARCHAR(10),
    payee_type VARCHAR(10));

CREATE OR REPLACE TABLE {RAW}.disbursement_evidence (
    evidence_id VARCHAR(20) PRIMARY KEY, loan_id VARCHAR(10), tranche_no DECIMAL(3,0), evidence_source VARCHAR(15),
    event_date DATE, reference VARCHAR(50), recorded_in VARCHAR(20));

CREATE OR REPLACE TABLE {RAW}.demands (
    loan_id VARCHAR(10), due_date DATE, instalment_no DECIMAL(4,0), kind VARCHAR(10), demand_paise DECIMAL(18,0));

CREATE OR REPLACE TABLE {RAW}.receipts (
    receipt_id VARCHAR(20) PRIMARY KEY, loan_id VARCHAR(10), value_date DATE, kind VARCHAR(12),
    amount_paise DECIMAL(18,0), principal_paise DECIMAL(18,0), due_date DATE);

CREATE OR REPLACE TABLE {RAW}.interest_postings (
    posting_id VARCHAR(20) PRIMARY KEY, loan_id VARCHAR(10), period_start DATE, period_end DATE,
    posted_paise DECIMAL(18,0), posted_on DATE, reverses_posting_id VARCHAR(20), is_manual BOOLEAN);

CREATE OR REPLACE TABLE {TRUTH}.lms_config (
    branch_id VARCHAR(10), valid_from DATE, valid_to DATE, applies_to VARCHAR(20), convention_id VARCHAR(40));

CREATE OR REPLACE TABLE {TRUTH}.planted_defects (
    defect_id VARCHAR(20), loan_id VARCHAR(10), tranche_no DECIMAL(3,0), kind VARCHAR(30), detail VARCHAR(500));

CREATE OR REPLACE TABLE {TRUTH}.expected (
    loan_id VARCHAR(10), period_start DATE, true_convention_id VARCHAR(40), true_fair_paise DECIMAL(18,0),
    true_posted_paise DECIMAL(18,0));

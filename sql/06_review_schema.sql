-- step: S06_REVIEW_SCHEMA
-- purpose: create the human review log: decisions on refunds and unexplained months, policy changes,
--          and released letters. Append-only, kept across re-runs. The audit pipeline never reads these,
--          so no review record can change a computed figure. Also evidence_additions: dates a person entered
--          from a branch reply. That table IS a pipeline input (S20), like any other evidence record
-- inputs: none
-- outputs: {POLICY}.review_decisions, policy_changes, letter_releases, release_batches, evidence_additions

CREATE SCHEMA IF NOT EXISTS {POLICY};

CREATE TABLE IF NOT EXISTS {POLICY}.review_decisions (
    decision_seq DECIMAL(18,0) IDENTITY, action_id VARCHAR(36), dataset_id VARCHAR(50), run_id VARCHAR(36),
    item_kind VARCHAR(12), loan_id VARCHAR(10), practice_code VARCHAR(3), period_start DATE,
    figure_paise DECIMAL(18,0), review_decision VARCHAR(12), decided_by VARCHAR(100), reason VARCHAR(500),
    decided_at TIMESTAMP);

CREATE TABLE IF NOT EXISTS {POLICY}.evidence_additions (
    evidence_id VARCHAR(20), dataset_id VARCHAR(50), loan_id VARCHAR(10), tranche_no DECIMAL(3,0),
    evidence_source VARCHAR(15), event_date DATE, reference VARCHAR(50), added_by VARCHAR(100), reason VARCHAR(500),
    added_at TIMESTAMP, withdrawn_by VARCHAR(100), withdrawn_reason VARCHAR(500), withdrawn_at TIMESTAMP);

CREATE TABLE IF NOT EXISTS {POLICY}.policy_changes (
    change_seq DECIMAL(18,0) IDENTITY, setting_key VARCHAR(50), old_value VARCHAR(100), new_value VARCHAR(100),
    changed_by VARCHAR(100), reason VARCHAR(500), changed_at TIMESTAMP);

CREATE TABLE IF NOT EXISTS {POLICY}.letter_releases (
    release_seq DECIMAL(18,0) IDENTITY, batch_id VARCHAR(36), dataset_id VARCHAR(50), run_id VARCHAR(36),
    loan_id VARCHAR(10), letter_lang VARCHAR(5), excess_paise DECIMAL(18,0), approved_by VARCHAR(500),
    released_by VARCHAR(100), released_at TIMESTAMP, text_sha256 VARCHAR(64), letter_text VARCHAR(20000));

CREATE TABLE IF NOT EXISTS {POLICY}.release_batches (
    batch_id VARCHAR(36), dataset_id VARCHAR(50), run_id VARCHAR(36), released_by VARCHAR(100),
    batch_note VARCHAR(500), released_at TIMESTAMP, letter_count DECIMAL(12,0), total_paise DECIMAL(18,0));

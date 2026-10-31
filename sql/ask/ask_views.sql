-- step: ASK_VIEWS
-- purpose: read-only views for ask-the-book over MCP. Each view is pinned to the latest completed audit run,
--   so an assistant cannot mix runs. Borrower names, raw evidence and SAHI_TRUTH are not exposed.
-- inputs: {OUT}.*, {POLICY}.practices, {POLICY}.settings, {RAW}.loans, {RAW}.branches
-- outputs: {ASK}.* views; the MCP user gets SELECT on {ASK} only (scripts/ask_setup.py)
-- not a pipeline step: run by `make ask-setup` after a load, no arithmetic beyond paise to rupees
CREATE SCHEMA IF NOT EXISTS {ASK};

CREATE OR REPLACE VIEW {ASK}.latest_run AS
SELECT run_id, dataset_id, started_at, finished_at, duration_ms, label
FROM {OUT}.audit_runs
WHERE status = 'DONE'
ORDER BY started_at DESC
LIMIT 1
COMMENT IS 'The audit run every other view in this schema is pinned to (latest completed run). duration_ms is the full audit inside Exasol';

CREATE OR REPLACE VIEW {ASK}.run_summary AS
SELECT s.loans_audited, s.tranches, s.periods_audited, s.posting_rows,
       s.posted_paise, s.fair_paise, s.refund_paise, CAST(s.refund_paise / 100 AS DECIMAL(18,2)) AS refund_rupees,
       s.refund_loans, s.refund_findings, s.ambiguous_paise, s.permitted_paise, s.permitted_loans,
       s.gap_tranches, s.gap_loans, s.gap_posted_paise, s.unexplained_periods, s.unexplained_loans, s.unexplained_excess_paise,
       s.undercharge_periods, s.conflict_tranches, s.fallback_tranches, s.fair_periods
FROM {OUT}.run_summary s
WHERE s.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'One row: book-level totals. refund_paise is the refund owed (REFUND, plus AMBIGUOUS when counted by policy). Gaps and unexplained are held out of the refund total';

CREATE OR REPLACE VIEW {ASK}.refund_ledger AS
SELECT l.loan_id, l.borrower_id, l.branch_id, l.product, l.practice_code, l.periods, l.days_affected,
       l.excess_paise, CAST(l.excess_paise / 100 AS DECIMAL(18,2)) AS excess_rupees, l.first_period, l.last_period
FROM {OUT}.refund_ledger l
WHERE l.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'Refund owed, one row per loan and RBI practice. Sum excess_paise for totals. practice_code: P1 sanction/agreement date, P2 cheque date, P3 full month, P4 advance EMI ignored, P5 EMI on sanctioned amount, AMB ambiguous';

CREATE OR REPLACE VIEW {ASK}.findings AS
SELECT f.finding_id, f.loan_id, f.borrower_id, f.branch_id, f.product, f.period_start, f.practice_code, f.status,
       f.days_affected, f.excess_paise, f.matched_convention_id, f.reason, f.sql_step_id
FROM {OUT}.findings f
WHERE f.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'One row per loan, billing month and practice, non-fair months only. status: REFUND, AMBIGUOUS, PERMITTED (disclosed, no refund), EVIDENCE_GAP, UNEXPLAINED, UNDERCHARGE. period_start is the first day of the billing month';

CREATE OR REPLACE VIEW {ASK}.money_in_hand AS
SELECT m.loan_id, m.tranche_no, m.amount_paise, m.payment_mode, m.resolved_date, m.resolved_source, m.confidence,
       m.conflict_flag, m.max_spread_days, m.missing_sources, m.available_sources
FROM {OUT}.money_in_hand m
WHERE m.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'Per tranche: the day the money actually reached the borrower, resolved from conflicting records. payment_mode e.g. CHEQUE, DD, NEFT, RTGS. confidence: CONFIRMED, FALLBACK, GAP (resolved_date NULL)';

CREATE OR REPLACE VIEW {ASK}.evidence_gaps AS
SELECT g.loan_id, g.tranche_no, g.branch_id, g.payment_mode, g.amount_paise, g.missing_source, g.available_sources,
       g.window_start, g.window_end, g.periods_affected, g.posted_paise_at_stake, g.suggested_query
FROM {OUT}.evidence_gaps g
WHERE g.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'Tranches the audit could not decide; kept out of the refund total. suggested_query is the drafted question to the branch';

CREATE OR REPLACE VIEW {ASK}.rollups AS
SELECT r.dimension, r.dim_value, r.status, r.loans, r.findings, r.excess_paise
FROM {OUT}.rollups r
WHERE r.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'Pre-aggregated totals. dimension is practice, branch, product or period; status as in findings';

CREATE OR REPLACE VIEW {ASK}.root_causes AS
SELECT c.branch_id, c.convention_id, c.practice_codes, c.loans, c.periods, c.excess_paise,
       c.first_period, c.last_period, c.earliest_sanction, c.latest_sanction
FROM {OUT}.root_causes c
WHERE c.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'What each branch''s loan system was actually doing: REFUND findings by branch and the convention that reproduced the postings';

CREATE OR REPLACE VIEW {ASK}.cohorts AS
SELECT c.branch_id, c.sanction_quarter, c.period_quarter, c.loans_in_cohort, c.loans_overcharged, c.excess_paise
FROM {OUT}.cohorts c
WHERE c.run_id = (SELECT run_id FROM {ASK}.latest_run)
COMMENT IS 'Sanction-quarter by charge-quarter overcharging per branch. A fix applied to new loans only shows as old sanction cohorts still overcharged';

CREATE OR REPLACE VIEW {ASK}.loans AS
SELECT l.loan_id, l.borrower_id, l.branch_id, b.branch_name, b.state_name, b.region, l.product,
       l.sanction_date, l.sanctioned_paise, l.tenure_months, l.status
FROM {RAW}.loans l
JOIN {RAW}.branches b ON b.branch_id = l.branch_id
COMMENT IS 'Loan master (no borrower names). product: HOME or PERSONAL. All data is synthetic';

CREATE OR REPLACE VIEW {ASK}.practices AS
SELECT p.practice_code, p.title, p.rbi_reference, p.introduced
FROM {POLICY}.practices p
COMMENT IS 'RBI practice codes used in findings and the refund ledger';

CREATE OR REPLACE VIEW {ASK}.policy_settings AS
SELECT s.setting_key, s.setting_value, s.description
FROM {POLICY}.settings s
COMMENT IS 'Current policy settings (interpretations the compliance team can change), e.g. whether a disclosed commitment fee is permitted';

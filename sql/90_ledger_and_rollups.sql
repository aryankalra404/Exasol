-- step: S90_LEDGER
-- purpose: refund ledger (refundable statuses only), evidence-gap work queue with a drafted branch query,
--          rollups, root causes (which LMS behaviour explains which loans), origination cohorts, the per-loan
--          figures a borrower letter may quote, interval-level proof for every finding, and a run summary.
-- inputs: {WORK}.findings, {WORK}.fp, {WORK}.mih, {WORK}.loan_base, {WORK}.fair_intervals, {WORK}.diff_intervals,
--         {RAW}.borrowers, {RAW}.branches, {WORK}.cfg
-- outputs: {OUT}.refund_ledger, evidence_gaps, rollups, root_causes, cohorts, letter_figures, balance_intervals,
--          excess_intervals, run_summary

CREATE OR REPLACE TABLE {WORK}.refundable AS
SELECT f.*
FROM {WORK}.findings f CROSS JOIN {WORK}.cfg g
WHERE f.status = 'REFUND' OR (f.status = 'AMBIGUOUS' AND g.include_ambiguous);

CREATE TABLE IF NOT EXISTS {OUT}.refund_ledger (
    run_id VARCHAR(36), borrower_id VARCHAR(10), loan_id VARCHAR(10), branch_id VARCHAR(10), product VARCHAR(10),
    practice_code VARCHAR(3), periods DECIMAL(5,0), days_affected DECIMAL(7,0), excess_paise DECIMAL(18,0),
    first_period DATE, last_period DATE, finding_ids VARCHAR(20000), sql_step_id VARCHAR(40));

INSERT INTO {OUT}.refund_ledger
SELECT '{RUN_ID}', borrower_id, loan_id, branch_id, product, practice_code, COUNT(DISTINCT period_start),
       SUM(days_affected), SUM(excess_paise), MIN(period_start), MAX(period_start),
       SUBSTR(GROUP_CONCAT(finding_id ORDER BY finding_id SEPARATOR ','), 1, 20000), 'S90_LEDGER'
FROM {WORK}.refundable
GROUP BY borrower_id, loan_id, branch_id, product, practice_code;

CREATE TABLE IF NOT EXISTS {OUT}.evidence_gaps (
    run_id VARCHAR(36), loan_id VARCHAR(10), tranche_no DECIMAL(3,0), branch_id VARCHAR(10), payment_mode VARCHAR(10),
    amount_paise DECIMAL(18,0), missing_source VARCHAR(100), available_sources VARCHAR(2000),
    window_start DATE, window_end DATE, periods_affected DECIMAL(5,0), posted_paise_at_stake DECIMAL(18,0),
    suggested_query VARCHAR(1000));

INSERT INTO {OUT}.evidence_gaps
SELECT '{RUN_ID}', m.loan_id, m.tranche_no, lb.branch_id, m.payment_mode, m.amount_paise, m.missing_sources,
       m.available_sources, m.ev_min, m.ev_max,
       (SELECT COUNT(*) FROM {WORK}.fp f WHERE f.loan_id = m.loan_id AND f.match_status = 'EVIDENCE_GAP'),
       (SELECT COALESCE(SUM(f.posted_paise), 0) FROM {WORK}.fp f WHERE f.loan_id = m.loan_id AND f.match_status = 'EVIDENCE_GAP'),
       SUBSTR('To ' || b.branch_name || ' branch (' || lb.branch_id || '): for loan ' || m.loan_id || ', tranche ' ||
       TO_CHAR(m.tranche_no) || ' (' || CASE m.payment_mode WHEN 'CHEQUE' THEN 'cheque' WHEN 'DD' THEN 'demand draft' ELSE m.payment_mode END ||
       '), please send the ' ||
       REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(m.missing_sources, ',', ' or '), 'HANDOVER_ACK', 'handover acknowledgement'),
               'RAIL_CREDIT', 'payment-rail credit'), 'LMS_DISB', 'loan-system disbursal'), 'CHEQUE_DATE', 'cheque') ||
       ' record showing the date the funds reached the ' ||
       CASE WHEN m.payment_mode IN ('CHEQUE', 'DD') THEN 'payee' ELSE 'beneficiary account' END ||
       '. Our records show: ' || m.available_sources || '.', 1, 1000)
FROM {WORK}.mih m
JOIN {WORK}.loan_base lb ON lb.loan_id = m.loan_id
JOIN {RAW}.branches b ON b.branch_id = lb.branch_id
WHERE m.confidence = 'GAP';

CREATE TABLE IF NOT EXISTS {OUT}.rollups (
    run_id VARCHAR(36), dimension VARCHAR(30), dim_value VARCHAR(50), status VARCHAR(15),
    loans DECIMAL(12,0), findings DECIMAL(12,0), excess_paise DECIMAL(18,0));

INSERT INTO {OUT}.rollups
SELECT '{RUN_ID}', d.dimension, d.dim_value, f.status, COUNT(DISTINCT f.loan_id), COUNT(*), SUM(f.excess_paise)
FROM {WORK}.findings f
JOIN {WORK}.loan_base lb ON lb.loan_id = f.loan_id
JOIN (
    SELECT finding_id, 'practice' AS dimension, COALESCE(practice_code, '-') AS dim_value FROM {WORK}.findings
    UNION ALL SELECT finding_id, 'branch', branch_id FROM {WORK}.findings
    UNION ALL SELECT finding_id, 'product', product FROM {WORK}.findings
    UNION ALL SELECT finding_id, 'period', TO_CHAR(period_start, 'YYYY-MM') FROM {WORK}.findings
) d ON d.finding_id = f.finding_id
GROUP BY d.dimension, d.dim_value, f.status;

-- root causes: one LMS behaviour (matched convention) at one branch, and every loan it explains
CREATE TABLE IF NOT EXISTS {OUT}.root_causes (
    run_id VARCHAR(36), branch_id VARCHAR(10), convention_id VARCHAR(40), practice_codes VARCHAR(20),
    loans DECIMAL(12,0), periods DECIMAL(12,0), excess_paise DECIMAL(18,0), first_period DATE, last_period DATE,
    earliest_sanction DATE, latest_sanction DATE);

INSERT INTO {OUT}.root_causes
SELECT '{RUN_ID}', f.branch_id, f.matched_convention_id, MAX(c.practice_codes),
       COUNT(DISTINCT f.loan_id), COUNT(DISTINCT f.loan_id || TO_CHAR(f.period_start)), SUM(f.excess_paise),
       MIN(f.period_start), MAX(f.period_start), MIN(lb.sanction_date), MAX(lb.sanction_date)
FROM {WORK}.refundable f
JOIN {WORK}.loan_base lb ON lb.loan_id = f.loan_id
LEFT JOIN {POLICY}.conventions c ON c.convention_id = f.matched_convention_id
WHERE f.status = 'REFUND'
GROUP BY f.branch_id, f.matched_convention_id;

-- cohorts: by branch and quarter of sanction, how many loans were still being overcharged in each period quarter.
-- A fix applied to new loans only shows up as old cohorts that keep getting charged after newer ones stop.
CREATE TABLE IF NOT EXISTS {OUT}.cohorts (
    run_id VARCHAR(36), branch_id VARCHAR(10), sanction_quarter VARCHAR(7), period_quarter VARCHAR(7),
    loans_in_cohort DECIMAL(12,0), loans_overcharged DECIMAL(12,0), excess_paise DECIMAL(18,0));

INSERT INTO {OUT}.cohorts
SELECT '{RUN_ID}', lb.branch_id,
       TO_CHAR(lb.sanction_date, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(lb.sanction_date) / 3)),
       TO_CHAR(f.period_start, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(f.period_start) / 3)),
       MAX(coh.n), COUNT(DISTINCT CASE WHEN r.loan_id IS NOT NULL THEN f.loan_id END), COALESCE(SUM(r.excess_paise), 0)
FROM {WORK}.fp f
JOIN {WORK}.loan_base lb ON lb.loan_id = f.loan_id
JOIN (SELECT branch_id, TO_CHAR(sanction_date, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(sanction_date) / 3)) AS q, COUNT(*) AS n
      FROM {WORK}.loan_base GROUP BY branch_id, TO_CHAR(sanction_date, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(sanction_date) / 3))) coh
  ON coh.branch_id = lb.branch_id AND coh.q = TO_CHAR(lb.sanction_date, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(lb.sanction_date) / 3))
LEFT JOIN (SELECT loan_id, period_start, SUM(excess_paise) AS excess_paise FROM {WORK}.refundable
           WHERE status = 'REFUND' GROUP BY loan_id, period_start) r
  ON r.loan_id = f.loan_id AND r.period_start = f.period_start
GROUP BY lb.branch_id,
         TO_CHAR(lb.sanction_date, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(lb.sanction_date) / 3)),
         TO_CHAR(f.period_start, 'YYYY') || '-Q' || TO_CHAR(CEIL(MONTH(f.period_start) / 3));

-- figures a borrower letter may quote, one row per loan and practice plus a TOTAL row
CREATE TABLE IF NOT EXISTS {OUT}.letter_figures (
    run_id VARCHAR(36), loan_id VARCHAR(10), borrower_id VARCHAR(10), display_name VARCHAR(100),
    preferred_language VARCHAR(5), product VARCHAR(10), branch_name VARCHAR(100), line_key VARCHAR(10),
    periods DECIMAL(5,0), days_affected DECIMAL(7,0), excess_paise DECIMAL(18,0), first_period DATE, last_period DATE);

INSERT INTO {OUT}.letter_figures
SELECT '{RUN_ID}', r.loan_id, r.borrower_id, bo.display_name, bo.preferred_language, lb.product, b.branch_name,
       COALESCE(r.practice_code, 'TOTAL'),
       COUNT(DISTINCT r.period_start), SUM(r.days_affected), SUM(r.excess_paise), MIN(r.period_start), MAX(r.period_start)
FROM {WORK}.refundable r
JOIN {WORK}.loan_base lb ON lb.loan_id = r.loan_id
JOIN {RAW}.borrowers bo ON bo.borrower_id = r.borrower_id
JOIN {RAW}.branches b ON b.branch_id = lb.branch_id
GROUP BY GROUPING SETS ((r.loan_id, r.borrower_id, bo.display_name, bo.preferred_language, lb.product, b.branch_name, r.practice_code),
                        (r.loan_id, r.borrower_id, bo.display_name, bo.preferred_language, lb.product, b.branch_name));

-- interval-level proof for loans with any non-fair finding: the fair path, and the extra balance each
-- matched convention charged on, with each interval's exact numerator
CREATE TABLE IF NOT EXISTS {OUT}.balance_intervals (
    run_id VARCHAR(36), loan_id VARCHAR(10), period_start DATE, interval_start DATE, interval_end DATE,
    balance_paise DECIMAL(18,0), annual_rate_pct DECIMAL(9,6), days DECIMAL(5,0), numerator DECIMAL(36,0));

INSERT INTO {OUT}.balance_intervals
SELECT '{RUN_ID}', fi.loan_id, fi.period_start, fi.i_start, fi.i_end, fi.bal, fi.rate_micro / 1000000, fi.days, fi.numerator
FROM {WORK}.fair_intervals fi
WHERE fi.loan_id IN (SELECT loan_id FROM {WORK}.findings);

CREATE TABLE IF NOT EXISTS {OUT}.excess_intervals (
    run_id VARCHAR(36), loan_id VARCHAR(10), period_start DATE, convention_id VARCHAR(40), interval_start DATE,
    interval_end DATE, extra_balance_paise DECIMAL(18,0), fee_balance_paise DECIMAL(18,0), annual_rate_pct DECIMAL(9,6),
    fee_rate_pct DECIMAL(9,6), days DECIMAL(5,0), numerator DECIMAL(36,0));

INSERT INTO {OUT}.excess_intervals
SELECT '{RUN_ID}', d.loan_id, d.period_start, d.convention_id, d.i_start, d.i_end, d.bal, d.fee,
       d.rate_micro / 1000000, d.fee_micro / 1000000, d.days, d.numerator
FROM {WORK}.diff_intervals d
JOIN {WORK}.fp f ON f.loan_id = d.loan_id AND f.period_start = d.period_start AND f.matched_convention_id = d.convention_id
WHERE f.match_status <> 'FAIR';

CREATE TABLE IF NOT EXISTS {OUT}.run_summary (
    run_id VARCHAR(36), loans_audited DECIMAL(12,0), tranches DECIMAL(12,0), periods_audited DECIMAL(12,0),
    posting_rows DECIMAL(12,0), posted_paise DECIMAL(18,0), fair_paise DECIMAL(18,0),
    refund_paise DECIMAL(18,0), refund_loans DECIMAL(12,0), refund_findings DECIMAL(12,0),
    ambiguous_paise DECIMAL(18,0), permitted_paise DECIMAL(18,0), permitted_loans DECIMAL(12,0),
    gap_tranches DECIMAL(12,0), gap_loans DECIMAL(12,0), gap_posted_paise DECIMAL(18,0),
    unexplained_periods DECIMAL(12,0), unexplained_loans DECIMAL(12,0), unexplained_excess_paise DECIMAL(18,0),
    undercharge_periods DECIMAL(12,0), conflict_tranches DECIMAL(12,0), fallback_tranches DECIMAL(12,0),
    fair_periods DECIMAL(12,0));

INSERT INTO {OUT}.run_summary
SELECT '{RUN_ID}',
    (SELECT COUNT(*) FROM {WORK}.loan_base),
    (SELECT COUNT(*) FROM {WORK}.mih),
    (SELECT COUNT(*) FROM {WORK}.fp),
    (SELECT COUNT(*) FROM {RAW}.interest_postings),
    (SELECT SUM(posted_paise) FROM {WORK}.fp),
    (SELECT SUM(fair_paise) FROM {WORK}.fp),
    (SELECT COALESCE(SUM(excess_paise), 0) FROM {WORK}.refundable),
    (SELECT COUNT(DISTINCT loan_id) FROM {WORK}.refundable),
    (SELECT COUNT(*) FROM {WORK}.refundable),
    (SELECT COALESCE(SUM(excess_paise), 0) FROM {WORK}.findings WHERE status = 'AMBIGUOUS'),
    (SELECT COALESCE(SUM(excess_paise), 0) FROM {WORK}.findings WHERE status = 'PERMITTED'),
    (SELECT COUNT(DISTINCT loan_id) FROM {WORK}.findings WHERE status = 'PERMITTED'),
    (SELECT COUNT(*) FROM {WORK}.mih WHERE confidence = 'GAP'),
    (SELECT COUNT(DISTINCT loan_id) FROM {WORK}.mih WHERE confidence = 'GAP'),
    (SELECT COALESCE(SUM(posted_paise), 0) FROM {WORK}.fp WHERE match_status = 'EVIDENCE_GAP'),
    (SELECT COUNT(*) FROM {WORK}.fp WHERE match_status = 'UNEXPLAINED'),
    (SELECT COUNT(DISTINCT loan_id) FROM {WORK}.fp WHERE match_status = 'UNEXPLAINED'),
    (SELECT COALESCE(SUM(excess_paise), 0) FROM {WORK}.fp WHERE match_status = 'UNEXPLAINED'),
    (SELECT COUNT(*) FROM {WORK}.fp WHERE match_status = 'UNDERCHARGE'),
    (SELECT COUNT(*) FROM {WORK}.mih WHERE conflict_flag),
    (SELECT COUNT(*) FROM {WORK}.mih WHERE confidence = 'FALLBACK'),
    (SELECT COUNT(*) FROM {WORK}.fp WHERE match_status = 'FAIR')
FROM DUAL;

-- step: S10_RUN_SETUP
-- purpose: snapshot policy settings for this run, find the audit window from the data, build month and
--          rate-span helpers. Nothing here is hardcoded to a dataset: the window comes from the postings.
-- inputs: {POLICY}.settings, {RAW}.loans, {RAW}.interest_postings, {RAW}.rate_history, {RAW}.kfs
-- outputs: {WORK}.cfg, {WORK}.audit_window, {WORK}.periods, {WORK}.rate_spans, {WORK}.loan_base

CREATE OR REPLACE TABLE {WORK}.cfg AS
SELECT
    CAST(MAX(CASE WHEN setting_key = 'conflict_tolerance_days' THEN setting_value END) AS DECIMAL(5,0)) AS conflict_tol_days,
    CAST(MAX(CASE WHEN setting_key = 'match_tolerance_paise' THEN setting_value END) AS DECIMAL(18,0)) AS match_tol_paise,
    MAX(CASE WHEN setting_key = 'allow_lms_fallback_electronic' THEN LOWER(setting_value) END) = 'true' AS allow_fallback,
    MAX(CASE WHEN setting_key = 'commitment_fee_permitted_if_disclosed' THEN LOWER(setting_value) END) = 'true' AS permit_cfee,
    MAX(CASE WHEN setting_key = 'include_ambiguous_in_refund_total' THEN LOWER(setting_value) END) = 'true' AS include_ambiguous
FROM {POLICY}.settings;

CREATE OR REPLACE TABLE {WORK}.audit_window AS
SELECT
    LEAST((SELECT MIN(TRUNC(sanction_date, 'MM')) FROM {RAW}.loans),
          (SELECT COALESCE(MIN(TRUNC(period_start, 'MM')), DATE '9999-12-01') FROM {RAW}.interest_postings)) AS data_start,
    (SELECT MAX(period_end) FROM {RAW}.interest_postings) AS audit_end
FROM DUAL;

-- one row per loan per billing month, from the sanction month (or an earlier posting, so that no posting can
-- fall outside the audit) to the end of the audit window
CREATE OR REPLACE TABLE {WORK}.periods AS
WITH months AS (
    SELECT ADD_MONTHS(w.data_start, CAST(n.lvl - 1 AS DECIMAL(5,0))) AS period_start
    FROM (SELECT LEVEL AS lvl FROM DUAL CONNECT BY LEVEL <= 1200) n
    CROSS JOIN {WORK}.audit_window w
    WHERE ADD_MONTHS(w.data_start, CAST(n.lvl - 1 AS DECIMAL(5,0))) < w.audit_end
)
SELECT l.loan_id, m.period_start, ADD_MONTHS(m.period_start, 1) AS period_end
FROM {RAW}.loans l
LEFT JOIN (SELECT loan_id, MIN(TRUNC(period_start, 'MM')) AS first_posted FROM {RAW}.interest_postings GROUP BY loan_id) fp
  ON fp.loan_id = l.loan_id
JOIN months m ON m.period_start >= LEAST(TRUNC(l.sanction_date, 'MM'), COALESCE(fp.first_posted, TRUNC(l.sanction_date, 'MM')));

-- rate in force over [span_start, span_end). Before the first rate row the initial rate applies.
CREATE OR REPLACE TABLE {WORK}.rate_spans AS
SELECT
    loan_id,
    CASE WHEN rn = 1 THEN DATE '1900-01-01' ELSE effective_date END AS span_start,
    COALESCE(next_date, DATE '9999-12-31') AS span_end,
    CAST(annual_rate_pct * 1000000 AS DECIMAL(18,0)) AS rate_micro
FROM (
    SELECT loan_id, effective_date, annual_rate_pct,
           ROW_NUMBER() OVER (PARTITION BY loan_id ORDER BY effective_date) AS rn,
           LEAD(effective_date) OVER (PARTITION BY loan_id ORDER BY effective_date) AS next_date
    FROM {RAW}.rate_history
) r;

-- per-loan facts used by later steps. divisor_den is the exact denominator of one interval's interest:
-- interest = balance_paise * rate_micro * days / (100 * 1,000,000 * divisor)
CREATE OR REPLACE TABLE {WORK}.loan_base AS
SELECT
    l.loan_id, l.borrower_id, l.branch_id, l.product, l.sanction_date, l.agreement_date, l.sanctioned_paise,
    k.day_count_basis,
    CASE WHEN k.day_count_basis = '30E_360' THEN 360 ELSE 365 END AS divisor,
    CAST(100000000 * (CASE WHEN k.day_count_basis = '30E_360' THEN 360 ELSE 365 END) AS DECIMAL(18,0)) AS den,
    k.commitment_fee_rate_pct,
    CAST(COALESCE(k.commitment_fee_rate_pct, 0) * 1000000 AS DECIMAL(18,0)) AS fee_micro,
    (SELECT SUM(t.amount_paise) FROM {RAW}.tranches t WHERE t.loan_id = l.loan_id) AS disbursed_paise,
    (SELECT MIN(r.value_date) FROM {RAW}.receipts r WHERE r.loan_id = l.loan_id AND r.kind = 'CLOSURE') AS closure_date
FROM {RAW}.loans l
JOIN {RAW}.kfs k ON k.loan_id = l.loan_id;

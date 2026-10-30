-- step: S60_CANDIDATE_CONVENTIONS
-- purpose: recompute every period whose posting differs from fair interest under every candidate convention,
--          side by side. Candidate numerator = fair numerator + that convention's difference numerator, so each
--          candidate is exact and rounded once, exactly like the fair figure.
-- inputs: {WORK}.period_audit, {WORK}.diff_intervals, {WORK}.loan_conv, {WORK}.cfg
-- outputs: {WORK}.candidates

CREATE OR REPLACE TABLE {WORK}.diff_period AS
SELECT loan_id, convention_id, period_start, SUM(numerator) AS n_diff, SUM(calendar_days) AS days_affected
FROM {WORK}.diff_intervals
GROUP BY loan_id, convention_id, period_start;

CREATE OR REPLACE TABLE {WORK}.candidates AS
SELECT pa.loan_id, pa.period_start, lc.convention_id,
       CAST(SIGN(pa.n_fair + COALESCE(dp.n_diff, 0)) * DIV(2 * ABS(pa.n_fair + COALESCE(dp.n_diff, 0)) + pa.den, 2 * pa.den)
            AS DECIMAL(18,0)) AS interest_paise,
       COALESCE(dp.days_affected, 0) AS days_affected
FROM {WORK}.period_audit pa
CROSS JOIN {WORK}.cfg g
JOIN {WORK}.loan_conv lc ON lc.loan_id = pa.loan_id
LEFT JOIN {WORK}.diff_period dp
       ON dp.loan_id = pa.loan_id AND dp.convention_id = lc.convention_id AND dp.period_start = pa.period_start
WHERE ABS(pa.posted_paise - pa.fair_paise) > g.match_tol_paise;

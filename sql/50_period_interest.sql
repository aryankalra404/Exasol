-- step: S50_PERIOD_INTEREST
-- purpose: entitled (fair) interest per loan per billing period, and the lender's net posted interest after
--          reversals. Rounding happens here, once per period: half up, on the exact sum of the numerators.
--          round_half_up(N / D) = sign(N) * DIV(2|N| + D, 2D), half away from zero, all in exact integers.
--          (N is only ever negative in a provisional EVIDENCE_GAP period.)
-- inputs: {WORK}.fair_intervals, {WORK}.loan_base, {RAW}.interest_postings, {WORK}.periods
-- outputs: {WORK}.period_audit

CREATE OR REPLACE TABLE {WORK}.fair_period AS
SELECT f.loan_id, f.period_start, SUM(f.numerator) AS n_fair
FROM {WORK}.fair_intervals f
GROUP BY f.loan_id, f.period_start;

CREATE OR REPLACE TABLE {WORK}.posted_period AS
SELECT loan_id, period_start,
       SUM(posted_paise) AS posted_paise,
       COUNT(*) AS posting_rows,
       MAX(CASE WHEN is_manual THEN 1 ELSE 0 END) = 1 AS has_manual,
       MAX(CASE WHEN reverses_posting_id IS NOT NULL THEN 1 ELSE 0 END) = 1 AS has_reversal,
       GROUP_CONCAT(posting_id ORDER BY posting_id SEPARATOR ',') AS posting_ids
FROM {RAW}.interest_postings
GROUP BY loan_id, period_start;

-- every (loan, period) where either side is non-zero
CREATE OR REPLACE TABLE {WORK}.period_audit AS
SELECT
    p.loan_id, p.period_start, p.period_end,
    COALESCE(fp.n_fair, 0) AS n_fair,
    CAST(SIGN(COALESCE(fp.n_fair, 0)) * DIV(2 * ABS(COALESCE(fp.n_fair, 0)) + lb.den, 2 * lb.den) AS DECIMAL(18,0)) AS fair_paise,
    CAST(COALESCE(pp.posted_paise, 0) AS DECIMAL(18,0)) AS posted_paise,
    pp.posting_ids, COALESCE(pp.has_manual, FALSE) AS has_manual, COALESCE(pp.has_reversal, FALSE) AS has_reversal,
    lb.den
FROM {WORK}.periods p
JOIN {WORK}.loan_base lb ON lb.loan_id = p.loan_id
LEFT JOIN {WORK}.fair_period fp ON fp.loan_id = p.loan_id AND fp.period_start = p.period_start
LEFT JOIN {WORK}.posted_period pp ON pp.loan_id = p.loan_id AND pp.period_start = p.period_start
WHERE COALESCE(fp.n_fair, 0) <> 0 OR pp.loan_id IS NOT NULL;

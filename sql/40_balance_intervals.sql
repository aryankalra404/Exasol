-- step: S40_BALANCE_INTERVALS
-- purpose: build constant-balance, constant-rate intervals, clipped to billing periods. Day-exact without a
--          row per day. Each interval carries the exact integer numerator of its interest:
--          balance_paise * rate_micro * days (+ fee balance * fee_micro * days). No division yet.
-- inputs: {WORK}.fair_events, {WORK}.diff_events, {WORK}.periods, {WORK}.rate_spans, {WORK}.loan_base
-- outputs: {WORK}.fair_intervals, {WORK}.diff_intervals

CREATE OR REPLACE TABLE {WORK}.fair_segments AS
SELECT loan_id, seg_start, seg_end, bal
FROM (
    SELECT loan_id, event_date AS seg_start,
           COALESCE(LEAD(event_date) OVER (PARTITION BY loan_id ORDER BY event_date), DATE '9999-12-31') AS seg_end,
           SUM(d_bal) OVER (PARTITION BY loan_id ORDER BY event_date ROWS UNBOUNDED PRECEDING) AS bal
    FROM {WORK}.fair_events
) s
WHERE bal <> 0;

CREATE OR REPLACE TABLE {WORK}.diff_segments AS
SELECT loan_id, convention_id, seg_start, seg_end, bal, fee
FROM (
    SELECT loan_id, convention_id, event_date AS seg_start,
           COALESCE(LEAD(event_date) OVER (PARTITION BY loan_id, convention_id ORDER BY event_date), DATE '9999-12-31') AS seg_end,
           SUM(d_bal) OVER (PARTITION BY loan_id, convention_id ORDER BY event_date ROWS UNBOUNDED PRECEDING) AS bal,
           SUM(d_fee) OVER (PARTITION BY loan_id, convention_id ORDER BY event_date ROWS UNBOUNDED PRECEDING) AS fee
    FROM {WORK}.diff_events
) s
WHERE bal <> 0 OR fee <> 0;

-- 30E/360 day count: day of month capped at 30, so f(date) = 360*y + 30*m + min(d, 30) and days = f(end) - f(start).
-- This telescopes, so splitting a period into intervals never changes its total day count.
CREATE OR REPLACE TABLE {WORK}.fair_intervals AS
SELECT loan_id, period_start, i_start, i_end, bal, rate_micro, days,
       CAST(bal AS DECIMAL(36,0)) * rate_micro * days AS numerator
FROM (
    SELECT loan_id, period_start, i_start, i_end, bal, rate_micro,
           CASE WHEN day_count_basis = '30E_360'
                THEN (360 * YEAR(i_end) + 30 * MONTH(i_end) + LEAST(DAY(i_end), 30))
                   - (360 * YEAR(i_start) + 30 * MONTH(i_start) + LEAST(DAY(i_start), 30))
                ELSE DAYS_BETWEEN(i_end, i_start) END AS days
    FROM (
        SELECT s.loan_id, p.period_start,
               GREATEST(s.seg_start, p.period_start, r.span_start) AS i_start,
               LEAST(s.seg_end, p.period_end, r.span_end) AS i_end,
               s.bal, r.rate_micro, lb.day_count_basis
        FROM {WORK}.fair_segments s
        JOIN {WORK}.periods p ON p.loan_id = s.loan_id AND p.period_start < s.seg_end AND p.period_end > s.seg_start
        JOIN {WORK}.rate_spans r ON r.loan_id = s.loan_id AND r.span_start < LEAST(s.seg_end, p.period_end)
                                 AND r.span_end > GREATEST(s.seg_start, p.period_start)
        JOIN {WORK}.loan_base lb ON lb.loan_id = s.loan_id
    ) x
) y;

CREATE OR REPLACE TABLE {WORK}.diff_intervals AS
SELECT loan_id, convention_id, period_start, i_start, i_end, bal, fee, rate_micro, fee_micro, days,
       CAST(DAYS_BETWEEN(i_end, i_start) AS DECIMAL(5,0)) AS calendar_days,
       (CAST(bal AS DECIMAL(36,0)) * rate_micro + CAST(fee AS DECIMAL(36,0)) * fee_micro) * days AS numerator
FROM (
    SELECT loan_id, convention_id, period_start, i_start, i_end, bal, fee, rate_micro, fee_micro,
           CASE WHEN day_count_basis = '30E_360'
                THEN (360 * YEAR(i_end) + 30 * MONTH(i_end) + LEAST(DAY(i_end), 30))
                   - (360 * YEAR(i_start) + 30 * MONTH(i_start) + LEAST(DAY(i_start), 30))
                ELSE DAYS_BETWEEN(i_end, i_start) END AS days
    FROM (
        SELECT s.loan_id, s.convention_id, p.period_start,
               GREATEST(s.seg_start, p.period_start, r.span_start) AS i_start,
               LEAST(s.seg_end, p.period_end, r.span_end) AS i_end,
               s.bal, s.fee, r.rate_micro, lb.fee_micro, lb.day_count_basis
        FROM {WORK}.diff_segments s
        JOIN {WORK}.periods p ON p.loan_id = s.loan_id AND p.period_start < s.seg_end AND p.period_end > s.seg_start
        JOIN {WORK}.rate_spans r ON r.loan_id = s.loan_id AND r.span_start < LEAST(s.seg_end, p.period_end)
                                 AND r.span_end > GREATEST(s.seg_start, p.period_start)
        JOIN {WORK}.loan_base lb ON lb.loan_id = s.loan_id
    ) x
) y;

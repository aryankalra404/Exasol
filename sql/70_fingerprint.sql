-- step: S70_FINGERPRINT
-- purpose: name the convention the LMS actually applied: the candidate that reproduces the posting to the paisa.
--          Includes the permitted check: a disclosed commitment fee that reproduces the posting is PERMITTED when
--          policy allows it. Nothing is guessed: no match means UNEXPLAINED, a GAP tranche means EVIDENCE_GAP.
-- inputs: {WORK}.period_audit, {WORK}.candidates, {POLICY}.conventions, {WORK}.mih, {WORK}.cfg
-- outputs: {WORK}.fp, {OUT}.fingerprints

CREATE OR REPLACE TABLE {WORK}.gap_period AS
SELECT pa.loan_id, pa.period_start,
       GROUP_CONCAT(DISTINCT m.tranche_no ORDER BY m.tranche_no SEPARATOR ',') AS gap_tranches
FROM {WORK}.period_audit pa
JOIN {WORK}.mih m ON m.loan_id = pa.loan_id AND m.confidence = 'GAP'
                  AND m.ev_min < pa.period_end AND m.ev_max >= pa.period_start
GROUP BY pa.loan_id, pa.period_start;

CREATE OR REPLACE TABLE {WORK}.matches AS
SELECT c.loan_id, c.period_start, c.convention_id, c.interest_paise, c.days_affected,
       cv.unfair_dimension_count, cv.is_permitted_variant, cv.practice_codes,
       (cv.is_permitted_variant AND g.permit_cfee) AS is_permitted
FROM {WORK}.candidates c
CROSS JOIN {WORK}.cfg g
JOIN {WORK}.period_audit pa ON pa.loan_id = c.loan_id AND pa.period_start = c.period_start
JOIN {POLICY}.conventions cv ON cv.convention_id = c.convention_id
WHERE ABS(c.interest_paise - pa.posted_paise) <= g.match_tol_paise;

-- several conventions can reproduce one period (e.g. "from sanction" and "full month" give the same figure when
-- money arrived early in a month that started after sanction). The loan's own posting history breaks the tie:
-- prefer the convention that reproduces the most of this loan's differing periods, then the fewest non-fair
-- dimensions. Only if that still leaves different practices is the period AMBIGUOUS.
CREATE OR REPLACE TABLE {WORK}.conv_support AS
SELECT m.loan_id, m.convention_id, COUNT(*) AS support
FROM {WORK}.matches m
LEFT JOIN {WORK}.gap_period gp ON gp.loan_id = m.loan_id AND gp.period_start = m.period_start
WHERE NOT m.is_permitted
  AND gp.loan_id IS NULL  -- evidence-gap periods use a provisional date, so they do not vote
GROUP BY m.loan_id, m.convention_id;

CREATE OR REPLACE TABLE {WORK}.best_match AS
SELECT loan_id, period_start,
       COUNT(*) AS n_tied,
       COUNT(DISTINCT practice_codes) AS n_practice_sets,
       GROUP_CONCAT(convention_id ORDER BY is_permitted_variant, convention_id SEPARATOR ';') AS tied_ids,
       MAX(support) AS support
FROM (
    SELECT m.*, s.support,
           DENSE_RANK() OVER (PARTITION BY m.loan_id, m.period_start
                              ORDER BY s.support DESC, m.unfair_dimension_count) AS rk
    FROM {WORK}.matches m
    JOIN {WORK}.conv_support s ON s.loan_id = m.loan_id AND s.convention_id = m.convention_id
    WHERE NOT m.is_permitted
) x
WHERE rk = 1
GROUP BY loan_id, period_start;

CREATE OR REPLACE TABLE {WORK}.closest AS
SELECT loan_id, period_start, convention_id, diff_paise
FROM (
    SELECT c.loan_id, c.period_start, c.convention_id, c.interest_paise - pa.posted_paise AS diff_paise,
           ROW_NUMBER() OVER (PARTITION BY c.loan_id, c.period_start
                              ORDER BY ABS(c.interest_paise - pa.posted_paise), c.convention_id) AS rn
    FROM {WORK}.candidates c
    JOIN {WORK}.period_audit pa ON pa.loan_id = c.loan_id AND pa.period_start = c.period_start
) x
WHERE rn = 1;

CREATE OR REPLACE TABLE {WORK}.fp AS
SELECT
    pa.loan_id, pa.period_start, pa.period_end, pa.posted_paise, pa.fair_paise,
    pa.posted_paise - pa.fair_paise AS excess_paise,
    pa.posting_ids, pa.has_manual, pa.has_reversal,
    gp.gap_tranches,
    CASE
        WHEN gp.loan_id IS NOT NULL THEN 'EVIDENCE_GAP'
        WHEN ABS(pa.posted_paise - pa.fair_paise) <= g.match_tol_paise THEN 'FAIR'
        WHEN pm.loan_id IS NOT NULL THEN 'PERMITTED'
        WHEN bm.loan_id IS NOT NULL AND pa.posted_paise < pa.fair_paise THEN 'UNDERCHARGE'
        WHEN bm.loan_id IS NOT NULL AND bm.n_practice_sets = 1 THEN 'MATCHED'
        WHEN bm.loan_id IS NOT NULL THEN 'AMBIGUOUS'
        WHEN pa.posted_paise < pa.fair_paise THEN 'UNDERCHARGE'
        ELSE 'UNEXPLAINED'
    END AS match_status,
    CASE WHEN gp.loan_id IS NOT NULL THEN NULL
         WHEN ABS(pa.posted_paise - pa.fair_paise) <= g.match_tol_paise THEN 'MIH|DIS|NET|EXACT'
         WHEN pm.loan_id IS NOT NULL THEN pm.convention_id
         WHEN bm.loan_id IS NOT NULL THEN REGEXP_SUBSTR(bm.tied_ids, '[^;]+')
    END AS matched_convention_id,
    CASE WHEN bm.n_tied > 1 THEN REPLACE(bm.tied_ids, ';', ',') END AS tied_convention_ids,
    CASE WHEN bm.loan_id IS NULL AND pm.loan_id IS NULL THEN cl.convention_id END AS closest_convention_id,
    CASE WHEN bm.loan_id IS NULL AND pm.loan_id IS NULL THEN cl.diff_paise END AS closest_diff_paise
FROM {WORK}.period_audit pa
CROSS JOIN {WORK}.cfg g
LEFT JOIN {WORK}.gap_period gp ON gp.loan_id = pa.loan_id AND gp.period_start = pa.period_start
LEFT JOIN (SELECT loan_id, period_start, MIN(convention_id) AS convention_id FROM {WORK}.matches WHERE is_permitted
           GROUP BY loan_id, period_start) pm
       ON pm.loan_id = pa.loan_id AND pm.period_start = pa.period_start
LEFT JOIN {WORK}.best_match bm ON bm.loan_id = pa.loan_id AND bm.period_start = pa.period_start
LEFT JOIN {WORK}.closest cl ON cl.loan_id = pa.loan_id AND cl.period_start = pa.period_start;

CREATE TABLE IF NOT EXISTS {OUT}.fingerprints (
    run_id VARCHAR(36), loan_id VARCHAR(10), period_start DATE, posted_paise DECIMAL(18,0), fair_paise DECIMAL(18,0),
    excess_paise DECIMAL(18,0), match_status VARCHAR(15), matched_convention_id VARCHAR(40),
    tied_convention_ids VARCHAR(2000), closest_convention_id VARCHAR(40), closest_diff_paise DECIMAL(18,0),
    posting_ids VARCHAR(2000), has_manual BOOLEAN, gap_tranches VARCHAR(100));

INSERT INTO {OUT}.fingerprints
SELECT '{RUN_ID}', loan_id, period_start, posted_paise, fair_paise, excess_paise, match_status, matched_convention_id,
       tied_convention_ids, closest_convention_id, closest_diff_paise, posting_ids, has_manual, gap_tranches
FROM {WORK}.fp;

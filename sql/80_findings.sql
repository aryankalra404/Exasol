-- step: S80_FINDINGS
-- purpose: one finding per loan, period and practice. Excess is always posted minus fair; attribution only
--          labels it. A matched convention with several unfair dimensions is split by adding dimensions one at a
--          time in a fixed order (start basis, principal basis, advance treatment, month rounding). The
--          increments telescope, so they sum to the excess exactly.
-- inputs: {WORK}.fp, {WORK}.matches, {WORK}.candidates, {WORK}.loan_base, {WORK}.mih, {POLICY}.conventions
-- outputs: {WORK}.findings, {OUT}.findings

CREATE OR REPLACE TABLE {WORK}.loan_evidence AS
SELECT loan_id, GROUP_CONCAT(evidence_ids ORDER BY tranche_no SEPARATOR ',') AS evidence_ids
FROM {WORK}.mih GROUP BY loan_id;

CREATE OR REPLACE TABLE {WORK}.attribution AS
WITH m AS (
    SELECT f.loan_id, f.period_start, f.posted_paise, f.fair_paise, f.matched_convention_id AS conv,
           REGEXP_SUBSTR(f.matched_convention_id, '[^|]+', 1, 1) AS sc,
           REGEXP_SUBSTR(f.matched_convention_id, '[^|]+', 1, 2) AS pc,
           REGEXP_SUBSTR(f.matched_convention_id, '[^|]+', 1, 3) AS ac,
           REGEXP_SUBSTR(f.matched_convention_id, '[^|]+', 1, 4) AS mc
    FROM {WORK}.fp f
    WHERE f.match_status = 'MATCHED' AND f.matched_convention_id <> 'CFEE'
),
steps AS (
    SELECT m.*,
           m.sc || '|DIS|NET|EXACT' AS c1,
           m.sc || '|' || m.pc || '|NET|EXACT' AS c2,
           m.sc || '|' || m.pc || '|' || m.ac || '|EXACT' AS c3
    FROM m
),
vals AS (
    -- interest after each step; the fair convention is the fair figure, the matched one is the posting
    SELECT s.*,
           CASE WHEN s.c1 = s.conv THEN s.posted_paise WHEN s.c1 = 'MIH|DIS|NET|EXACT' THEN s.fair_paise ELSE k1.interest_paise END AS i1,
           CASE WHEN s.c2 = s.conv THEN s.posted_paise WHEN s.c2 = 'MIH|DIS|NET|EXACT' THEN s.fair_paise ELSE k2.interest_paise END AS i2,
           CASE WHEN s.c3 = s.conv THEN s.posted_paise WHEN s.c3 = 'MIH|DIS|NET|EXACT' THEN s.fair_paise ELSE k3.interest_paise END AS i3
    FROM steps s
    LEFT JOIN {WORK}.candidates k1 ON k1.loan_id = s.loan_id AND k1.period_start = s.period_start AND k1.convention_id = s.c1
    LEFT JOIN {WORK}.candidates k2 ON k2.loan_id = s.loan_id AND k2.period_start = s.period_start AND k2.convention_id = s.c2
    LEFT JOIN {WORK}.candidates k3 ON k3.loan_id = s.loan_id AND k3.period_start = s.period_start AND k3.convention_id = s.c3
)
SELECT loan_id, period_start, conv, CASE sc WHEN 'CHQ' THEN 'P2' ELSE 'P1' END AS practice_code, i1 - fair_paise AS amount_paise, 1 AS step_no
FROM vals WHERE sc <> 'MIH'
UNION ALL
SELECT loan_id, period_start, conv, 'P5', i2 - i1, 2 FROM vals WHERE pc = 'SAN'
UNION ALL
SELECT loan_id, period_start, conv, 'P4', i3 - i2, 3 FROM vals WHERE ac = 'IGN'
UNION ALL
SELECT loan_id, period_start, conv, 'P3', posted_paise - i3, 4 FROM vals WHERE mc = 'FULL'
UNION ALL
-- a disclosed commitment fee that policy does not permit is charging before disbursement: P1
SELECT loan_id, period_start, matched_convention_id, 'P1', posted_paise - fair_paise, 1
FROM {WORK}.fp WHERE match_status = 'MATCHED' AND matched_convention_id = 'CFEE';

CREATE OR REPLACE TABLE {WORK}.findings AS
SELECT
    f.loan_id || ':' || TO_CHAR(f.period_start, 'YYYYMM') || ':' || COALESCE(a.practice_code, x.status) AS finding_id,
    f.loan_id, lb.borrower_id, lb.branch_id, lb.product, f.period_start,
    CAST(NULL AS DECIMAL(3,0)) AS tranche_no,
    COALESCE(a.practice_code, x.practice_code) AS practice_code,
    x.status,
    CAST(COALESCE(mt.days_affected, 0) AS DECIMAL(5,0)) AS days_affected,
    COALESCE(a.amount_paise, f.excess_paise) AS excess_paise,
    f.matched_convention_id,
    x.reason,
    f.posting_ids || ',' || le.evidence_ids AS evidence_ids
FROM {WORK}.fp f
JOIN {WORK}.loan_base lb ON lb.loan_id = f.loan_id
JOIN {WORK}.loan_evidence le ON le.loan_id = f.loan_id
LEFT JOIN {WORK}.matches mt ON mt.loan_id = f.loan_id AND mt.period_start = f.period_start
                            AND mt.convention_id = f.matched_convention_id
LEFT JOIN {WORK}.attribution a ON a.loan_id = f.loan_id AND a.period_start = f.period_start AND f.match_status = 'MATCHED'
JOIN (
    SELECT fp2.loan_id, fp2.period_start,
           CASE fp2.match_status WHEN 'MATCHED' THEN 'REFUND' ELSE fp2.match_status END AS status,
           CASE WHEN fp2.match_status = 'AMBIGUOUS' THEN 'AMB'
                WHEN fp2.match_status = 'PERMITTED' THEN 'P1' END AS practice_code,
           CASE fp2.match_status
               WHEN 'PERMITTED' THEN 'KFS discloses a commitment fee of ' || TO_CHAR(lb2.commitment_fee_rate_pct) ||
                    '% a year on the undisbursed amount and the posting reproduces it exactly. Permitted under the current '
                    || 'policy setting for disclosed commitment fees; no refund.'
               WHEN 'EVIDENCE_GAP' THEN 'Money-in-hand date cannot be decided for tranche ' || fp2.gap_tranches ||
                    '. Kept out of the refund total until the branch supplies the missing record.'
               WHEN 'UNEXPLAINED' THEN 'No candidate convention reproduces the posting. Closest is ' ||
                    fp2.closest_convention_id || ', off by ' || TO_CHAR(fp2.closest_diff_paise) || ' paise.' ||
                    CASE WHEN fp2.has_manual THEN ' A manual journal entry was posted for this period.' ELSE '' END
               WHEN 'UNDERCHARGE' THEN 'Posted interest is below the fair figure. Not refundable; noted for completeness.'
               WHEN 'AMBIGUOUS' THEN 'Excess is known but several conventions reproduce the posting: ' ||
                    fp2.tied_convention_ids || '. Practice not uniquely named.'
           END AS reason
    FROM {WORK}.fp fp2
    JOIN {WORK}.loan_base lb2 ON lb2.loan_id = fp2.loan_id
    WHERE fp2.match_status <> 'FAIR'
) x ON x.loan_id = f.loan_id AND x.period_start = f.period_start
WHERE a.loan_id IS NULL OR a.amount_paise <> 0;

CREATE TABLE IF NOT EXISTS {OUT}.findings (
    run_id VARCHAR(36), finding_id VARCHAR(60), loan_id VARCHAR(10), borrower_id VARCHAR(10), branch_id VARCHAR(10),
    product VARCHAR(10), period_start DATE, tranche_no DECIMAL(3,0), practice_code VARCHAR(3), status VARCHAR(15),
    days_affected DECIMAL(5,0), excess_paise DECIMAL(18,0), matched_convention_id VARCHAR(40), reason VARCHAR(500),
    evidence_ids VARCHAR(2000), sql_step_id VARCHAR(40));

INSERT INTO {OUT}.findings
SELECT '{RUN_ID}', finding_id, loan_id, borrower_id, branch_id, product, period_start, tranche_no, practice_code,
       status, days_affected, excess_paise, matched_convention_id, SUBSTR(reason, 1, 500), SUBSTR(evidence_ids, 1, 2000),
       'S80_FINDINGS'
FROM {WORK}.findings;

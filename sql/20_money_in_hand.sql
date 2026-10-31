-- step: S20_MONEY_IN_HAND
-- purpose: resolve the day each tranche's money actually reached the borrower or payee, from conflicting
--          evidence, using the editable precedence table. Flag conflicts. Mark GAP when no defensible date.
-- inputs: {RAW}.tranches, {RAW}.disbursement_evidence, {POLICY}.date_precedence, {WORK}.cfg
-- outputs: {WORK}.mih, {OUT}.money_in_hand

-- evidence per tranche per source. Duplicate records of one source keep the earliest date (smallest refund
-- claim, so the conservative choice) and raise the conflict flag below.
CREATE OR REPLACE TABLE {WORK}.ev_src AS
SELECT loan_id, tranche_no, evidence_source,
       MIN(event_date) AS first_date, MAX(event_date) AS last_date, COUNT(*) AS n_records,
       GROUP_CONCAT(evidence_id ORDER BY evidence_id SEPARATOR ',') AS evidence_ids
FROM {RAW}.disbursement_evidence
GROUP BY loan_id, tranche_no, evidence_source;

CREATE OR REPLACE TABLE {WORK}.mih_pick AS
SELECT loan_id, tranche_no, evidence_source, rule, resolved_date
FROM (
    SELECT t.loan_id, t.tranche_no, p.evidence_source, p.rule,
           CASE WHEN p.rule = 'MAX_WITH_CHEQUE_DATE'
                THEN GREATEST(e.first_date, COALESCE(c.first_date, e.first_date))
                ELSE e.first_date END AS resolved_date,
           ROW_NUMBER() OVER (PARTITION BY t.loan_id, t.tranche_no ORDER BY p.rank) AS rn
    FROM {RAW}.tranches t
    CROSS JOIN {WORK}.cfg g
    JOIN {POLICY}.date_precedence p ON p.payment_mode = t.payment_mode
    JOIN {WORK}.ev_src e ON e.loan_id = t.loan_id AND e.tranche_no = t.tranche_no AND e.evidence_source = p.evidence_source
    LEFT JOIN {WORK}.ev_src c ON c.loan_id = t.loan_id AND c.tranche_no = t.tranche_no AND c.evidence_source = 'CHEQUE_DATE'
    WHERE p.rule <> 'FALLBACK' OR g.allow_fallback
) x
WHERE rn = 1;

CREATE OR REPLACE TABLE {WORK}.mih AS
SELECT
    t.loan_id, t.tranche_no, t.amount_paise, t.payment_mode,
    pk.resolved_date,
    pk.evidence_source AS resolved_source,
    CASE WHEN pk.loan_id IS NULL THEN 'GAP' WHEN pk.rule = 'FALLBACK' THEN 'FALLBACK' ELSE 'CONFIRMED' END AS confidence,
    chq.first_date AS cheque_date,
    sp.ev_min, sp.ev_max,
    -- for a GAP the latest known date is used as a provisional start so later periods can still be audited;
    -- the periods inside the uncertainty window are reported as EVIDENCE_GAP instead
    COALESCE(pk.resolved_date, sp.ev_max) AS effective_date,
    CASE WHEN pk.loan_id IS NULL THEN sp.ev_max > sp.ev_min
         ELSE GREATEST(ABS(DAYS_BETWEEN(sp.ev_min, pk.resolved_date)), ABS(DAYS_BETWEEN(sp.ev_max, pk.resolved_date))) > g.conflict_tol_days
              OR sp.dup_sources > 0 END AS conflict_flag,
    CAST(DAYS_BETWEEN(sp.ev_max, sp.ev_min) AS DECIMAL(5,0)) AS max_spread_days,
    ms.missing_sources,
    sp.evidence_ids,
    sp.available_sources
FROM {RAW}.tranches t
CROSS JOIN {WORK}.cfg g
LEFT JOIN {WORK}.mih_pick pk ON pk.loan_id = t.loan_id AND pk.tranche_no = t.tranche_no
LEFT JOIN {WORK}.ev_src chq ON chq.loan_id = t.loan_id AND chq.tranche_no = t.tranche_no AND chq.evidence_source = 'CHEQUE_DATE'
LEFT JOIN (
    SELECT loan_id, tranche_no, MIN(first_date) AS ev_min, MAX(last_date) AS ev_max,
           SUM(CASE WHEN n_records > 1 AND first_date <> last_date THEN 1 ELSE 0 END) AS dup_sources,
           GROUP_CONCAT(evidence_ids ORDER BY evidence_source SEPARATOR ',') AS evidence_ids,
           -- readable for the branch query: "cheque dated 31 Jul 2024; payment-rail credit 02 Aug 2024"
           GROUP_CONCAT(CASE evidence_source WHEN 'LMS_DISB' THEN 'loan-system disbursal' WHEN 'CHEQUE_DATE' THEN 'cheque dated'
                                             WHEN 'HANDOVER_ACK' THEN 'handover acknowledged' WHEN 'RAIL_CREDIT' THEN 'payment-rail credit'
                                             ELSE evidence_source END || ' ' || TO_CHAR(first_date, 'DD Mon YYYY')
                        || CASE WHEN n_records > 1 AND first_date <> last_date THEN ' and ' || TO_CHAR(last_date, 'DD Mon YYYY') ELSE '' END
                        ORDER BY first_date, evidence_source SEPARATOR '; ') AS available_sources
    FROM {WORK}.ev_src GROUP BY loan_id, tranche_no
) sp ON sp.loan_id = t.loan_id AND sp.tranche_no = t.tranche_no
LEFT JOIN (
    SELECT t2.loan_id, t2.tranche_no,
           GROUP_CONCAT(p2.evidence_source ORDER BY p2.rank SEPARATOR ',') AS missing_sources
    FROM {RAW}.tranches t2
    JOIN {POLICY}.date_precedence p2 ON p2.payment_mode = t2.payment_mode
    LEFT JOIN {WORK}.ev_src e2 ON e2.loan_id = t2.loan_id AND e2.tranche_no = t2.tranche_no AND e2.evidence_source = p2.evidence_source
    WHERE e2.loan_id IS NULL
    GROUP BY t2.loan_id, t2.tranche_no
) ms ON ms.loan_id = t.loan_id AND ms.tranche_no = t.tranche_no;

CREATE TABLE IF NOT EXISTS {OUT}.money_in_hand (
    run_id VARCHAR(36), loan_id VARCHAR(10), tranche_no DECIMAL(3,0), amount_paise DECIMAL(18,0),
    payment_mode VARCHAR(10), resolved_date DATE, resolved_source VARCHAR(15), confidence VARCHAR(10),
    conflict_flag BOOLEAN, max_spread_days DECIMAL(5,0), missing_sources VARCHAR(100),
    effective_date DATE, gap_window_start DATE, gap_window_end DATE, evidence_ids VARCHAR(2000),
    available_sources VARCHAR(2000));

INSERT INTO {OUT}.money_in_hand
SELECT '{RUN_ID}', loan_id, tranche_no, amount_paise, payment_mode, resolved_date, resolved_source, confidence,
       conflict_flag, max_spread_days, missing_sources, effective_date,
       CASE WHEN confidence = 'GAP' THEN ev_min END, CASE WHEN confidence = 'GAP' THEN ev_max END,
       evidence_ids, available_sources
FROM {WORK}.mih;

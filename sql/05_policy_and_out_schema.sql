-- step: S05_POLICY_SEED
-- purpose: create policy and result schemas; seed default policy rows only where missing,
--          so edits made from the app survive re-runs
-- inputs: none
-- outputs: {POLICY}.settings, date_precedence, practices, conventions; empty {OUT}.* tables

CREATE SCHEMA IF NOT EXISTS {POLICY};
CREATE SCHEMA IF NOT EXISTS {OUT};
CREATE SCHEMA IF NOT EXISTS {WORK};

CREATE TABLE IF NOT EXISTS {POLICY}.settings (
    setting_key VARCHAR(50) PRIMARY KEY, setting_value VARCHAR(100), description VARCHAR(500));

INSERT INTO {POLICY}.settings (setting_key, setting_value, description)
SELECT k, v, d FROM VALUES
    ('conflict_tolerance_days', '0', 'Evidence dates further apart than this from the resolved date raise a conflict flag'),
    ('match_tolerance_paise', '0', 'A candidate convention reproduces a posting if it is within this many paise'),
    ('allow_lms_fallback_electronic', 'true', 'For NEFT/RTGS/IMPS with no rail credit record, accept the LMS disbursement date (confidence FALLBACK)'),
    ('commitment_fee_permitted_if_disclosed', 'true', 'A commitment fee from sanction date is permitted when the KFS discloses it'),
    ('include_ambiguous_in_refund_total', 'true', 'Count AMBIGUOUS findings (excess known, practice not unique) in the refund total')
    AS t(k, v, d)
WHERE k NOT IN (SELECT setting_key FROM {POLICY}.settings);

CREATE TABLE IF NOT EXISTS {POLICY}.date_precedence (
    payment_mode VARCHAR(10), rank DECIMAL(2,0), evidence_source VARCHAR(15), rule VARCHAR(20));

INSERT INTO {POLICY}.date_precedence (payment_mode, rank, evidence_source, rule)
SELECT m, r, s, ru FROM VALUES
    ('NEFT', 1, 'RAIL_CREDIT', 'USE'), ('NEFT', 2, 'LMS_DISB', 'FALLBACK'),
    ('RTGS', 1, 'RAIL_CREDIT', 'USE'), ('RTGS', 2, 'LMS_DISB', 'FALLBACK'),
    ('IMPS', 1, 'RAIL_CREDIT', 'USE'), ('IMPS', 2, 'LMS_DISB', 'FALLBACK'),
    ('CHEQUE', 1, 'HANDOVER_ACK', 'MAX_WITH_CHEQUE_DATE'),
    ('DD', 1, 'HANDOVER_ACK', 'MAX_WITH_CHEQUE_DATE')
    AS t(m, r, s, ru)
WHERE NOT EXISTS (SELECT 1 FROM {POLICY}.date_precedence);

CREATE TABLE IF NOT EXISTS {POLICY}.practices (
    practice_code VARCHAR(3) PRIMARY KEY, title VARCHAR(200), rbi_reference VARCHAR(200), introduced DATE);

INSERT INTO {POLICY}.practices (practice_code, title, rbi_reference, introduced)
SELECT c, t, r, d FROM VALUES
    ('P1', 'Interest from sanction or agreement date instead of disbursement', 'RBI Fair Practices Code for Lenders: Charging of Interest, 29 Apr 2024', DATE '2024-04-29'),
    ('P2', 'Interest from the cheque date when the cheque was handed over later', 'RBI Fair Practices Code for Lenders: Charging of Interest, 29 Apr 2024', DATE '2024-04-29'),
    ('P3', 'Full-month interest on mid-month disbursal or repayment', 'RBI Fair Practices Code for Lenders: Charging of Interest, 29 Apr 2024', DATE '2024-04-29'),
    ('P4', 'Interest on the full amount despite advance instalments collected', 'RBI Fair Practices Code for Lenders: Charging of Interest, 29 Apr 2024', DATE '2024-04-29'),
    ('P5', 'Interest on the sanctioned instead of the disbursed amount', 'RBI Miscellaneous Supervisory Directions, 31 Jul 2026', DATE '2026-07-31'),
    ('P6', 'Amortisation change after part-disbursement not communicated against KFS', 'RBI Miscellaneous Supervisory Directions, 31 Jul 2026', DATE '2026-07-31')
    AS t(c, t, r, d)
WHERE c NOT IN (SELECT practice_code FROM {POLICY}.practices);

-- 4 x 2 x 2 x 2 = 32 conventions plus the disclosed commitment fee variant
CREATE OR REPLACE TABLE {POLICY}.conventions AS
SELECT
    sb.code || '|' || pb.code || '|' || ad.code || '|' || mr.code AS convention_id,
    sb.val AS start_basis, pb.val AS principal_basis, ad.val AS advance_treatment, mr.val AS month_rounding,
    (sb.fair AND pb.fair AND ad.fair AND mr.fair) AS is_fair,
    CAST((CASE WHEN sb.fair THEN 0 ELSE 1 END) + (CASE WHEN pb.fair THEN 0 ELSE 1 END)
       + (CASE WHEN ad.fair THEN 0 ELSE 1 END) + (CASE WHEN mr.fair THEN 0 ELSE 1 END) AS DECIMAL(1,0)) AS unfair_dimension_count,
    FALSE AS is_permitted_variant,
    CAST(TRIM(BOTH ',' FROM sb.practice || ',' || pb.practice || ',' || ad.practice || ',' || mr.practice) AS VARCHAR(20)) AS practice_codes
FROM (SELECT * FROM VALUES ('MIH', 'MONEY_IN_HAND', TRUE, ''), ('CHQ', 'CHEQUE_DATE', FALSE, 'P2'),
                           ('SNC', 'SANCTION_DATE', FALSE, 'P1'), ('AGR', 'AGREEMENT_DATE', FALSE, 'P1')
      AS t(code, val, fair, practice)) sb
CROSS JOIN (SELECT * FROM VALUES ('DIS', 'DISBURSED', TRUE, ''), ('SAN', 'SANCTIONED', FALSE, 'P5') AS t(code, val, fair, practice)) pb
CROSS JOIN (SELECT * FROM VALUES ('NET', 'NETTED', TRUE, ''), ('IGN', 'IGNORED', FALSE, 'P4') AS t(code, val, fair, practice)) ad
CROSS JOIN (SELECT * FROM VALUES ('EXACT', 'EXACT', TRUE, ''), ('FULL', 'FULL_MONTH', FALSE, 'P3') AS t(code, val, fair, practice)) mr
UNION ALL
SELECT 'CFEE', 'MONEY_IN_HAND', 'DISBURSED', 'NETTED', 'EXACT', FALSE, 1, TRUE, 'P1' FROM DUAL;

-- practice_codes can carry inner empty segments (e.g. 'P2,,,P3'); normalise them
UPDATE {POLICY}.conventions SET practice_codes = REGEXP_REPLACE(practice_codes, ',+', ',');

CREATE TABLE IF NOT EXISTS {OUT}.audit_runs (
    run_id VARCHAR(36) PRIMARY KEY, dataset_id VARCHAR(50), started_at TIMESTAMP, finished_at TIMESTAMP,
    duration_ms DECIMAL(12,0), git_sha VARCHAR(40), policy_snapshot VARCHAR(20000), loan_count DECIMAL(12,0),
    posting_count DECIMAL(12,0), status VARCHAR(10), label VARCHAR(200));

CREATE TABLE IF NOT EXISTS {OUT}.step_timings (
    run_id VARCHAR(36), sql_step_id VARCHAR(40), started_at TIMESTAMP, duration_ms DECIMAL(12,0), rows_out DECIMAL(18,0));

CREATE TABLE IF NOT EXISTS {OUT}.lineage (
    sql_step_id VARCHAR(40) PRIMARY KEY, file_path VARCHAR(200), description VARCHAR(500), statement_sha VARCHAR(64));

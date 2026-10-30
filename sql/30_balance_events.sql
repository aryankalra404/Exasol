-- step: S30_BALANCE_EVENTS
-- purpose: turn tranches and receipts into dated balance changes. The fair path gets every event.
--          Each candidate convention is stored only as its difference from the fair path, so a convention
--          that moves one tranche by eight days costs two rows, not a full copy of the loan.
-- inputs: {WORK}.mih, {WORK}.loan_base, {RAW}.receipts, {POLICY}.conventions
-- outputs: {WORK}.fair_events, {WORK}.diff_events

CREATE OR REPLACE TABLE {WORK}.fair_events AS
SELECT loan_id, event_date, SUM(d_bal) AS d_bal
FROM (
    SELECT loan_id, effective_date AS event_date, amount_paise AS d_bal FROM {WORK}.mih
    UNION ALL
    SELECT loan_id, value_date, -principal_paise FROM {RAW}.receipts WHERE principal_paise <> 0
) e
GROUP BY loan_id, event_date;

-- conventions that apply to a loan: every non-fair one, plus CFEE only when the KFS discloses a fee
CREATE OR REPLACE TABLE {WORK}.loan_conv AS
SELECT lb.loan_id, c.convention_id, c.start_basis, c.principal_basis, c.advance_treatment, c.month_rounding
FROM {WORK}.loan_base lb
CROSS JOIN {POLICY}.conventions c
WHERE NOT c.is_fair
  AND (NOT c.is_permitted_variant OR lb.commitment_fee_rate_pct IS NOT NULL);

CREATE OR REPLACE TABLE {WORK}.diff_events AS
WITH tranche_start AS (
    -- the date each tranche starts accruing under each convention
    SELECT loan_id, convention_id, principal_basis, tranche_no, amount_paise, effective_date,
           CASE WHEN month_rounding = 'FULL_MONTH' THEN TRUNC(raw_start, 'MM') ELSE raw_start END AS conv_start
    FROM (
        SELECT lc.loan_id, lc.convention_id, lc.principal_basis, lc.month_rounding, m.tranche_no, m.amount_paise,
               m.effective_date,
               CASE lc.start_basis
                   WHEN 'CHEQUE_DATE' THEN CASE WHEN m.payment_mode IN ('CHEQUE', 'DD') AND m.cheque_date IS NOT NULL
                                                THEN m.cheque_date ELSE m.effective_date END
                   WHEN 'SANCTION_DATE' THEN CASE WHEN m.tranche_no = 1 THEN lb.sanction_date ELSE m.effective_date END
                   WHEN 'AGREEMENT_DATE' THEN CASE WHEN m.tranche_no = 1 THEN lb.agreement_date ELSE m.effective_date END
                   ELSE m.effective_date END AS raw_start
        FROM {WORK}.loan_conv lc
        JOIN {WORK}.mih m ON m.loan_id = lc.loan_id
        JOIN {WORK}.loan_base lb ON lb.loan_id = lc.loan_id
    ) s
),
moved_receipts AS (
    -- only advance instalments and closures can move between conventions
    SELECT lc.loan_id, lc.convention_id, r.principal_paise, r.value_date,
           CASE WHEN r.kind = 'ADVANCE_EMI' AND lc.advance_treatment = 'IGNORED' AND r.due_date IS NOT NULL THEN r.due_date
                WHEN r.kind = 'CLOSURE' AND lc.month_rounding = 'FULL_MONTH'
                     THEN CASE WHEN DAY(r.value_date) = 1 THEN r.value_date ELSE ADD_MONTHS(TRUNC(r.value_date, 'MM'), 1) END
                ELSE r.value_date END AS conv_date
    FROM {WORK}.loan_conv lc
    JOIN {RAW}.receipts r ON r.loan_id = lc.loan_id
    WHERE r.kind IN ('ADVANCE_EMI', 'CLOSURE') AND r.principal_paise <> 0
),
raw_diff AS (
    -- principal added under the convention
    SELECT loan_id, convention_id, conv_start AS event_date, amount_paise AS d_bal, CAST(0 AS DECIMAL(18,0)) AS d_fee
    FROM tranche_start WHERE principal_basis = 'DISBURSED'
    UNION ALL
    -- sanctioned basis: the full sanction accrues from tranche 1's start until closure
    SELECT ts.loan_id, ts.convention_id, ts.conv_start, lb.sanctioned_paise, 0
    FROM tranche_start ts JOIN {WORK}.loan_base lb ON lb.loan_id = ts.loan_id
    WHERE ts.principal_basis = 'SANCTIONED' AND ts.tranche_no = 1
    UNION ALL
    SELECT lc.loan_id, lc.convention_id,
           CASE WHEN lc.month_rounding = 'FULL_MONTH' AND DAY(lb.closure_date) <> 1
                THEN ADD_MONTHS(TRUNC(lb.closure_date, 'MM'), 1) ELSE lb.closure_date END,
           -(lb.sanctioned_paise - lb.disbursed_paise), 0
    FROM {WORK}.loan_conv lc JOIN {WORK}.loan_base lb ON lb.loan_id = lc.loan_id
    WHERE lc.principal_basis = 'SANCTIONED' AND lb.closure_date IS NOT NULL AND lb.sanctioned_paise <> lb.disbursed_paise
    UNION ALL
    -- minus the fair tranche events
    SELECT loan_id, convention_id, effective_date, -amount_paise, 0 FROM tranche_start
    UNION ALL
    -- moved receipts: convention date minus fair date
    SELECT loan_id, convention_id, conv_date, -principal_paise, 0 FROM moved_receipts
    UNION ALL
    SELECT loan_id, convention_id, value_date, principal_paise, 0 FROM moved_receipts
    UNION ALL
    -- disclosed commitment fee: a fee balance on the undisbursed amount from sanction to each money-in-hand date
    SELECT lc.loan_id, lc.convention_id, lb.sanction_date, 0, lb.sanctioned_paise
    FROM {WORK}.loan_conv lc JOIN {WORK}.loan_base lb ON lb.loan_id = lc.loan_id
    WHERE lc.convention_id = 'CFEE'
    UNION ALL
    SELECT lc.loan_id, lc.convention_id, m.effective_date, 0, -m.amount_paise
    FROM {WORK}.loan_conv lc JOIN {WORK}.mih m ON m.loan_id = lc.loan_id
    WHERE lc.convention_id = 'CFEE'
    UNION ALL
    SELECT lc.loan_id, lc.convention_id, lb.closure_date, 0, -(lb.sanctioned_paise - lb.disbursed_paise)
    FROM {WORK}.loan_conv lc JOIN {WORK}.loan_base lb ON lb.loan_id = lc.loan_id
    WHERE lc.convention_id = 'CFEE' AND lb.closure_date IS NOT NULL AND lb.sanctioned_paise <> lb.disbursed_paise
)
SELECT loan_id, convention_id, event_date, SUM(d_bal) AS d_bal, SUM(d_fee) AS d_fee
FROM raw_diff
GROUP BY loan_id, convention_id, event_date
HAVING SUM(d_bal) <> 0 OR SUM(d_fee) <> 0;

# Domain rules

Source of truth for every interest rule. The SQL pipeline and the Python oracle both implement this document, independently. If they disagree, one of them (or this doc) is wrong: fix it, never paper over it.

Any change here needs a `DECISIONS.md` entry and matching changes in the SQL and the oracle.

## Glossary

| Term | Meaning |
|---|---|
| LMS | Loan management system: the lender's system that posts interest. The thing under audit |
| KFS | Key Facts Statement: what the borrower was promised (rate, day-count basis, disbursal schedule, fees, APR) |
| Tranche | One part-disbursement of a loan |
| Money-in-hand date | The day the borrower (or their payee, such as a builder) actually had the money. Interest may start from this day |
| Pre-EMI | Interest-only payments on disbursed tranches before full EMIs start (common in under-construction home loans) |
| Advance EMI | Instalment(s) collected upfront at disbursement |
| Posting | One interest amount the LMS charged for one loan for one billing period |
| Convention | A way of computing interest. One is fair; the others reproduce specific RBI practices |
| Fingerprint | The convention that reproduces a posting exactly |
| Excess | Posted interest minus fair interest for a period |

## Money and arithmetic

- Amounts at rest: integer **paise**, `DECIMAL(18,0)`
- Rates: annual percent, `DECIMAL(9,6)` (8.75% is `8.750000`)
- Intermediates: `DECIMAL(36,12)`. Never floating point
- **Rounding: half up to the paisa, once per loan per billing period**, after summing all intervals in that period. Never round per interval or per day
- Python: `decimal.Decimal` with `ROUND_HALF_UP`, context precision >= 36

## Time

- All dates are calendar dates in IST. No times of day
- Intervals are **half-open: `[start, end)`**. Interest accrues for each day `d` with `start <= d < end`
- A disbursement with money-in-hand date `D` accrues interest from `D` inclusive
- A repayment with value date `R` reduces principal from `R` inclusive (no interest on the repaid amount for day `R`)
- **Billing period:** calendar month, `[1st of month, 1st of next month)`. One posting per loan per period while principal is outstanding

## Day-count basis

Use the basis disclosed in the KFS. Default `ACT_365`.

- `ACT_365` (actual/365 fixed): `days = end - start`, divisor 365, including in leap years
- `30E_360` (30E/360): day of month capped at 30 for both dates, `days = 360*(y2-y1) + 30*(m2-m1) + (d2-d1)`, divisor 360

Interest for one interval: `balance_paise * rate_pct / 100 * days / divisor`.

**Worked check (Meena):** ₹12,00,000 at 8.75% for 8 days, ACT_365: `120000000 * 8.75 / 100 * 8 / 365 = 230136.986...` paise → **230137 paise = ₹2,301.37**.

## Money-in-hand resolution

Each tranche has several date evidence records (`disbursement_evidence` in the contract). Sources:

| Source | What it is |
|---|---|
| `SANCTION` | Loan sanction date (never a valid money-in-hand date; kept for comparison) |
| `AGREEMENT` | Loan agreement date (same) |
| `LMS_DISB` | Disbursement date recorded in the LMS |
| `CHEQUE_DATE` | Date printed on the cheque or DD |
| `HANDOVER_ACK` | Date the cheque was acknowledged as received by the borrower or payee |
| `RAIL_CREDIT` | Date the NEFT/RTGS/IMPS credit landed in the beneficiary account |

**Default precedence** (stored as data in `policy_date_precedence`, editable):

| Payment mode | Rule |
|---|---|
| NEFT, RTGS, IMPS | `RAIL_CREDIT`. If missing and `allow_lms_fallback_electronic` is true, use `LMS_DISB` with confidence `FALLBACK`. Otherwise `GAP` |
| CHEQUE, DD | `max(HANDOVER_ACK, CHEQUE_DATE)` (a cheque cannot be money in hand before its date). If `HANDOVER_ACK` missing: `GAP` |

**Outputs per tranche:** resolved date, resolved source, confidence (`CONFIRMED`, `FALLBACK`, `GAP`), conflict flag, max spread in days.

- **Conflict flag:** any non-sanction/agreement source differs from the resolved date by more than `conflict_tolerance_days` (default 0). Flagged, not hidden. Conflicts do not stop resolution
- **GAP:** no defensible date. The tranche's periods are excluded from the refund total and listed in the evidence-gap queue with the missing source named

## Conventions

A convention is a combination of four dimensions. The fair convention is the first value of each.

| Dimension | Values | RBI practice when not fair |
|---|---|---|
| `start_basis` | `MONEY_IN_HAND` (fair), `CHEQUE_DATE`, `SANCTION_DATE`, `AGREEMENT_DATE` | P2 for cheque, P1 for sanction/agreement |
| `principal_basis` | `DISBURSED` (fair), `SANCTIONED` | P5 |
| `advance_treatment` | `NETTED` (fair: advance instalment reduces principal from its receipt date), `IGNORED` (reduction applied only from the instalment's due date) | P4 |
| `month_rounding` | `EXACT` (fair), `FULL_MONTH` (a disbursement in a period accrues from the period start; a closing repayment accrues to the period end) | P3 |

That is 4 x 2 x 2 x 2 = **32 candidates**, plus one permitted variant:

- `DISCLOSED_COMMITMENT_FEE`: fair interest plus a commitment fee on the undisbursed amount from sanction to money-in-hand, at the rate the KFS discloses. Only a candidate when the KFS discloses one

**What each dimension does to the balance path:**
- `start_basis` moves the date each tranche's principal starts accruing
- `principal_basis = SANCTIONED` accrues on the full sanctioned amount from the first accrual date instead of the disbursed balance
- `advance_treatment = IGNORED` delays the principal reduction of `ADVANCE_EMI` receipts to their due date
- `month_rounding = FULL_MONTH` snaps disbursement start dates back to the period start and closing repayment dates forward to the next period start

## Principal path

- Principal increases with each tranche (on the date set by `start_basis`)
- Principal decreases by the **principal component** of each receipt, as recorded on the receipt, on its value date (or as `advance_treatment` says)
- **We do not re-amortise.** Excess is measured per period on the recorded principal path. A fair system would have allocated slightly more of each EMI to principal, so this slightly understates refunds. It is conservative and stated in `LIMITS.md`
- Rate changes (`rate_history`) split intervals on their effective date

## Fingerprinting

For each posting (loan, period):

1. Compute interest under every candidate convention for that period
2. Find candidates whose amount equals the posted amount within `match_tolerance_paise` (default 0)
3. Label:
   - The fair convention matches → `FAIR`
   - `DISCLOSED_COMMITMENT_FEE` matches and policy allows it → `PERMITTED`
   - One or more unfair candidates match → `MATCHED`. Pick the one with the fewest non-fair dimensions. If still tied, `AMBIGUOUS` and keep all tied candidates
   - Nothing matches → `UNEXPLAINED`
4. Any tranche feeding this period has confidence `GAP` → status `EVIDENCE_GAP` regardless of match

**Excess does not depend on attribution.** `excess = posted - fair`. Fingerprinting only names the practice. Negative excess is recorded as `UNDERCHARGE` and never refunded.

## Attributing excess to practices

When a matched convention has several unfair dimensions (for example cheque date + full month), split the excess by adding dimensions one at a time in this fixed order and taking each step's increment:

`start_basis` → `principal_basis` → `advance_treatment` → `month_rounding`

The increments sum exactly to the total excess, so no paisa is lost or double-counted.

## Finding statuses

| Status | Meaning | In refund total? |
|---|---|---|
| `FAIR` | Posting matches fair interest | No finding |
| `REFUND` | Unfair convention matched, positive excess | Yes |
| `AMBIGUOUS` | Unfair, excess known, practice not uniquely named | Yes (excess is known), practice shown as all tied codes |
| `PERMITTED` | Matches a disclosed, policy-allowed term | No, reason shown |
| `EVIDENCE_GAP` | Money-in-hand date cannot be decided | No, listed separately with the missing source |
| `UNEXPLAINED` | No candidate reproduces the posting | No, listed separately with the closest candidate and difference |
| `UNDERCHARGE` | Posted less than fair | No |

## Practice codes

| Code | Practice | Source |
|---|---|---|
| P1 | Interest from sanction or agreement date instead of disbursement | RBI circular 29 Apr 2024 |
| P2 | Interest from cheque date when cheque handed over later | RBI circular 29 Apr 2024 |
| P3 | Full-month interest on mid-month disbursal or repayment | RBI circular 29 Apr 2024 |
| P4 | Interest on full amount despite advance instalments collected | RBI circular 29 Apr 2024 |
| P5 | EMI or interest on sanctioned instead of disbursed amount | RBI directions 31 Jul 2026 |
| P6 | Amortisation change after part-disbursement not communicated against KFS | RBI directions 31 Jul 2026 (Tier 1) |

P6 is not a posting-level convention. It is a separate check: compare the effective EMI schedule after each tranche with the KFS amortisation schedule and the communications log.

## Policy settings (defaults)

Stored in `policy_settings`, editable from the app. Every audit run snapshots the policy it used.

| Key | Default |
|---|---|
| `conflict_tolerance_days` | 0 |
| `match_tolerance_paise` | 0 |
| `allow_lms_fallback_electronic` | true |
| `commitment_fee_permitted_if_disclosed` | true |
| `include_ambiguous_in_refund_total` | true |

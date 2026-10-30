# Problem

## Problem statement (submitted, no technology in it)

> An internal auditor at a housing finance company can't show that no borrower paid interest for days before their money actually reached them, because the dates that decide interest (sanction, the disbursement date in the loan system, the day a cheque or tranche was really handed over) sit in records that disagree, and the only thing computing interest is the loan system she is supposed to be checking. If this worked, she would know every overcharged borrower and the exact refund owed, with evidence, before the regulator's inspection finds it.

**Deck version:** A lender's auditor can't prove its borrowers were only charged interest for days they actually had the money, because the dates that decide it sit in records that disagree. If this worked, every overcharged borrower would get the exact refund, with proof.

## Who

| Role | Who | What changes for them |
|---|---|---|
| User | Internal or concurrent auditor, or compliance head, at an HFC, NBFC or bank | A finding per loan, classified by RBI practice, with the source rows and dates behind it, instead of a sample and an extrapolation |
| Beneficiary | Borrowers, most of all home-loan borrowers paid in tranches or by cheque | The exact excess interest returned. Amounts are usually too small and too hidden for a borrower to spot alone |
| Second user | Head of loan operations | A re-runnable check after every loan-system configuration change, so a fix for new loans that skipped old ones gets caught |

**Why a housing finance persona:** staged disbursement, cheques to builders and sellers, and pre-EMI interest put most RBI practices into one product. The engine itself is product-agnostic.

## The practices RBI named

From the RBI circular *Fair Practices Code for Lenders: Charging of Interest* (29 Apr 2024), based on onsite examinations for the period ended 31 Mar 2023:

1. Interest charged from the **sanction or agreement date** instead of the actual disbursement date
2. Interest charged from the **date on a cheque** that was handed over days later
3. Interest for the **whole month** when disbursal or repayment happened mid-month
4. Interest on the **full amount** despite advance instalments already collected

RBI supervisors advised refunds, and all banks, co-op banks and NBFCs (including HFCs) were directed to review and make system-level changes.

On **31 Jul 2026** RBI re-codified these into its Miscellaneous Supervisory Directions and added two more:

5. **EMI computed on the sanctioned amount** instead of the disbursed amount, without consent
6. **Amortisation changes after each part-disbursement** not communicated against the KFS schedule

The KFS circular (15 Apr 2024) requires every retail and MSME loan to carry a Key Facts Statement with the disbursal schedule and amortisation schedule. That gives the audit a documented "what was promised" to compare against.

## Why it is hard today

- The loan management system is the thing under audit. If its "disbursement date" field holds the cheque date, every report built on it inherits the error
- The true money-in-hand date may only exist in other records: handover acknowledgements, payment-rail credits, branch registers
- General audit analytics tools run tests over extracts, but the date-evidence logic, the RBI practice list and the refund ledger are left to the auditor to build
- Recomputing interest for one loan in a spreadsheet is easy. Deciding which date is real when records disagree, naming the rule the system actually applied, and separating unfair practice from disclosed terms, across the whole book, is not

## Our distinction

1. **Money-in-hand date from conflicting evidence.** Resolve sanction, loan-system disbursement, cheque, handover acknowledgement and payment-rail credit dates with an explicit, editable precedence rule. Flag conflicts instead of hiding them
2. **Convention fingerprinting.** Recompute each posted interest amount under every candidate convention. The one that reproduces the posting to the paisa names what the system did. The posting itself is the evidence
3. **Permitted versus unfair.** Check KFS and sanction terms before calling anything a violation. A disclosed commitment fee or a disclosed day-count basis is not a false positive
4. **Paisa-exact refund ledger with lineage** back to source rows and the SQL step that produced each figure
5. **Whole book, re-runnable,** so a configuration fix that covered new loans but not old ones shows up on the next run

## What we must not claim

- **Prevalence.** RBI has not published how many lenders, loans or rupees were involved. Do not state or imply a number
- **That it is still happening.** The 2026 re-codification signals continuing supervisory concern. It is not proof of current prevalence
- **How auditors test this today.** No public account found. "They sample" is an assumption (see `LIMITS.md`)
- **"First" or "only".** We found no product doing this combination. That is not proof none exists
- **Legal verdicts.** Contested interpretations (for example a commitment fee from sanction) are policy settings, not rulings

## Size per borrower

Often small. Five extra days on ₹5,00,000 at 10% a year is ₹684.93. That is why borrowers rarely notice and why detection must happen on the lender's side. The pitch leans on breadth and fairness, not dramatic per-person losses.

## Sources

- [ExaThon India 2026 event page](https://www.exasol.com/events/exathon-india-2026/)
- [Exasol Personal](https://www.exasol.com/personal/) and [GitHub](https://github.com/exasol/exasol-personal)
- [RBI, Fair Practices Code for Lenders: Charging of Interest, 29 Apr 2024](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12678) ([PDF](https://website.rbi.org.in/documents/87730/39710850/Fair+Practices+Code+for+Lenders+Charging+of+Interest.pdf))
- RBI Miscellaneous Supervisory Directions, 31 Jul 2026 (RRB text verified; NBFC, co-op and commercial bank versions from summaries, verify before quoting)
- [RBI Key Facts Statement for Loans and Advances, 15 Apr 2024](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663)
- RBI Ombudsman Annual Report 2024-25 (loans and advances the largest complaint category)
- [Vinod Kothari Consultants, Fair Lending: RBI bars several practices](https://vinodkothari.com/?p=50040) (commitment fee interpretation)

Verify every link and quote before it goes into the deck or README.

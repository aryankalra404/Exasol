# Limits

What this does not do, what we assumed, and where it can be wrong. Add to this whenever you hit one.

## Data

- **All data is synthetic.** Generated with fixed seeds to mirror the shape of a housing finance company's loan book. No real borrowers, lenders or records. Names and IDs are fake
- Real handover dates may only exist on paper. The tool then reports an evidence gap, which is itself a finding, but it reduces the refund total it can defend

## Method

- **No re-amortisation.** Excess is measured per period on the principal path the LMS recorded. A fair system would have allocated slightly more of each EMI to principal, so refunds are slightly understated (conservative)
- **Only the listed conventions are recognised.** A posting produced by any other rule is reported as `UNEXPLAINED`, not guessed
- **Calendar-month billing periods** are assumed. Lenders with other posting cycles need the period definition changed
- Gaps and unexplained rows are excluded from the refund total by design

## Interpretation

- **Not legal advice.** Contested interpretations (for example a commitment fee from sanction date, or what counts as disbursement for a cheque to a builder) are policy settings, not verdicts
- RBI's 31 Jul 2026 directions were verified for the RRB text; NBFC, co-op and commercial bank versions were read through summaries

## Assumptions not yet validated

- **How auditors test interest charging today.** We found no public account. "They sample" is an assumption, not a finding
- **Prevalence.** RBI has not published how many lenders, loans or rupees were involved. We do not state a number

## Platform

- Runs on Exasol Personal local (single node). Scale figures are from our laptop and stated with hardware
- Exasol Personal allows 20 connections; the app uses a small pool

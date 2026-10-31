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
- **Weekends only, no holiday calendar.** The generator shifts rail credits past weekends; RBI's holiday list is not loaded
- **Days affected** for a finding is the calendar days on which the matched convention's balance differed from fair in that month; when one finding is split across several practices, each row shows the same days
- **Fallback dates can produce undercharges.** With no rail credit record, the LMS date is used (policy setting); if the money actually landed later, fair interest is overstated and the month can show as UNDERCHARGE. These are listed, never refunded
- **Broken-period interest is not a separate case.** Interest from disbursal to the first EMI is part of the fair path; there is no separately disclosed broken-period charge to test as a false positive
- **A wrong day count in the LMS** (30E/360 against a KFS that says ACT/365) is not one of the 33 conventions, so it lands in UNEXPLAINED or UNDERCHARGE, by design
- **AMBIGUOUS months remain** where no month of the same loan separates the candidates (often single-month differences). Their excess is known and counted by default (policy setting)
- **`findings.tranche_no` is not filled yet**; the loan page shows which tranche from the evidence timeline

## Interpretation

- **Not legal advice.** Contested interpretations (for example a commitment fee from sanction date, or what counts as disbursement for a cheque to a builder) are policy settings, not verdicts
- **RBI worked example read through excerpts.** rbi.org.in served a CAPTCHA to scripted requests, so the illustration's figures (EMI, total interest, fee, APR) come from RBI's annex as quoted in search results, not a direct read. The rate (15%) is derived as the one that reproduces all of them. Open the annex in a browser before quoting it
- RBI's 31 Jul 2026 directions were verified for the RRB text; NBFC, co-op and commercial bank versions were read through summaries

## Ask the book

- **The assistant writes the SQL, so it can ask the wrong question.** Exasol computes every number, and the SQL is always shown, but a mis-joined query gives a wrong answer. The refund ledger and the screens remain the record; answers are for exploration
- Only the latest completed run is visible; comparing runs is done in the app

## Assumptions not yet validated

- **How auditors test interest charging today.** We found no public account. "They sample" is an assumption, not a finding
- **Prevalence.** RBI has not published how many lenders, loans or rupees were involved. We do not state a number

## Platform

- Runs on Exasol Personal local (single node). Scale figures are from our laptop and stated with hardware
- Exasol Personal allows 20 connections; the app uses a pool of four
- Exasol local VM as measured: 2 vCPU, 8 GB RAM, on an Apple M4 (16 GB) MacBook

## Generator realism

- One LMS configuration per branch and period, with the "fixed for new loans only" story at BR001 to BR003 (July 2024). Real books will have more variety; anything outside the 33 conventions shows as UNEXPLAINED rather than a wrong label
- Pre-EMI interest is collected on the 5th; EMIs are fixed after the last tranche; no re-amortisation on rate change (tenure absorbs it)
- APR is disclosed as the loan rate (fees not modelled); the APR check (Tier 2) is not built
- Letters: English, Hindi and Tamil. The Hindi and Tamil wording has not been reviewed by a native-speaking compliance writer; month names stay in English

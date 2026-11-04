# Limits

What this does not do, what we assumed, and where it can be wrong. Add to this whenever you hit one.

## Data

- **All data is synthetic.** Generated with fixed seeds to mirror the shape of a housing finance company's loan book. No real borrowers, lenders or records. Names and IDs are fake
- Real handover dates may only exist on paper. The tool then reports an evidence gap, which is itself a finding, but it reduces the refund total it can defend

## Method

- **No re-amortisation.** Excess is measured per period on the principal path the LMS recorded. A fair system would have allocated slightly more of each EMI to principal, so refunds are slightly understated (conservative)
- **Only the listed conventions are recognised.** A posting produced by any other rule is reported as `UNEXPLAINED`, not guessed
- **Calendar-month billing periods** are assumed. Uploads with a posting that does not start on the 1st are refused. Lenders with other posting cycles need the period definition changed
- **A missing posting counts as zero charged,** so an extract that stops early shows many Undercharge months. They are listed, never refunded
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
- **RBI worked example checked against the annex.** Annex B and C of the KFS circular (15 Apr 2024), read in a browser on 31 Oct 2026, print ₹20,000, 24 months, 15% fixed, ₹400 fees, ₹19,600 net, EMI ₹970, total interest ₹3,274, APR 17.07%, all in whole rupees. Our exact EMI (₹969.73) and interest (₹3,273.58) round to those; RBI does not print paise
- **The 29 Apr 2024 interest circular now shows as withdrawn** on rbi.org.in, consistent with its practices moving into the 31 Jul 2026 directions. Quote it as what RBI found in 2024, not as the current instruction
- RBI's 31 Jul 2026 directions were verified for the RRB text; NBFC, co-op and commercial bank versions were read through summaries

## Ask the book

- **The assistant writes the SQL, so it can ask the wrong question.** Exasol computes every number, and the SQL is always shown, but a mis-joined query gives a wrong answer. The refund ledger and the screens remain the record; answers are for exploration
- Only the latest completed run is visible; comparing runs is done in the app

## Review and release

- **Outcomes are per loan, and refund wins.** A loan owed money counts as Refund even if another of its months is still open; the evidence level shows that
- **A held refund stays in the refund total** until the evidence or policy changes. Holds have no owner or due date
- **Released does not mean delivered.** This tool never contacts a borrower; it hands approved letters over as a ZIP and cannot see what happens next
- **A review cannot edit a figure.** To change a refund, correct the evidence or policy and re-run
- **An approval follows the figure, not the reasoning.** It stays valid across re-runs while that row's amount is unchanged, even if the policy behind it changed
- **Branch replies are entered one at a time, and the document is not stored.** The app keeps the date, a reference and who entered it. It does not record that a query was sent, and it cannot check the date against the document. A wrong date changes the result until it is withdrawn and the audit re-run
- **Ambiguous months are reviewed per loan,** as the `AMB` ledger row, and only while counted in the refund total
- **A released letter whose figure later changes is flagged,** on Review and release, but no correction letter is drafted

## Assumptions not yet validated

- **No person has blind-tested this yet.** The generator, the SQL and the oracle share an author, so agreement on generated books proves less than it appears to. One machine-written blind round found a real bug that both the SQL and the oracle shared (`RED_TEAM.md`), so more may exist. It tested against our own `DOMAIN.md`, not against a person's reading of RBI's text
- **How auditors test interest charging today.** We found no public account. "They sample" is an assumption, not a finding
- **Prevalence.** RBI has not published how many lenders, loans or rupees were involved. We do not state a number

- **Source records show the loaded extract, not a copy per run.** On an older run or after a change, the panel warns if another book is loaded or the month's posted total differs from what the run audited. It does not detect a changed evidence date, rate or repayment until the audit is re-run

## Platform

- **Single-user local tool, self-declared names.** No login or roles. Review decisions, policy changes and releases record a typed name and reason, so the log shows what was claimed, not a verified identity, and the same name can approve and release. A lender deployment would put the app behind its own sign-on and enforce separate approver and releaser roles. Data comes in through `make load` or a ZIP upload on the Data page (up to 512 MB); one book is loaded at a time
- **Uploaded books have no truth tables**, so fingerprint accuracy and robustness can only be measured on generated books

- Runs on Exasol Personal local (single node). Scale figures are from our laptop and stated with hardware
- Exasol Personal allows 20 connections; the app uses a pool of four
- The Exasol VM's clock can fall behind after the laptop sleeps (measured about 3 days). Timestamps and hold ages use the app's clock, never the database's
- Exasol local VM as measured: 2 vCPU, 8 GB RAM, on an Apple M4 (16 GB) MacBook

## Generator realism

- One LMS configuration per branch and period, with the "fixed for new loans only" story at BR001 to BR003 (July 2024). Real books will have more variety; anything outside the 33 conventions shows as UNEXPLAINED rather than a wrong label
- Pre-EMI interest is collected on the 5th; EMIs are fixed after the last tranche; no re-amortisation on rate change (tenure absorbs it)
- APR is disclosed as the loan rate (fees not modelled); the APR check (Tier 2) is not built
- Letters: English, Hindi and Tamil. The Hindi and Tamil wording has not been reviewed by a native-speaking compliance writer; month names stay in English
- The live panel samples twice a second, so the SQL and query plan on screen are samples and a statement that finishes between them never appears, including in the walk-through after a run, where a quick step can have nothing to show, and a very small book can show no SQL at all; step times come from the run log and are complete. It shows SQL text from every session on the database, so the app must stay bound to localhost. A run whose process was killed shows as running for up to an hour, until a newer run starts or the hour passes

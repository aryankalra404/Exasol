# Demo

All names and figures are synthetic.

## 3-minute video script

1. **0:00 to 0:20, the person.** "Priya audits a housing finance company. RBI has told lenders to stop these interest practices and refund the excess. Her loan system is the only thing computing interest, and it is what she has to check." Show the RBI text for two seconds
2. **0:20 to 0:50, the whole book.** One click runs the audit inside Exasol. Show measured runtime and row counts, loans per practice, total excess. Point out the evidence-gap and unexplained queues next to the total
3. **0:50 to 1:40, Meena's home loan.** Tranche 2 of ₹12,00,000 at 8.75%: cheque dated 3 Mar, handover acknowledged 11 Mar. Timeline shows every date source side by side. Fingerprint panel shows the posted March interest matches "from cheque date", not the fair convention. Eight days on that tranche: ₹2,301.37. Click the figure to see source rows and the SQL step
4. **1:40 to 2:20, the hard cases.** (a) Raghav: charged from sanction, but his KFS disclosed a commitment fee and the posting reproduces it. PERMITTED under current policy, no refund, setting visible. (b) Asha: cheque tranche, no handover record, other dates 4 days apart. "Cannot decide", kept out of the refund total, branch query generated
5. **2:20 to 2:45, the outcome.** Meena's refund letter, then the checker re-reading every figure against the ledger
6. **2:45 to 3:00, why it holds up.** Oracle agreement figure, false-positive result, one-command setup, MIT licence

Opening matters most: the date conflict and the fingerprint must be on screen in the first minute so nobody files this under "interest calculator".

## Live demo day (top 5)

- 15 min present + 5 min Q&A. Live demo 40%, Q&A depth 30%, real-world applicability 20%, communication 10%. Slides without a working demo are not scored
- Run live on a **fresh seed** to show it is not canned
- Live policy toggle: flip commitment fee permission, re-run, totals change
- Have ready: SQL for money-in-hand and fingerprint steps, `LIMITS.md`, answers on interpretation, data realism, and what a real lender would need to connect
- Backup: recorded video and screenshots if the laptop or network fails

## Prep checklist

- [ ] Demo dataset id and seed fixed, documented
- [ ] Meena, Raghav, Asha present in every dataset (fixtures)
- [ ] Measured numbers for the overview screen
- [ ] Screen recording at 1080p, readable font sizes

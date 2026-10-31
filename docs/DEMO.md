# Demo

All names and figures are synthetic.

## 3-minute video script

1. **0:00 to 0:20, the person.** "Priya audits a housing finance company. RBI has told lenders to stop these interest practices and refund the excess. Her loan system is the only thing computing interest, and it is what she has to check." Show the RBI text for two seconds
2. **0:20 to 0:50, the whole book.** One click runs the audit inside Exasol. Show measured runtime and row counts, loans per practice, total excess. Point out the evidence-gap and unexplained queues next to the total
3. **0:50 to 1:40, Meena's home loan** (`#/loan/LDM0001`, search "Meena"). Tranche 2 of ₹12,00,000 at 8.75%: cheque dated 3 Mar 2025, handover acknowledged 11 Mar. Timeline shows every date source side by side, with the 8 days charged before money in hand shaded. "Why this figure" shows the posted March interest is reproduced exactly by "from the cheque date": ₹12,00,000 × 8.75% × 8 days = ₹2,301.37. Click "SQL that matched it" for the statement
4. **1:40 to 2:20, the hard cases.** (a) Raghav: charged from sanction, but his KFS disclosed a commitment fee and the posting reproduces it. PERMITTED under current policy, no refund, setting visible. (b) Asha: cheque tranche, no handover record, other dates 4 days apart. "Cannot decide", kept out of the refund total, branch query generated
5. **2:20 to 2:45, the outcome.** Meena's refund letter, then the checker re-reading every figure against the ledger
6. **2:45 to 3:00, why it holds up.** Oracle agreement (232,890 of 232,890 periods, 0 paise), RBI's own KFS illustration reproduced to the paisa by the SQL, 0 false positives, robustness (no fair or permitted month refunded even at heavy defects), green CI, MIT licence

Opening matters most: the date conflict and the fingerprint must be on screen in the first minute so nobody files this under "interest calculator".

## Live demo day (top 5)

- 15 min present + 5 min Q&A. Live demo 40%, Q&A depth 30%, real-world applicability 20%, communication 10%. Slides without a working demo are not scored
- Run live on a **fresh seed** to show it is not canned
- Live policy toggle: flip commitment fee permission, re-run, totals change
- Ask the book live from an MCP client (`docs/ASK.md`): "how much do we owe borrowers disbursed by cheque in 2024?", show the SQL, then show the same client being refused a read of `SAHI_TRUTH`
- Meena's letter in Tamil as well as English and Hindi, checker green each time
- Data page: download the template, upload it as a book (three loans), show Meena's ₹2,301.37 again on an uploaded book, then reload the sample. Answers "how would a lender use this?" on screen
- Overview: download the inspection pack and open its README
- Have ready: SQL for money-in-hand and fingerprint steps, `tests/test_rbi_fixtures.py`, `eval/reports/robustness.json`, `LIMITS.md`, answers on interpretation, data realism, and what a real lender would need to connect
- Backup: recorded video and screenshots if the laptop or network fails

## Running the demo

```bash
make demo LOANS=10000   # seed 42; Meena, Raghav, Asha are always LDM0001-LDM0003
make app                # http://127.0.0.1:8000
```

Flow: Overview → root causes → Meena (search) → Raghav (`LDM0002`) → Asha (`LDM0003`, then Work queues → Evidence gaps) → Fix coverage (BR001: every loan still charged was sanctioned before Jul 2024) → Policy: turn off "commitment fee permitted", re-run, compare → Meena's letter (English, Hindi, Tamil) → Method & lineage.

## Prep checklist

- [x] Demo dataset id and seed fixed, documented (`s42_n10000`)
- [x] Meena, Raghav, Asha present in every dataset (fixtures)
- [x] Measured numbers for the overview screen
- [ ] Screen recording at 1080p, readable font sizes

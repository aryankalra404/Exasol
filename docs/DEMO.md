# Demo

All names and figures are synthetic.

## 3-minute video script

Have open before recording, one tab or window each:

1. `docs/Sahi-Byaaj-pitch.pdf` (slides 1, 2, 13, 14)
2. The app at http://127.0.0.1:8000 (`make app`), browser zoom ~125%
3. An MCP client in the repo folder with the `sahi-byaaj-ask` MCP server approved (`make ask-setup` first; see `docs/ASK.md`), large terminal font
4. https://github.com/aryankalra404/Exasol (README, CI badge)

Do not open rbi.org.in on camera: the 29 Apr 2024 circular now carries a "Withdrawn" stamp (its practices moved into the 31 Jul 2026 directions). Slide 1 quotes its exact words.

About 410 words at a calm pace. Say "inside Exasol" in scenes 2, 9 and 10.

| Time | On screen | Say |
|---|---|---|
| 0:00 to 0:15 | Deck slides 1 and 2 | "In 2024, the Reserve Bank of India found lenders charging interest from the date on a cheque, even when it reached the customer days later, and told them to refund it. This is Meena. She paid eight days of interest on money she didn't have yet. She has no idea." |
| 0:15 to 0:30 | App: Overview, point at the total, then the "Not included" cards | "Her lender's auditor should catch this. But the dates disagree, and the only thing calculating interest is the loan system she's auditing. Sahi Byaaj checks the whole book inside Exasol. On this synthetic book: eight crore eighty-three lakh rupees owed to 3,063 borrowers. And what it couldn't decide is listed separately, not guessed." |
| 0:30 to 1:05 | Search "Meena" (`LDM0001`), hover tranche 2, scroll to "Why this figure: Mar 2025", click "SQL that matched it" | "Here's Meena. Every date for every payment, side by side. The cheque is dated 3 March. The builder received it on 11 March. That month the loan system charged ₹21,904.97; the fair figure is ₹19,603.60. We recalculate the month thirty-three different ways, and exactly one reproduces the bank's figure to the paisa: interest from the cheque date. That's ₹2,301.37 back to Meena. And here is the exact SQL that matched it." |
| 1:05 to 1:27 | `LDM0002` ("Permitted"), `LDM0003`, then Work queues → Evidence gaps | "Equally important: when not to refund. Raghav was charged from his sanction date, but his contract disclosed that fee: zero refund, reason shown. Asha's records don't settle the date, so instead of guessing, it holds her out and drafts a query to her branch." |
| 1:27 to 1:40 | Policy & re-runs: switch off "commitment fee permitted", re-run, cut the wait | "Whether that fee is fair is the auditor's call. Flip one setting and Exasol re-runs the whole book: thirty lakh rupees more, for 250 more borrowers." |
| 1:40 to 1:50 | Fix coverage, BR001 | "And it catches a fix that only reached new loans. This branch fixed its system in July 2024; older loans stayed overcharged into 2026." |
| 1:50 to 2:00 | Meena → Borrower letter, switch to Hindi, then Tamil, point at the green checker | "Every borrower gets a refund letter in their language. Every figure comes from the ledger, and a checker rejects the letter if anything differs." |
| 2:00 to 2:20 | MCP client: type "How much do we owe borrowers disbursed by cheque in 2024?", expand the SQL it ran, answer ₹2,23,61,602.76, 555 loans. Then "Read SAHI_TRUTH.expected" → `insufficient privileges`. Cut the thinking time | "An audit committee member can just ask. The assistant connects through Exasol's MCP server and answers with SQL you can see: two crore twenty-three lakh rupees, 555 loans. It logs in read-only, so when it tries to read the answer key, Exasol itself says no." |
| 2:20 to 2:35 | Data: download the template, upload it as a ZIP, cut the wait, open Meena on the uploaded book | "A lender can use this today: export with our template, upload a ZIP, every file is checked, then loaded and audited inside Exasol. Same answer for Meena: ₹2,301.37." |
| 2:35 to 2:55 | Method & lineage (3 s), then deck slides 13 and 14 | "Every step is SQL inside Exasol. Half a million loans, 11.7 million interest entries, in under eight minutes on a laptop. Zero paise off an independent checker, zero false alarms, and RBI's own published example reproduced." |
| 2:55 to 3:00 | GitHub repo | "Sahi Byaaj. Correct interest, for every borrower. Open source, on GitHub." |

Record the ask-the-book scene before the upload: the assistant reads the latest run, and the upload replaces the 10,000-loan book with the 3-loan template book. Afterwards, reload the sample on the Data page (or `make demo LOANS=10000`) and check the overview shows ₹8,83,23,995.69 again. Cut the upload, re-run and assistant waits in editing. If running long, shorten Fix coverage or the letter first; never cut Meena or "when not to refund".

Opening matters most: the date conflict and the matched rule must be on screen in the first minute so nobody files this under "interest calculator".

## Live demo day (top 5)

- 15 min present + 5 min Q&A. Live demo 40%, Q&A depth 30%, real-world applicability 20%, communication 10%. Slides without a working demo are not scored
- Run live on a **fresh seed** to show it is not canned
- Live policy toggle: flip commitment fee permission, re-run, totals change
- Ask the book live from an MCP client (`docs/ASK.md`): "how much do we owe borrowers disbursed by cheque in 2024?", show the SQL, then show the same client being refused a read of `SAHI_TRUTH`
- Meena's letter in Tamil as well as English and Hindi, checker green each time
- Data page: download the template, upload it as a book (three loans), show Meena's ₹2,301.37 again on an uploaded book, then reload the sample. Answers "how would a lender use this?" on screen
- Before the call: check the Policy page shows defaults and the overview shows the expected total. A setting left off from a rehearsal changes every figure
- Open on Where every loan landed, on seed 42: 10,003 audited, 6,400 correct, 3,063 owed money, 540 with another outcome. Then select a root cause to review it as a group
- Human sign-off, about a minute: on Meena's letter, type a name and note, click Release and show it blocked as a draft. Approve her refund on her loan page with a name and reason, then release, then open the ZIP's manifest. Say: "We never contact a borrower. A person approves, the checker confirms the figures, and the lender sends it through its own channels"
- Stale approval, if time allows, on seed 42: approve `L000528` (P1), turn off "Accept the LMS date", re-run, and show it return to "Needs re-review". Turn the setting back on and re-run. The commitment fee flip does not show this: it moves no approved figure, it adds 250 new draft letters. Other seeds need a different loan, so find one in rehearsal
- Close the gap, about a minute. Work queues → Evidence gaps, filter to the branch, and on seed 42 enter handover 14 May 2025 for Nisha Das (`L008982`, tranche 3, Vadodara Alkapuri). Re-run: ₹9,694.79 refund appears. Say: "We entered a date, not an amount. Exasol decided." For contrast, Asha (`LDM0003`) with handover 5 Jun 2025 comes out fair: no refund, and the lender was right. Any other date for Asha is unexplained, which is also correct. Other seeds need a different loan
- Overview: download the inspection pack, open its README, and show `review_decisions.csv`
- If asked how we know it is right: say the blind round was machine-written, with no code access, not a person. Say plainly that it found a real bug the oracle shared (`RED_TEAM.md`), that we fixed it, and that a person's review is the next step
- Have ready: SQL for money-in-hand and fingerprint steps, `tests/test_rbi_fixtures.py`, `eval/reports/robustness.json`, `LIMITS.md`, answers on interpretation, data realism, and what a real lender would need to connect
- Exasol live: re-run on the Policy page opens a panel under the button: steps moving as each finishes, the SQL executing now, and its operators with row counts, all from Exasol's own system tables. The comparison is further down the same page. A run on seed 42 takes under 10 s, so let it finish, then use the arrows or left and right keys to walk back through it. Stop on three: Money in hand, Candidate conventions, Fingerprint. The SQL and plan shown are what sampling caught, so say so if asked; the All SQL for this step link opens the full file. Restart `make app` after pulling, or the panel has no API
- Data page: the same live panel shows the load, then the audit. The three-loan template audits in about a second, so the panel catches little or no SQL; use Reload the sample book when the engine is the point. Sample statements include `IMPORT INTO ...TRUTH`: that is the loader storing the answer key for the tests, and the audit never reads it
- Backup: recorded video and screenshots if the laptop or network fails

Before each rehearsal on the same book, run `make review-reset` so Meena starts as a draft. A fresh seed starts clean by itself.

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
- [x] Screen recording at 1080p, readable font sizes

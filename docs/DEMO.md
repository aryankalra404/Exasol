# Demo

All names and figures are synthetic.

## 3-minute video script

Have open before recording, one tab or window each:

1. `docs/Sahi-Byaaj-pitch.pdf` (slides 1, 2, 12, 13)
2. The app at http://127.0.0.1:8000 (`make app`), browser zoom ~125%
3. https://github.com/aryankalra404/Exasol (README, CI badge)

Do not open rbi.org.in on camera: the 29 Apr 2024 circular now carries a "Withdrawn" stamp (its practices moved into the 31 Jul 2026 directions). Slide 1 quotes its exact words.

| Time | On screen | Say |
|---|---|---|
| 0:00 to 0:15 | Deck slides 1 and 2 | "RBI found lenders charging interest from the date on a cheque handed over days later, and told them to refund it. Meena paid 8 days of interest on money she didn't have yet. She has no idea." |
| 0:15 to 0:35 | App: Overview | "Sahi Byaaj audits the whole book inside Exasol. This test book: ₹8,83,23,995.69 owed to 3,063 borrowers. And everything it couldn't decide is shown here, not guessed." |
| 0:35 to 1:15 | Search "Meena" (`LDM0001`) | "Every date for every payment, side by side. Cheque dated 3 March, handed over 11 March. The bank posted ₹21,904.97; fair is ₹19,603.60. One rule reproduces the bank's figure to the paisa: from the cheque date." Click "SQL that matched it" |
| 1:15 to 1:45 | `LDM0002`, then `LDM0003`, then Work queues | "Raghav: his contract disclosed this fee, so no refund. Asha: her records don't settle the date, so it drafts a query to the branch instead of guessing." |
| 1:45 to 2:00 | Policy & re-runs | "If the auditor decides that fee isn't fair, one switch re-runs the whole book in Exasol: ₹30.7 lakh more, 250 more borrowers." If the live re-run is slow on camera, show the run comparison |
| 2:00 to 2:15 | Fix coverage | "This branch fixed its system in July 2024, but only for new loans. Older loans stayed overcharged into 2026." |
| 2:15 to 2:30 | Borrower letter, switch to Hindi or Tamil | "The refund letter, in the borrower's language. Every figure comes from the ledger and is checked." |
| 2:30 to 2:37 | Method & lineage | "Every step is SQL inside Exasol, with its timing and fingerprint." |
| 2:37 to 2:55 | Deck slides 12 and 13 | "Half a million loans in under 8 minutes on a laptop. 0 paise off an independent checker. Zero false alarms. RBI's own example reproduced." |
| 2:55 to 3:00 | GitHub repo | "Open source, MIT. Everything reproduces from the README." |

Opening matters most: the date conflict and the matched rule must be on screen in the first minute so nobody files this under "interest calculator".

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

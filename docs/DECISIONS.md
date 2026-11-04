# Decisions

Short log of non-obvious choices. Newest at the bottom. Each entry: what, why, what we gave up. Status: `accepted`, `superseded by Dxx`, `proposed`.

---

**D01. Build the interest audit, not reconciliation or fraud** (accepted)
- Why: regulator-stated problem with refunds ordered; no public Track 01 entry on it; Exasol does the core work; correctness checkable to the paisa
- Gave up: microfinance household-cap idea (bigger impact story, weaker novelty and circular evaluation)

**D02. All audit math in SQL inside Exasol** (accepted)
- Why: 25% of score is effective use of Exasol; set-based exact decimals are the right tool; keeps the app thin
- Gave up: faster iteration in pandas

**D03. Integer paise at rest, DECIMAL(36,12) intermediates, round half up once per period** (superseded by D15)
- Why: paisa-exact claims need exact arithmetic and one well-defined rounding point
- Gave up: nothing meaningful

**D04. Balance intervals, not day-by-day rows** (accepted)
- Why: scales to millions of loans; still day-exact
- Gave up: simpler SQL

**D05. Conventions as 4 dimensions (32 candidates) plus a disclosed-commitment-fee variant** (accepted)
- Why: covers combinations (cheque date + full month) without hand-listing; set-based to compute all at once
- Gave up: some unrealistic combinations get computed anyway (cheap)

**D06. Excess = posted - fair; attribution only labels it** (accepted)
- Why: the refund does not depend on naming the practice correctly, so mislabelling cannot change money
- Gave up: nothing

**D07. No re-amortisation; excess measured on the recorded principal path** (accepted)
- Why: re-amortising cascades through every later EMI and needs the lender's allocation rules; conservative understatement is defensible
- Gave up: a few paise to rupees of refund on long-running unfair loans. Stated in LIMITS

**D08. GAP and UNEXPLAINED are excluded from the refund total** (accepted)
- Why: the total must be defensible line by line; uncertain rows are shown separately with what is missing
- Gave up: a bigger headline number

**D09. Money-in-hand precedence is data, not code** (accepted)
- Why: interpretations differ between lenders; the compliance head can change them and re-run
- Gave up: nothing

**D10. Hidden LMS config lives only in SAHI_TRUTH** (accepted)
- Why: fingerprinting must infer the convention from postings alone, or the evaluation is circular
- Gave up: nothing

**D11. Generator writes CSV, loaded with IMPORT via pyexasol** (accepted)
- Why: simplest portable path on a local Mac install
- Revisit if load time dominates at large sizes (Parquet)

**D12. FastAPI + Next.js static build, one process for the demo** (superseded by D19)
- Why: Python keeps DB access close to the pipeline; Next.js gives a better auditor UI than Streamlit; static build avoids two servers at demo time
- Gave up: Streamlit's speed of building

**D13. UDFs only for APR (Tier 2)** (accepted)
- Why: APR is an IRR, found iteratively; everything else is better as plain SQL and a UDF would hide the work. Local UDFs also need the script language container installed
- Gave up: nothing

**D14. AI only phrases text and answers questions over results; it never computes or classifies** (accepted)
- Why: deterministic, checkable outputs are the whole pitch
- Gave up: flashier "AI auditor" framing

**D15. Exact integer numerators instead of DECIMAL(36,12) intermediates** (accepted)
- What: each interval's interest is the integer `balance_paise * rate_micro * days`; a month sums them and rounds once with `sign(N) * DIV(2|N| + D, 2D)`
- Why: no decimal-division scale questions at all; Exasol `DIV` on `DECIMAL(36,0)` is exact; the oracle can reproduce it independently in plain integers
- Gave up: nothing

**D16. Candidate conventions as differences from the fair path** (accepted)
- What: S30 stores, per convention, only the dated balance changes that differ from fair; candidate = fair numerator + difference numerator
- Why: 33 full loan histories per loan would be ~30x the rows; differences are usually two rows per tranche. Exact because interest is linear in balance
- Gave up: a slightly less obvious SQL shape (explained in the step header and DOMAIN.md)

**D17. Loan-history tie-break before fewest dimensions** (accepted)
- What: when several conventions reproduce one month, prefer the one that reproduces the most of that loan's differing months; then fewest unfair dimensions; else AMBIGUOUS
- Why: some months are genuinely indistinguishable on their own (from-sanction vs full-month); the same loan's other months are legitimate evidence. On the 2,003-loan test book this cut AMBIGUOUS months from 407 to 94, and every MATCHED month was then either the hidden convention or numerically identical to it
- Gave up: a purely per-month rule. Evidence-gap months do not vote, because their fair figure is provisional (the oracle caught this)

**D18. Duplicate evidence keeps the earliest date; GAP periods are bounded by the evidence window** (accepted)
- Why: earliest gives the smaller refund claim, so the total stays defensible; the conflict is flagged. A GAP only makes the months it could affect uncertain, so later months are still audited
- Gave up: a larger refund total on duplicate-ack loans

**D19. React + Vite static build instead of Next.js** (accepted)
- Why: the UI is a static single-page app served by the FastAPI process; Vite builds it in under a second with no server runtime. Fonts are bundled (`@fontsource`) so the demo works offline
- Gave up: Next.js routing conventions (not needed; hash routing)

**D20. Letters in English and Hindi; Tamil not yet** (superseded 31 Oct: Tamil added, same template and checker)
- Why: time. A Tamil-preferring borrower gets the English letter and the UI says so
- Gave up: Tamil (Tier 1 item, done 31 Oct)

**D21. RBI worked example as a one-loan fixture run through the real pipeline** (accepted)
- Why: a public anchor the generator did not produce. RBI's illustration (Rs 20,000, 24 months, EMI Rs 969.73, interest Rs 3,274, fee Rs 400, APR 17.07%) does not quote the rate in the excerpts we could read; 15% p.a. reproduces all four figures at once, and the test asserts that. 30E/360 is disclosed in the fixture so each whole month is balance x rate / 12, as in RBI's schedule. The SQL test loads it into separate `RBIFIX_*` schemas and drops them after, so demo data is untouched
- Gave up: comparing row by row with RBI's printed schedule (the RBI PDF host served a CAPTCHA, so rows were not read directly)

**D22. Ask-the-book through Exasol's MCP server, a dedicated user and latest-run views** (accepted)
- Why: the audit committee asks ad-hoc questions the screens do not anticipate. Exasol's own MCP server does the plumbing; a separate `ASK_READER` with `SELECT` on `SAHI_ASK` only means the database, not the prompt, keeps the assistant away from `SAHI_TRUTH`, raw evidence and borrower names, and off every write. Views pinned to the latest completed run stop an assistant from summing across runs. The starter kit's MCP user reads every schema, so it was not used
- Gave up: the kit's one-command `exakit mcp-setup`; an in-app chat box (would need an API key in the demo)

**D23. Generator streams rows to CSV instead of holding the book in memory** (accepted)
- Why: peak memory was 3.6 GB at 100k loans, so 1M would not fit beside the Exasol VM. Rows are written per table in the same order, so output is byte-identical (checked on s42_n10000: every CSV and the manifest match); peak memory at 100k is now 277 MB
- Gave up: nothing

**D24. Load your own book from the app: ZIP upload checked against the table DDL, then the normal loader** (accepted)
- Why: a user opening the app needs to see what data it is showing and how to put their own in. The upload is checked file by file against `sql/01_raw_schema.sql` (columns, dates, whole paise, booleans, widths, loan references) before Exasol is touched, so a bad file never half-replaces a book; if Exasol still rejects it, the previous book is reloaded. It then goes through the same `scripts/load.py` IMPORT and audit as `make demo`. The ZIP is sent as the raw request body so no extra upload library is needed
- Gave up: multi-book side by side (one book loaded at a time; runs of earlier books stay in history); very large books, which load faster with `make load`

**D25. Inspection pack is a copy, not a report** (accepted)
- Why: what an inspector needs is the rows and the means to check them: the ledger, every finding with its evidence ids, the branch queries, the policy snapshot, and the SQL files whose SHA-256 must match `lineage`. A ZIP of CSVs and SQL is what an audit file holds; nothing is recalculated
- Gave up: a formatted PDF


**D26. Human review is a separate append-only log; a decision can never change a figure** (accepted)
- Why: the app told people to review items but could not record the outcome, and nobody signed off before a letter could leave. A decision stores who, why and the figure seen, copied from the ledger by SQL. If a re-run changes the figure, the decision goes stale and the row needs a fresh look. To change a refund, a person changes evidence or policy and re-runs, which keeps "every number is computed by SQL" true
- Gave up: reviewer-entered adjustments; real identity (names are self-declared until a lender puts the app behind its sign-on)

**D27. Release letters, do not send them** (accepted)
- Why: a lender sends through its own approved channels, under its own compliance controls, and the demo data has no real recipients. Release re-runs the checker on every letter, stores the exact text with its SHA-256, and produces a ZIP and manifest. The status says "Released" because this tool cannot know whether a letter was delivered
- Gave up: delivery tracking, bounces, consent handling

**D28. Red-team loans are written outside the team's code, and answers come first** (accepted)
- Why: agreement on generated books is partly circular, because one author wrote the generator, the SQL and the oracle. Answers written before the first run cannot be fitted to the result. The harness reports disagreements and never decides who is right. `RT_*` schemas are dropped each run, so results always use default policy and the demo book stays untouched
- Gave up: speed; this needs a person who has not read the code. A machine-written round with no code access was run first and is labelled as such everywhere; it does not count as a person's review

**D29. A branch reply is entered as evidence, then the audit re-runs** (accepted)
- Why: the gap queue drafted a query but nothing happened when the branch answered. The reviewer enters a date and document reference, never a figure, and the same SQL rules decide the result, which may be a refund, fair, or unexplained. The oracle reads the same entries from its own path, so it can still disagree. Stored in `SAHI_POLICY` because `make load` rebuilds `SAHI_RAW`
- Gave up: attaching the document itself; bulk entry from a file

**D30. Every loan gets one outcome, and refunds show their evidence level, not a "correct" label** (accepted)
- Why: the loans found correct were invisible, and an auditor needs "these are clean" as much as "these are wrong". Refunds are reviewed by root cause, because nobody clicks through thousands of rows. The level says what the evidence is ("exact match, confirmed date"), not that a refund is certain: a matching record can still be wrong. Disagreeing dates do not lower the level, because that disagreement is often what proves the overcharge
- Gave up: a single confidence score, which would hide what the doubt actually is

**D31. The live view reads Exasol's system tables rather than having the pipeline report progress** (accepted)
- Why: judges should see the engine itself, not an animation we could have scripted. `EXA_DBA_SESSIONS` and `EXA_DBA_PROFILE_RUNNING` give the real statement and operators, and the existing run log gives step progress, so `scripts/audit.py` did not change. Its own connection means a poll never waits on the app's pool
- It opens on the Policy page, not a page of its own, so the re-run, the engine and the changed totals stay on one screen
- Gave up: a complete statement list, which needs auditing or profiling switched on; polling is a sample and the panel says so. Watching a terminal run in the app

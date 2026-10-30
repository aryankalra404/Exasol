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

**D20. Letters in English and Hindi; Tamil not yet** (accepted)
- Why: time. A Tamil-preferring borrower gets the English letter and the UI says so
- Gave up: Tamil (Tier 1 item, still open)


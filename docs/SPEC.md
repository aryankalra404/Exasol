# Spec

What we build, in priority order. Tiers are cut lines: finish a tier fully (tested, documented) before starting the next. If time runs short, the lowest unfinished tier is dropped, not half-shipped.

## Tier 0: must ship (submission is incomplete without it)

**Data**
- Synthetic loan book generator, fixed seed, sizes from 100 to 1M+ loans
- Products: home loan (staged tranches, cheques to builders/sellers, pre-EMI), personal loan
- Hidden per-branch, per-period loan-system configuration (which conventions it applies), written only to the truth schema. Includes the story: an unfair convention fixed for new loans in mid-2024 but never migrated for existing ones
- Injected defects: missing handover acks, conflicting dates, reversed and re-posted interest, holiday-shifted credits, manual adjustments

**Engine (all SQL in Exasol)**
1. Load raw extracts
2. Resolve money-in-hand date per tranche (precedence table as data, conflict flag, evidence gap)
3. Build constant-balance intervals (no day-by-day expansion)
4. Entitled (fair) interest per billing period, exact decimals, KFS day-count basis
5. Candidate conventions recomputed side by side
6. Fingerprint: which convention reproduces each posting to the paisa
7. Permitted check against KFS and sanction terms, driven by an editable policy table
8. Findings, refund ledger, evidence-gap list, unexplained queue, rollups (practice, branch, product, config period)
9. Lineage: every finding carries the SQL step id and source row references

**Practices covered in Tier 0:** P1 sanction/agreement date, P2 cheque date, P3 full month, P4 advance instalment ignored, P5 EMI on sanctioned amount. (Codes defined in `DOMAIN.md`.)

**App (reads result tables only)**
- Book overview: totals, loans per practice, refund total, evidence gaps, unexplained, measured runtime
- Loan timeline: every date source side by side, resolved date, fingerprint panel, click a figure to see source rows and SQL step
- Refund ledger with filters and CSV export
- Evidence-gap queue

**Borrower letter**
- One-page refund letter in English, every figure substituted from the ledger
- Checker re-reads the letter and rejects it if any figure differs from the ledger

**Proof**
- Independent Python oracle (exact `Decimal`), agreement on 10,000+ loans, largest deviation reported
- RBI worked examples as fixtures (digital lending fact-sheet: ₹20,000 over 24 months, instalment ₹969.73 rounded to ₹970)
- False-positive suite: disclosed commitment fee, disclosed 30/360, fairly posted periods. Broken-period interest is part of the fair path, not a separate case (`LIMITS.md`)
- Fingerprint accuracy against the hidden configuration, including share sent to "unexplained"
- Measured scale run on our laptop: rows, runtime, hardware

**Docs and submission**
- README (overview, setup, usage), run guide, deployment instructions
- `WHY_EXASOL.md`, `DECISIONS.md`, `LIMITS.md`, `CONTRIBUTING.md`, MIT licence
- One-command setup and demo
- Pitch deck (PDF), demo video under 3 minutes, problem statement

## Tier 1: differentiators (strongly wanted)

- **Live policy toggle:** flip a policy (for example "commitment fee from sanction is permitted if disclosed"), the book re-audits in Exasol, totals change on screen, run time shown
- **Config regression mode:** diff two audit runs, group changes by loan-system config period, surface "fixed for new loans, old loans never migrated"
- **P6:** amortisation changes after part-disbursement not communicated (needs KFS amortisation schedule and a communications log)
- **Loan against property** as a third product
- **Letters in Hindi and Tamil,** same checker (built)
- **Evidence-gap branch query** auto-drafted per gap ("handover ack missing for tranche 2")
- CI running tests on every push, badge in README
- **Human review and release (built, added for the finale):** approve or hold each refund with a name and reason, record outcomes on unexplained months, sign policy changes, release approved letters as a ZIP and manifest. Decisions never change a figure. See `DECISIONS.md` D26, D27

## Tier 2: stretch

- **Ask the book (built, see `ASK.md`):** assistant over Exasol's MCP server, read-only on the `SAHI_ASK` views. Shows the SQL it ran. Never computes a number itself
- **APR check** against KFS disclosed APR via a Python UDF (IRR is iterative, the one place a UDF is justified)
- **Blind red team (machine-written round done, a person still wanted, see `RED_TEAM.md`):** someone who did not write the generator builds about 10 adversarial loans from the RBI text. Report results including misses
- Robustness curve: defect level from none to heavy vs refund totals and gap counts
- Cloud deployment guide (Exasol Personal on AWS)

## Explicitly out

Sending letters to borrowers (`DECISIONS.md` D27), penal charges, prepayment charges, floating-rate pass-through and reset lags, GST, NPA classification, restructured loans and moratoria, credit cards, co-lending, OCR of real documents, posting refunds back into a loan system, any legal opinion on contested interpretations.

## Acceptance criteria for the demo loans

These are fixtures, checked by tests. Figures are synthetic.

| Loan | Setup | Expected |
|---|---|---|
| Meena (home) | Tranche 2 ₹12,00,000 at 8.75%, cheque dated 3 Mar, handover ack 11 Mar | Fingerprint = from cheque date. Excess for tranche 2 in March = 8 days = ₹2,301.37 |
| Raghav (home) | Charged from sanction date, KFS discloses a commitment fee that the posting reproduces | Status PERMITTED under default policy, ₹0 refund, visible policy reason |
| Asha (home) | Tranche paid by cheque, no handover record, cheque date and rail credit 4 days apart | Status EVIDENCE_GAP, excluded from refund total, branch query generated |

Check: 12,00,000 × 0.0875 × 8 / 365 = 2,301.3698... → ₹2,301.37.

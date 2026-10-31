# Sahi Byaaj

[![ci](https://github.com/aryankalra404/Exasol/actions/workflows/ci.yml/badge.svg)](https://github.com/aryankalra404/Exasol/actions/workflows/ci.yml)

**A full-book interest audit for Indian lenders, built on Exasol Personal.**
ExaThon India 2026, Track 01: Money, Risk & Regulation.

> An internal auditor at a housing finance company can't show that no borrower paid interest for days before their money actually reached them, because the dates that decide interest sit in records that disagree, and the only thing computing interest is the loan system she is supposed to be checking. If this worked, she would know every overcharged borrower and the exact refund owed, with evidence, before the regulator's inspection finds it.

In April 2024 RBI found lenders charging interest from the sanction date, from the date on a cheque handed over days later, for whole months when money was out for part of one, and on advance EMIs already collected. It told them to refund, and in July 2026 wrote these practices, plus two new ones on part-disbursed loans, into its supervisory directions.

Sahi Byaaj checks this for every loan, every tranche and every day, inside Exasol:

- **Finds the day the money actually reached the borrower** from conflicting records (LMS date, cheque date, handover acknowledgement, payment-rail credit), with an editable precedence rule and visible conflicts
- **Names the rule the lender's system applied** by recomputing each posting under 33 candidate conventions and matching to the paisa. Nothing is labelled from outside; the posting is the evidence
- **Separates unfair practice from disclosed, permitted terms** using the Key Facts Statement and an editable policy
- **Produces a paisa-exact refund ledger** with lineage to source rows and the SQL step behind each figure
- **Shows what it cannot decide** (evidence gaps, unexplained postings) instead of guessing, with a drafted query to the branch for every gap

All data is synthetic. See [docs/LIMITS.md](docs/LIMITS.md).

## Results, as measured

Exasol Personal local, single node, VM with 2 vCPU. Demo and 100k books: VM 8 GB on an Apple M4 MacBook (16 GB), 30 Oct 2026. 500k book: VM 12 GB on an Apple M4 MacBook Air (24 GB), 31 Oct 2026. Full table in [docs/STATUS.md](docs/STATUS.md).

| | Demo book | 100k book | 500k book |
|---|---|---|---|
| Loans / tranches | 10,003 / 15,794 | 100,003 / 157,461 | 500,003 / 785,974 |
| Interest postings | 234,195 | 2,342,745 | 11,702,698 |
| Billing periods recomputed | 232,890 | 2,329,775 | 11,639,169 |
| Full audit inside Exasol, end to end | 16.2 to 17.4 s | 120.6 s | 479.0 s |
| Independent oracle agreement | 232,890 of 232,890 periods, all loans | 70,361 of 70,361 periods, random 3,003 loans | 69,895 of 69,895 periods, random 3,003 loans |
| Largest deviation from oracle | 0 paise | 0 paise | 0 paise |

Fingerprint accuracy against the generator's hidden configuration (demo book): every one of 7,535 MATCHED periods names either the hidden convention (6,612) or one that produces the identical figure (923); all 2,072 PERMITTED periods are exact. Periods the tool could not decide go to EVIDENCE_GAP (252), UNEXPLAINED (454) or AMBIGUOUS (385); every UNEXPLAINED period traces to a planted defect.

False positives: 0 wrongly flagged. Disclosed commitment fees, a disclosed 30E/360 basis and fairly posted months are never sent to the ledger (`tests/test_false_positives.py`). Public anchor: RBI's own KFS illustration (₹20,000 over 24 months, EMI ₹969.73, APR 17.07%) runs through the full SQL pipeline and every month reproduces to the paisa (`tests/test_rbi_fixtures.py`).

Robustness (`make robustness`): the same 10,000-loan book with no defects, the default level and three times that. With no defects the refund total equals the true unfair excess exactly; with 1,338 and 4,057 planted defects it recovers 98.37% and 96.82%, and the rest waits in the gap and unexplained queues. No level refunds a single fair or permitted month.

## The three demo loans

| Loan | What happened | What Sahi Byaaj says |
|---|---|---|
| **Meena**, home loan, `LDM0001` | Tranche 2 of ₹12,00,000 at 8.75%: cheque dated 3 Mar 2025, handover acknowledged 11 Mar | Posting reproduced exactly by "from the cheque date" (P2). Excess 8 days = **₹2,301.37** |
| **Raghav**, home loan, `LDM0002` | Charged from sanction date, but his KFS discloses a commitment fee and the posting reproduces it | **PERMITTED** under default policy, ₹0 refund, reason shown. Flip the policy and it becomes a P1 refund |
| **Asha**, home loan, `LDM0003` | Cheque tranche, no handover record, cheque date and rail credit 4 days apart | **EVIDENCE_GAP**: kept out of the total, query to the branch drafted |

Check: 12,00,000 × 8.75% × 8 / 365 = 2,301.3698… → ₹2,301.37.

## Quick start

Needs macOS on Apple Silicon (or Linux/WSL), Python 3.11+, Node 18+.

```bash
# 1. Exasol Personal, local
curl https://www.exasol.com/install/starter-kit.sh | sh
exasol install local

# 2. Connection: copy the template, then put the password from
#    ~/.exasol/personal/deployments/default/secrets.json into .env
cp .env.example .env

# 3. Python + web dependencies
make setup

# 4. Generate a 10,000-loan synthetic book, load it into Exasol, run the audit
make demo LOANS=10000

# 5. Tests, and the independent oracle against every loan
make test
make oracle LOANS=10000

# 6. The auditor app on http://127.0.0.1:8000
make app

# 7. Optional: ask the book from an MCP client (read-only views, see docs/ASK.md)
make ask-setup && make ask-smoke
```

## What you see

- **Overview**: the refund total, what is held out of it and why, excess by RBI practice and branch, and *what the loan system was actually doing* (one row per branch and behaviour, found from the postings alone)
- **Loan**: every date source per tranche on one timeline, every billing month posted vs recomputed, and *why this figure*: the fair interest interval by interval, the extra balance that was charged and on which days, the postings, and the SQL step
- **Refund ledger**: filter, sort, export CSV
- **Work queues**: evidence gaps with drafted branch queries, unexplained, ambiguous, permitted, undercharge
- **Fix coverage**: was a fix applied to everyone or only new loans? Sanction-cohort × charge-quarter heatmap. A fix that covered only new loans shows as old cohorts still being charged
- **Policy & re-runs**: flip an interpretation, re-run the whole book in Exasol, compare runs loan by loan
- **Letter**: borrower refund letter in English, Hindi or Tamil, every figure from the ledger, rejected by the checker if any figure differs
- **Method & lineage**: each SQL step with its file, SHA-256 and timing
- **Ask the book** (any MCP client): "how much do we owe borrowers disbursed by cheque in 2024?" answered by SQL over read-only views through Exasol's MCP server, SQL shown. The assistant's database user cannot read the truth tables or borrower names, or write anything. See [ASK](docs/ASK.md)

## How it works

```
generator (synthetic book + simulated LMS with a hidden per-branch config)
   └─ CSV ──IMPORT──► Exasol SAHI_RAW
                         └─ sql/10..90, in Exasol ──► SAHI_OUT ──► API + UI, letters
oracle (independent Python, day by day) ──► compared with SAHI_OUT, to the paisa
```

- **Exact arithmetic**: each interval's interest is the integer `balance_paise × rate × days`; each month is rounded half up once with integer `DIV`. No floats anywhere
- **Intervals, not days**: balances change a few dozen times per loan, so the SQL works on constant-balance intervals clipped to billing months
- **All 33 conventions at once**: each convention is stored only as its difference from the fair path (often two rows), so candidate figures are fair + difference, computed side by side
- **Fingerprint, then label**: the convention that reproduces the posting names the practice; ties are broken by the loan's own posting history. Excess is always posted minus fair, so a wrong label can never change a refund

Details: [DOMAIN](docs/DOMAIN.md) (rules), [WHY_EXASOL](docs/WHY_EXASOL.md) (step → SQL file map).

## Docs

| Doc | What |
|---|---|
| [PROBLEM](docs/PROBLEM.md) | Problem, users, evidence, sources |
| [SPEC](docs/SPEC.md) | Scope and acceptance criteria |
| [DOMAIN](docs/DOMAIN.md) | Interest rules, conventions, RBI practice codes |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Components and data flow |
| [CONTRACT](docs/CONTRACT.md) | Tables and interfaces |
| [WHY_EXASOL](docs/WHY_EXASOL.md) | What runs in Exasol and why |
| [ASK](docs/ASK.md) | Ask the book over MCP, read-only |
| [FEATURES](docs/FEATURES.md) | Feature thinking: built, next, rejected |
| [DECISIONS](docs/DECISIONS.md) | Decision log |
| [LIMITS](docs/LIMITS.md) | Limitations and assumptions |
| [DEMO](docs/DEMO.md) | Demo script |
| [STATUS](docs/STATUS.md) | Task board and measured results |

## Licence

[MIT](LICENSE)

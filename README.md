# Sahi Byaaj

**A full-book interest audit for Indian lenders, built on Exasol Personal.**
ExaThon India 2026, Track 01: Money, Risk & Regulation.

> An internal auditor at a housing finance company can't show that no borrower paid interest for days before their money actually reached them, because the dates that decide interest sit in records that disagree, and the only thing computing interest is the loan system she is supposed to be checking. If this worked, she would know every overcharged borrower and the exact refund owed, with evidence, before the regulator's inspection finds it.

In April 2024 RBI found lenders charging interest from the sanction date, from the date on a cheque handed over days later, for whole months when money was out for part of one, and on advance EMIs already collected. It told them to refund, and in July 2026 wrote these practices, plus two new ones on part-disbursed loans, into its supervisory directions.

Sahi Byaaj checks this for every loan, every tranche and every day, inside Exasol:

- **Finds the day the money actually reached the borrower** from conflicting records, with an editable precedence rule and visible conflicts
- **Names the rule the lender's system applied** by recomputing each posting under every candidate convention and matching to the paisa
- **Separates unfair practice from disclosed, permitted terms** using the Key Facts Statement
- **Produces a paisa-exact refund ledger** with lineage to source rows and the SQL step behind each figure
- **Shows what it cannot decide** (evidence gaps, unexplained postings) instead of guessing

All data is synthetic. See [docs/LIMITS.md](docs/LIMITS.md).

## Status

Under active development for the 31 Oct 2026 submission. See [docs/STATUS.md](docs/STATUS.md).

## Quick start

Setup, data generation, audit run and app instructions will be added here as each part lands.

```
# 1. Install Exasol Personal (macOS / Linux / WSL)
curl https://www.exasol.com/install/starter-kit.sh | sh

# 2. Configure connection
cp .env.example .env   # fill in DSN, user, password

# 3. Remaining steps: TBD
```

## Docs

| Doc | What |
|---|---|
| [PROBLEM](docs/PROBLEM.md) | Problem, users, evidence, sources |
| [SPEC](docs/SPEC.md) | Scope and acceptance criteria |
| [DOMAIN](docs/DOMAIN.md) | Interest rules, conventions, RBI practice codes |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Components and data flow |
| [CONTRACT](docs/CONTRACT.md) | Tables and interfaces |
| [WHY_EXASOL](docs/WHY_EXASOL.md) | What runs in Exasol and why |
| [DECISIONS](docs/DECISIONS.md) | Decision log |
| [LIMITS](docs/LIMITS.md) | Limitations and assumptions |

## Licence

[MIT](LICENSE)

# Contributing

Thanks for looking. Sahi Byaaj is MIT licensed and welcomes issues and pull requests.

## Ground rules

- Every audit figure is computed in SQL inside Exasol. Python and JS only read results (the test oracle is the one exception)
- Money is integer paise; no floating point anywhere
- Interest rules are defined in `docs/DOMAIN.md`. Change the doc, the SQL and the oracle together
- Shared table shapes are defined in `docs/CONTRACT.md`. Bump its version when you change them
- Synthetic data only. Never add real borrower, lender or employer data

## Workflow

1. Fork and branch from `main`
2. Make a small, focused change with tests
3. Run the test suite (see README)
4. Update the docs your change affects
5. Open a pull request with a one-line summary and what you tested

## Commit messages

One line, plain English, describing what changed. For example: `add 30e/360 day count to period interest`.

## Reporting issues

Include the dataset seed and size, the loan id, what you expected and what you got.

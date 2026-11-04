# Features: what makes this more than an interest calculator

Brainstorm, 30 Oct 2026. Lens: Priya, internal auditor at a housing finance company, three weeks before an RBI inspection. Her questions, in order: *How much do we owe? Which loans? What proves it? What can't we prove yet? Did the fix actually work?*

All features are deterministic. Every figure comes from SQL in Exasol.

## Built

| Feature | Priya's question | Where |
|---|---|---|
| **Book headline with honest exclusions** | How much do we owe, and what are we not sure about? | Book. Refund total next to gaps, unexplained, permitted and ambiguous, each with its own queue |
| **"Why this figure"** | What proves this rupee? | Loan page. Posted vs fair vs excess, fair interest interval by interval, the extra balance charged and on which days, the postings, and the SQL step |
| **Show source records** | What was this decided from? | Loan page, Why this figure. The stored rows for that month, the row that set each date, the statement that read them, and the steps to the decision. See `D32` |
| **Evidence timeline per tranche** | When did the money really arrive? | Loan page. Every date source on one axis, the resolved date, and a band showing the days charged before money was in hand |
| **Root causes: what the loan system was doing** | What do we fix? | Book. One row per (branch, behaviour): "from the cheque date, 19 loans, ₹61,565". One configuration fix closes the row |
| **Fix coverage: "fixed for new loans only?" cohorts** | Did last year's fix actually cover everyone? | Regression. Sanction quarter × charge quarter heatmap. Old cohorts that stay dark after newer ones clear show an unmigrated fix |
| **Evidence-gap work queue with drafted branch queries** | What do I ask the branch for? | Work queues. One card per tranche, naming what is missing and what we have, with copy-ready text |
| **Policy as settings + re-run + run compare** | What if legal says the commitment fee is not OK? | Policy. Flip a setting, re-run the whole book in Exasol, see the rupee and loan deltas computed by SQL |
| **Ask the book (MCP)** | What else does the committee want to know? | Any MCP client, through Exasol's MCP server as a read-only user on latest-run views; SQL always shown. See `ASK.md` |
| **Checked borrower letters (English, Hindi, Tamil)** | Can we send this without a wrong number? | Letter. Every figure from the ledger; a checker re-reads the letter and rejects any mismatch or stray amount |
| **Close the evidence gap** | The branch replied. Now what? | Work queues. Enter the date and reference, re-run, and the same SQL rules decide. No amount is entered, and a wrong entry can be withdrawn. See `D29` |
| **Where every loan landed** | Which loans are clean? | Overview and All loans. One outcome per loan, adding up to the book |
| **Review by root cause, with evidence level** | How do I review thousands of refunds? | Overview → a root cause → Review & release. Each row says why and what evidence backs it. See `D30` |
| **Review and release** | Who signed this off before it went out? | Review and release, loan, letter, queues, policy. Approve or hold with a name and reason; a changed figure sends the row back; only approved letters release, as a ZIP and manifest. See `D26`, `D27` |
| **Method with lineage** | Can the inspector see how it was computed? | Method. Each step's SQL, SHA-256 and timing for this run |
| **Inspection pack** | What do I hand the inspector? | Overview. One ZIP: totals, ledger, every finding, branch queries, policy used, SQL with SHA-256 |
| **Data page: load your own book** | How do I run this on our loans? | Data. What is loaded, a template with every column, ZIP upload checked against the table definitions before Exasol changes, reload the sample |

## Next, in priority order

1. **Fill `findings.tranche_no`** so a finding names its tranche directly
2. **P6 check** (amortisation change after part-disbursement not communicated) using `kfs_amortisation` and `communications`
3. **"Sample vs whole book" panel.** If the team had sampled 50 loans, how many of these practices would it have found? (Needs field validation of how auditors sample; see Risk 1 in PROBLEM.md)

## Rejected

- **An AI auditor that decides practices.** Breaks the core promise: the posting itself is the evidence, and every label is reproducible
- **A single risk score per loan.** Hides the evidence an auditor needs; the status plus excess plus reason already says more
- **Auto-posting refunds back into the LMS.** Out of scope and not the auditor's job

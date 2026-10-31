"""End-to-end check of ask-the-book: start the MCP server as ASK_READER over stdio, list what it exposes,
run the example questions' SQL through its query tool, and confirm a write is refused.

Runs inside the MCP server's own environment (it provides the `mcp` client library):
    uvx --from exasol-mcp-server@2.3.0 python -m eval.ask_smoke
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent

# Questions an audit committee member might ask, with the SQL an assistant would send. The SQL only reads
# SAHI_ASK views; every amount comes from the audit's result tables.
EXAMPLES = [
    ("How much do we owe borrowers in total, and how many loans?",
     "SELECT refund_rupees, refund_loans, gap_loans, unexplained_loans FROM SAHI_ASK.run_summary"),
    ("How much do we owe borrowers whose money was disbursed by cheque in 2024?",
     "SELECT CAST(SUM(l.excess_paise) / 100 AS DECIMAL(18,2)) AS owed_rupees, COUNT(DISTINCT l.loan_id) AS loans "
     "FROM SAHI_ASK.refund_ledger l WHERE l.loan_id IN (SELECT m.loan_id FROM SAHI_ASK.money_in_hand m "
     "WHERE m.payment_mode = 'CHEQUE' AND YEAR(m.resolved_date) = 2024)"),
    ("Which RBI practice accounts for the most refund?",
     "SELECT l.practice_code, p.title, CAST(SUM(l.excess_paise) / 100 AS DECIMAL(18,2)) AS owed_rupees, COUNT(DISTINCT l.loan_id) AS loans "
     "FROM SAHI_ASK.refund_ledger l LEFT JOIN SAHI_ASK.practices p ON p.practice_code = l.practice_code "
     "GROUP BY l.practice_code, p.title ORDER BY 3 DESC"),
    ("At BR001, are loans sanctioned after the July 2024 fix still being overcharged?",
     "SELECT CASE WHEN sanction_quarter >= '2024-Q3' THEN 'sanctioned from Jul 2024' ELSE 'sanctioned before' END AS cohort, "
     "SUM(loans_overcharged) AS loan_quarters_overcharged, CAST(SUM(excess_paise) / 100 AS DECIMAL(18,2)) AS excess_rupees "
     "FROM SAHI_ASK.cohorts WHERE branch_id = 'BR001' AND period_quarter >= '2024-Q3' GROUP BY 1 ORDER BY 1"),
    ("How much posted interest is waiting on evidence from branches?",
     "SELECT COUNT(*) AS tranches, CAST(SUM(posted_paise_at_stake) / 100 AS DECIMAL(18,2)) AS posted_rupees_at_stake "
     "FROM SAHI_ASK.evidence_gaps"),
]


def text(result) -> str:
    return "\n".join(c.text for c in result.content if getattr(c, "text", None))


async def main() -> int:
    params = StdioServerParameters(command=str(ROOT / ".venv" / "bin" / "python"), args=["-m", "scripts.ask_mcp"], cwd=str(ROOT))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = sorted(t.name for t in (await session.list_tools()).tools)
        print("tools:", ", ".join(tools))
        print("views:", text(await session.call_tool("list_exasol_tables_and_views", {"schema_name": "SAHI_ASK"}))[:400])
        out = []
        for question, sql in EXAMPLES:
            res = await session.call_tool("execute_exasol_query", {"query": sql})
            print(f"\nQ: {question}\nSQL: {sql}\n-> {text(res)[:600]}")
            out.append({"question": question, "sql": sql, "result": text(res), "is_error": bool(res.isError)})
        write_try = await session.call_tool("execute_exasol_query", {"query": "SELECT 1 FROM SAHI_TRUTH.expected LIMIT 1"})
        print("\ntruth read as ASK_READER ->", text(write_try)[:200])
        out.append({"question": "(boundary) read SAHI_TRUTH", "sql": "SELECT 1 FROM SAHI_TRUTH.expected LIMIT 1",
                    "result": text(write_try), "is_error": bool(write_try.isError)})
    (ROOT / "eval" / "reports").mkdir(exist_ok=True)
    (ROOT / "eval" / "reports" / "ask_smoke.json").write_text(json.dumps({"tools": tools, "examples": out}, indent=2) + "\n")
    return 0 if all(not o["is_error"] for o in out[:-1]) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

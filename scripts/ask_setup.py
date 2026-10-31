"""Set up ask-the-book: SAHI_ASK views and a read-only database user for the MCP server.

The user can log in and SELECT from the SAHI_ASK views only. It cannot read SAHI_RAW evidence, SAHI_TRUTH
or borrower names, and it cannot write anything. That limit is enforced by Exasol's privileges, not by the
MCP server or the prompt. The password is generated once and stored in .env (gitignored).

Usage: python -m scripts.ask_setup
"""

from __future__ import annotations

import json
import secrets

from scripts.db import ROOT, connect, load_env, schemas
from scripts.sqlrun import SQL_DIR, render, statements

ASK_USER = "ASK_READER"


def ask_password() -> str:
    env = load_env()
    if env.get("EXASOL_ASK_PASSWORD"):
        return env["EXASOL_ASK_PASSWORD"]
    password = secrets.token_hex(16)
    path = ROOT / ".env"
    text = path.read_text() if path.exists() else ""
    path.write_text(text + ("" if text.endswith("\n") or not text else "\n")
                    + f"EXASOL_ASK_USER={ASK_USER}\nEXASOL_ASK_PASSWORD={password}\n")
    return password


def setup() -> dict:
    s = schemas()
    password = ask_password()
    conn = connect()
    for stmt in statements(render((SQL_DIR / "ask" / "ask_views.sql").read_text())):
        conn.execute(stmt)
    users = {r[0] for r in conn.execute("SELECT user_name FROM EXA_ALL_USERS").fetchall()}
    if ASK_USER in users:
        conn.execute(f'ALTER USER {ASK_USER} IDENTIFIED BY "{password}"')
    else:
        conn.execute(f'CREATE USER {ASK_USER} IDENTIFIED BY "{password}"')
    conn.execute(f"GRANT CREATE SESSION TO {ASK_USER}")
    conn.execute(f"GRANT SELECT ON SCHEMA {s['ASK']} TO {ASK_USER}")
    views = [r[0] for r in conn.execute("SELECT view_name FROM EXA_ALL_VIEWS WHERE view_schema = {s} ORDER BY 1",
                                        {"s": s["ASK"]}).fetchall()]
    conn.close()
    return {"schema": s["ASK"], "user": ASK_USER, "views": views}


def main() -> None:
    print(json.dumps(setup(), indent=2))


if __name__ == "__main__":
    main()

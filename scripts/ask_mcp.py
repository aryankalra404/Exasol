"""Start Exasol's MCP server as the read-only ASK_READER user, limited to the SAHI_ASK views.

Used by the project .mcp.json or any MCP client config: command `.venv/bin/python -m scripts.ask_mcp`.
Reads the connection from .env so no secret lives in a client config file. Run `make ask-setup` first.
"""

from __future__ import annotations

import json
import os
import sys

from scripts.db import load_env, schemas

SERVER = "exasol-mcp-server@2.3.0"


def server_env() -> dict[str, str]:
    env = load_env()
    if not env.get("EXASOL_ASK_PASSWORD"):
        sys.exit("EXASOL_ASK_PASSWORD missing in .env: run `make ask-setup` first")
    ask = schemas(env)["ASK"]
    settings = {
        "schemas": {"like_pattern": ask},
        "views": {"enable": True},
        "tables": {"enable": False},
        "functions": {"enable": False},
        "scripts": {"enable": False},
        "enable_read_query": True,
        "enable_write_query": False,
        "enable_preprocessor_tools": False,
        "default_row_limit": 200,
    }
    return {
        **os.environ,
        "EXA_DSN": env["EXASOL_DSN"],
        "EXA_USER": env.get("EXASOL_ASK_USER", "ASK_READER"),
        "EXA_PASSWORD": env["EXASOL_ASK_PASSWORD"],
        # Exasol Personal local ships a self-signed certificate
        "EXA_SSL_CERT_VALIDATION": "false",
        "EXA_MCP_SETTINGS": json.dumps(settings),
    }


def main() -> None:
    os.execvpe("uvx", ["uvx", SERVER], server_env())


if __name__ == "__main__":
    main()

"""Execute numbered SQL files against Exasol with schema and run-id substitution."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from scripts.db import ROOT, schemas

SQL_DIR = ROOT / "sql"


def header(path: Path) -> dict[str, str]:
    """Read the '-- step:' / '-- purpose:' header comment of a SQL file."""
    meta: dict[str, str] = {}
    key = None
    for line in path.read_text().splitlines():
        if not line.startswith("--"):
            break
        m = re.match(r"--\s*(\w+):\s*(.*)", line)
        if m:
            key = m.group(1)
            meta[key] = m.group(2).strip()
        elif key:
            meta[key] += " " + line.lstrip("- ").strip()
    return meta


def statements(text: str) -> list[str]:
    """Split on semicolons that end a line. Comment lines are dropped."""
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    parts = re.split(r";\s*(?:\n|$)", body)
    return [p.strip() for p in parts if p.strip()]


def render(text: str, run_id: str | None = None) -> str:
    for key, value in schemas().items():
        text = text.replace("{" + key + "}", value)
    if run_id is not None:
        text = text.replace("{RUN_ID}", run_id)
    return text


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_file(conn, path: Path, run_id: str | None = None) -> tuple[int, int]:
    """Run every statement in a file. Returns (duration_ms, rows affected by the last statement)."""
    t0 = time.perf_counter()
    rows = 0
    for stmt in statements(render(path.read_text(), run_id)):
        try:
            st = conn.execute(stmt)
            rows = st.rowcount()
        except Exception as exc:  # surface the failing statement
            raise RuntimeError(f"{path.name} failed:\n{stmt[:800]}\n--> {exc}") from exc
    return int((time.perf_counter() - t0) * 1000), rows

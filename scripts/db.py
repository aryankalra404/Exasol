"""Shared Exasol connection helper. Reads settings from .env at the repo root."""

from __future__ import annotations

import os
from pathlib import Path

import pyexasol

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    # real environment variables win over .env
    for key in list(env) + [k for k in os.environ if k.startswith("EXASOL_")]:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def schemas(env: dict[str, str] | None = None) -> dict[str, str]:
    env = env or load_env()
    return {
        "RAW": env.get("EXASOL_SCHEMA_RAW", "SAHI_RAW"),
        "POLICY": env.get("EXASOL_SCHEMA_POLICY", "SAHI_POLICY"),
        "OUT": env.get("EXASOL_SCHEMA_OUT", "SAHI_OUT"),
        "TRUTH": env.get("EXASOL_SCHEMA_TRUTH", "SAHI_TRUTH"),
        "WORK": env.get("EXASOL_SCHEMA_WORK", "SAHI_WORK"),
        "ASK": env.get("EXASOL_SCHEMA_ASK", "SAHI_ASK"),
    }


def connect(**kwargs) -> pyexasol.ExaConnection:
    env = load_env()
    return pyexasol.connect(
        dsn=env["EXASOL_DSN"],
        user=env["EXASOL_USER"],
        password=env["EXASOL_PASSWORD"],
        encryption=True,
        # Exasol Personal local ships a self-signed certificate
        websocket_sslopt={"cert_reqs": 0},
        fetch_dict=kwargs.pop("fetch_dict", False),
        **kwargs,
    )

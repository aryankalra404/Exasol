"""The live view: step states, which statement is featured, and that a poll reads what Exasol really reports."""

from __future__ import annotations

import pytest

from app.api import live
from tests.test_demo_and_oracle import needs_db

STEPS = [{"step_id": s, "file_path": "", "purpose": ""} for s in ("S10", "S20", "S30")]
DONE = {"duration_ms": 5, "rows_out": 7}


@pytest.mark.parametrize("timings, status, states", [
    ({"S10": DONE}, "RUNNING", ["done", "running", "waiting"]),
    ({}, "RUNNING", ["running", "waiting", "waiting"]),
    ({"S10": DONE}, "FAILED", ["done", "failed", "waiting"]),
    ({"S10": DONE, "S20": DONE, "S30": DONE}, "DONE", ["done", "done", "done"]),
    ({}, None, ["waiting", "waiting", "waiting"]),
])
def test_step_states(timings, status, states):
    assert [s["state"] for s in live.step_states(STEPS, timings, status)] == states


def test_the_audit_statement_is_featured_over_a_screen_reading_results():
    read = {"command_name": "SELECT", "sql_text": f"SELECT 1 FROM {live.S['OUT']}.findings"}
    commit = {"command_name": "COMMIT", "sql_text": "COMMIT /* AUTO */"}
    write = {"command_name": "CREATE TABLE AS", "sql_text": f"CREATE TABLE {live.S['WORK']}.fair_intervals AS SELECT 1"}
    assert live.pick_current([commit, read, write]) is write
    assert live.pick_current([commit, read]) is read
    assert live.pick_current([]) is None


def test_passwords_never_reach_the_screen():
    assert "secret" not in live._mask("CREATE USER x IDENTIFIED BY secret")


@needs_db
def test_snapshot_reports_the_database_and_every_pipeline_step():
    d = live.snapshot()
    assert d["version"]
    assert [s["step_id"] for s in d["steps"]] == [p["step_id"] for p in live.pipeline()]
    assert d["current"] is None or d["current"]["session_id"]

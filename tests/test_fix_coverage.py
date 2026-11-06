"""Fix coverage verdicts against the generator's hidden LMS configuration, which the audit never sees.

The expected verdict for each branch comes from generator.generate.LMS_CONFIG, not from the SQL. A verdict is
read from postings alone, so this is the check that test months can tell a real fix from a quiet month.
"""

from __future__ import annotations

import pytest

from generator.generate import LMS_CONFIG
from scripts.db import connect, schemas
from tests.test_demo_and_oracle import needs_db


def expected_verdicts() -> dict[str, str]:
    """Branch -> verdict the hidden config implies, for branches whose main rule stays unfair at some point."""
    out = {}
    for branch in sorted({c[0] for c in LMS_CONFIG}):
        rows = sorted((c for c in LMS_CONFIG if c[0] == branch), key=lambda c: c[1])
        fair_at_start = rows[0][3] in ("MIH|DIS|NET|EXACT", "CFEE")
        if fair_at_start:
            continue
        if len(rows) == 1:
            out[branch] = "NOT_FIXED"
        else:
            out[branch] = "NEW_LOANS_ONLY" if rows[-1][2] == "NEW_LOANS" else "ALL_LOANS"
    return out


@pytest.fixture(scope="module")
def latest():
    conn = connect()
    s = schemas()
    version = conn.execute(f"SELECT MAX(generator_version) FROM {s['RAW']}.dataset_info").fetchval()
    if version == "upload":
        pytest.skip("uploaded book has no hidden configuration")
    run = conn.execute(f"SELECT run_id FROM {s['OUT']}.audit_runs WHERE status = 'DONE' ORDER BY started_at DESC LIMIT 1").fetchval()
    if run is None:
        pytest.skip("no audit run")
    return conn, s["OUT"], run


def table(latest, name):
    conn, out, run = latest
    st = conn.execute(f"SELECT * FROM {out}.{name} WHERE run_id = {{r}}", {"r": run})
    cols = [c.lower() for c in st.column_names()]
    return [dict(zip(cols, r)) for r in st.fetchall()]


def test_expected_config_is_not_empty():
    want = expected_verdicts()
    assert want["BR001"] == "NEW_LOANS_ONLY"
    assert want["BR004"] == "ALL_LOANS"
    assert want["BR005"] == "NOT_FIXED"
    assert "BR009" not in want


@needs_db
def test_main_rule_verdict_matches_hidden_config(latest):
    got = {r["branch_id"]: r["verdict"] for r in table(latest, "fix_coverage") if r["is_main"]}
    assert got == expected_verdicts()


@needs_db
def test_one_main_rule_per_branch(latest):
    rows = table(latest, "fix_coverage")
    mains = [r["branch_id"] for r in rows if r["is_main"]]
    assert len(mains) == len(set(mains)) == len({r["branch_id"] for r in rows})


@needs_db
def test_grid_adds_up_to_the_summary(latest):
    grid: dict[tuple[str, str], list[int]] = {}
    for g in table(latest, "fix_coverage_grid"):
        t = grid.setdefault((g["branch_id"], g["convention_id"]), [0, 0, 0])
        t[0] += int(g["old_rule_months"])
        t[1] += int(g["fair_months"])
        t[2] += int(g["undecided_months"])
    for r in table(latest, "fix_coverage"):
        assert grid[(r["branch_id"], r["convention_id"])] == [
            int(r["old_rule_months"]), int(r["fair_months"]), int(r["undecided_months"])]


@needs_db
def test_loans_to_correct_match_the_list(latest):
    counts: dict[tuple[str, str], int] = {}
    for f in table(latest, "fix_loans"):
        k = (f["branch_id"], f["convention_id"])
        counts[k] = counts.get(k, 0) + 1
        assert int(f["old_rule_months"]) > 0
    for r in table(latest, "fix_coverage"):
        assert int(r["loans_to_correct"]) == counts.get((r["branch_id"], r["convention_id"]), 0)
        assert int(r["loans_with_undisbursed"]) <= int(r["open_loans_to_correct"]) <= int(r["loans_to_correct"])


@needs_db
def test_a_new_loans_only_fix_leaves_older_loans_failing_every_test(latest):
    rows = [r for r in table(latest, "fix_coverage") if r["is_main"] and r["verdict"] == "NEW_LOANS_ONLY"]
    assert rows
    for r in rows:
        assert int(r["older_old_rule_months"]) > 0
        assert int(r["older_fair_months"]) == 0
        assert int(r["newer_old_rule_months"]) == 0

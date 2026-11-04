"""Show source records: raw rows come back as stored, the right row is named, and a changed row is admitted."""

from __future__ import annotations

import json
import re

import pytest

from app.api import source
from scripts.demo_tamper import statement
from tests.test_demo_and_oracle import needs_db
from tests.test_review import client  # noqa: F401


def _evidence(eid, tranche, src, when):
    return {"evidence_id": eid, "tranche_no": tranche, "evidence_source": src, "event_date": when}


def test_the_row_that_set_the_date_is_named():
    rows = [_evidence("E1", 1, "CHEQUE_DATE", "2025-03-03"), _evidence("E2", 1, "HANDOVER_ACK", "2025-03-11"),
            _evidence("E3", 1, "LMS_DISB", "2025-03-03")]
    tranche = {"tranche_no": 1, "resolved_date": "2025-03-11", "resolved_source": "HANDOVER_ACK"}
    assert source.deciding_ids(rows, [tranche]) == ["E2"]


def test_a_cheque_handed_over_before_its_date_is_set_by_the_cheque_date():
    rows = [_evidence("E1", 1, "CHEQUE_DATE", "2025-03-11"), _evidence("E2", 1, "HANDOVER_ACK", "2025-03-03")]
    tranche = {"tranche_no": 1, "resolved_date": "2025-03-11", "resolved_source": "HANDOVER_ACK"}
    assert source.deciding_ids(rows, [tranche]) == ["E1"]


def test_no_row_is_named_for_a_gap_or_another_tranche():
    rows = [_evidence("E1", 1, "CHEQUE_DATE", "2025-03-03"), _evidence("E2", 2, "HANDOVER_ACK", "2025-03-11")]
    gap = {"tranche_no": 1, "resolved_date": None, "resolved_source": None}
    other = {"tranche_no": 1, "resolved_date": "2025-03-11", "resolved_source": "HANDOVER_ACK"}
    assert source.deciding_ids(rows, [gap]) == [] and source.deciding_ids(rows, [other]) == []


def test_the_date_rule_comes_from_the_run_snapshot_and_respects_its_fallback_setting():
    snap = {"settings": {"allow_lms_fallback_electronic": "true"}, "date_precedence": [
        {"payment_mode": "NEFT", "rank": "2", "evidence_source": "LMS_DISB", "rule": "FALLBACK"},
        {"payment_mode": "NEFT", "rank": "1", "evidence_source": "RAIL_CREDIT", "rule": "USE"},
        {"payment_mode": "CHEQUE", "rank": "1", "evidence_source": "HANDOVER_ACK", "rule": "MAX_WITH_CHEQUE_DATE"}]}
    assert [p["evidence_source"] for p in source.precedence(json.dumps(snap), "NEFT")] == ["RAIL_CREDIT", "LMS_DISB"]
    snap["settings"]["allow_lms_fallback_electronic"] = "false"
    assert [p["evidence_source"] for p in source.precedence(json.dumps(snap), "NEFT")] == ["RAIL_CREDIT"]
    assert source.precedence(None, "NEFT") == []


def test_a_changed_posting_or_another_book_is_admitted():
    same = source.freshness("d1", "d1", 2190497, 2190497)
    assert same["same_extract"] and same["posted_matches"]
    assert not source.freshness("d1", "d1", 2190497, 2190498)["posted_matches"]
    assert not source.freshness("d1", "d2", 2190497, 2190497)["same_extract"]


def test_a_stored_integer_json_cannot_carry_goes_as_a_string():
    assert source.cell(2190497) == 2190497
    assert source.cell(2**53) == str(2**53)
    assert source.cell(True) is True and source.cell(None) is None and source.cell("8.75") == "8.75"


def test_statements_read_only_named_columns_and_never_the_truth_schema():
    for _, _, sql in source.RECORDS:
        assert sql.startswith("SELECT ") and "*" not in sql
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE)\b", sql)
        assert source.S["TRUTH"] not in sql


def test_the_tamper_helper_moves_only_between_its_two_known_values():
    assert statement("R", False).endswith("posted_paise = 2190498 WHERE posting_id = 'PDM0001010' AND posted_paise = 2190497")
    assert statement("R", True).endswith("posted_paise = 2190497 WHERE posting_id = 'PDM0001010' AND posted_paise = 2190498")


def _record(body, key):
    r = next(x for x in body["records"] if x["key"] == key)
    return [dict(zip(r["columns"], row)) for row in r["rows"]]


@needs_db
def test_meena_shows_the_rows_behind_her_refund(client):  # noqa: F811
    body = client.get("/api/runs/latest/loans/LDM0001/source/2025-03-01").json()
    evidence = {e["evidence_id"]: e for e in _record(body, "evidence")}
    assert evidence["EDM000121"]["evidence_source"] == "CHEQUE_DATE" and evidence["EDM000121"]["event_date"] == "2025-03-03"
    assert evidence["EDM000122"]["recorded_in"] == "BRANCH_REGISTER" and evidence["EDM000122"]["event_date"] == "2025-03-11"
    assert "EDM000122" in body["deciding_evidence_ids"] and "EDM000121" not in body["deciding_evidence_ids"]
    assert [(p["posting_id"], p["posted_paise"]) for p in _record(body, "postings")] == [("PDM0001010", 2190497)]
    decision = body["decision"]
    assert decision["fingerprint"]["match_status"] == "MATCHED" and decision["fingerprint"]["fair_paise"] == 1960360
    assert decision["refund_paise"] == 230137
    assert body["freshness"] == {"same_extract": True, "posted_in_run": 2190497, "posted_now": 2190497, "posted_matches": True}
    sql = next(r["sql"] for r in body["records"] if r["key"] == "postings")
    assert "'LDM0001'" in sql and "'2025-03-01'" in sql and "{" not in sql


@needs_db
def test_a_disclosed_fee_shows_the_term_that_permits_it(client):  # noqa: F811
    loan = client.get("/api/runs/latest/loans/LDM0002").json()
    month = next(p["period_start"] for p in loan["periods"] if p["match_status"] == "PERMITTED")
    body = client.get(f"/api/runs/latest/loans/LDM0002/source/{month}").json()
    assert body["decision"]["refund_paise"] == 0
    assert _record(body, "kfs")[0]["commitment_fee_rate_pct"] is not None


@needs_db
def test_a_gap_names_no_deciding_row_and_every_outcome_has_rows(client):  # noqa: F811
    loan = client.get("/api/runs/latest/loans/LDM0003").json()
    month = next(p["period_start"] for p in loan["periods"] if p["match_status"] == "EVIDENCE_GAP")
    body = client.get(f"/api/runs/latest/loans/LDM0003/source/{month}").json()
    gap = [t for t in body["decision"]["tranches"] if t["confidence"] == "GAP"]
    assert gap and _record(body, "evidence") and _record(body, "postings")
    gap_ids = {e["evidence_id"] for e in _record(body, "evidence") if e["tranche_no"] in {t["tranche_no"] for t in gap}}
    assert not gap_ids & set(body["deciding_evidence_ids"])
    fair = next(p["period_start"] for p in client.get("/api/runs/latest/loans/LDM0001").json()["periods"] if p["match_status"] == "FAIR")
    assert client.get(f"/api/runs/latest/loans/LDM0001/source/{fair}").json()["decision"]["findings"] == []


@needs_db
@pytest.mark.parametrize("loan, month, status", [("LDM0001", "1999-01-01", 404), ("NOSUCH", "2025-03-01", 404), ("LDM0001", "March", 400)])
def test_a_month_that_was_not_audited_is_refused(client, loan, month, status):  # noqa: F811
    assert client.get(f"/api/runs/latest/loans/{loan}/source/{month}").status_code == status

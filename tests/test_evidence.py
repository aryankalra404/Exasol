"""A date entered from a branch reply goes through the same rules as all evidence, and the oracle agrees."""

from __future__ import annotations

import socket
import threading
import time
import uuid
from datetime import date

import pytest

from app.api.review import clean_evidence_date
from tests.test_demo_and_oracle import needs_db


def test_evidence_date_must_be_real_and_not_in_the_future():
    assert clean_evidence_date(" 2025-06-06 ", "2026-10-01") == "2025-06-06"
    for bad in ("", "06/06/2025", "2025-02-30", "2026-10-02"):
        with pytest.raises(ValueError):
            clean_evidence_date(bad, "2026-10-01")


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    from generator.generate import generate
    from scripts.db import connect, schemas
    from scripts.load import load
    for key in ("RAW", "POLICY", "OUT", "TRUTH", "WORK"):
        monkeypatch.setenv(f"EXASOL_SCHEMA_{key}", f"EVFIX_{key}")
    book = generate(seed=1, loans=0, as_of=date(2026, 10, 1), defect_scale=0.0, out_root=tmp_path)
    load(book)
    yield book
    conn = connect()
    for key in ("RAW", "POLICY", "OUT", "TRUTH", "WORK"):
        conn.execute(f"DROP SCHEMA IF EXISTS {schemas()[key]} CASCADE")
    conn.close()


def _months(run_id: str, loan: str) -> dict:
    from scripts.db import connect, schemas
    conn = connect()
    out = {r[0]: r[1:] for r in conn.execute(
        f"SELECT TO_CHAR(period_start, 'YYYY-MM-DD'), match_status, fair_paise, excess_paise, matched_convention_id "
        f"FROM {schemas()['OUT']}.fingerprints WHERE run_id = {{r}} AND loan_id = {{l}}", {"r": run_id, "l": loan}).fetchall()}
    conn.close()
    return out


@needs_db
def test_entered_date_settles_the_gap_and_withdrawing_restores_it(isolated):
    from eval.oracle_agreement import entered_evidence
    from oracle.oracle import audit
    from scripts.audit import now, run_audit
    from scripts.db import connect, schemas

    book = isolated
    s = schemas()
    first = run_audit("before")["run_id"]
    assert _months(first, "LDM0003")["2025-06-01"][0] == "EVIDENCE_GAP"
    meena = _months(first, "LDM0001")

    conn = connect()
    dataset = conn.execute(f"SELECT dataset_id FROM {s['RAW']}.dataset_info").fetchval()
    eid = f"RV{uuid.uuid4().hex[:12].upper()}"
    conn.execute(f"INSERT INTO {s['POLICY']}.evidence_additions (evidence_id, dataset_id, loan_id, tranche_no, evidence_source, "
                 f"event_date, reference, added_by, reason, added_at) VALUES ({{i}}, {{d}}, 'LDM0003', 1, 'HANDOVER_ACK', '2025-06-06', "
                 f"'ACK-TEST', 'pytest', 'test', {{t}})", {"i": eid, "d": dataset, "t": now()})

    second = run_audit("after")["run_id"]
    june = _months(second, "LDM0003")["2025-06-01"]
    assert june[0] != "EVIDENCE_GAP"
    assert _months(second, "LDM0001") == meena, "another loan must not move"
    resolved = conn.execute(f"SELECT TO_CHAR(resolved_date, 'YYYY-MM-DD'), resolved_source, confidence FROM {s['OUT']}.money_in_hand "
                            f"WHERE run_id = {{r}} AND loan_id = 'LDM0003' AND tranche_no = 1", {"r": second}).fetchone()
    assert resolved == ("2025-06-06", "HANDOVER_ACK", "CONFIRMED")
    assert eid in conn.execute(f"SELECT policy_snapshot FROM {s['OUT']}.audit_runs WHERE run_id = {{r}}", {"r": second}).fetchval()

    # the oracle, reading the same entered date from its own path, must reach the same answer
    extra = entered_evidence(conn)
    assert [e["event_date"] for e in extra] == ["2025-06-06"]
    results = {str(r.period_start): r for r in audit(book, ["LDM0003"], extra)}
    for period, row in _months(second, "LDM0003").items():
        assert results[period].status == row[0] and results[period].fair == int(row[1]), period

    conn.execute(f"UPDATE {s['POLICY']}.evidence_additions SET withdrawn_by = 'pytest', withdrawn_reason = 'test', withdrawn_at = {{t}} "
                 f"WHERE evidence_id = {{i}}", {"t": now(), "i": eid})
    third = run_audit("withdrawn")["run_id"]
    conn.close()
    assert _months(third, "LDM0003")["2025-06-01"][0] == "EVIDENCE_GAP"


@needs_db
def test_api_validates_and_keeps_withdrawn_entries():
    import uvicorn

    from app.api.main import POL, app, db
    from tests.test_review import _Client

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    client = _Client(f"http://127.0.0.1:{port}")

    def wipe():
        with db() as c:
            c.execute(f"DELETE FROM {POL}.evidence_additions WHERE added_by = 'pytest-evidence'")

    wipe()
    try:
        before = client.get("/api/runs/latest/summary").json()["summary"]["refund_paise"]
        rid = client.get("/api/runs/latest/summary").json()["run"]["run_id"]
        url = f"/api/runs/{rid}/evidence"
        gap = client.get(f"/api/runs/{rid}/gaps").json()
        if not gap:
            pytest.skip("no evidence gaps on this book")
        body = {"loan_id": gap[0]["loan_id"], "tranche_no": gap[0]["tranche_no"], "event_date": "2025-06-06",
                "reference": "ACK-1", "reviewer": "pytest-evidence", "reason": "test"}
        assert client.post(url, {**body, "reviewer": ""}).status_code == 400
        assert client.post(url, {**body, "reference": " "}).status_code == 400
        assert client.post(url, {**body, "event_date": "2099-01-01"}).status_code == 400
        assert client.post(url, {**body, "tranche_no": 99}).status_code == 404

        r = client.post(url, body)
        assert r.status_code == 200, r.text
        entry = next(e for e in r.json() if e["added_by"] == "pytest-evidence")
        assert entry["entry_state"] == "PENDING" and entry["evidence_source"] == gap[0]["missing_source"].split(",")[0]
        assert client.post(url, body).status_code == 409, "a second date needs the first withdrawn"

        # entering a date moves nothing until a run applies it
        assert client.get("/api/runs/latest/summary").json()["summary"]["refund_paise"] == before

        w = client.post(f"{url}/{entry['evidence_id']}/withdraw", {"reviewer": "pytest-evidence", "reason": "typed wrong"})
        assert next(e for e in w.json() if e["evidence_id"] == entry["evidence_id"])["entry_state"] == "NEVER_USED"
        assert client.post(f"{url}/{entry['evidence_id']}/withdraw", {"reviewer": "pytest-evidence", "reason": "again"}).status_code == 404
        assert client.post(url, body).status_code == 200, "a new date is allowed after withdrawing"
    finally:
        wipe()
        server.should_exit = True
        thread.join(timeout=10)

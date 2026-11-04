"""Human review and letter release. Decisions never change a figure, and only approved letters can be released."""

from __future__ import annotations

import hashlib
import io
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date

import pytest

from app.api.review import build_letters, clean_actor, release_zip
from tests.test_demo_and_oracle import ROOT, needs_db
from tests.test_letters import ROWS


def test_every_action_needs_a_name_and_a_reason():
    assert clean_actor("  Priya   N ", " checked  the cheque ") == ("Priya N", "checked the cheque")
    for name, reason in (("", "why"), ("   ", "why"), ("who", ""), ("who", "  ")):
        with pytest.raises(ValueError):
            clean_actor(name, reason)


def test_pipeline_never_reads_the_review_log():
    tables = re.compile(r"review_decisions|policy_changes|letter_releases|release_batches", re.I)
    pipeline = [p for p in (ROOT / "sql").glob("*.sql") if int(p.name.split("_")[0]) >= 10]
    assert pipeline and not [p.name for p in pipeline if tables.search(p.read_text())]


def test_release_letters_pass_the_checker_and_carry_their_hash():
    letters, failed = build_letters(ROWS, ROWS)
    assert not failed and [x["loan_id"] for x in letters] == ["LDM0001"]
    assert "₹2,301.37" in letters[0]["letter_text"]
    assert letters[0]["text_sha256"] == hashlib.sha256(letters[0]["letter_text"].encode()).hexdigest()
    assert build_letters(ROWS, ROWS, "ta")[0][0]["letter_lang"] == "ta"


def test_release_stops_a_letter_the_checker_rejects():
    tampered = [{**r, "excess_paise": 230138} for r in ROWS]
    letters, failed = build_letters(ROWS, tampered)
    assert letters == [] and failed == ["LDM0001"]
    letters, failed = build_letters(ROWS, [])
    assert letters == [] and failed == ["LDM0001"]


def test_release_zip_holds_letters_manifest_and_says_not_sent():
    letters, _ = build_letters(ROWS, ROWS)
    rows = [{**letters[0], "approved_by": "Priya", "released_by": "Ravi", "released_at": "2026-11-05 10:00:00"}]
    batch = {"batch_id": "a" * 36, "released_by": "Ravi", "released_at": "2026-11-05 10:00:00", "run_id": "r",
             "dataset_id": "d", "letter_count": 1, "total_paise": 230137, "batch_note": "first batch"}
    z = zipfile.ZipFile(io.BytesIO(release_zip(batch, rows)))
    base = "letter_release_aaaaaaaa/"
    assert z.read(base + "letters/LDM0001_en.txt").decode() == letters[0]["letter_text"]
    manifest = z.read(base + "manifest.csv").decode()
    assert "Priya" in manifest and "230137" in manifest and letters[0]["text_sha256"] in manifest
    assert "does not mean a borrower has received" in z.read(base + "README.txt").decode().replace("\n", " ")


class _Reply:
    def __init__(self, status_code: int, content: bytes):
        self.status_code, self.content = status_code, content
        self.text = content.decode(errors="replace")

    def json(self):
        return json.loads(self.content)


class _Client:
    """Calls the real app over HTTP, standard library only."""

    def __init__(self, base: str):
        self.base = base

    def _send(self, method: str, path: str, body=None) -> _Reply:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return _Reply(r.status, r.read())
        except urllib.error.HTTPError as e:
            return _Reply(e.code, e.read())

    def get(self, path: str) -> _Reply:
        return self._send("GET", path)

    def post(self, path: str, json: dict) -> _Reply:
        return self._send("POST", path, json)

    def put(self, path: str, json: dict) -> _Reply:
        return self._send("PUT", path, json)


@pytest.fixture
def client():
    """The app against the loaded book. Everything this test writes is signed `pytest-review` and removed after."""
    import uvicorn

    from app.api.main import POL, app, db

    def wipe():
        with db() as c:
            c.execute(f"DELETE FROM {POL}.release_batches WHERE released_by = 'pytest-review'")
            c.execute(f"DELETE FROM {POL}.letter_releases WHERE released_by = 'pytest-review'")
            c.execute(f"DELETE FROM {POL}.review_decisions WHERE decided_by = 'pytest-review'")
            c.execute(f"DELETE FROM {POL}.policy_changes WHERE changed_by = 'pytest-review'")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    wipe()
    yield _Client(f"http://127.0.0.1:{port}")
    wipe()
    server.should_exit = True
    thread.join(timeout=10)


WHO = {"reviewer": "pytest-review", "reason": "test"}


def _meena(client, rid):
    return client.get(f"/api/runs/{rid}/loans/LDM0001").json()


@needs_db
def test_review_flow_end_to_end(client):
    from app.api.main import POL, db

    rid = client.get("/api/runs/latest/summary").json()["run"]["run_id"]
    before = client.get("/api/runs/latest/summary").json()["summary"]["refund_paise"]
    if _meena(client, rid)["letter"]["letter_state"] != "DRAFT":
        pytest.skip("Meena has real review records on this book; run `make review-reset` first")
    url = f"/api/runs/{rid}"

    # a draft cannot be released, and every action needs a name and a reason
    r = client.post(f"{url}/releases", json={**WHO, "loan_ids": ["LDM0001"]})
    assert r.status_code == 409 and "draft" in r.json()["detail"]
    body = {"loan_id": "LDM0001", "practice_code": "P2", "decision": "APPROVED"}
    assert client.post(f"{url}/review/decisions", json={**body, "reviewer": "", "reason": "x"}).status_code == 400
    assert client.post(f"{url}/review/approve-filtered", json=WHO).status_code == 400

    # hold, then approve: the latest decision counts and the figure comes from the ledger
    assert client.post(f"{url}/review/decisions", json={**body, **WHO, "decision": "HOLD"}).status_code == 200
    assert _meena(client, rid)["review"][0]["review_state"] == "HOLD"
    assert client.post(f"{url}/review/decisions", json={**body, **WHO}).status_code == 200
    m = _meena(client, rid)
    assert m["review"][0]["review_state"] == "APPROVED" and int(m["review"][0]["reviewed_paise"]) == 230137
    assert m["letter"]["letter_state"] == "APPROVED" and len(m["review_history"]) == 2

    # review changes no figure
    assert client.get("/api/runs/latest/summary").json()["summary"]["refund_paise"] == before

    # a figure that moved makes the approval stale, and the letter goes back to draft
    with db() as c:
        c.execute(f"UPDATE {POL}.review_decisions SET figure_paise = 1 WHERE decided_by = 'pytest-review' AND review_decision = 'APPROVED'")
    assert _meena(client, rid)["review"][0]["review_state"] == "STALE"
    assert _meena(client, rid)["letter"]["letter_state"] == "DRAFT"
    assert client.post(f"{url}/releases", json={**WHO, "loan_ids": ["LDM0001"]}).status_code == 409
    assert client.post(f"{url}/review/decisions", json={**body, **WHO}).status_code == 200

    # release once, in Tamil, then download what was stored
    r = client.post(f"{url}/releases", json={**WHO, "loan_ids": ["LDM0001"], "lang": "ta"})
    assert r.status_code == 200, r.text
    batch = r.json()
    assert int(batch["letter_count"]) == 1 and int(batch["total_paise"]) == 230137
    assert _meena(client, rid)["letter"]["letter_state"] == "RELEASED"
    assert client.post(f"{url}/releases", json={**WHO, "loan_ids": ["LDM0001"]}).status_code == 409
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/releases/{batch['batch_id']}/letters.zip").content))
    name = next(n for n in z.namelist() if n.endswith("LDM0001_ta.txt"))
    assert "₹2,301.37" in z.read(name).decode()

    # the inspector sees all of it
    pack = zipfile.ZipFile(io.BytesIO(client.get(f"{url}/inspection-pack.zip").content))
    names = "\n".join(pack.namelist())
    for f in ("review_decisions.csv", "policy_changes.csv", "release_batches.csv", "letter_releases.csv"):
        assert f in names
    decisions = pack.read(next(n for n in pack.namelist() if n.endswith("review_decisions.csv"))).decode()
    assert "pytest-review" in decisions


@needs_db
def test_filtered_approval_skips_holds_and_settings_log_who_and_why(client):
    rid = client.get("/api/runs/latest/summary").json()["run"]["run_id"]
    url = f"/api/runs/{rid}"
    assert client.post(f"{url}/review/decisions", json={"loan_id": "LDM0001", "practice_code": "P2", "decision": "HOLD", **WHO}).status_code == 200
    r = client.post(f"{url}/review/approve-filtered", json={"q": "LDM0001", **WHO})
    assert r.status_code == 200 and int(r.json()["row_count"]) == 0
    assert _meena(client, rid)["review"][0]["review_state"] == "HOLD"

    key = "conflict_tolerance_days"
    current = next(s["setting_value"] for s in client.get("/api/policy/settings").json()["settings"] if s["setting_key"] == key)
    assert client.put("/api/policy/settings", json={"setting_key": key, "setting_value": "9", "changed_by": "", "reason": "x"}).status_code == 400
    try:
        got = client.put("/api/policy/settings", json={"setting_key": key, "setting_value": "9", "changed_by": "pytest-review", "reason": "test"}).json()
        assert got["changes"][0]["changed_by"] == "pytest-review" and got["changes"][0]["old_value"] == current
    finally:
        back = client.put("/api/policy/settings", json={"setting_key": key, "setting_value": str(current), "changed_by": "pytest-review", "reason": "restore"})
        assert back.status_code == 200, back.text


@needs_db
def test_unexplained_decision_moves_no_money(client):
    summary = client.get("/api/runs/latest/summary").json()
    rid, before = summary["run"]["run_id"], summary["summary"]["refund_paise"]
    rows = client.get(f"/api/runs/{rid}/queue/UNEXPLAINED?size=1").json()
    if not rows:
        pytest.skip("no unexplained months on this book")
    item = {"loan_id": rows[0]["loan_id"], "period_start": rows[0]["period_start"], "decision": "CLEARED", **WHO}
    assert client.post(f"/api/runs/{rid}/review/unexplained", json=item).status_code == 200
    row = client.get(f"/api/runs/{rid}/queue/UNEXPLAINED?size=1").json()[0]
    assert row["review_state"] == "CLEARED" and row["decided_by"] == "pytest-review"
    assert client.get("/api/runs/latest/summary").json()["summary"]["refund_paise"] == before
    assert date.fromisoformat(item["period_start"])

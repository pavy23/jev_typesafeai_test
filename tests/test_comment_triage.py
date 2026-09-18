"""Offline checks for samples/comment_triage: request shape per comment, and the routing policy."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "samples" / "comment_triage"))

import triage  # noqa: E402

COMMENTS = json.loads((ROOT / "samples/comment_triage/comments.json").read_text())
BASELINE = json.loads((ROOT / "samples/comment_triage/contract_baseline.json").read_text())
FIXTURE = json.loads((ROOT / "samples/comment_triage/fixtures/answers.json").read_text())


class _Handler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        _Handler.received.append(body)
        # Answer from the fixture keyed by the drawing in the state, so replies match comments.
        cid = next(c["id"] for c in COMMENTS if c["drawing"] == body["state"]["comment"]["drawing"])
        payload = json.dumps(FIXTURE[cid]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


@pytest.fixture(scope="module")
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_state_uses_exact_clause_lookup():
    st = triage.build_state(COMMENTS[1], BASELINE)  # OC-002 cites Spec Part III 5.1.2
    assert st["spec_baseline_for_cited_clause"].startswith("Secondary barrier insulation 270 mm")
    st = triage.build_state(COMMENTS[2], BASELINE)  # OC-003 cites "-"
    assert st["spec_baseline_for_cited_clause"] is None


def test_live_path_sends_five_questions_per_comment(mock_server, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("TYPESAFE_BASE_URL", mock_server)
    _Handler.received.clear()

    import asyncio
    responses = asyncio.run(triage.judge_live(COMMENTS, BASELINE, concurrency=3, record=False))

    assert len(_Handler.received) == len(COMMENTS) == len(responses)
    for body in _Handler.received:
        assert set(body["questions"]) == {"discipline", "beyond_spec", "class_reapproval", "impact", "response_type"}
        assert body["questions"]["discipline"]["type"] == "choice"
        assert "other" in body["questions"]["discipline"]["criteria"]
        assert body["questions"]["impact"]["type"] == "score"
        assert len(body["questions"]["impact"]["criteria"]) == 4
        assert body["model"] == "jev-latest"


def test_policy_routing_on_fixture():
    responses = triage.judge_fixture(COMMENTS)
    rows = {r.id: r for r in (triage.apply_policy(c, responses[c["id"]]) for c in COMMENTS)}

    assert rows["OC-003"].track == "technical_reply"          # typo fix
    assert rows["OC-005"].track == "technical_reply"          # confirmation request
    assert rows["OC-002"].track == "variation_order"          # insulation upgrade
    assert "CLASS" in rows["OC-002"].flags and "MAJOR_IMPACT" in rows["OC-002"].flags
    assert rows["OC-007"].track == "human_review"             # rejection candidate, low confidence
    assert rows["OC-008"].track == "human_review"             # split discipline, low confidence
    assert "LOW_CONFIDENCE" in rows["OC-008"].flags

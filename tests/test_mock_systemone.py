"""Offline end-to-end check: run the demo against a local mock of /v1/systemone.

Proves (without network access to typesafe.ai) that the request body we send matches the
documented wire schema and that the SDK decodes a schema-conformant response into the
typed answer objects the demo prints.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from typesafe_sdk import Choice, Noul, Score, TypeSafeAuthenticationError, TypeSafeClient

# Shape copied from the SDK's generated wire schema (typesafe_sdk/_schemas/models.py).
MOCK_RESPONSE = {
    "model": "jev-latest",
    "usage": {"billing_units": 1, "input_tokens": 210, "output_tokens": 12},
    "answers": {
        "schedule_risk": {"type": "noul", "noul": 0.73},
        "owning_dept": {
            "type": "choice",
            "choice": "cargo_system",
            "confidence": 0.81,
            "probabilities": {"hull_design": 0.12, "cargo_system": 0.81, "production": 0.03, "procurement": 0.04},
        },
        "cost_impact": {
            "type": "score",
            "score": 2.6,
            "confidence": 0.7,
            "legend": {"0": "Negligible", "1": "Minor", "2": "Moderate", "3": "Major"},
            "probabilities": {"0": 0.0, "1": 0.05, "2": 0.3, "3": 0.65},
        },
    },
}


class _Handler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        _Handler.received.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})

        if self.headers.get("Authorization") != "Bearer test-key":
            payload = json.dumps({"error": {"message": "invalid api key"}}).encode()
            self.send_response(401)
        else:
            payload = json.dumps(MOCK_RESPONSE).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):  # keep pytest output quiet
        pass


@pytest.fixture(scope="module")
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


QUESTIONS = {
    "schedule_risk": Noul(instructions="Will this delay erection?", criteria={"true": "yes it will", "false": "no"}),
    "owning_dept": Choice(instructions="Owner?", criteria={"hull_design": None, "cargo_system": "insulation", "production": None, "procurement": None}),
    "cost_impact": Score(instructions="Cost?", criteria=["Negligible", "Minor", "Moderate", "Major"]),
}


def test_request_matches_wire_schema_and_response_decodes(mock_server):
    _Handler.received.clear()
    with TypeSafeClient(api_key="test-key", base_url=mock_server) as client:
        resp = client.system_one(state={"doc_type": "ecr", "body": "thicker insulation"}, questions=QUESTIONS)

    # --- request side ---
    req = _Handler.received[0]
    assert req["path"] == "/v1/systemone"
    assert req["auth"] == "Bearer test-key"
    body = req["body"]
    assert set(body) == {"state", "model", "questions"}
    assert body["model"] == "jev-latest"
    assert body["state"] == {"doc_type": "ecr", "body": "thicker insulation"}
    assert body["questions"]["schedule_risk"] == {
        "type": "noul",
        "instructions": "Will this delay erection?",
        "criteria": {"true": "yes it will", "false": "no"},
    }
    assert body["questions"]["owning_dept"]["type"] == "choice"
    assert body["questions"]["owning_dept"]["criteria"]["cargo_system"] == "insulation"
    assert body["questions"]["cost_impact"] == {
        "type": "score",
        "instructions": "Cost?",
        "criteria": ["Negligible", "Minor", "Moderate", "Major"],
    }

    # --- response side ---
    assert resp.model == "jev-latest"
    assert resp.usage.input_tokens == 210
    assert resp.nouls["schedule_risk"].noul == pytest.approx(0.73)
    assert resp.choices["owning_dept"].choice == "cargo_system"
    assert resp.choices["owning_dept"].probabilities["cargo_system"] == pytest.approx(0.81)
    score = resp.scores["cost_impact"]
    assert score.score == pytest.approx(2.6)
    assert score.legend == {0: "Negligible", 1: "Minor", 2: "Moderate", 3: "Major"}  # int-keyed
    assert score.probabilities[3] == pytest.approx(0.65)


def test_bad_key_raises_authentication_error(mock_server):
    with TypeSafeClient(api_key="wrong", base_url=mock_server) as client, pytest.raises(TypeSafeAuthenticationError) as exc:
        client.system_one(state="x", questions={"q": Noul(instructions="?")})
    assert exc.value.status == 401

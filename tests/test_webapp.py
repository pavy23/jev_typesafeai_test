"""Playground backend checks in mock mode (no key, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TYPESAFE_MOCK", "1")
    import importlib
    import app as webapp
    importlib.reload(webapp)
    return TestClient(webapp.app)


def test_index_and_status(client):
    assert client.get("/").status_code == 200
    s = client.get("/api/status").json()
    assert s["mock"] is True


def test_evaluate_mock_returns_wire_shape(client):
    body = {
        "state": {"comment": {"text": "thicker insulation"}},
        "questions": {
            "yes": {"type": "noul", "instructions": "?"},
            "pick": {"type": "choice", "instructions": "?", "criteria": {"a": None, "b": "bee", "other": None}},
            "grade": {"type": "score", "instructions": "?", "criteria": ["low", "mid", "high"]},
        },
    }
    r = client.post("/api/evaluate", json=body)
    assert r.status_code == 200, r.text
    a = r.json()["answers"]
    assert 0 <= a["yes"]["noul"] <= 1
    assert a["pick"]["choice"] in {"a", "b", "other"}
    assert abs(sum(a["pick"]["probabilities"].values()) - 1) < 0.01
    assert set(a["grade"]["legend"]) == {"0", "1", "2"}
    assert 0 <= a["grade"]["score"] <= 2


def test_evaluate_rejects_bad_question(client):
    r = client.post("/api/evaluate", json={"state": "x", "questions": {"q": {"type": "bogus"}}})
    assert r.status_code == 400
    r = client.post("/api/evaluate", json={"state": "x", "questions": {}})
    assert r.status_code == 400

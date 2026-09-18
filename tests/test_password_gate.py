import base64
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))


def _client(monkeypatch, password):
    monkeypatch.setenv("TYPESAFE_MOCK", "1")
    if password is None:
        monkeypatch.delenv("PLAYGROUND_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("PLAYGROUND_PASSWORD", password)
    import importlib
    import app as webapp
    importlib.reload(webapp)
    return TestClient(webapp.app)


def test_no_password_means_open(monkeypatch):
    assert _client(monkeypatch, None).get("/api/status").status_code == 200


def test_password_required_and_checked(monkeypatch):
    c = _client(monkeypatch, "s3cret")
    r = c.get("/api/status")
    assert r.status_code == 401 and r.headers["WWW-Authenticate"].startswith("Basic")
    bad = base64.b64encode(b"anyone:wrong").decode()
    assert c.get("/api/status", headers={"Authorization": f"Basic {bad}"}).status_code == 401
    good = base64.b64encode(b"anyone:s3cret").decode()
    assert c.get("/api/status", headers={"Authorization": f"Basic {good}"}).status_code == 200

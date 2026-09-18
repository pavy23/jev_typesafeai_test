"""TypeSafe playground — a tiny local web UI for trying System One.

The browser never sees your API key: it talks to this server, and this server talks to
TypeSafe with TYPESAFE_API_KEY from the environment / .env (keep credentials server-side).

Run:
  python webapp/app.py            # http://127.0.0.1:8000  (needs TYPESAFE_API_KEY)
  python webapp/app.py --mock     # no key, no network: fake answers so you can explore the UI
  python webapp/app.py --auto     # live if TYPESAFE_API_KEY is set, otherwise mock (used by Codespaces)
"""

from __future__ import annotations

import argparse
import base64
import os
import random
import secrets
import time
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from typesafe_sdk import AsyncTypeSafeClient, TypeSafeAPIError, TypeSafeError

load_dotenv()
STATIC = Path(__file__).parent / "static"
MOCK = os.environ.get("TYPESAFE_MOCK") == "1"

app = FastAPI(title="TypeSafe playground")


@app.middleware("http")
async def password_gate(request: Request, call_next):
    """When PLAYGROUND_PASSWORD is set (hosted deployments), require it via HTTP Basic auth.

    The browser shows its own login prompt; any username is accepted. Without the variable
    (local / Codespaces, where the port itself is private) nothing is asked.
    """
    expected = os.environ.get("PLAYGROUND_PASSWORD")
    if expected:
        header = request.headers.get("authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                _, _, given = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(given, expected)
            except Exception:  # noqa: BLE001 - malformed header is just "not authenticated"
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="TypeSafe playground"'})
    return await call_next(request)


class EvaluateRequest(BaseModel):
    state: Any
    questions: dict[str, dict[str, Any]]
    model: str | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {
        "mock": MOCK,
        "has_key": bool(os.environ.get("TYPESAFE_API_KEY")),
        "base_url": os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai"),
        "default_model": os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest"),
    }


@app.get("/api/models")
async def models():
    if MOCK:
        return {"models": [{"name": "jev-latest", "description": "(mock) flagship System One model", "release_date": "2026-01-01"}]}
    try:
        async with AsyncTypeSafeClient(timeout=30.0) as client:
            r = await client.models.list()
        return {"models": [{"name": m.name, "description": m.description, "release_date": m.release_date} for m in r.models]}
    except TypeSafeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/api/evaluate")
async def evaluate(req: EvaluateRequest):
    if not req.questions:
        raise HTTPException(status_code=400, detail="At least one question is required.")
    t0 = time.perf_counter()
    if MOCK:
        body = _mock_answers(req.questions, req.model or "jev-latest")
    else:
        try:
            async with AsyncTypeSafeClient(timeout=30.0) as client:
                # The SDK accepts raw question dicts ({"type": ..., ...}) straight from the browser.
                r = await client.system_one(state=req.state, questions=req.questions, model=req.model)
            body = r.raw_http_response.json()
        except TypeSafeAPIError as e:
            return JSONResponse(status_code=e.status, content={"error": str(e), "request_id": e.request_id})
        except TypeSafeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
    body["_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    body["_mock"] = MOCK
    return body


def _mock_answers(questions: dict[str, dict[str, Any]], model: str) -> dict[str, Any]:
    """Random but schema-correct answers so the UI can be exercised without a key."""
    answers: dict[str, Any] = {}
    for name, q in questions.items():
        t = q.get("type")
        if t == "noul":
            answers[name] = {"type": "noul", "noul": round(random.random(), 3)}
        elif t == "choice":
            labels = list(q.get("criteria", {}))
            if not labels:
                raise HTTPException(400, f'choice question "{name}" needs criteria')
            w = [random.random() ** 2 for _ in labels]
            probs = {k: round(v / sum(w), 3) for k, v in zip(labels, w)}
            best = max(probs, key=probs.get)
            answers[name] = {"type": "choice", "choice": best, "confidence": probs[best], "probabilities": probs}
        elif t == "score":
            levels = q.get("criteria", [])
            if not levels:
                raise HTTPException(400, f'score question "{name}" needs criteria')
            w = [random.random() ** 2 for _ in levels]
            probs = {str(i): round(v / sum(w), 3) for i, v in enumerate(w)}
            ev = sum(int(k) * v for k, v in probs.items())
            answers[name] = {
                "type": "score", "score": round(ev, 2), "confidence": max(probs.values()),
                "legend": {str(i): lv for i, lv in enumerate(levels)}, "probabilities": probs,
            }
        else:
            raise HTTPException(400, f'question "{name}": unknown type {t!r} (use noul | choice | score)')
    return {"model": model, "usage": {"input_tokens": 0, "output_tokens": 0}, "answers": answers}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", action="store_true", help="fake answers, no API key or network needed")
    ap.add_argument("--auto", action="store_true", help="live when TYPESAFE_API_KEY is set, else mock")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    a = ap.parse_args()
    if a.mock or (a.auto and not os.environ.get("TYPESAFE_API_KEY")):
        os.environ["TYPESAFE_MOCK"] = "1"
        MOCK = True
    elif not os.environ.get("TYPESAFE_API_KEY"):
        raise SystemExit("TYPESAFE_API_KEY is not set. Put it in .env, or run with --mock to explore the UI without a key.")
    gate = " · password required" if os.environ.get("PLAYGROUND_PASSWORD") else ""
    print(f"TypeSafe playground -> http://{a.host}:{a.port}  ({'MOCK answers' if MOCK else 'live API'}{gate})")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")

"""TypeSafe AI System One trial.

Sends one piece of *state* (here: a shipyard engineering change request) plus three
typed questions — one of each primitive the API supports — and prints the typed,
probability-weighted answers.

  noul   -> yes/no probability (0..1)
  choice -> one label from a set you define, with a probability per label
  score  -> expected score on an ordered rubric you define (index 0..N-1)

Usage:
  python trial/systemone_demo.py             # live call (needs TYPESAFE_API_KEY)
  python trial/systemone_demo.py --dry-run   # print the exact JSON body, no network
  python trial/systemone_demo.py --models    # list models available to your key

Wire contract verified against the official SDK (typesafe-sdk 0.6.0), whose schemas are
generated from https://api.typesafe.ai/openapi.json:
  POST {TYPESAFE_BASE_URL}/v1/systemone   Authorization: Bearer <key>
  body: {"state": ..., "model": "jev-latest", "questions": {name: {"type": ..., ...}}}
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv
from typesafe_sdk import Choice, Noul, Score, TypeSafeAPIError, TypeSafeClient, TypeSafeError
from typesafe_sdk._core.json import serialize

# --- state: what the model is asked to judge -------------------------------------------
# Any JSON (string / object / array) is accepted. A structured object lets you keep
# fields separate instead of flattening everything into prose.
STATE = {
    "doc_type": "engineering_change_request",
    "project": "H-1234 174K LNGC",
    "ecr_no": "ECR-2026-0417",
    "title": "Cargo tank No.2 dome insulation thickness change",
    "body": (
        "Owner requests increasing the secondary barrier insulation thickness on the "
        "No.2 tank dome from 270 mm to 300 mm to reduce BOR margin. Impact: hull outfitting "
        "drawings (3 sheets) reissue, ~2 weeks re-work on the dome trunk, material "
        "already on order — vendor lead time 6 weeks. Requested before block erection "
        "of DK-21 (scheduled in 5 weeks)."
    ),
    "requested_by": "Owner site team",
    "stage": "erection",
}

# --- questions: one of each primitive --------------------------------------------------
QUESTIONS = {
    # noul: yes/no, answered as a probability.
    "schedule_risk": Noul(
        instructions="Will this change likely delay the block erection milestone?",
        criteria={
            "true": "The change cannot be completed before the erection date without slipping it.",
            "false": "The change can be absorbed within the current schedule.",
        },
    ),
    # choice: pick one label; every label gets a probability.
    "owning_dept": Choice(
        instructions="Which department should own this ECR?",
        criteria={
            "hull_design": "Hull structure or hull outfitting drawing changes.",
            "cargo_system": "Cargo containment, insulation, or BOR-related changes.",
            "production": "Purely schedule/sequence changes with no drawing impact.",
            "procurement": "Primarily a material or vendor issue.",
            "other": "None of the above fits.",
        },
    ),
    # score: ordered rubric, index 0 = first entry. Returns an expected value, so it can
    # land between integers (e.g. 2.4).
    "cost_impact": Score(
        instructions="Rate the cost impact of this ECR.",
        criteria=[
            "Negligible: no re-work, no material change.",
            "Minor: drawing reissue only, < 1 week re-work.",
            "Moderate: re-work 1–4 weeks or material re-order.",
            "Major: re-work > 4 weeks, or affects a milestone.",
        ],
    ),
}


def dry_run(model: str) -> None:
    body = {"state": STATE, "model": model, "questions": QUESTIONS}
    print(json.dumps(json.loads(serialize(body)), indent=2, ensure_ascii=False))


def list_models(client: TypeSafeClient) -> None:
    for m in client.models.list().models:
        print(f"{m.name:<16} {m.release_date:<12} {m.description}")


def run(client: TypeSafeClient, model: str | None) -> None:
    response = client.system_one(state=STATE, questions=QUESTIONS, model=model)

    print(f"model: {response.model}")
    print(f"usage: input_tokens={response.usage.input_tokens} output_tokens={response.usage.output_tokens}")
    print()

    for name, a in response.nouls.items():
        print(f"[noul]   {name}: P(yes)={a.noul:.3f}")
    for name, a in response.choices.items():
        probs = ", ".join(f"{k}={v:.2f}" for k, v in sorted(a.probabilities.items(), key=lambda kv: -kv[1]))
        print(f"[choice] {name}: {a.choice} (confidence={a.confidence:.2f})  [{probs}]")
    for name, a in response.scores.items():
        probs = ", ".join(f"{k}={v:.2f}" for k, v in sorted(a.probabilities.items()))
        print(f"[score]  {name}: {a.score:.2f} / {len(a.legend) - 1} (confidence={a.confidence:.2f})  [{probs}]")

    # Policy lives in code, separate from the judgments, so thresholds can change without re-running
    # inference. These numbers are placeholders — tune them on your own ECR history.
    risk = response.nouls["schedule_risk"].noul
    cost = response.scores["cost_impact"]
    dept = response.choices["owning_dept"]
    escalate = risk >= 0.6 or cost.score >= 2.5 or dept.confidence < 0.5 or dept.choice == "other"
    print()
    print(f"policy: {'ESCALATE to change board' if escalate else 'auto-route to ' + dept.choice}"
          f"  (risk={risk:.2f}, cost={cost.score:.2f}, dept_conf={dept.confidence:.2f})")

    # Raw payload, useful while you learn the response shape.
    print("\n--- raw response ---")
    print(json.dumps(response.raw_http_response.json(), indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the request body and exit (no network)")
    parser.add_argument("--models", action="store_true", help="list models available to this API key")
    parser.add_argument("--model", default=None, help="model name (default: jev-latest or TYPESAFE_DEFAULT_MODEL)")
    args = parser.parse_args(argv)

    load_dotenv()  # reads .env if present; real env vars take precedence

    if args.dry_run:
        dry_run(args.model or "jev-latest")
        return 0

    try:
        with TypeSafeClient(timeout=30.0) as client:
            if args.models:
                list_models(client)
            else:
                run(client, args.model)
    except TypeSafeAPIError as e:
        # status / request_id are what support will ask for
        print(f"API error: {e}", file=sys.stderr)
        return 2
    except TypeSafeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

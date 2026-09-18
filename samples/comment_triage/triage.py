"""Owner comment triage with TypeSafe System One.

Shipyards receive hundreds of owner comments on drawings and specifications per project.
Each one has to be routed to a discipline, checked against the contract specification
(is it Builder's scope, or an Owner's change that needs a Variation Order?), and flagged
for class re-approval. This sample lets Jev supply the *judgments* while code keeps the
*rules*: the exact spec clause lookup, the routing policy, and the thresholds.

Per comment, ONE request carries five independent questions (they run in parallel inside
the API and cannot see each other's answers):

  discipline        choice  which engineering discipline should own the reply
  beyond_spec       noul    does the request exceed the contract specification baseline?
  class_reapproval  noul    would implementing it require Classification Society re-approval?
  impact            score   cost/schedule impact on a 0-3 rubric
  response_type     choice  the commercially correct kind of reply

Modes
  python samples/comment_triage/triage.py                 # live: needs TYPESAFE_API_KEY
  python samples/comment_triage/triage.py --record        # live, and save answers to fixtures/answers.json
  python samples/comment_triage/triage.py --fixture       # offline: replay fixtures/answers.json (synthetic!)
  python samples/comment_triage/triage.py --dry-run OC-002  # print the exact request for one comment

Outputs out/triage.csv and out/triage.md next to this file.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score, SystemOneResponse, TypeSafeError
from typesafe_sdk._core.json import serialize

HERE = Path(__file__).parent
OUT = HERE / "out"
FIXTURE = HERE / "fixtures" / "answers.json"

# ---------------------------------------------------------------------------------------
# 1. State: everything the model needs, as named fields. The spec clause is an EXACT lookup
#    done in code — the model is never asked to remember the contract.
# ---------------------------------------------------------------------------------------


def build_state(comment: dict, baseline: dict) -> dict:
    return {
        "project": baseline["project"],
        "contract_rules": baseline["contract_rule_summary"],
        "comment": {
            "drawing": comment["drawing"],
            "text": comment["text"],
            "clause_ref": comment["clause_ref"],
        },
        # None when the comment cites no clause; the questions say how to treat that.
        "spec_baseline_for_cited_clause": baseline["spec_baseline"].get(comment["clause_ref"]),
    }


# ---------------------------------------------------------------------------------------
# 2. Questions. Instructions carry the full judgment (question IDs are not sent to the
#    model). Criteria define every possible answer, including a no-match outcome.
# ---------------------------------------------------------------------------------------

QUESTIONS = {
    "discipline": Choice(
        instructions=(
            "Based on `comment.text` and `comment.drawing`, which engineering discipline should own "
            "the technical reply to this owner comment?"
        ),
        criteria={
            "hull_structure": "Steel scantlings, plating, stiffeners, foundations, structural analysis.",
            "hull_outfitting": "Deck machinery, cranes, accommodation, piping outside the machinery space.",
            "machinery": "Main/auxiliary engines, purifiers, pumps, compressors, engine-room arrangement.",
            "electrical": "Switchboards, cables, automation, lighting.",
            "cargo_containment": "Cargo tanks, insulation, secondary barrier, BOR, cargo handling.",
            "naval_architecture": "Stability, trim, damage stability, hydrodynamics, performance guarantees.",
            "other": "None of the above clearly applies.",
        },
    ),
    "beyond_spec": Noul(
        instructions=(
            "Does the owner's request in `comment.text` go beyond what the Builder already owes under "
            "`spec_baseline_for_cited_clause` and `contract_rules`? Treat a request for something the "
            "baseline already provides, a typo correction, or a request for confirmation as NOT beyond spec. "
            "If `spec_baseline_for_cited_clause` is null, judge from `contract_rules` and the comment alone."
        ),
        criteria={
            "true": "The request adds, upgrades, or changes scope relative to the specification baseline.",
            "false": "The request is within the baseline: a clarification, a correction, or already provided.",
        },
    ),
    "class_reapproval": Noul(
        instructions=(
            "If the request in `comment.text` were implemented, would it likely require re-approval by the "
            "Classification Society? Use the last item of `contract_rules` as the criterion."
        ),
        criteria={
            "true": "It changes structural scantlings, stability, or the cargo containment system.",
            "false": "It is a non-structural, non-stability, non-containment change, or no change at all.",
        },
    ),
    "impact": Score(
        instructions="Rate the likely cost and schedule impact on the Builder of implementing `comment.text`.",
        criteria=[
            "None: a typo fix, a confirmation, or a change absorbed in normal drawing revision.",
            "Minor: drawing reissue and small material change, no effect on any milestone.",
            "Moderate: re-work of one to four weeks, new material order, or a vendor re-engineering loop.",
            "Major: re-work over four weeks, a milestone at risk, or a change to class-approved design.",
        ],
    ),
    "response_type": Choice(
        instructions=(
            "Given `contract_rules` and `spec_baseline_for_cited_clause`, what kind of reply should the "
            "Builder send for `comment.text`?"
        ),
        criteria={
            "accept_no_cost": "The request is within the specification or is a plain correction; accept.",
            "quote_variation_order": "The request exceeds the specification; accept in principle but quote cost and schedule for a Variation Order.",
            "reject_with_reason": "The request contradicts the contract or a rule and should be declined with a technical or contractual reason.",
            "clarify_or_confirm": "The comment is a question or asks for confirmation; reply with the requested information only.",
            "other": "None of the above fits.",
        },
    ),
}


# ---------------------------------------------------------------------------------------
# 3. Policy: pure code over the raw judgments. Change thresholds here without re-running
#    inference. THESE NUMBERS ARE PLACEHOLDERS — calibrate on your own comment history.
# ---------------------------------------------------------------------------------------

T_BEYOND_SPEC = 0.60      # P(beyond spec) at or above this => treat as Owner's change
T_CLASS = 0.50            # P(class re-approval) at or above this => flag to class coordinator
T_IMPACT_MAJOR = 2.5      # expected score at or above this => commercial escalation
T_LOW_CONF = 0.50         # any choice below this confidence => human review


@dataclass
class Triage:
    id: str
    drawing: str
    discipline: str
    discipline_conf: float
    p_beyond_spec: float
    p_class: float
    impact: float
    impact_conf: float
    response_type: str
    response_conf: float
    track: str          # "technical_reply" | "variation_order" | "human_review"
    flags: str          # ";"-joined

    @property
    def sort_key(self):
        rank = {"human_review": 0, "variation_order": 1, "technical_reply": 2}
        return (rank[self.track], -self.impact)


def apply_policy(comment: dict, r: SystemOneResponse) -> Triage:
    disc = r.choices["discipline"]
    resp = r.choices["response_type"]
    beyond = r.nouls["beyond_spec"].noul
    cls = r.nouls["class_reapproval"].noul
    imp = r.scores["impact"]

    flags: list[str] = []
    if cls >= T_CLASS:
        flags.append("CLASS")
    if imp.score >= T_IMPACT_MAJOR:
        flags.append("MAJOR_IMPACT")

    # "Any serious condition" rules stay separate; no weighted blend hides them.
    if disc.confidence < T_LOW_CONF or resp.confidence < T_LOW_CONF or resp.choice == "other" or disc.choice == "other":
        track = "human_review"
        flags.append("LOW_CONFIDENCE")
    elif resp.choice == "reject_with_reason":
        track = "human_review"  # a rejection is always signed off by a person
        flags.append("REJECTION")
    elif resp.choice == "quote_variation_order" or (beyond >= T_BEYOND_SPEC and imp.score >= 1.5):
        track = "variation_order"
    else:
        track = "technical_reply"

    return Triage(
        id=comment["id"], drawing=comment["drawing"],
        discipline=disc.choice, discipline_conf=disc.confidence,
        p_beyond_spec=beyond, p_class=cls,
        impact=imp.score, impact_conf=imp.confidence,
        response_type=resp.choice, response_conf=resp.confidence,
        track=track, flags=";".join(flags),
    )


# ---------------------------------------------------------------------------------------
# 4. Execution: one request per comment, N in flight. Fixture mode replays saved answers.
# ---------------------------------------------------------------------------------------


async def judge_live(comments: list[dict], baseline: dict, concurrency: int, record: bool) -> dict[str, dict]:
    sem = asyncio.Semaphore(concurrency)
    raw: dict[str, dict] = {}

    async with AsyncTypeSafeClient(timeout=30.0) as client:
        async def one(c: dict) -> tuple[str, SystemOneResponse]:
            async with sem:
                return c["id"], await client.system_one(state=build_state(c, baseline), questions=QUESTIONS)

        results = await asyncio.gather(*(one(c) for c in comments))

    responses = {}
    for cid, resp in results:
        responses[cid] = resp
        raw[cid] = resp.raw_http_response.json()
    if record:
        FIXTURE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
        print(f"recorded {len(raw)} responses -> {FIXTURE}", file=sys.stderr)
    return responses


def judge_fixture(comments: list[dict]) -> dict[str, SystemOneResponse]:
    """Replay saved responses through the SDK decoder, so the rest of the code path is identical."""
    import httpx2

    saved = json.loads(FIXTURE.read_text())
    out = {}
    for c in comments:
        body = saved[c["id"]]
        http = httpx2.Response(200, json=body, request=httpx2.Request("POST", "https://fixture.local/v1/systemone"))
        out[c["id"]] = SystemOneResponse._decode(http)  # noqa: SLF001 - fixture replay only
    return out


# ---------------------------------------------------------------------------------------
# 5. Reporting
# ---------------------------------------------------------------------------------------


def write_reports(rows: list[Triage]) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / "triage.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

    lines = ["| ID | Track | Discipline | Reply | P(beyond spec) | P(class) | Impact | Flags |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r.id} | **{r.track}** | {r.discipline} ({r.discipline_conf:.2f}) | {r.response_type} ({r.response_conf:.2f}) "
            f"| {r.p_beyond_spec:.2f} | {r.p_class:.2f} | {r.impact:.1f} | {r.flags} |"
        )
    (OUT / "triage.md").write_text("\n".join(lines) + "\n")


def print_table(rows: list[Triage]) -> None:
    print(f"{'ID':<7}{'TRACK':<17}{'DISCIPLINE':<27}{'REPLY':<30}{'BEYOND':>7}{'CLASS':>7}{'IMPACT':>7}  FLAGS")
    for r in rows:
        print(
            f"{r.id:<7}{r.track:<17}{r.discipline + f' ({r.discipline_conf:.2f})':<27}"
            f"{r.response_type + f' ({r.response_conf:.2f})':<30}"
            f"{r.p_beyond_spec:>7.2f}{r.p_class:>7.2f}{r.impact:>7.1f}  {r.flags}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", action="store_true", help="replay fixtures/answers.json instead of calling the API")
    ap.add_argument("--record", action="store_true", help="call the API and save responses to fixtures/answers.json")
    ap.add_argument("--dry-run", metavar="ID", help="print the request body for one comment id and exit")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args(argv)
    load_dotenv()

    comments = json.loads((HERE / "comments.json").read_text())
    baseline = json.loads((HERE / "contract_baseline.json").read_text())

    if args.dry_run:
        c = next((c for c in comments if c["id"] == args.dry_run), None)
        if c is None:
            print(f"no comment {args.dry_run}", file=sys.stderr)
            return 1
        body = {"state": build_state(c, baseline), "model": "jev-latest", "questions": QUESTIONS}
        print(json.dumps(json.loads(serialize(body)), indent=2, ensure_ascii=False))
        return 0

    try:
        if args.fixture:
            print("NOTE: fixture mode — answers are synthetic placeholders, not Jev output.\n", file=sys.stderr)
            responses = judge_fixture(comments)
        else:
            responses = asyncio.run(judge_live(comments, baseline, args.concurrency, args.record))
    except TypeSafeError as e:
        print(f"TypeSafe error: {e}", file=sys.stderr)
        return 2

    rows = sorted((apply_policy(c, responses[c["id"]]) for c in comments), key=lambda r: r.sort_key)
    print_table(rows)
    write_reports(rows)
    print(f"\nwrote {OUT / 'triage.csv'} and {OUT / 'triage.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

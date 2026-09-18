#!/usr/bin/env bash
# Plain-HTTP equivalent of systemone_demo.py, for checking the API without any SDK.
# Requires TYPESAFE_API_KEY in the environment (or in .env: `set -a; . ./.env; set +a`).
set -euo pipefail
: "${TYPESAFE_API_KEY:?set TYPESAFE_API_KEY}"
BASE_URL="${TYPESAFE_BASE_URL:-https://api.typesafe.ai}"

curl -sS "$BASE_URL/v1/systemone" \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "state": "I was charged twice for my LNG carrier class survey. Please fix this ASAP.",
  "model": "jev-latest",
  "questions": {
    "is_urgent":  {"type": "noul",   "instructions": "Is the sender asking for urgent handling?"},
    "category":   {"type": "choice", "instructions": "What is this ticket about?",
                   "criteria": {"billing": null, "technical": null, "other": null}},
    "severity":   {"type": "score",  "instructions": "How severe is the issue?",
                   "criteria": ["cosmetic", "inconvenient", "blocking", "financial loss"]}
  }
}
JSON
echo

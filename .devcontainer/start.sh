#!/usr/bin/env bash
# Starts (or restarts) the playground in the background each time the codespace starts.
# Live when TYPESAFE_API_KEY is present as a Codespaces secret, otherwise MOCK mode.
cd "$(dirname "$0")/.."
pkill -f "webapp/app.py" 2>/dev/null || true
nohup python webapp/app.py --auto --host 0.0.0.0 --port 8000 > /tmp/playground.log 2>&1 &
sleep 1
echo "playground: $(head -1 /tmp/playground.log)"

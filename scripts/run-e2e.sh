#!/usr/bin/env bash
# Pre-release E2E gate: run the live /api/chat suite against a
# running ADMZ server.
#
# Usage:
#   scripts/run-e2e.sh                  # default: localhost:4242
#   ADMZ_E2E_BASE_URL=http://...  scripts/run-e2e.sh
#
# Cost: ~$0.03-$0.05 per full run (real Gemini API credits).
# Time: ~3-5 minutes wall clock.

set -euo pipefail

cd "$(dirname "$0")/.."

BASE_URL="${ADMZ_E2E_BASE_URL:-http://127.0.0.1:4242}"

echo "=== E2E gate ==="
echo "  server: $BASE_URL"

# Liveness probe — fail fast if the server isn't reachable.
if ! curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1; then
    echo "ERROR: ADMZ server not reachable at $BASE_URL"
    echo "Start it with:"
    echo "  python -m admz api --host 127.0.0.1 --port 4242"
    exit 1
fi
echo "  ✓ server alive"

# Confirm the Gemini key is configured (no point burning a minute
# of test time only to find the chatbot isn't configured).
if ! curl -fsS "$BASE_URL/api/chat" \
        -H "Content-Type: application/json" \
        -d '{"message":"reply with the single word ok","use_tools":false}' \
        --max-time 30 >/dev/null 2>&1; then
    echo "ERROR: /api/chat is not responding successfully."
    echo "Check that ADMZ_GEMINI_API_KEY is set + the chatbot is configured."
    exit 1
fi
echo "  ✓ /api/chat working"

# Pick the right python — try .venv first, fall back to PATH.
PY="${PY:-.venv/Scripts/python.exe}"
if [ ! -x "$PY" ]; then
    PY="${PY:-.venv/bin/python}"
fi
if [ ! -x "$PY" ]; then
    PY=python
fi

echo
echo "=== running suite ==="
"$PY" -m pytest tests/e2e --run-e2e -v --no-cov "$@"

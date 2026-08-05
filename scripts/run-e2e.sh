#!/usr/bin/env bash
# Pre-release E2E gate: run the live /api/chat suite against a
# running ADMZ server.
#
# Usage:
#   scripts/run-e2e.sh                  # default: staging, localhost:4243
#   ADMZ_E2E_BASE_URL=http://...  scripts/run-e2e.sh
#
# Never production (CLAUDE.md: "Never point tests, agents, or experiments
# at :4242"). This script refuses before doing anything — before even the
# liveness probe below — if the resolved target is :4242. See
# admz/target_guard.py for the check and its escape hatch (#180).
#
# Cost: ~$0.03-$0.05 per full run (real Gemini API credits).
# Time: ~3-5 minutes wall clock.

set -euo pipefail

cd "$(dirname "$0")/.."

BASE_URL="${ADMZ_E2E_BASE_URL:-http://127.0.0.1:4243}"

# Pick the right python — try .venv first, fall back to PATH. Needed now
# (before anything else runs) so the target guard below can import admz.
PY="${PY:-.venv/Scripts/python.exe}"
if [ ! -x "$PY" ]; then
    PY="${PY:-.venv/bin/python}"
fi
if [ ! -x "$PY" ]; then
    PY=python
fi

# Refuse before doing anything else — including the liveness probe — if
# this resolves to production. Delegates to admz.target_guard so this
# check can't drift from the one tests/e2e/conftest.py runs (#180).
if ! "$PY" -c "
import sys
from admz.target_guard import refuse_if_production
try:
    refuse_if_production('$BASE_URL', source='ADMZ_E2E_BASE_URL (or the :4243 default)')
except RuntimeError as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
"; then
    exit 1
fi

echo "=== E2E gate ==="
echo "  server: $BASE_URL"

# Liveness probe — fail fast if the server isn't reachable.
if ! curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1; then
    echo "ERROR: ADMZ server not reachable at $BASE_URL"
    echo "Start it with:"
    echo "  python -m admz api --host 127.0.0.1 --port 4243"
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

echo
echo "=== running suite ==="
"$PY" -m pytest tests/e2e --run-e2e -v --no-cov "$@"

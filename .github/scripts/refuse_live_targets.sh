#!/usr/bin/env bash
# Refuse to run if this job has been pointed at live hardware.
#
# Two suites in this repo talk to real things over the network:
#
#   tests/e2e/                     defaults to http://127.0.0.1:4242 — the
#                                  PRODUCTION instance, managing a live Axis
#                                  fleet (issue #180). Opt-in via --run-e2e.
#   tests/test_chat_action_live.py drives REAL CAMERAS (verify=False, 8/16/24s
#                                  retries) whenever ADMZ_LIVE_CHAT_TESTS is set.
#
# ci.yml excludes both at the path level, so this script is the second latch:
# it catches someone adding one of these variables to the workflow, a repo
# variable, or an environment, without noticing what it turns on. Neither latch
# alone is sufficient — the path excludes can be edited, and an env var alone
# would be silent.
#
# This is deliberately a denylist of *targeting* variables, not a general
# environment scrub.

set -uo pipefail

LIVE_VARS=(
  ADMZ_LIVE_CHAT_TESTS   # unlocks tests/test_chat_action_live.py -> real cameras
  ADMZ_CHAT_TEST_URL     # retargets that suite
  ADMZ_E2E_BASE_URL      # retargets tests/e2e/ (default :4242 = production)
  ADMZ_E2E_API_KEY       # authenticates e2e writes against a real instance
  ADMZ_DEV_API_KEY       # same, via the dev-key fallback chain
)

found=0
for var in "${LIVE_VARS[@]}"; do
  if [ -n "${!var:-}" ]; then
    echo "::error title=Live-hardware variable set in CI::${var} is set. It points the test suite at a running ADMZ instance and, through it, at real Axis devices. CI must never drive live hardware."
    echo "  !! ${var} is set"
    found=1
  fi
done

if [ "${found}" -ne 0 ]; then
  {
    echo "## Refusing to run: CI is pointed at live hardware"
    echo
    echo "One or more live-target variables are set in this job's environment."
    echo "The e2e suite defaults to \`http://127.0.0.1:4242\` — the **production**"
    echo "instance managing a real Axis fleet (issue #180) — and the live chat"
    echo "battery drives **real cameras**."
    echo
    echo "Remove the variable. Do not remove this check."
  } >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
  exit 1
fi

echo "No live-target variables set; the suite will run fully offline."

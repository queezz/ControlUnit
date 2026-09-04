#!/bin/bash
#
# Start the control unit on the rig, with the web view on the lab network.
#
# The Raspberry Pi launches this from ~/Desktop/aktest.sh. It lives in the
# repository so the launcher travels with the code it starts, and so a change
# to how the rig is started is reviewable like any other change.
#
# Any extra arguments are passed through, so a run can still be narrowed to
# the Pi itself:
#
#     scripts/run_controlunit.sh --host 127.0.0.1
#
set -euo pipefail

# Run from the repository root, whichever checkout this script sits in.
cd "$(dirname "$0")/.."

exec python -m controlunit.main --web "$@"

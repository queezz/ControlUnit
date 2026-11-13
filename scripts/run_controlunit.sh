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

# The program's error output is kept in a file beside the data as well as
# on the terminal. The desktop shortcut has no terminal, so until now a
# traceback from a dying worker went nowhere: the reader's deaths of
# 2026-08-19 and 2026-09-09 left no record of what killed them.
errors="$HOME/work/cudata/controlunit.stderr.log"
mkdir -p "$(dirname "$errors")"
{ echo; echo "# $(date '+%Y-%m-%d %H:%M:%S') started"; } >> "$errors"

# And how it ended. On 2026-11-11 at 16:47 the program restarted with no
# reason anywhere, so this shell now waits for the program instead of
# becoming it (it used to `exec`), and writes its exit status after the
# "started" line: 0 for Quit or the window closed, 128 + the signal for a
# signal the program handled (143 SIGTERM, 129 SIGHUP, 130 SIGINT), the same
# numbers for a second SIGTERM or Ctrl+C that ended a shutdown at once, 137
# for a kill it could not handle. An error no code caught no longer ends it
# (its Log says so, and it carries on with the outputs held); 1 is Python
# itself failing to start or to go on. The program's own last Log line says
# the same in words.
#
# Closing the terminal this runs in sends SIGHUP to the program, this shell
# and `tee` alike. The program stops through Stop's own path on it; the trap
# keeps this shell alive until the program has, to write the line (a trap
# set here is reset in the program, which handles its own); and `tee`
# ignores it, so the program's last words still reach the file.
trap ':' HUP TERM INT
status=0
python -m controlunit.main --web "$@" 2> >(trap '' HUP TERM INT; tee -a "$errors" >&2) \
    || status=$?
echo "# $(date '+%Y-%m-%d %H:%M:%S') exited with status $status" >> "$errors"
exit "$status"

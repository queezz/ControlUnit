#!/usr/bin/env sh
# Copy the lab's roster of names to the rig, so the Control tab offers the
# same names PIHTI Log does. See push_roster.ps1 for the whole story; this
# is the same copy for a macOS or Linux shell.
#
#     scripts/push_roster.sh                       # vault under ~/Dropbox, rig pi@pihti
#     scripts/push_roster.sh ~/Dropbox/Obsidian/pihti pi@10.249.254.21
set -eu
vault="${1:-$HOME/Dropbox/Obsidian/pihti}"
rig="${2:-pi@pihti}"
roster="$vault/People/operators.json"
[ -f "$roster" ] || { echo "No roster at $roster" >&2; exit 1; }
grep -q '"pihti-operators/v1"' "$roster" || { echo "$roster is not a pihti-operators/v1 roster" >&2; exit 1; }
ssh "$rig" "mkdir -p .controlunit"
scp "$roster" "$rig:.controlunit/operators.json"
echo "Roster copied to $rig:~/.controlunit/operators.json; the Control tab reads it within a second."

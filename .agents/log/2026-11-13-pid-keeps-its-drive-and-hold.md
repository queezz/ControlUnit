# The PID keeps its drive, and Hold beside Off — 2026-11-13, 4.30.0

Queezz, after the audit of the student runs (vault note "Student runs
audit 2026-10-22 to 11-13", and `.agents/directions.md`): he chose "PID
keeps its drive", then "Just go through the list and fix the big obvious
problems. Maybe subagents and worktrees? Up to you." This slice is the
PID half, done here; the gauge-settings half went to an Opus subagent in
its own worktree and is integrated separately.

## Checked before building

The rig's own log for 11-13 (read-only, `nice grep`): "no discharge at
the 1900 mV ceiling" at 15:24:56, 16:34:15 and 16:43:52; "discharge lit at
1900 mV" at 15:25:05; "engaged at 2500 mV … Ip 2.389 A" at 16:38:30; "PID
turned off" at 16:20:03 and 16:38:45 with a discharge at 1.5 A. The code:
`ramp()` brings a drive above the ceiling down at once; "PID off" calls
`turn_off_currentcontrol_voltage`, which zeroes the DAC. The audit's copy
of `cu_20261111_164721.csv`: with `PresetV_cathode` 0 from 15:25:25, Ip_c
reads 2.379–2.384 A until 15:25:52, then −0.02 A.

## What was built

- `CathodeLoop.hold`: one step that keeps the drive and the integral.
  The reader uses it for the 2 s grace when the current is below Lit
  Above, so a dropout neither winds the drive up nor answers it.
- The reader keeps `_lit_drive`, the drive of the last step with a
  discharge (or the start drive of a lit engagement). Unlit, the ramp's
  ceiling is the larger of that and `Unlit Ceiling mV`, so a discharge
  lost above the ceiling is held there, with a red "discharge lost;
  holding the cathode at N mV, the drive it was lit at" line; one lost
  below it walks up to the ceiling with the old lines.
- The plateau (Ip flat near 2.38 A) is not handled: on the 11-13 data its
  1 s range overlaps a regulated discharge's (p50 0.035 against 0.06 A),
  so no flatness test separates them cleanly, and its cause is hardware or
  measurement, with queezz. While the plateau reads above the setpoint the
  loop drives down, which is the safe direction.
- Web: Hold (`{"hold": true}`, `MainApp.hold_currentcontrol_voltage`,
  which puts the loop's last command in the dock's millivolt box and calls
  `set_cathode_drive`) and Off, each with a title saying what happens to
  the drive; the card turns to Manual when the rig queues a Hold. The PID
  row has the Manual row's grid so three presses fit one line. The rig's
  Qt dock keeps its own PID off.

Tests: the old "goes out → down to the ceiling" test became "keeps the
drive it was lit at" (2200 mV held through 60 s, relit with the
proportional answer); a grace test (no wind-up); an argon case below the
ceiling; Hold through the real app; the command, summary and page.
pytest 724 passed, mkdocs clean, node 65 passed.

Not done: replaying 11-13 through the loop. The loop's output changes the
plasma, so an open-loop replay predicts nothing past the first dropout;
the tests carry the dropout itself.

## Perimeter Walk (the Cathode card)

Scratch `lab start controlunit-dummy --port 48937` as for 4.29.2 (scratch
LAB roots and home, offscreen Qt, no browser opened, 4187 untouched,
port freed at the end). As the holder: manual 2200 mV, PID 1.5 A (the
dummy has no discharge, so the loop sat at 1900 mV as before). Hold in the
page: PID 0 A, drive 1900 mV kept, outputs "cathode drive", card turned to
Manual, Log "Cathode drive set to 1900 mV, PID off" and "plasma current PID
off, drive held". Engaged again, Off: 0 mV, no outputs, "plasma current
PID off, drive 0". The PID row 34 px, one line, Set/Hold/Off inside the
card at 1280×1000 and 375×812 (no horizontal overflow); rails 76 px at
0–100 % scroll at 1280×700; console clean, no failed requests. Tabs,
anchors and history are untouched by this slice and were walked for 4.29.2
the same day.

agent: claude

## The gauge half, from the worktree

An Opus subagent in its own git worktree (branch
`worktree-agent-a851f61f70d19a19a`, commit `5841014`, cut from `cf19666`)
built the remembered screen (`controlunit/screen_memory.py`,
`~/.controlunit/screen.json`), the Log line for a dock gauge press, and the
watchdog's longer line across a sampling change. Reviewed here (the diff,
and the module), merged with `--no-ff`; the merged tree passes pytest 738,
mkdocs, node 65, and left nothing in this PC's real `~/.controlunit`.
Live on the scratch instance: Pd Torr 1e-7, Pu2 off and 10 s set from the
web, the program stopped and started, and the Log said "Restored from the
last run: Pd Torr 1e-7, Pu2 off, sampling 10 s". Before the first Start the
web state knows only the restored values that differ from the defaults
(Pd's range, Pu2's mode); Start pushes the rest, as before. The web view's
own "stale" line still switches to the short threshold at once on a
sampling change (left; it is the web status's, not the watchdog's).

agent: claude

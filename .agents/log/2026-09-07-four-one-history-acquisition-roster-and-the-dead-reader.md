# 2026-09-07 — 4.1.0: history in the browser, acquisition from a laptop, the roster, and the reader that died

queezz opened with eight complaints against 4.0.0 on the rig and a
screenshot of each; by the end of the day 4.1.0 was on master, pulled to
the Pi, and a ninth thing — his student's "data logging interrupted" — had
an explanation from the rig's own records. Three Opus agents built the
slices in scratch worktrees outside Dropbox, one walked the result, and
this session designed, integrated, and read the rig.

## What he asked for, and what shipped

- "Can't stop, run, modify" turned out to mean the Acquisition group was
  read-only. Now a browser starts and stops a run and sets the sampling
  time through the same queue as every setter; Start is the one control
  live while nothing runs. Stopping no longer forces the Remote switch off
  — a browser that stops must be able to start again — and the operator
  lock is still released on stop. `main.py`'s on/off and sampling handlers
  were split so the rig's own switch and the browser share one code path.
- "Full scale does nothing; keep historic data locally." The Live tab
  keeps its own history: one fill from the ring on open, then `since=`
  polls for what is new, a day per channel in the browser; window buttons
  cut locally and Full is what this browser has seen. The Pi answers a
  handful of rows a poll however long the page is open.
- "1e-5 is ugly; value cards with a colour hint." Readouts render
  3.16×10⁻⁵ with a real superscript at a height that does not change when
  a value crosses into exponent form; each card carries a wash and border
  of its own pen, with the name larger. Log axes tick in 10⁻⁵.
- "The viewer shows nothing about the zero." Ip, Bu and Bd cards carry a
  line, `zero −0.345 A` or `as measured`, and the Data card says once that
  the three read minus the zero while the data file keeps the signal.
- "Multiple gauges unreadable; log for IGs, normal for baratrons." Three
  charts: plasma current, ion gauges (log by default), Baratrons (linear),
  each with its own scale row.
- "Maybe something on the display side" for the spiky current: a centred
  moving median, off/5/15/51 samples, over every line and the readouts.
- "Asks to invent a name." The Acting-as field is a list from the lab's
  roster when the Pi holds a copy of PIHTI Log's `People/operators.json`;
  free text where it does not. The copy is `scripts/push_roster.ps1`,
  names never enter git; a letter to PIHTI Log proposes `/api/roster` so
  the rig can follow the vault by itself.
- "Opening lab tab is very slow." The Lab tab is served from what the Pi
  already knows and asks the LAN behind that, with a sixth honest state,
  `checking`; measured 56 ms to paint on the scratch rig.
- "About 10 seconds for the quit button" after Stop: the ADC loop slept a
  whole sampling period before reading its abort flag. Workers now sleep
  through `DeviceThread.pause`, which looks every tenth of a second.
- The diagnostics tab and raw voltages are in directions, ready to build.

## The reader that died

Mizuno-kun's journal for 2026-08-19 and 20 says "data logging
interrupted" four times. The rig's `controlunit.log` and the data files
show each time the file simply stopping mid-run with no "stopped" line,
then "Starting acquisition" when he cycled the switch: the ADC worker
thread died between two samples and the window stayed up. Nothing
recorded why — the read loop has no error handling and the launcher keeps
no error output — and his notes describe arcing. Through queezz he
confirmed gas by hand and no PID; the cathode supply is wired for voltage
control from the DAC, which held its last voltage, so the plasma ran on
unwatched. queezz decided: hold the outputs and alarm — the rig's LED and
the display's buzzer, the web view blinking and speaking — with the reader
made to survive an I²C error and a Restart reader press to raise it
mid-run. All of it is one slice in directions.

## Measured

Perimeter Walk on a scratch rig at 127.0.0.1:48945 with dummy hardware,
switch on, acquiring, HOME redirected: sixteen tab presses land at scroll
0; every reachable anchor 15.8–16.1 px clear of the bar; both rails at
76 px at 0/25/50/75/100% scroll on Live and Control at 1280×1000 and
1280×700; the Live rail's last card ends exactly at the rail's edge at
700 px (`604 === 604`), which is why Display and Poll became one Readouts
card; the readout row and chart tops unchanged through 24 presses and
eleven seconds of polling; no console error from the app; `no-store` on
every response plus `?v=4.1.0` on assets. Two findings fixed after the
walk: the doc's series poll rate sentence, and Lab's Open links now open
beside the page. Stop, start, sampling and the refusals were exercised
end to end through the API on the scratch rig.

## Gates and deployment

326 tests, `flake8 --select=E9,F63,F7,F82` clean (the repository carries
no flake8 config and the full default run has never passed here; the
agents measured their own files unchanged against master), strict docs
build. Version 4.1.0 in both places. queezz pushed master himself and
ruled that a session pushes only on his word and pulls to an idle rig
itself; both agent documents now say so. The Pi's checkout at
`~/work/aktest` is at 4.1.0, clean, nothing running; the restart is his.
Merge commits carry no `agent:` trailer: the harness refused every
`git commit --amend`, so they stand with git's default message.

## Fleet

Orders `20260904-a6d06945-a3aa26` and `20260904-9dbc0c87-9d702f`
collected after their answers went into directions; letter
`20260904-39c8138b-140030` collected and answered by
`20260907-7a212c6c-cbea2a` (the ampere date is 2026-09-05, file
`cu_20260905_105520.csv`); the four lab-cli and diagram notes logged. SSH
to the Pi now runs through the Windows agent, which keeps the key across
reboots; recorded in this session's memory.

## Later the same day: 4.2.0, the fence and the services board

Two more slices, both his live word. "Let's add `plasmabox` word just in
case. Not security, just a fence one can walk over": the lab's word lives
in `~/.controlunit/fence.txt` on the Pi (written there already, 4.1.0
ignores it), a browser types it once on the Control tab, and every setter
and Take over is refused with "type the lab's word first" until it has;
Stop all outputs never is. Verified on a scratch rig with the fence set:
setters 403 before, a wrong word 403, the right word 200 and the same
setter 202, stop-all 202 throughout, the rail's reason line at its
two-line height and no card moving.

Then PIHTI Log's letter relaying "I like the pihti-diagram way for the
services. And we need to sync that in all 3 siblings": the Lab tab is the
diagram's board now — Check with Ask again now and the checked time on
the left, one card per service with Version, Says, Runs, Start and Open,
The ensemble explained once on the right with the six states — and the
state meanings are shared: a refused connection or an HTTP error is
`down`, a timeout or an unresolved name `unreachable`. It still paints at
once and asks behind. On the scratch rig the first paint read `checking`
and a warm cache read "Checked 17:08:46."; the refused case could not be
shown on this Windows box, whose closed loopback ports time out instead
of refusing (the Pi's Linux refuses, and seven monkeypatched cases pin
the mapping). Two rail notes and the roster note were shortened or
dropped so the Control rail fits a 700px window with the fence row; both
rails measured at 76px at 0/25/50/75/100% scroll at 700px.

397 tests, lint and strict docs green. Version 4.2.0. Letter
`20260907-d526b38c-482393` collected and answered.

## Night: 4.2.1, the board at a glance

Two more letters relayed his corrections: ControlUnit starts from its own
screen, never from lab; and the diagram's 0.8.0 explainer is a glance —
one lead line, the chips with three-word meanings, the rest behind More —
because three muted paragraphs were "too long and too quiet". Built and
measured on the scratch rig at 700px: right rail 483px collapsed, 627px
expanded, inside its 680px; More and Less at one position (445px); a start
command shown stays shown across the board's refresh; the self card reads
"From the rig's own screen: the desktop shortcut starts the whole program,
web view included." 406 tests. A `start_how` line per neighbour in the
Pi's `neighbours.yml` is the one machine-local follow-up.

## Late: 4.2.2 and 4.3.0

A favicon, the tool's own tile — CU in amber on charcoal, nothing smaller,
because a dot vanished at 16px. Then his "averages are cheap and good":
at one second and slower the reader converts every 0.2 s through the
period and records one row of means, raw voltages averaged and then
converted so a file row stays self-consistent; below a second nothing
changes; an abort mid-period records no partial row. 418 tests, the
MainApp end-to-end at 1 s sampling among them. Untested on the real ADC:
whether nine channels convert inside 0.2 s on the Pi; if not, the period
simply yields fewer readings and still ends on time.

agent: claude fable 5.1

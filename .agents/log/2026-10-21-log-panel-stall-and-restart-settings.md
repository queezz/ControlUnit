# The hang of 2026-10-21, and Stop/Start forgetting the sampling — 4.29.1

Queezz: "Can you take a look into the rig? It hang again today, I had to
close the terminal from which it run." Then: "How about fixing it? Also
the restart from Webui, it should remember settings, not run with
whatever is default and invisible."

## What the rig's records said

Read over SSH (Windows OpenSSH; Git Bash's ssh has no key for `pihti`)
and `/api/health`, nothing set. The program had been restarted at 16:48:50
and was acquiring at 10 s with no outputs live.

The run `cu_20261019_165735.csv` never crashed. From 17:00 on 10-19 one
ADC channel read stalled at each of the two log lines written every 30 s:
5 s at first, 25 s by midnight, and 87–94 s per line on 10-21. The file
went from 526 rows an hour to 14. Cause: `log_message` added each line by
`setHtml(toHtml() + line)` on the Qt Log panel, and PyQt holds the GIL
while Qt does it. Measured off-rig, panel visible: 0.18 s per line at 250
lines, 0.58 s at 500; hidden, 0.04 s at 1000. The restarts of 10-13,
10-16 and 10-19 look like the same fault.

Second fault, same run: Kawabata set 10 s from the web view and pressed
Stop and Start at 16:57; the new reader took settings.yml's 0.1 s while
the dock, the watchdog and the web view said 10 s.

The Kikusui LAN was "LOST" for most of that run. It is not the cause:
queezz switches the supply off when it is not in use, so the recorder
fails to connect during pump-downs by design (owner statement 2026-10-21).

Vault: `Experiments/Troubleshooting/ControlUnit slowdown from its own Log
panel 2026-10-21.md` and a line in `Troubles.md`.

## What shipped

Implemented by an Opus subagent from a packet written here, reviewed and
gated here.

- The panel is appended to at an end cursor, never rebuilt, and capped at
  200 lines (queezz: "100 or 200 is more than enough. The qt side is
  there for redundancy and history"). About 2 ms a line, flat.
- Routine 30-second timing summaries go to the file and the web Log only
  (`send_routine`, `log_routine`); overruns still reach the panel.
- Every Start pushes the dock's sampling time to the new reader and the
  web status before the threads start, beside the gauge modes and ranges
  (which also moved before the threads start), and logs "Started with
  sampling … s". Outputs are not carried over.

Gates: pytest 718 passed; `mkdocs build --strict` clean; `node --test` 65
passed (subagent's run, no web code changed).

## Left, for queezz

From the subagent's audit, not changed:

- A restart forgets the Ip, Bu and Bd baselines, consistently everywhere.
- The QMS sync switch can show on after a restart while the new reader
  records 0; it drives a GPIO line to another instrument, so it was
  treated as output-like and not re-driven.
- After Stop, the Cathode dock's PID ampere and manual mV boxes keep
  showing their last values while the hardware is at 0.
- The sampling cannot be changed from the web while stopped; a change on
  the rig's combo while stopped takes effect at the next Start.

Not deployed: master is local until queezz says push, and the rig was
acquiring when read.

agent: claude

## Then: the Kikusui sidecar during pump-downs

Queezz: "Do we need 39 seconds sampling of a PSU being off? A perfect
noise." (The hung run's sidecar has 4525 `unavailable` rows in two days,
one per ~38 s because the recorder's thread was starved too; at the
normal 5 s retry it would be 17 000 a day.) Then: "Maybe some heuristic?
Or off several times, then check regularly if it comes back, and report
when it does???"

Done here directly, in the same unreleased 4.29.1: one `unavailable` row
per outage, its first; LOST in the Log only after three missed polls in a
row (`KikusuiLogger.LOST_AFTER`, about ten seconds), saying the supply may
be off and that it is checked every 5 s; BACK only after a LOST. A shorter
blip is one row and nothing in the Log. The retry stays at 5 s so the
supply is seen within seconds of being switched on. pytest 719 passed;
mkdocs clean.

agent: claude

## Deployed, 2026-10-22 00:38 (4.29.1)

Queezz: "Deploy. Then restart the acquisition". Pushed `7ed816f..41e716c`.
A script run on the Pi from `/tmp`, stopping at the first thing not as
expected (it removed itself and its cookie jar): health `acquiring`, no
outputs; state read first (sampling 10 s, Pd Torr 1e-7, Pu2 Torr 1e-5,
sync off); as the roster's `Kuzmin Arseniy` with the lab's word from the
Pi's own file, take control from Kawabata, stop (`cu_20261021_164856.csv`
closed), `idle`, TERM, process gone, `pull --ff-only` to `41e716c`,
`compileall` clean, started through `~/Desktop/aktest.sh` in lxterminal on
display `:0`, health 4.29.1, the gauges put back from the state read
before the stop, acquisition started, sampling 10 s:
`cu_20261022_003813.csv`. The rig's log shows "Started with sampling 0.1 s"
then "ADC sampling set to 10.0" a second later — the web cannot set the
sampling while stopped, and a fresh program's combo is settings.yml's —
and the Kikusui LOST line ten seconds after the start, the supply being
off, with one `unavailable` row in its file. Control is left with the
session's identity from 127.0.0.1; a browser takes it back with Take over.

agent: claude

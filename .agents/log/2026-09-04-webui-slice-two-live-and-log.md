# 2026-09-04 — web view slice two, "Live", and the Lab tab's honest cards

Slice two of the design brief "ControlUnit on the LAN": the read-only Live
and Log tabs, on `master`, version 0.6.0. Built and walked off-rig on the
dummy hardware. The rig was looked at over SSH, read-only, and left alone:
it was acquiring on `~/work/aktest` at `4130906` the whole session (started
19:31, real hardware, 9 channels at 10 Hz, `ok` at `pihti:4187`). Nothing
here has been restarted onto the rig; that is queezz's step and directions
carries the exact commands.

## What shipped

- **The status record grew.** `RigStatus` now keeps the latest converted
  value per channel, a ring of the last two hours of samples (capped at
  200 000 rows however fast the rig samples), the last thousand message-log
  lines, the run's file name, start and sample count, and the setpoints the
  rig holds. The Qt main thread writes all of it from methods it already
  runs: `_adc_step` hands over each step's samples, converted and zero-
  adjusted exactly as the screen shows them; `log_message` hands over each
  line, tags stripped and this machine's data folder removed; `create_file`
  starts a run; the plasma, gas, gauge and sync setters record what they
  set; `abort_all_threads` now also clears the acquiring flag, so a run the
  workers end on their own no longer reads as acquiring. Every write is a
  few list appends behind a lock, and a failure in the web hand-over is
  printed and swallowed rather than allowed to stop the loop.
- **Three routes.** `/api/state` (values with units, setpoints, run facts,
  freshness), `/api/series?window=&points=` (thinned `[t, v]` pairs per
  channel, at most 600 points however long the window, the last point always
  kept), `/api/log?since=`. All `no-store`; none carries a path.
- **Live is home.** Five readouts in the rig's own pen colours, a plasma
  chart and a log-axis pressure chart on plain canvas, no library. Left
  rail: Window (the same eight choices as the Qt control dock), Channels,
  pressure axis log/lin; choices are remembered per browser and are
  conveniences, never facts. Right rail: this run (file name, started,
  samples, rate, hardware, plasma PID, gas flow presets) and the data chip —
  `live`, `stale` (no sample for five sampling periods, never less than two
  seconds), `idle` — explained once, beneath the chip.
- **Log** at `/log`: newest first, an order switch in the left rail, a Find
  and the log facts in the right. New lines are inserted; nothing already on
  the page is re-rendered.
- **Lab** at `/lab`, the tab bar shared by all three, Control still a
  marker. Neighbour addresses now come from `~/.controlunit/neighbours.yml`,
  which may also say `where` a service runs and how to `start` it there; a
  card with neither says nothing about starting. This is the fix for the
  two Lab defects queezz reported: the page no longer assumes every
  neighbour is started by `lab` on the machine reading it.

## The settings.yml trap

Slice one read neighbours from `~/.controlunit/settings.yml`. On the Pi that
file does not exist, and writing one holding only a `Neighbours:` block
would have crashed the next start: `readsettings.select_settings` treats a
local `settings.yml` as a complete replacement for the packaged one, looks
up `Settings Version` in it without catching `KeyError`, and if the version
matches replaces the whole configuration with the local file. The diagram
session's note of today, which hands over both addresses "for your
Neighbours block", would have led straight into this. Neighbours therefore
have their own small file; the old block is still read when the new file is
absent. Written into `docs/architecture/web-ui.md` and the module docstring.

## Smoke run and gates

Booted off-rig with `HOME` redirected to the session scratchpad, so the data
folder and log file landed there and `~/work/cudata` was never written.
Loading `/` and `/api/state` before acquisition answered 200 with `idle`;
after starting acquisition through the same slot the Qt switch calls, state
read `live` with an age of 0.22 s, the file `cu_20260904_195724.csv`, 27
samples after three seconds, and a 27-point series; after stopping, `idle`
again. This is also the only reproduction attempt for the reported logo
error: it did not reproduce.

Gates, from the repository root with the shared `hardware-dev` interpreter
and `QT_QPA_PLATFORM=offscreen`, exit codes captured, nothing piped:
`pytest -q` 71 passed (36 new); `mkdocs build --strict` clean, after the
docs requirements were installed into the environment, which had lost
them; `flake8 --select=E9,F63,F7,F82` clean.

## The Perimeter Walk

Delegated to a subagent on Opus (the Fable budget was low; queezz's call to
spend the other tier), against a scratch instance on `127.0.0.1:48937` with
`HOME` redirected to the scratchpad, two stand-in neighbours on 48938 and
48939, and the dummy ADC patched in the driver to return slow waves so the
charts move. All ten steps on all three tabs, measured in the real DOM.

- **Tab bar** measured 56.00 px on every tab at every size; every rail
  offset read 76 px (`56 + 20`) at rest and at 0/25/50/75/100 % of the
  scroll range, `.rail-left` and `.rail-right` alike, at 1280×1000 and
  1280×700, on Live, Log and Lab. Identical, not merely non-decreasing.
  Both rails fit their box at 700 px (`scrollHeight === clientHeight`,
  604 = 604), so no rail becomes a second page scrollbar.
- **Below the breakpoint** (900×700): one column; control rail above the
  reading column, context rail below; on Lab the empty control track is
  `display: none` with zero height. No horizontal scroll anywhere.
- **Stability under updates:** ten seconds of polling on Live, samples
  10509 → 10599, all five readouts changed value; the readout row, both
  canvases, both right-rail cards, the left rail and the document height
  held pixel-identical tops and heights.
- **Every tab pressed from inside every tab**, own tab included, from a
  scrolled page: twelve pressings, each landing at that tab's home at
  scroll 0. Control is a span with no `href`, absent from the interactive
  tree. Back and Forward across `/ → /log → /lab` landed where a reader
  expects, each at scroll 0. Reload restored the remembered window,
  channels and axis on Live and the order on Log, rails at 76 after each.
- **Slice checks:** plasma chart in `#8d3de3` with the emphasised end dot;
  four pressure pens drawn; log-axis labels `1e-5, 1e-4, 1e-3`; x axis in
  clock time; all eight Window buttons work and persist, `Full` showing the
  whole run; the Data chip `live` at 0.0–0.3 s; the file name `cu_….csv`
  with no path; the Log tab's savepath line carries the file name only;
  Find and Order work and survive reload; the poll duplicates nothing.
  Lab: the diagram card says "Runs on this Pi, as a system service." with
  its systemd line behind the toggle; the PIHTI Log card, whose config has
  no `where`/`start`, shows no start block at all; toggles hold `left: 854,
  width: 80` when the word changes.
- **Teaching count:** each data-state meaning renders once on Live, each
  neighbour-state meaning once on Lab. Structure alone: Live, pick a
  window; Log, type in Find; Lab, read the three chips and press Open.
- **Console and network:** no application errors on any tab; every one of
  500 buffered requests went to `127.0.0.1:48937`, nothing to the internet.

Two defects the walk found and fixed, both front-end only:

1. **Pressure readouts broke mid-number.** At 1280 px a readout card leaves
   94 px inside; the unit sat beside the value in a second track, and
   `overflow-wrap: anywhere` broke `3.11e-4` after the `e`: value height
   65 px (two lines) against 32 px for Ip, and the whole row grew the moment
   a value went exponential — the one thing the CSS promised never happens.
   Fixed in `controlunit.css`: the unit moves up beside the name, the value
   takes the full width on one line at 1.2 rem, stepping to 1 rem in the
   1200–1320 px band. Re-measured: every value one line at 29 px, cards a
   uniform 74 px, and the worst case `-5.00e-3` overflows by 0 px at 1200
   and 1280.
2. **The linear pressure axis mixed two notations** (`4.00e-4 … 1.00e-4`
   above a plain `0.000`), because the readout formatter was reused for
   tick labels. Fixed in `live.js` with a tick formatter that takes its
   decimals from the tick step: lin now reads `0.0000, 0.0001, …` and the
   plasma axis `0, 1, 2, 3`; log unchanged.

Teardown: the three launcher PIDs killed as trees (the Python 3.14 launcher
spawns the child that holds the port); afterwards 48937, 48938 and 48939
held no listener. Two of queezz's own listeners changed during the walk by
no action of the walk's: PIHTI Log on 4310 restarted under a new PID at
20:09, and 4319 stopped listening; the scratch instance bound only 48937
and probed only 48938/48939.

## Mail

- Posted a note to `code/pihti-log`, `20260904-23d80336-c85325`, answering
  their letter `20260904-ec356017-5a06b4`: shape accepted as proposed, port
  4187 and path `/api/health`, neighbours polled server-side. A note, since
  it ends the matter.
- Read and acted on the diagram session's note `20260904-925fa9a3-8a460b`
  (its address `pihti:5000` and the journal's `AK-office.local:4310`); they
  are in the neighbours file directions hands queezz. Notes have no receipt.

## Deployed to the Pi, short of the restart

On queezz's live instruction ("pull the master, I'll restart"), which
crosses the read-only-rig line `.agents/README.md` states: both checkouts,
`~/work/aktest` and `~/work/ControlUnit`, fast-forwarded to `b7537ac`, and
`~/.controlunit/neighbours.yml` written with the diagram at `pihti:5000` and
PIHTI Log at `AK-office.local:4310`. Checked from the Pi: the file parses
through the program's own reader, `AK-office.local` resolves to
10.249.254.17, and both neighbours answer their health route. The running
process, PID 27135 on 0.5.0, was not touched; it keeps acquiring until
queezz restarts it. PIHTI Log's health body carries `status` and `version`
but no `service` or `detail`, which our reader accepts as `ok` with an
empty sentence.

## Left

- Deploying 0.6.0 to the rig and writing its neighbours file: owner work,
  in directions with the commands.
- The `lab-cli` registry entry for the web port: ready to build, in
  directions.
- Slice three, browser control: waits on the owner decision.
- Not built from the brief's Live rail: an "Open in" card linking the
  diagram's plot of the current file, because the diagram's plot URL shape
  is not known here; and the pressure-axis "limits" choice, because
  autoscale was enough to read the charts and limits need inputs the rail
  law would have to house.

agent: claude fable 5.1

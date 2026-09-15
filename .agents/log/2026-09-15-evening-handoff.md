# Evening handoff — 4.19.5 on the rig, data pulled, analysis under way

For the session that continues from queezz's home. State at hand-off,
2026-09-15 evening (JST):

## Where things are

- master and the Pi's checkout (`~/work/aktest`) are at 4.19.5; the rig
  is running it, logging vacuum only at 0.1 Hz (`cu_20260915_192533.csv`)
  with every PSU turned off.
- Today's run files, Kikusui sidecars and the two logs are copied from
  the rig into the repository's git-ignored `data/rig/2026-09-15/`, which
  Dropbox carries to his home machine. The main plasma run is
  `cu_20260915_184419.csv` (18:44–19:25, 10 Hz) with its sidecar.
- Shipped today: 4.18.0 (Pu2 on channel 16), 4.18.1 (every gauge's
  settings pushed at Start), 4.18.2 (Ion gauges card by place; switch
  labels fit), 4.19.0 (panel-meter readouts from his sketch, cathode V/I
  cards, no plus sign), 4.19.1–4.19.5 (the rig's own screen: five then
  six values, three large, gauges mouse-sized on one row, Uc/Ic in the
  value browser, the Cathode dock's Kikusui lines gone).

## What is open, in `.agents/directions.md`

Every direction he gave today is recorded there with a design: the
status-line Sampling/QMS-sync controls and the rail (Window to the
charts' toolbar, Ion gauges card on its own, the chart with every curve
off keeping its axes, the OUTPUT lamp), the Monitor header strip, the
instrument-off toggles with their `<name>_off` columns, the IG_u/IG_d
typeset labels with the self-explaining file header, the cathode
current on the plasma chart, the PID rebuild packet (bumpless pickup,
selectable held quantity, tuning log) for later this week, the noise
study, the NAS backup, the letter to the Diagram. Two questions wait
for him: whether the OUTPUT lamp should press, and whether the time
window becomes drag-to-zoom.

## Under way when this was written

An analysis subagent is working on the pulled data: Hall Ip against the
supply's current, the noise of Ip/Bu/Bd/Pu at 10 Hz with a filter
recommendation per channel, plasma current against gas and cathode over
the 18:44 run, what "off" looks like in the files, and timing gaps. Its
deliverables are docs/diagnostics/2026-09-15-plasma-run-and-noise.md
with PNGs under docs/assets/diagnostics/2026-09-15/ and a vault note
under Experiments/Troubleshooting. If those files exist and the strict
docs build passes, the analysis landed; if not, rerun it from the packet
in this session's transcript or from the noise-study item in directions.

## Rules of the road he set today

- He wants finished things, one at a time, and subagents for the
  low-level work; this session coordinates and inspects.
- The rig's screen is for the person at the rig (few, large numbers);
  the WebUI gets everything.
- No plus sign on a number; the sign's width is reserved. Panel-meter
  cards: name/tag top-left, unit bottom-right, digits alone, "×10-"
  small and the exponent digit full height.
- The cathode's colour is #ff6b35 everywhere; nothing else wears it.

## The analysis landed

docs/diagnostics/2026-09-15-plasma-run-and-noise.md with six plots and
the vault note are written and committed; the findings and what each
asks of the code are a directions item ("Findings of the 2026-09-15
evening analysis"). Headlines: the ADC file's PresetV_* columns are dead
for a manual run; Ip carries two instrument lines (0.133 Hz and fs/3)
that a 3-sample boxcar and a 1 s mean remove; the plasma followed
filament power up the staircase; the discharge supply's own 1 A is not
logged anywhere; off states cannot be told from the analogue channels.

## Later the same night

Shipped 4.20.0: the cathode current Ic on the plasma chart on its own
right axis in the cathode's orange, and the chart's scale choice (auto,
0–1 A, 0–3 A). Inspected live on a scratch instance with a patched feed:
both pills, the orange right axis, 0–1 A pinning the left axis to a flat
line at 0.8 A. Builder's Perimeter Walk in its report: rails 76 px at
every depth at both heights; 390 and 320 without overflow, the legend
wrapping cleanly at 320. Gates: 598 pytest, 34 node, strict docs.

Rules and decisions of the night, all in AGENTS.md or directions: a
session stops, starts or sets anything on the rig only on his direct
word in the chat; the Kikusui link gets exactly one write, OUTP 0, as an
always-allowed safety press (the next build, after this one); the
instrument-off switches are ControlUnit's own and the Diagram reads
ControlUnit, consulting never overwriting; heuristics suggest, never
decide; Bd is meaningful above 1e-5 Torr; the instrument ranges are to
be confirmed from manuals and data; a Telegram reporter and cameras are
designed and wait on his bot and his hardware. The letter to the Diagram
is posted (20260915-ec9708ab-ef1123). The rig is still acquiring vacuum
at 0.1 Hz on 4.19.5; 4.20.0 waits on an idle rig to be pulled.

Then 4.21.0: the Kikusui output off/on press, the link's only two
writes, inspected here at the client (one gate in `_send`, identity
before a write, readback) and by its gates: 643 pytest, 41 node, strict
docs. The rig still acquires vacuum on 4.19.5; 4.20.0 and 4.21.0 wait on
an idle rig to be pulled.

agent: claude fable 5.1

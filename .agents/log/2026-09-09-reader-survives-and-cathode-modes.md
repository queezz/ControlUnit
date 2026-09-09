# The reader survives, and the cathode has two modes — 2026-09-09, evening

queezz came back from a diagnostic run with the preanode leaking current
(his PIHTI Log session `pl-session-ee5eaa131aaeebe0cf22`, read from the
vault and its API) and three asks: why "logging stopped", which he
suspected was the PID or the Kikusui DAC logic; a manual cathode mode
beside the PID; and how to hand the Kikusui back to its own knob.

## What the records said

Read over SSH from the rig, read-only, while it acquired at 0.1 Hz:

- Two runs died mid-row today: `cu_20260909_170319.csv` at 18:20:36 and
  `cu_20260909_182654.csv` at 18:27:27, 33 s after it started. No
  "Sensor thread ADC stopped" line in `controlunit.log` at either time —
  that line appears only at the deliberate stops (18:54:21). Both last
  rows carry the PID driving the cathode (`PresetV_cathode` 1881 and
  1930 mV, setpoint 0.5 A) and `Ip_c` jumping 1.3–2.4 A between samples
  a tenth of a second apart, which is the preanode dumping current.
- So the reader thread ended on an exception between two samples, the
  same shape as Mizuno-kun's four "data logging interrupted" of
  2026-08-19/20. The PID lives inside that thread: with it dead, "PID
  on" changed the setpoint and nothing computed an output. That is what
  read at the rig as "Kikusui doesn't reply" (18:33). Stop/Start built a
  fresh thread and both came back. Not the DAC, not the supply.
- The Pi itself is clean: `vcgencmd get_throttled` = `0x0` twelve days
  after boot (no under-voltage, no throttling, ever), 50 °C, no I²C or
  power line in the kernel journal. The fault is on the I²C wires that
  the ADC board and the cathode DAC share, under the arc. The launcher
  kept no stderr, so the exception's own words are not recorded; from
  4.11.0 they will be.

## What shipped, 4.11.0

- `devices/adc.py`: `collect_data` retries a failed read every 0.5 s
  until the board answers or the run is aborted, logs the first failure,
  repeats every 30 s, and logs the recovery with the gap; the per-period
  record/control step is guarded, dropping the rows in hand rather than
  ending the thread. `devices/adc_setter.py`: the conversion-ready poll
  is bounded (10 000 polls) and raises `TimeoutError` instead of spinning.
- `main.py`: a 2 s watchdog logs "Reader lost" once when no sample has
  arrived for twice the web view's stale line (never under 5 s), and
  "Reader back" with the gap when one does. Outputs are never touched
  from there (owner decision 2026-09-07, "Hold and alarm!").
- `scripts/run_controlunit.sh` tees stderr into
  `~/work/cudata/controlunit.stderr.log` with a dated start line.
- The cathode's two modes. Rig: the "Ip PID" dock is now **Cathode**
  with a PID row (amperes) and a Manual row (millivolts, 0–5000); the
  Settings dock's "Output voltage" row moved there. Setting either turns
  the other off and zeroes the other's box. Web: `POST /api/cathode`
  (`{"mv": 0..5000}` or `{"off": true}`), gated as `plasma`; the Control
  tab's group is **Cathode** with a PID | Manual mode switch remembered
  per browser that sends nothing, the manual row with ±1000/100/10/1
  draft steps sharing the gas rows' draft logic, and one feedback line
  read from the rig ("Held · PID 0.50 A" / "Held · manual 1900 mV" /
  "off"). Built by an Opus subagent from a packet; its perimeter walk
  is summarised below.
- `docs/hardware/cathode-control.md`: the two modes and the Kikusui's
  own knob (CF10 Ext. CC ON for the DAC, OFF for the front-panel knob;
  J1 pins 11/15; CF12 `Lo` = 0–5 V for 0–40 A), from the manual scans in
  the vault. AGENTS.md gained a Neighbours section (owner instruction:
  "see the pihti log" means the vault's journal file, not the web UI).

## Verification

- `pytest -q`: 501 passed (251 before the web slice; 15 new in
  `tests/test_reader_survives.py`, `test_web_commands.py`,
  `test_qt_acquisition.py`). `node --test` on the three `.cjs` files:
  15 pass. `mkdocs build --strict` clean.
- Web perimeter walk (subagent, scratch instance on 127.0.0.1:4199 with
  HOME redirected, dummy hardware, port freed after): gate-closed state
  disables every new control through the existing `.sets` blanket; mode
  switch issues zero requests and survives reload; steps clamp 0..5000
  and never send; Set/Off bodies are exactly `{"mv":1900}` and
  `{"off":true}`; both rails at 76 px at every scroll depth at 1280×1000
  and 1280×700; no overflow at 390 px; anchors, tabs and Escape as
  before. The gate-open half rests on the cookbook's synthetic state
  (Qt was offscreen), so the live `{"mv"}` path end-to-end is covered by
  `test_web_commands.py` and not by a browser.
- Not run on hardware. The rig is at 4.8.6 and was acquiring all
  evening; nothing was pulled or restarted.

## Left open

- Alarm, Restart-reader press, thermocouple: still in directions.
- The I²C hardware side (grounding of the arc, shielding of the two
  boards' leads) is his; recorded in directions with the measurements.
- Two pre-existing web nits the subagent noticed: `location.reload()`
  on a deep link does not scroll the rail to the section, and "Read Ip"
  prints "— A" for a null value.

Local commit only; push and the rig's pull on queezz's word.

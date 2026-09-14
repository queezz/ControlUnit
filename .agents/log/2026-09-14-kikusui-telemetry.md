# 2026-09-14 — Run diagnosis and read-only Kikusui recording

## Owner decisions

The preanode short is solved by his physical repair. The student PID attempted
ignition plus regulation; its replacement should engage on an established
discharge and take over the held filament drive smoothly. First collect
Kikusui V/I during ordinary manual discharges and bakes, including connection
reliability, before PID changes or filament-condition warning thresholds.
LAN loss in this recording-only stage leaves manual control unchanged.
Recorded in AGENTS.md, directions and the PIHTI troubleshooting note.

## Evidence

Read September 14 journal, completed cu_20260914_173253.csv and Pi logs/source.
49,295 complete rows; two automatic ADC recoveries at 18:31:35 and 18:36:05.
Discharge-window cadence averages 0.100043 s, max 0.182482 s. PID handover
requests 5500 mV at 18:50:04; offline replay reproduces elapsed-manual-time
integral saturation plus the out-of-limit 1000 mV offset. DAC clamps to 4095.
Off-plasma Ip zero is about -0.326 A; manual cathode commands are missing from
ADC CSV metadata. Details and source hash: docs/diagnostics/2026-09-14-run-and-kikusui.md.
No PID fix was made; no filament-thinning conclusion is possible from this run.

## 4.15.0 implementation

Optional machine-local kikusui.yml, independently timed read-only recorder,
paired kikusui_*.csv with source/version/cadence metadata, requested manual
command and PID target, measured V/I, output-enable state, identity, poll time
and explicit failure rows. One warning per outage; recovery queries only,
with identity checks; no last-good value reused. Numeric address and total
transaction deadline bound LAN waits. A connected read and waits are interrupted
at Stop, after the hardware teardown. File errors stop only this recorder.
Off-rig dummy mode cannot contact a real supply and labels all synthetic rows.

ADC file schema and existing Ci/Cv readouts remain unchanged. This first stage
is recording only; telemetry live display/API and retirement of the unwired
analog placeholders remain in directions. This preserves independent timing
and avoids silently changing the meaning of historical columns.

## Verification

- Full pytest gate: 563 passed in 24.27 s, QT_QPA_PLATFORM=offscreen,
  bytecode/cache disabled and a fresh external basetemp. Earlier full run
  also passed 563. New tests cover fragmented replies, invalid measurements,
  bounded trickle, disconnect/reconnect/identity change, missing rows,
  overwrite refusal, interrupting a real blocked socket, and Qt lifecycle.
- Strict MkDocs build passed with output outside Dropbox.
- Ruff installed into the shared hardware-dev environment for the required
  gate. New logger/tests have no findings. Whole controlunit/tests scan has
  271 legacy findings; changed existing main.py and test_qt_acquisition.py
  were compared against HEAD using the same Ruff configuration and add none
  (17 and 3 findings respectively, unchanged). No unrelated lint sweep.
- git diff --check passed. No web layout or architecture-diagram modification.
- Finished recorder against the actual output-off PSU: six successful polls,
  output_on=0 throughout, whole-poll times 5.985–11.012 ms, worker stopped.
  Only *IDN?, MEAS:VOLT?, MEAS:CURR?, OUTP? are permitted on its transport.
  Hardware outage testing was simulated, never induced on the apparatus.

## Coordination and handoff

Posted the owner's explicit snapshot request to code/pihti-log as
20260914-86630ead-525f3f: attach all known ControlUnit state like its existing
vacuum-diagram capture, durable data table and optional picture, possible
labelled averaging window, source/freshness and unavailable fields. Explained
that new Kikusui logging is initially a sidecar and not a live API promise.

Saved and indexed the lab note directly in the vault, without rewriting the
journal. Local master release only: no push, Pi pull, restart, configuration
write or output command. The Pi was still acquiring slowly when inspected.
Enable machine-local configuration and deploy on the owner's push/restart
schedule before claiming live experiment logging. Setup is in
docs/hardware/kikusui-lan.md.

agent: codex

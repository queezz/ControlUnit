# Hall supply reference correction — 2026-09-30

Queezz connected the Hall supply to the neighbouring ADC terminal and asked
for it to improve plasma-current readings, explicitly not for display.
He authorized stopping/restarting the rig if needed. The 2026-09-19 Opus
handoff and diagnostic identify Ip as channel 0 and its neighbour as 1.

4.22.0 adds Vhall on channel 1, immediately after Ip in scan order, at
10 V range to avoid clipping a nominal 5 V supply at 5.0176 V. Ip_c is
25 * (Ip / Vhall - 0.5) A, using settings for scale, nominal supply and
zero ratio. The provisional 5 A/V scale remains uncalibrated. Raw voltages
are retained and the CSV header gives the formula. No voltage card/curve
was added. Existing Ip readouts and PID consume the corrected current.
Missing, non-finite or outside-4..6-V references yield NaN current, with
loss/recovery messages; PID does not issue a command from invalid current.
Older settings without a reference retain the legacy fixed-zero formula.
Settings schema is 1.5. Filters/longer zero windows remain separate work.

Read-only rig inspection: 4.19.5, commit e141e3b, clean checkout; acquisition
at 1 Hz, operating state measuring, no live commanded outputs, Remote off.
No ~/.controlunit/settings.yml. Kikusui telemetry was unavailable (timeout).
Sandbox networking/interpreter access needed escalation; both worked after
approval. No rig process or outputs have been changed. Actual channel-1
voltage remains to be verified with the sole ADC reader stopped. Deployment
requires the owner's explicit push instruction under AGENTS.md; do not
bypass that by copying an uncommitted patch onto the running rig.

Validation: paired-supply tests cover varying supply and current, raw-row
preservation, invalid/missing reference, loss/recovery and legacy settings.
Full pytest: 668 passed; strict MkDocs build passed (output in machine TEMP). Old reader
fixtures now provide a valid reference instead of 0.5 V on every channel.
The pre-existing untracked controlunit.egg-info directory was left alone.

agent: codex
# Full Kikusui WebUI readouts — 4.17.0

Owner: "Webui should get this too. Proper values, not small side text."

Added two full readout cards for LAN-measured voltage/current, in Operate,
Observe and Monitor. Small/big sizing applies; the Kikusui group folds
independently and remembers its state. Its one-line summary shows status
when open and compact V/I when folded, explicitly marked SIM for dummy data.
The manual cathode row no longer calls the unwired analog Cv a measurement.
ADC columns and actuator behavior are unchanged.

The GUI publishes a locked recorder snapshot into RigStatus every 500 ms.
/api/state carries a separate kikusui object. It ages even if Qt stops
publishing; stale/unavailable/stopped measurements are omitted. Browser
expiry also clears numbers if a request hangs, and a failed request says
ControlUnit unreachable. File exposure is a basename, not a home directory.

Validation: 566 pytest tests passed (26.22 s), 31 JavaScript behavior tests
passed, strict MkDocs build passed, diff whitespace clean. Full ruff reports
271 existing findings; changed-file comparison adds none. Tests cover Qt
publication, API freshness independent of ADC/Qt refresh, defensive copies,
missing values, browser timeout/recovery and rejection of the analog alias.

Perimeter Walk completed using a lab-managed simulated preview on loopback
48937, with scratch LAB_CONFIG/RUNTIME/LOG roots and HOME outside Dropbox.
Browser DOM access was established before implementation.

1. Pressed every top navigation link (ControlUnit, Log, Lab), including the
   current/home tab; destinations open correctly.
2. Exercised all links on the changed Live surface: those tabs and Access.
3. Access anchor landed at 132.55 px, below the 56 px fixed bar. The new
   telemetry group introduces no fragment anchors.
4. Browser Back/Forward restored Log/Lab, Access and Observe/Monitor states.
5. Reloaded the mode deep link and folded panel; preferences restored.
   Normal reload after preview restart requested all assets at v4.17.0.
6. Checked desktop 1280x1000 and 1280x700, phones 390x844 and 320x700.
7. Both desktop rails stayed at top 76 px through scroll; final 700 px
   sampling included y=0,537,781. No horizontal overflow on either phone.
8. Used the page for over two minutes: reading, sizing, folding, modes,
   scroll, navigation, and simulated outage/recovery/publisher stall.
9. Start/Stop and manual controls remain the operator's entry/next run;
   telemetry is two numerical cards with one status label, no explanations
   repeated beside values. Dummy data is labelled, including when folded.
10. Final DOM verified open status visible, a stable 36 px folded/open phone
    header, and no browser errors before intentional server shutdown.

After stopping the preview the browser showed ControlUnit unreachable and
both measurements as dashes. lab stop killed the tracked process tree and
48937 was confirmed free; the owner's local 4187 listener remained absent.
No rig changes, push or deployment. Rig testing/configuration remain pending
an idle/closed application and the owner's word to push, as before.

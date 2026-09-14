# Kikusui GUI readout and rig preparation

Owner asked whether logging was wired to the GUI and requested a rig test.
4.15.0 already starts/stops its sidecar with acquisition; 4.16.0 adds a
compact measured V/I row and recording/output status below manual cathode
controls. No web UI changes. A locked snapshot is published only after CSV
flush. Failed, stale and stopped telemetry clears the numbers; simulated
measurements are labelled. Shutdown still turns off hardware first.

Six read-only polls from the Pi to the supply all succeeded,
2.772–3.266 ms per V/I/output poll, output disabled throughout. No instrument
setters or acquisition changes were sent. This is connectivity evidence,
not a discharge reliability test.

The Pi was still acquiring 9 channels at 0.1 Hz on 4.14.1, checkout 32959f2,
with no machine-local kikusui.yml. Do not pull or restart that run. Push is
still awaiting the owner's word; restart remains theirs. Configure the
actual supply address outside git at deployment, then verify the paired CSV
and displayed readings during the owner's manual discharge/bake.

Offscreen render with explicitly loaded Arial confirmed the Cathode panel
fits its existing control width with the compact readout beneath it.

Validation: 565 tests passed (24.25 s); strict MkDocs build passed; telemetry and dock lint clean, no new findings in legacy files; git diff --check passed.

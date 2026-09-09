# Compact reading header — 2026-09-09

Implemented 4.8.6: status, command feedback and readout sizing share a wrapping header immediately above the readings. Empty feedback and output notes reserve no space. Readout sizing stays beside the readings.

Validation: 481 pytest tests passed and strict MkDocs build passed. Dummy browser preview at 1280 px showed a 28.6 px header and readouts at y=112.6. At 700 px, queued baseline feedback fit alongside status and sizing; at 390 px the header wrapped without horizontal overflow. Monitor retained its controls. No real hardware commands were sent.

Local commit only; deployment remains pending owner request.

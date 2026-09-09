# Vessel pressure overlays — 2026-09-09

Added 4.9.0 pressure grouping beside the pressure plots: By gauge preserves Pu/Pd and Bu/Bd; By vessel pairs Pu/Bu and Pd/Bd. Existing legend and baseline buttons move with their channel, retaining handlers and visibility. Each vessel has its own remembered log/linear setting, separate from gauge-group settings. Actual signed readings and baseline residuals are unchanged; there is no curve alignment or normalization.

Validation: 481 pytest tests, five Node behavior tests, strict documentation build, and diff whitespace check passed. Synthetic browser preview verified both pairs drawing, negative values excluded on log, grouping round-trip, baseline placement, reload persistence, Observe and Monitor, and 700 px layout without horizontal overflow. No real rig operations. A complete unrelated navigation perimeter walk was not repeated for this change.

Committed locally; push and rig pull await owner request.

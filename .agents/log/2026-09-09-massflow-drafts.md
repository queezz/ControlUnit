# Mass-flow draft controls — 2026-09-09

Added 4.10.0 large typed draft inputs and one-click ±1000/100/10/1 mV adjustments. Click steps change only the draft; Set validates and sends it. Zero keeps its immediate zero-command behavior. Applied setpoints are prominent red figures beside larger measured values. Inputs initialize from rig setpoints and polls preserve drafts. Step bounds use the existing server-declared limit. Existing remote/acquisition/access gates cover all new buttons.

Verification: 481 pytest tests passed; Node gas test covers all step sizes, no command while editing, integer/range validation, clamp boundaries, poll preservation and explicit Set/Zero. Strict docs passed. Synthetic browser check: 3500 typed plus 100 queued 3600 on Set, while Applied remained the rig's 0 mV; 390 px viewport had no horizontal overflow. No hardware operations. Full unrelated navigation perimeter walk not repeated.

Local commit only; deployment pending owner request.

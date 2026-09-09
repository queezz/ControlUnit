# Monitor space and controls — 4.8.5

Owner asked to remove Polling/Poll duplication, make mode switches easier
to find, use Monitor width, default its readouts big, and expose Window and
Median. Switch now uses a fixed header position (desktop y6, phone y58),
independent of changing column layout. Monitor uses full width, computes
available canvas height shared among active panels, and preserves a minimum
140px canvas on short displays. Window/Median move as the same DOM controls,
with markers restoring their original positions outside Monitor. Monitor
size has an independent saved preference defaulting big.

481 pytest, 4 Node behavior tests and strict docs passed. Browser measured
2145px content at 2200px viewport and verified plot expansion from 141px to
282px with one remaining active panel at 1600x1000. Window/Median remained
selected and unique across modes. Switch positions identical across modes:
1600px desktop x1262.5/y6, 390px phone x12/y58; no phone horizontal overflow.
Monitor small choice survived reload. Final additional navigation sweep tool
timed out, so no completion claim for that sweep. Scratch preview lab PID
25380, port48964, stopped after checks. Not pushed or deployed.

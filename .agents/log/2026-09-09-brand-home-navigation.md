# Brand as home — 4.8.4

Removed duplicate Live navigation; ControlUnit links home and carries the
active-page indication. Browser checked all three destinations. The prior
turn's two full test attempts crashed natively in Qt paintEvent during an
acquisition test. Deployment retry passed all 481 tests without code changes;
4 Node behavior tests and strict MkDocs also passed. The crash remains
intermittent, not diagnosed or fixed by this navigation change.

Owner requested deployment. Rig health port was down, SSH confirmed no
controlunit.main process and a clean checkout at 51fb889. Release includes
stationary mode switch, idle gauge preparation and Baratron residual/log
corrections. Fullscreen space utilization was discussed but not implemented.

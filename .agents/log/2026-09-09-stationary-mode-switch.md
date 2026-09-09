# Stationary mode switch — 4.8.1

Owner reported the mode trio moving as the view changes. Anchored the
single switch at viewport bottom center, fixed each button to 80px, and
separated Monitor actions from its box. Added bottom space so the final
content can scroll clear of the switch. No mode logic changed.

Measured all three buttons across Operate/Observe/Monitor/Operate:
1280x700: x 508.5/592.5/676.5, y 647.359375.
1280x1000: identical x, y 947.359375.
390x844: x 63.5/147.5/231.5, y 791.359375.
Every button was 80x34.640625 in every mode. Scrolling kept the dock fixed.
Verified reload/history, Monitor drawer and every top tab; no console
errors. 480 pytest tests and strict MkDocs passed. Preview listener 38512
was child of lab PID 39408 and stopped after review. Not pushed/deployed.

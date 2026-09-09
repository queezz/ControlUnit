# Unified Live — 4.8.0

User accepted one Live surface with Operate, Observe and Monitor beside
readouts. Removed the separate Control tab/template. Both root and legacy
/control render the same page; /control opens Operate, old normal-mode
bookmarks open Observe. Browser mode changes preserve the existing DOM,
plot history and display choices. Observe/Monitor hide hardware setters;
Monitor has a Display drawer. No mode transition posts a command.

Validation: 480 pytest tests, 3 Node behavior tests, strict MkDocs build.
Browser exercised modes, curve/size preferences, Monitor drawer, Back and
Forward, deep reload, legacy anchors, all three tabs and the brand link.
Desktop rail offsets remained 76px at rest/middle/end at 700 and 1000
heights. All anchor headings landed below the 56px chrome. Phone Observe
and Monitor fit without horizontal overflow; Remote-off gates remained
closed after switching modes. No console errors. Preview PID 22060 parent
of listener 5016, isolated loopback port 48964; stopped after verification.
No push or rig deployment performed.

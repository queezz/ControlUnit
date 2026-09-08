# 2026-09-09 — Control beside live trends

Owner asked to go bigger after accepting the small 4.6.1 cleanup. 4.7.0
places operation controls on the left, shared Live readouts/charts in the
center, and access/display/run settings on the right. Gas held/measured
feedback is directly below its input; plasma feedback follows its setter.
Gauge settings expand; baseline zeroing stays directly available. Access
starts open if a name, word, Remote switch or ownership needs attention and
opens on a newly blocked gate. The Access link opens its section, including
on deep-link reload. Stop confirmation and all queue/rig gates remain.

Live and Control share `_live_readings.html` and live.js. Live owns the
periodic state polling; Control consumes its state event and asks that same
poller to refresh after commands. Fast mode therefore accelerates both.
No acquisition, Qt thread, hardware or command-queue change.

Bu fix: its flat pill explicitly restores it without hiding the moving
curve. Off/on also restores it. Overrides survive browser preferences;
presets reset them. Nonpositive log samples remain absent. Two Node tests
exercise production drawing decisions and click handlers (not a duplicate
algorithm), including refresh, remembered choices, off/on, presets and log
handling. Run `node --test tests/web_live_behavior.cjs` alongside pytest.

Validation: 478 Python tests and two Node behavioral tests pass; strict
MkDocs and diff whitespace checks pass. Python count decreased by one
because the two obsolete separate-faceplate layout tests became one fused
layout test. Tests still verify command gates, control roles and facts.

Browser verification used the existing isolated synthetic fixture under
CreatorTemp/fleet-scratch-controlunit-web-polish-20260908, no hardware drain
or neighbour probes. DOM preflight passed. Bu was restored, redrawn,
reloaded and toggled off/on. Remote-off, idle and another-owner gating were
checked; fields remained editable and Stop all outputs remained available.
A draft H2 value survived polling and the access shortcut. All six existing
section targets landed below the 56px bar at 1280x700 and 1280x1000.
Measured rail tops stayed 76px across scroll samples at both heights.
Routine controls and collapsed access fit 604px rails at 1280x700. Expanding
settings permits rail scrolling. At 390x844 and 1024x768 there was no
horizontal overflow in readouts or output feedback.

Native browser navigation was more reliable than immediate batched
Playwright navigation in this session; Log/Lab/Control/Live were reached,
and Log history plus the access deep link/reload were checked. Screenshot
capture repeatedly failed with `Page.captureScreenshot` timeouts, including
full-page capture. Visual screenshot review remains incomplete; the numeric
DOM checks are not claimed as a replacement. The owner should review the
actual layout before deployment. No push or Pi changes in this session.

Final spacing check: baseline group bottom 592.78px, Stop all outputs card
top 611.78px at 1280x700, both rails top 76px and neither overflowing in the
routine view. Browser error/warning log was empty. Preview process tree
(PID 15076) was stopped and the listening port/process absence verified;
temporary browser tab closed and viewport reset. Fixture retained outside
Dropbox for follow-up review.

agent: codex

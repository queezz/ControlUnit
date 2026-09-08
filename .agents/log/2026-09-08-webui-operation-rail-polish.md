# 2026-09-08 — WebUI operation rail polish

Owner authorized a small pass inside the existing tabs before a larger
Control/Live fusion. Version 4.6.1 moves pressure-axis switches beside their
own curve pills, gives Start/Stop prominent rail positions, and puts Remote,
ownership, operator name and lab word in the rail. Stop all outputs remains
separate and always available, with quieter outline styling. Main setter
groups use plain names. Existing handlers and hardware behavior are unchanged.

Big/small readouts, smoothing including readouts, presets, Monitor and useful
curve suppression remain intact. Bu's inability to return was reproduced
in synthetic data: flat Bu -> off -> flat while Bd moves. That is a separate
open bug, not evidence that suppression should be removed.

Validation: 479 tests pass; strict MkDocs build and git diff --check pass.
Browser preview used a standalone synthetic RigStatus with no hardware
command drain or neighbour probes, served only on 127.0.0.1:48964 through a
scratch lab-cli registry. Tested all four tabs at 1280x700 and 1280x1000;
rails stayed at y=76 across scroll positions. At 1280x700 both Control rails
fit their 604px available height, including word/name and Stop all outputs.
Idle, remote-off, another-owner and allowed scenarios retained identical
control positions and correct gating. Name and word stayed editable while
setting was gated. Draft H2 input survived polling and an anchor click.
Stop displayed its existing acquisition/output confirmation.

Live scale, median and size choices persisted on reload. Monitor history,
reload, controls drawer and Escape were exercised. Control anchors were
clicked; the relocated Acting-as anchor reached sec-who. Desktop 1440x900
was visually inspected. Control and Live at 390x844 had no horizontal
overflow; both chart scale groups stayed within the viewport.

Browser automation intermittently timed out during batched hash navigation
and the final Control back/forward check (CDP focus emulation); no claim of a
completed final Control history/console check. The successful Monitor history
check preceded those tooling failures. No Pi access or deployment. The
synthetic preview and its process tree are stopped at handoff.

Scratch: CreatorTemp/fleet-scratch-controlunit-web-polish-20260908, retained
for reproducing Bu and reviewing validation output. No push.

agent: codex

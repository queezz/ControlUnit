# 2026-09-08 — Repair the Python workflow's checkout import

queezz reported the failed GitHub email for `d64ff61` and asked to fix the
old workflow. The Python application run failed during collection, before
tests ran: `tests/test_adc_average.py` could not import `controlunit`.

Evidence: run https://github.com/queezz/ControlUnit/actions/runs/34204608009,
job 101991071924. Dependency installation and both lint commands passed;
`pytest -q` exited 2 with `ModuleNotFoundError: No module named 'controlunit'`.
The separate MkDocs Pages run 34204607818 succeeded. This workflow does not
deploy to the Pi.

Changed `.github/workflows/pythonapp.yml` to use `python -m pytest -q`,
matching AGENTS.md and placing the checkout root on the import path. The
pytest install uses the same interpreter, and the test step explicitly sets
`QT_QPA_PLATFORM=offscreen`. No runtime, dependency, version or Pages change.
Fleet RULES.md section 5 describes a fleet without test CI; this is a repair
of ControlUnit's already-existing workflow requested by queezz, not a new CI
rollout.

Validation in the shared hardware-dev environment: 479 tests passed in
20.73 seconds, exit 0; strict MkDocs build passed, exit 0. Pytest ran with
the cache provider disabled, bytecode disabled and a fresh external base
directory; docs output also went outside Dropbox. No Linux runner was run
locally. The next GitHub run remains the hosted verification.

Committed on master at queezz's request. No push, Pi access, service start
or restart.

## UI clarification carried forward

queezz clarified that Bu vanishes and its curve pill cannot restore it:
this is a bug, not a request to remove curve suppression. Large readouts,
smoothing (including readouts), the curve pills and useful suppression are
intentional features to preserve. Shared pressure axes can conceal dynamics
across orders of magnitude; Baratron offsets cross zero, and the Hall sensor
without plasma is noisy. The earlier directions proposal to always draw
every selected curve is not an accepted design. No plotting change made in
this workflow repair; reproduce the Bu failure before choosing its fix.

agent: codex

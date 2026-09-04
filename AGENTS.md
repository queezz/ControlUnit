# AGENTS.md

Orientation for agents working in this repository.

ControlUnit is the Raspberry Pi hardware node for live plasma-lab acquisition
and closed-loop gas and plasma-current control. It is launched through the
sibling `lab-cli` registry as `lab controlunit`; fleet discovery and project
boundaries remain in the sibling `fleet` repository.

## Environment

The operational target is the Raspberry Pi. For off-device tests,
documentation, and dummy-hardware development, share the fleet's single
hardware development environment outside Dropbox; do not create a dedicated
ControlUnit venv:

- Windows: `~/.venvs/hardware-dev/Scripts/python.exe`
- macOS/Linux: `~/.venvs/hardware-dev/bin/python`

Bare `python` on the Windows machine can resolve to Inkscape's interpreter, so
always use the explicit venv path. `pyproject.toml` declares the package and
its version (the same number as `controlunit/_version.py`; a test holds them
equal, and the fleet reads the declared one). The rig installs nothing: it
runs from its checkout, with its packages from apt. Off-rig, install the
declared dependencies and run from the repository root:

```powershell
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-docs.txt pytest
```

Before every commit:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -m pytest -q
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -m mkdocs build --strict
```

## Running on the rig

The Raspberry Pi starts the control unit with `scripts/run_controlunit.sh`,
which `~/Desktop/aktest.sh` calls. The launcher lives in the repository rather
than only on the Pi's desktop, so a change to how the rig starts is reviewed
like any other change, and so it travels with the code it starts.

The web view stays off unless `--web` is passed, and the launcher passes it.
When on, it answers on the lab network by default at `http://pihti:4187/`
(owner decision 2026-09-04, "the whole point is LAN": the rig is one machine
and the view is read from a laptop or a phone); `--host 127.0.0.1` narrows a
run to the Pi itself. The view is read-only either way - it reads a small
status record the main thread writes, and never touches a worker.

## Read first

1. [README.md](README.md) — current hardware, runtime status, and documentation.
2. `../fleet/RULES.md` — fleet-wide commit, environment, and gate conventions.
3. `../fleet/MAP.md` — sibling projects and hardware boundaries.
4. [docs/Archaeology.md](docs/Archaeology.md) — codebase history and design record.
5. [docs/architecture/qt-threading.md](docs/architecture/qt-threading.md) — runtime ownership and shutdown rules.

## Invariants

- `controlunit/settings.yml` is the canonical channel map and conversion registry.
- Keep hardware libraries behind the existing dummy-device boundary so the GUI
  still boots off-rig on Windows and macOS.
- Preserve Qt thread ownership and the hardware-first shutdown order documented
  under `docs/architecture/`.
- Do not put machine-specific paths, credentials, virtual environments, or build
  caches in this Dropbox-synced repository.
- Regenerate `docs/assets/graphviz/runtime_architecture.svg` from its DOT source
  with `scripts/build_graphviz.py` whenever the architecture diagram changes.

Commit directly to `master` when asked, stage paths deliberately, and end every
agent-written commit with the bare trailer `agent: <the agent that wrote it>`.
Do not add `Co-Authored-By` trailers or create tags unless the owner asks.

Pushing is not gated in this repository (owner decision 2026-09-04). A session
that has run the gates may push its own commits, `master` included. Fleet's
`RULES.md` §1 reserves pushes for queezz so that no session puts work on a
remote he has not seen; that still holds in the fleet repository, and he named
it an unnecessary gate here. Tags remain his.

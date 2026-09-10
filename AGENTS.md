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
run to the Pi itself. The view reads a small status record the main thread
writes and never touches a worker; what a browser may set goes through a
queue the main thread drains, behind the Remote switch on the rig's screen.

### Before pulling a new version onto the Pi

A pull and a restart take the rig away from whoever is using it, and "not
acquiring" was never the same as "safe". On 2026-08-19 the ADC reader died
mid-run and the plasma kept going, because the cathode DAC held the voltage
it had been given: nothing was being recorded and the apparatus was still
driven. So a session reads the rig's own operating state before it pulls:

```powershell
curl http://pihti:4187/api/health
```

The `detail` says one of three things. `idle, not recording` is stopped, and
a pull may go ahead. `acquiring …` is a run in progress: do not pull, and
say so — the restart is queezz's to schedule. Anything containing `outputs
live:` means gas or the cathode is holding something, recording or not:
**refuse the pull**, name the outputs the report listed, and leave the rig
alone until a person has turned them off at the rig or from the Control tab.
The same three states are the left pill at the head of the Live tab, and
`/api/state` carries them as `operating.state` and `operating.outputs`.

The Control tab offers names from the lab's roster when the Pi holds a copy
of it at `~/.controlunit/operators.json`. Names are people and never enter
git; `scripts/push_roster.ps1` (or `.sh`) copies the vault's file to the Pi,
and is run again whenever the roster changes. Beside it, `~/.controlunit/fence.txt`
may hold one line, the lab's word, which a browser types once before it may
set anything — a fence one may walk over, never anybody's password, and
absent on every machine that has not been given one.

## Neighbours, and where their records are read

The rig's siblings are read from their files, not their web pages (owner
instruction 2026-09-09, "this repo needs to know its neighbours"; the web
views are for people, and an agent has no need of one):

- **PIHTI Log** is the lab journal. Its record is the Obsidian vault in
  Dropbox beside the code, `Dropbox/Obsidian/pihti`: one Markdown file a
  day at `Journal/YYYY/MM/YYYY-MM-DD.md`, with attachments under
  `Attachments/PIHTI Log/` and `media/`. When queezz says "see the pihti
  log", open that day's file. The served view at `http://<office PC>:4310/`
  is what people read and write; its `/api/sessions/<id>` answers a session
  link as JSON when the vault is not at hand. Hardware notes live in the
  same vault under `Hardware/` — the Kikusui supply's manual pages are
  scans in `Hardware/Equipment/Kikusui Power Supplies.md`.
- **The explainers** (`20-Code/2025-explaners`, published as aklab-howto)
  carry the lab's own hardware write-ups under `docs/hardware/`, including
  the control unit's boards and the Kikusui page.
- **PIHTI Diagram** (`2024-interactive-diagram`) is the vacuum-state
  diagram the journal's captures come from.

Fleet is still the discovery surface for anything else: `fleet find`,
`fleet info`.

**The lab record is written directly (owner ruling 2026-09-09).** A
session here writes the vault when the work leaves something the lab
should keep — a diagnosis, a procedure, a change in how the rig is
driven — as a new note under the folder its kind lives in
(`Experiments/Troubleshooting/`, `Software/`, `Hardware/`) and a line in
the hub that indexes it, appending, never rewriting a sentence of his.
This is not a crossing of the fleet's "a letter, never a file" rule and
no warning is owed: in his words, ControlUnit, PIHTI Log and the Diagram
"are three sides of one thing, my plasma", the vault is not a git
repository with gates to dodge, and "starting a commander for this write
is a waste". The journal's own day file stays his to write. Code in a
sibling's *repository* is still a letter.

## Read first

1. [README.md](README.md) — current hardware, runtime status, and documentation.
2. `../fleet/RULES.md` — fleet-wide commit, environment, and gate conventions.
3. `../fleet/MAP.md` — sibling projects and hardware boundaries.
4. [docs/Archaeology.md](docs/Archaeology.md) — codebase history and design record.
5. [docs/architecture/qt-threading.md](docs/architecture/qt-threading.md) — runtime ownership and shutdown rules.

## Invariants

- WebUI is a control panel, not a generic rail layout (owner decision
  2026-09-09). Keep controls beside what they affect when that improves
  operation: readout small/big belongs beside the readouts on Control and
  Live. This takes precedence over fleet's generic control-in-rail rule.

- `controlunit/settings.yml` is the canonical channel map and conversion registry.
- Keep hardware libraries behind the existing dummy-device boundary so the GUI
  still boots off-rig on Windows and macOS.
- Preserve Qt thread ownership and the hardware-first shutdown order documented
  under `docs/architecture/`.
- Do not put machine-specific paths, credentials, virtual environments, or build
  caches in this Dropbox-synced repository.
- Regenerate `docs/assets/graphviz/runtime_architecture.svg` from its DOT source
  with `scripts/build_graphviz.py` whenever the architecture diagram changes.

Commit completed, validated work directly to `master` before handing back; do
not wait for a separate commit request or leave a dirty tree for the next
session (owner clarification 2026-09-11). Stage paths deliberately, and end
every agent-written commit with the bare trailer `agent: <the agent that wrote it>`.
Do not add `Co-Authored-By` trailers or create tags unless the owner asks.

A session pushes `master` when queezz says so in the chat, and not on its
own (owner decision 2026-09-07, narrowing his 2026-09-04 ruling that pushes
were not gated here; he pushed 4.1.0 himself and said "you can push when I
tell you to"). Fleet's `RULES.md` §1 reserves pushes for queezz so that no
session puts work on a remote he has not seen; his word in the chat is that
seeing. Tags remain his. Pulling to the rig's idle checkout is a session's,
as `.agents/README.md` says.

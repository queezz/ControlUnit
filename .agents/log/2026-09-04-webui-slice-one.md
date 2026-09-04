# 2026-09-04 — web view slice one, "Alive", on branch `webui`

Slice one of the design brief "ControlUnit on the LAN" (2026-09-04). Built on
a new branch `webui` off `master`, not pushed, not tagged, master untouched.
The rig has uncommitted work in the isolated-DAC (MCP4725) code, so nothing
under `controlunit/devices/`, `controlunit/settings.yml`, `readsettings.py` or
the Qt docks was opened, and the merge should be trivial.

## What shipped

- `python -m controlunit.main --web [--host] [--port]` starts a Flask app on a
  daemon thread inside the Qt process. Werkzeug, threaded. Default host
  `127.0.0.1`, default port 4187. Without `--web` the program behaves exactly
  as before, and the Flask import never happens.
- `GET /api/health` returns `{service, version, status, detail}` and nothing
  else. `ok` only while acquisition is running on real hardware; `degraded`
  when acquisition is stopped or the dummy stubs are loaded. The detail
  sentence reads like "acquiring 9 channels at 10 Hz" or "idle, dummy
  hardware". No path, address or secret appears in the body.
- `GET /api/neighbours` returns this service plus PIHTI Log and the PIHTI
  diagram, each with a name, an address for display, a state, a version and a
  detail sentence. The two neighbours are asked from this machine's own side
  with urllib, a two second timeout, and a ten second cache, so a browser never
  has to read another origin. Their addresses come from a `Neighbours:` block
  in the machine-local `~/.controlunit/settings.yml`; the web package reads
  that file itself and `readsettings.py` was not touched.
- Five states, never conflated: `ok`, `degraded`, `down` (it answered and said
  so, including an HTTP error code), `unreachable` (nothing answered from this
  machine), and `not configured` (this machine has no address for it).
- Every response carries `Cache-Control: no-store`, and the stylesheet and
  script URLs are keyed to the version as well (`?v=0.5.0`), so a live upgrade
  cannot serve new markup against an old stylesheet either way.
- One page at `/`: a sticky top bar naming ControlUnit and its version, with
  Live, Control and Log marked "soon" and not pressable, and Lab as the working
  tab. The fleet three-track `.page` grid — the left control track stands empty
  because the Lab tab has nothing to switch, and no controls were invented to
  fill it. Main column: three service cards with a state chip, the version, one
  detail sentence, an Open link, and how to start the service behind a
  show/hide toggle that leads with plain words and keeps the literal `lab`
  line collapsed. Right rail: where each service lives on this machine, and the
  one legend explaining the five states. The page refreshes the three states
  every thirty seconds and writes them into elements that already exist.
- Dressing: the brief's warm charcoal and amber, so the rig's browser tab tells
  apart from the diagram's and the journal's cool dark. System sans plus a
  monospace for values, one stylesheet, one script, nothing from the internet,
  no icon font, `prefers-reduced-motion` honoured, every control bordered and
  filled at rest.
- Version bumped to 0.5.0. `flask>=3,<4` added to `requirements.txt` and
  installed into the shared `hardware-dev` environment. `simple_pid`, which the
  ADC worker has always imported but which no requirements file declares, had
  to be installed into that environment too before the program would boot
  off-rig; the missing declaration is left alone here so the rig's pending push
  merges cleanly.

## Gates

Run from the repository root with `$env:QT_QPA_PLATFORM = "offscreen"` and the
shared interpreter `~/.venvs/hardware-dev/Scripts/python.exe`, exit codes
captured rather than read off a summary line, neither gate piped:

- `python -m pytest -q` — 35 passed, `PYTEST_EXIT:0`.
- `python -m mkdocs build --strict` — built in 1.75 s, `MKDOCS_EXIT:0`.

Twelve of those tests are new: the health shape and every branch of its status
mapping, the `no-store` header on the page and both routes, the five neighbour
states with urllib monkeypatched, the ten second cache, and the page rendering
with version-keyed assets and exactly one explanation per state.

## The Perimeter Walk

Run in a real browser against a scratch instance, all ten steps.

- **Every top tab pressed from inside the surface.** Live, Control and Log are
  markers, not doors: pressing each left the page, the scroll position and the
  title unchanged. Pressing Lab while already on Lab, scrolled to the bottom,
  reloaded its own home and landed at the top with the disclosure toggles back
  in their resting state.
- **Every link clicked.** The brand link and the Lab tab both return home. The
  PIHTI Log card's Open link navigated to `127.0.0.1:48938`, the address the
  local config names. The PIHTI diagram card's Open link was clicked while
  nothing was listening on 48939 and the browser refused the connection, which
  is the honest outcome for a neighbour the page has just called unreachable;
  with a service standing there it answered instead. With no `Neighbours:`
  block at all both Open links render `aria-disabled` with no address.
- **Anchors:** the surface defines none. There is no section navigation on the
  Lab tab and none was invented, so there is nothing to land.
- **Back and Forward** from every state reached: back out of the PIHTI Log
  stub returned to the Lab page with all three chips intact and the rail at its
  resting offset; forward returned to it again.
- **Reload** (`location.reload()`) on the page restored the surface: the same
  three states, scroll at the top, toggles collapsed.
- **Two window heights, 1280×1000 and 1280×700**, both measured.
- **Rail offset identity**, `getBoundingClientRect().top` on `.rail-right`:

  | window | scroll range | samples at 0/25/50/75/100 % | rail top |
  | --- | --- | --- | --- |
  | 1280×1000 | 141 px | scrollY 0, 35, 71, 106, 141 | 76 px at every sample |
  | 1280×700 | 441 px | scrollY 0, 110, 221, 331, 441 | 76 px at every sample |

  Identical, not merely non-decreasing. The offset is the sum it claims to be:
  the tab bar measured exactly 56 px (`--bar`) plus the 20 px content gap, and
  the sticky `top` is written as that `calc()`. Two defects were found and
  fixed by this measurement rather than by reading the CSS: the bar rendered
  59 px because a small "soon" marker inherited the tab's 24 px line box and
  added its own border, which would have made the rail jump 3 px the instant
  stickiness engaged; and the show/hide button shifted 5 px sideways when its
  word changed, now held by one `min-width`. The rail fits its own box at both
  heights (`scrollHeight` 604 = `clientHeight` 604 at 700 px) so it never
  becomes a second page scrollbar, and at 700 px its travel budget — the
  containing block's 1065 px minus its own 604 px — exceeds the page's 441 px
  of scroll, so it does not reach the end-of-container release either.
- **Below the rail breakpoint** (900×700) the grid becomes one column, the
  empty control track is gone, and the context rail stands above the reading
  column rather than below it. Same DOM, different placement.
- **Two minutes of ordinary use**, and the refresh watched for movement: with
  the diagram's stand-in stopped between polls, its chip changed from `down` to
  `unreachable` on the thirty second refresh with every measured address
  identical — chip tops 162/423/687, card tops 142/403/667, card heights
  245/248/248, rail 76, document height 1000, before and after.
- **Teaching checks.** Counted on the rendered page, not in the template: each
  of the five state meanings renders exactly once, all of them in the rail
  legend; the chips elsewhere state and do not explain. Reading only headings,
  tabs and controls, a person finds the three services and their states first,
  and finds how to start any of them behind the one toggle on its card.

All five states were seen live in the browser, not only asserted in tests:
`degraded` on this service under the dummy stubs, `ok` and `down` from
stand-in neighbours, `unreachable` with nothing listening, and `not
configured` with the settings block removed. The console carried no error from
the application; the only 404 came from the stand-in, which serves nothing but
its health route. Every request the page made went to a loopback address.

## The scratch run

Loopback only, on pinned ports confirmed free before use: **48937** for the
application, 48938 and 48939 for two stand-in neighbours. The application was
run directly from the shared venv in the background rather than through `lab
start`, and the reason is the fleet's own rule about redirecting every path an
application writes: `readsettings.init_configuration` derives its data folder
and log file from the home directory, and `lab start` has no per-service way to
move that. The scratch process was given its own `USERPROFILE` and `HOME`
under the session's temporary directory outside Dropbox, so the data folder,
the log file and `~/.controlunit/settings.yml` all landed in scratch and the
owner's `~/work/cudata` was never written. No `lab` service was started or
stopped.

Stopped as a tree with `taskkill /PID <pid> /T /F`, and both halves verified:
the tracked launcher PID 16324, its real interpreter child 30284, and both
stand-ins are gone, and ports 48937 and 48939 hold no socket at all while
48938 holds only three `TimeWait` remnants of the walk's own fetches. The
owner's running services were left alone — `audioarchive` on PID 31524 and
`fleet` on PID 47628 carried the same PIDs before and after. `lab status` was
read once at the start and once at the end to establish that; nothing of the
owner's was started, stopped or reconfigured.

## What is next

Slice two, "Live", as the brief orders it: the locked snapshot the Qt main
thread writes on `data_ready`, `/api/state`, `/api/series` and `/api/log`, the
Live and Log tabs with their own rails, and the two canvas strip charts drawn
without a CDN. It stays read-only, so it can go on the rig before the control
decision is made. Slice three, browser control, still waits on the owner's
second directions question.

Two smaller things this slice deliberately left: registering `www = 4187` and
`version_url = "/api/health"` for `controlunit` in `lab-cli/services.toml`,
which is a commit in another repository under its own contract, and the reply
to PIHTI Log's letter `20260904-ec356017-5a06b4`, which directions still holds
ready to send with the port once queezz settles it.

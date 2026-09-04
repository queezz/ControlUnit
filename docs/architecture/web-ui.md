# Web view

An optional, read-only browser view of the rig, served from inside the
ControlUnit process. It is switched on with `--web`, which the rig's launcher
`scripts/run_controlunit.sh` passes, and answers on the lab network at
`http://pihti:4187/` by default.

## Where it sits

The Qt main thread owns every worker and is the only caller of worker slots;
the [threading rules](qt-threading.md) are untouched. The web view is a Flask
application on a daemon thread that never imports PyQt and never touches a
worker. It reads one object, `controlunit.web.status.RigStatus`, which the
main thread keeps up to date from methods it already runs:

| Main-thread method | What it records |
| --- | --- |
| `create_file` | a new run: the data file's name, the ring emptied |
| `_adc_step` | the samples that step delivered, converted and zero-adjusted as the screen shows them |
| `log_message` | one message-log line, tags stripped |
| `update_current_values`, the plasma and gauge setters | the setpoints the rig holds |
| `__onoff`, `abort_all_threads` | whether acquisition runs |

The record keeps the latest value of every channel, a ring of the last two
hours of samples, the last thousand log lines, and the run facts. Writes are
a few list appends behind a lock, so a browser being open does not slow the
acquisition loop. The CSV on disk remains the only durable record.

## Routes

All responses carry `Cache-Control: no-store`. No response carries a path, an
address or a credential; the data file appears by name only.

| Route | Answers |
| --- | --- |
| `GET /` | the Live tab |
| `GET /log` | the Log tab |
| `GET /lab` | the Lab tab |
| `GET /api/health` | `{service, version, status, detail}` — the ensemble's contract; `ok` only while acquiring on real hardware |
| `GET /api/neighbours` | this service and its two neighbours, each with a state |
| `GET /api/state` | latest values, setpoints, run facts and freshness; polled once a second, or four times a second under Poll: fast |
| `GET /api/series?window=300&points=600` | thinned `[t, v]` pairs per channel over the last `window` seconds, `0` for all held |

A window is cut by walking the ring backwards from the newest sample and
stopping at the first one outside it, so twenty seconds costs two hundred
rows however long the ring has grown, and the Live tab may ask four times a
second without the Pi paying for two hours of samples each time. `window=0`
still copies the whole ring, because the whole ring is what it asked for.
| `GET /api/log?since=N` | log lines after sequence number `N` |

## Tabs

- **Live** — the five signals the rig's own graph draws, in its own pen
  colours, as readouts and two canvas strip charts: plasma current, and the
  pressures on a log axis. The left rail chooses the window, the channels,
  the pressure axis, the readout size and the poll rate; the right rail states
  the run and how fresh the data is. Data is `live`, `stale` (no sample for
  five sampling periods, never less than two seconds) or `idle` (acquisition
  off). `Display: big` makes the five readouts the column's lead, for reading
  the rig from a metre away, and is remembered per browser. `Poll: fast` asks
  for state and series four times a second instead of once and twice, for
  watching a value settle while a gauge is zeroed at the rig; it keeps
  whatever window is chosen, and it is deliberately forgotten on reload so a
  page left open overnight stops asking.
- **Log** — the same message log the Qt Log dock shows, newest first, with a
  Find and an order switch.
- **Lab** — the three services of the lab ensemble with a state each: `ok`,
  `degraded`, `down` (it answered and said so), `unreachable` (nothing
  answered from this machine) and `not configured`.
- **Control** — named in the tab bar and not built. Whether a browser may
  change a setpoint is an open owner decision.

## Machine-local configuration

Neighbour addresses live in `~/.controlunit/neighbours.yml` on the machine
that serves the page, never in the repository:

```yaml
pihti-diagram:
  url: http://pihti:5000
  where: on this Pi, as a system service
  start: sudo systemctl start pihti.service
pihti-log:
  url: http://ak-office.local:4310
  where: on the office Windows PC
  start: lab pihti-log
```

`url` is required. `where` and `start` are optional and describe how that
service is started on the machine it runs on; a card with neither says
nothing about starting. This is a separate file on purpose: the program
treats a local `~/.controlunit/settings.yml` as a complete replacement for
the packaged settings, so a settings file holding only neighbours would stop
the rig from starting.

## Off-rig development

The dummy hardware stubs let the whole program, web view included, boot on
Windows and macOS from the shared `hardware-dev` environment. A scratch run
binds loopback on a confirmed-free port with `HOME` redirected, so the data
folder and log file land outside the owner's own folders:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -m controlunit.main --web --host 127.0.0.1 --port 48937
```

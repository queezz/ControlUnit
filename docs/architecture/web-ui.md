# Web view

An optional browser view of the rig, served from inside the ControlUnit
process. It is switched on with `--web`, which the rig's launcher
`scripts/run_controlunit.sh` passes, and answers on the lab network at
`http://pihti:4187/` by default. Reading is open to anyone on that network;
setting a setpoint is gated by the switch on the rig, and by an operator
lock so that two people never drive one plasma without seeing each other.
Both are described below.

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
| `start_acquisition`, `stop_acquisition`, `abort_all_threads` | whether acquisition runs |
| `set_sampling` | the sampling time the run holds |
| `_toggle_remote` | whether a browser may set anything |
| `abort_all_threads`, `_toggle_remote` | letting go of the operator lock |
| `_adjust_zeros` | the baselines the display subtracts |
| the command drain | what became of the last command a browser sent |

The record keeps the latest value of every channel, a ring of the last two
hours of samples, the last thousand log lines, and the run facts. Writes are
a few list appends behind a lock, so a browser being open does not slow the
acquisition loop. The CSV on disk remains the only durable record.

## The command path, and the gate

A browser may change a setpoint. It does so without ever calling a worker
slot, because the web thread must not: a press becomes a small record on a
`queue.Queue`, and the Qt main thread drains that queue on a 200 ms QTimer
and calls the same methods its own buttons call. A setpoint therefore has
one code path whether it came from the rig's touchscreen or from a laptop.
The queue and the drain live in `controlunit.web.commands`, which imports
nothing from PyQt; the timer lives in `main.py` and exists only under
`--web`. The Flask thread stays a daemon thread and the hardware-first
shutdown order is untouched.

```
browser  --POST-->  Flask thread  --checked record-->  queue
                                                         |
                          Qt main thread, every 200 ms --+--> the same slots
                                                              the buttons call
```

Values are checked in the Flask thread before anything is queued, so the
main thread is never handed a command it should have refused. A queued
command answers `202 {"id": ...}` and nothing more: what actually happened
is read from the next `/api/state`, which carries `last_command` (kind,
actor, a short summary, the time and the outcome). The browser never assumes
its own request succeeded.

**Who may press what.** Setting needs the **Remote** switch turned on in the
Qt control dock, on the rig's own screen, beside the on/off switch. It rests
off and cannot be turned on from a browser. That switch is the whole
authorisation: a person standing at the rig decides whether the network may
move anything.

The switch stays exactly where that person put it. It used to be forced off
whenever acquisition stopped, so that a laptop could not hold a gate over a
rig that is not running; now that a browser may start and stop a run, a
switch that turned itself off would strand the very person who had just
pressed Stop, so the stop path no longer touches it. The operator lock below
is still let go of when acquisition stops, which is the part of that design
that answers *who*; the browser that stopped the run claims the lock again
with its next setter, and Start is one.

A name is asked for and never waited for. `POST /api/identify` sets an
`actor` cookie and the Control tab's left rail has an "Acting as" field, but
it is a label so the log can say who, never a credential and never a claim
of identity. Somebody who has typed no name is logged, and holds control, by
the address their browser is at. Requiring one had made a rig with its switch
already thrown refuse every command, which reads as a broken page rather
than a locked one (owner report 2026-09-05).

Without the switch a setter is `403` with the reason; a command that needs
the workers when none are running is `409`; a body that does not say
something the rig accepts is `400`. **Stop all outputs** is the one exception and is
always allowed — name or no name, switch or no switch, acquiring or not —
because it only ever calls the `turn_off_voltages` the shutdown path calls
and drives the hardware to zero.

Every drained command is written to the message log with the name, the
value, the origin address and the time, so it appears in the Qt Log dock,
the log file and the Log tab. The origin address is the deliberate exception
to "no response carries an address": a command that moved gas or cathode
current says where it came from.

## The operator lock

The switch answers *may anyone set from a browser*; the lock answers *which
one of them*. It exists for one question the owner asked: two people must not
control one plasma without seeing each other.

**The first browser to send a setter holds control**, taken the moment a
setter (`mfc`, `plasma`, `gauge`, `sync`, `zero`) is queued. It is held by
the browser's own address, and shown under the name that browser has saved,
or under the address itself while it has saved none. So the same name from
another address is another person — two laptops, one shared name, still two
people at one rig — and saving a name after taking control renames the
holder rather than locking them out of their own session.
**Stop all outputs never takes the lock and is never gated by it.**

Every Control page says who holds it, in one line in the Remote card of the
left rail: *"Arseniy has control since 21:40 from 10.249.254.30"*, or *"Nobody
has control"* when it is free. That line is written on the rig, in
`commands.holder_sentence`, and carried in `/api/state` as `control.line`, so
the page and a refusal cannot word it two ways; the address in it is the same
deliberate exception the command log makes. A second person's setters are
refused `403` with that very sentence as the reason, and their page shows the
setters disabled with the reason stated once in the rail, exactly as the
switch-off case does — plus a **Take over** button they may press.

**Take over** (`POST /api/take-over`) moves the lock to the presser. It is a
command in its own right: the main thread logs it with the new name, the
origin and the time, and the previous holder's page shows the new holder
within one poll. Taking over when nobody holds control simply takes it;
taking over what you already hold is a no-op with `200`. The button is
disabled while you hold control and while the Remote switch is off.

**The rig's own screen always wins.** Nothing a person does at the Qt window
is ever gated by the lock. The main thread lets go of it — through
`commands.release(app, reason)`, which also writes the log line — when
acquisition stops (*"Control released (acquisition stopped)"*) and when the
Remote switch goes off (*"Control released (Remote switch off)"*). There is no
idle timeout: a lock held quietly through a long overnight run is the normal
case, not a fault.

The lock lives on the `CommandQueue` as an `OperatorLock`, behind its own
`threading.Lock`: it is decided in the web thread, where the commands arrive,
and read from both threads. `/api/state` reads it from the queue rather than
from a copy in `RigStatus`, because a second copy could only ever go stale.
The reply also carries `control.mine`, since a browser cannot see its own
address and so cannot work out for itself whether the holder is the reader.

The lock is a courtesy between colleagues, not a security boundary: a name is
a label a person typed, and anyone on the lab network may press Take over. It
makes the other person visible; the Remote switch on the rig is what makes
setting possible at all.

## Baselines

Plasma current and both Baratrons can be read from a baseline. Pressing
"O Ip", "O Bu" or "O Bd" in the Scales dock, or "Zero now" on the Control
tab, asks the ADC worker to take the mean of that channel's recent converted
column as its zero. The worker answers with all three zeros at once through
`send_zero_adjustment`; the main thread stores them and subtracts them in
the three places a person reads a value — the dock's readouts, the plots,
and what the web view is handed. **The CSV on disk is never adjusted**: a
zero is a way of reading a signal, not a change to the record. The zeros the
rig currently holds are carried in `/api/state` as `zeros`.

## Routes

All responses carry `Cache-Control: no-store`. No response carries a path or
a credential; the data file appears by name only.

| Route | Answers |
| --- | --- |
| `GET /` | the Live tab |
| `GET /control` | the Control tab |
| `GET /log` | the Log tab |
| `GET /lab` | the Lab tab |
| `GET /api/health` | `{service, version, status, detail}` — the ensemble's contract; `ok` only while acquiring on real hardware |
| `GET /api/neighbours` | `{services: [...], checked_at: "HH:MM:SS"\|null}` — this service and its two neighbours, each with a state, and when the last probe finished on this machine's clock; answers from what this machine already knows and asks the LAN behind the answer |
| `GET /api/neighbours?fresh=1` | the same, with the cached answer thrown away first: every row comes back `checking` and the probe runs behind the reply, so the press never waits for the LAN |
| `GET /api/roster` | `{"names": [...]}` — the lab's operator names this machine holds a copy of, empty when it holds none |
| `GET /api/state` | latest values, setpoints, run facts, freshness, the Remote switch, the zeros, who has control and the last command; polled once a second, or four times a second under Poll: fast |
| `GET /api/series?window=300&points=600` | thinned `[t, v]` pairs per channel over the last `window` seconds, `0` for all held |
| `GET /api/series?since=1757200000&points=3000` | the same, but only samples strictly newer than that stamp; `since` wins over `window` |

A window is cut by walking the ring backwards from the newest sample and
stopping at the first one outside it, so twenty seconds costs two hundred
rows however long the ring has grown, and the Live tab may ask four times a
second without the Pi paying for two hours of samples each time. `window=0`
still copies the whole ring, because the whole ring is what it asked for.

`since` is the same walk against a stamp rather than a span, and it is what
the Live tab actually sends. That tab keeps its own history: it fills once
from the ring when the page opens (`window=0&points=3000`, which carries the
whole ring at full resolution, two hours at the rig's 0.1 Hz being 720
samples) and then asks only for what it has not seen. So a page left open all
afternoon costs the Pi the handful of rows that arrived since it last asked,
rather than the afternoon it already holds. Nothing newer is an empty answer,
not an error. The reply carries both `window` and `since` back, so a reader
of the response can tell which question was asked.
| `GET /api/log?since=N` | log lines after sequence number `N` |
| `POST /api/identify` | `{"name": "..."}` — remember, in this browser, the name to write beside a command |
| `POST /api/take-over` | take control of the rig from whoever holds it; `200` either way, `403` without the switch |
| `POST /api/stop-all` | every output to zero; always allowed |
| `POST /api/acquisition/start` | begin a run; `409` when one is already running |
| `POST /api/acquisition/stop` | end the run, close the data file, drop every output |
| `POST /api/sampling` | `{"seconds": 10\|1\|0.1\|0.01}` — the sampling times the Settings dock offers |
| `POST /api/mfc/<1\|2>` | `{"mv": 0..5000}` — a gas flow setpoint; `0` is the Zero button |
| `POST /api/plasma-current` | `{"a": 0..3}` or `{"off": true}` |
| `POST /api/gauge` | `{"mode": "Torr"\|"Pa"}` and/or `{"range": -8..-3}` |
| `POST /api/sync` | `{"on": true\|false}` — the QMS sync line |
| `POST /api/zero` | `{"channel": "Ip"\|"Bu"\|"Bd"}` — take that channel's baseline |

## Tabs

- **Live** — the five signals the rig's own graph draws, in its own pen
  colours, as readouts and three canvas strip charts: plasma current, the
  ion gauges (log axis by default) and the Baratrons (linear by default).
  Two pressure panels rather than one, because one axis could not serve both
  kinds of gauge: the ion gauges cross decades, the Baratrons sit in a narrow
  band around their own offset, and drawn together neither was readable
  (owner report 2026-09-06). Each panel scales to its own visible channels.
  The left rail chooses the window, the channels, an axis for each pressure
  panel, the smoothing, the readout size and the poll rate; the right rail
  states the run and how fresh the data is. Data is `live`, `stale` (no
  sample for five sampling periods, never less than two seconds) or `idle`
  (acquisition off).

    **The browser keeps its own history.** The page fills once from the ring
    and then asks `since` (above), appending into a per-channel store capped
    at a day. The window buttons cut that store and redraw without asking the
    rig anything, so `Full` is what this browser has seen — said once, as an
    aside on the Window card's heading. A new run — a different start time or
    a different file — empties the store and refills it from the ring.

    **Readouts.** A value reads as `1.22×10⁻⁵`, mantissa and a real
    superscript exponent, never `1.22e-5`; zero reads `0`; a current in
    amperes stays plain. Each card is washed with its own pen at 14% and
    bordered with it at 45%, so the eye finds a channel before it reads the
    name. On Ip, Bu and Bd one always-present line says what baseline the
    number has already taken off — `zero -0.345 A`, or `as measured` — and
    what a zero is is explained once, in the right rail's Data card.

    **Smoothing** is a centred moving median over `off | 5 | 15 | 51`
    samples, applied to every line and to the five readouts, for the plasma
    current's spikes until the hardware RC filter arrives. A median and not a
    mean: it drops a spike without smearing the step when a setpoint really
    moves.

    `Size: big`, in the Readouts card, makes the five readouts the column's lead, for reading
    the rig from a metre away, and is remembered per browser. `Poll: fast`, in the same card,
    asks for state and series four times a second instead of once a second and once every two seconds,
    for watching a value settle while a gauge is zeroed at the rig; it keeps
    whatever window is chosen, and it is deliberately forgotten on reload so a
    page left open overnight stops asking. Every other choice in that rail is
    remembered.
- **Log** — the same message log the Qt Log dock shows, newest first, with a
  Find and an order switch.
- **Lab** — the lab ensemble's own board, built in the PIHTI diagram's shape
  so the three surfaces read the same (owner decision 2026-09-07, "I like the
  pihti-diagram way for the services, and we need to sync that in all 3
  siblings"). One card per service, this one first: a head carrying the name
  and the state, then four facts — **Version**, **Says** (what the service's
  own health report said), **Runs** (the machine it runs on) and **Start**
  (the line that starts it there) — then either an Open button, the sentence
  *"This is the service you are reading."*, or *"No address on this machine."*
  The left rail holds the one control this tab has, **Ask again now**, with a
  line beneath it reading *"Not checked yet."* or *"Checked 14:02:57."*; the
  right rail holds one card, **The ensemble**, which is where a state is
  explained, once, for the whole page. Every chip elsewhere states its word
  and nothing more.

    **The six states.** `ok`, `degraded` and `down` are what a service said
    of itself, and `down` covers a refused connection too — a machine that
    is there with nothing listening on the port answered the knock.
    `unreachable` is nothing answering from this machine at all: the two
    seconds ran out, or the name never resolved. `degraded` also covers an
    answer that was not a health report. `not configured` means this machine
    has no address for that service, and `checking` means it is asking now
    and has not heard back. The three surfaces word these the same way.

    **The page never waits for the LAN.** It is served from what the machine
    already knows — the last answers, however old, or `checking` when there
    are none — and the neighbours are asked on a background thread behind
    that. The tab asks again every two seconds while any card still says
    `checking`, every thirty once they have all resolved, and not at all
    while the tab is hidden, asking once the moment it is looked at again.
    **Ask again now** throws the cached answer away and is answered in the
    same breath, with `checking` rows and the probe running behind them; the
    button is disabled until that answer lands. The checked line keeps saying
    when the last answer landed while a new one is on its way, because when
    this machine last heard back and what it is doing now are two different
    facts. A neighbour this machine has no address for is `not configured`
    from the first paint, because that answer needs nobody.
- **Control** — five headed groups in operating order: Acquisition, Gas
  flow, Plasma current, Gauge and sync, and Baselines. Acquisition states
  the run's facts and carries the two presses that begin and end it, and
  the four sampling times the rig's own Settings dock offers; **Stop** asks
  once in the browser before it sends, in the same words the group's note
  uses. Every other row shows the setpoint the rig holds beside the value it
  measures. **Start** is the one control enabled while nothing is running —
  the switch and control of the rig are still needed — and every other
  control needs a run as before. The left rail carries the gate —
  the switch's state, who has control and the Take over button, the one
  reason setting is off right now, the name — chosen from the lab's roster
  where this machine holds a copy of one, typed where it does not — and
  the always-allowed Stop all outputs; the right rail carries this run and
  an index of the five groups. A control the gate would refuse is disabled
  and still visibly bordered, and the reason is stated once in the rail,
  never on a row.

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

`url` is required. `where` and `start` are optional and become the **Runs**
and **Start** facts on that service's card: `where` is the machine it runs
on, and `start` is the literal line that starts it *there*, copied onto the
card exactly as this file writes it. Neither is ever guessed — a card whose
entry says nothing shows an em dash rather than a command invented from the
service's name, because a line that does not work on that machine is worse
than no line at all. This is a separate file on purpose: the program
treats a local `~/.controlunit/settings.yml` as a complete replacement for
the packaged settings, so a settings file holding only neighbours would stop
the rig from starting.

### The lab's roster of names

The name written beside a command is chosen from a list where the machine
serving the page has one, so that one person is spelled one way across the
lab's logs. The list is `~/.controlunit/operators.json`, a copy of the
names-only roster PIHTI Log reads from the Obsidian vault,
`<vault>/People/operators.json`, in that program's own schema:

```json
{"schema": "pihti-operators/v1",
 "operators": [{"username": "hashizuka", "display_name": "Hashizuka Takuma"}]}
```

Only `pihti-operators/v1` is read, and only `display_name` reaches the page,
since the log prints display names. The file is reread whenever its
modification time or size changes, and never looked at more than once a
second. A missing, unreadable or malformed file means no names, and the
Acting-as field stays the free-text box it has always been.

The Pi has no Dropbox and no vault, so the copy is pushed from a machine
that has the vault, by the script kept beside the rig's launcher. Names are
people, so the file itself never enters git; the script does. Run it again
whenever the roster changes, and the Control tab picks the new list up
within a second, no restart needed. It stays a courtesy list rather than a
credential or a list of who may drive the rig.

```powershell
scripts\push_roster.ps1
```

```bash
scripts/push_roster.sh
```

Both take the vault and the rig as optional arguments (`-Vault`, `-Rig`;
positional in the shell form) and default to the vault under Dropbox and
`pi@pihti`.

`POST /api/identify` still takes any cleaned name where the machine has no
roster; where it has one, a name that is not on it is refused `400` with
"choose a name from the lab's roster".

## Off-rig development

The dummy hardware stubs let the whole program, web view included, boot on
Windows and macOS from the shared `hardware-dev` environment. A scratch run
binds loopback on a confirmed-free port with `HOME` redirected, so the data
folder and log file land outside the owner's own folders:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -m controlunit.main --web --host 127.0.0.1 --port 48937
```

# Web view

An optional browser view of the rig, served from inside the ControlUnit
process. It is switched on with `--web`, which the rig's launcher
`scripts/run_controlunit.sh` passes, and answers on the lab network at
`http://pihti:4187/` by default. Reading is open to anyone on that network;
setting a setpoint is gated by the switch on the rig, by the lab's word
where the machine serving the page holds one, and by an operator lock so
that two people never drive one plasma without seeing each other. All three
are described below.

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

Where the machine serving the page holds one, **the lab's word** stands
beside the switch: a browser types it once at `POST /api/fence` and carries
it in a cookie afterwards, and until it has, every kind the switch gates —
every setter and Take over — is refused `403` with *"type the lab's word
first"*. It is a fence one may walk over and never a credential (owner
decision 2026-09-07, "not security, just a fence one can walk over"): it is
compared as plain text, it is nobody's password, **Stop all outputs is never
behind it**, and a machine holding no word has no fence at all — see *The
lab's word* under Machine-local configuration.

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
the workers when none are running is `409`. Gauge mode/range can be prepared
while idle (4.8.2): the displayed setting updates immediately and startup
passes it to the ADC. Remote and operator gates still apply. A body that does not say
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
| `GET /` | the unified Live page (Operate by default, `?mode=observe` hides operation controls); `?mode=monitor` renders it with the tab bar and both rails out of the way and the charts across the whole window, anything unknown renders the ordinary page |
| `GET /control` | compatibility address for Live in Operate mode |
| `GET /log` | the Log tab |
| `GET /lab` | the Lab tab |
| `GET /api/health` | `{service, version, status, detail}` — the ensemble's contract; `ok` whenever the rig is up, idle included, `degraded` only for something actually impaired. `detail` says what the rig is doing: `idle, not recording`, `acquiring 9 channels at 10 Hz`, and — whether or not anything is being recorded — `outputs live:` with the outputs named |
| `GET /api/neighbours` | `{services: [...], checked_at: "HH:MM:SS"\|null}` — this service and its two neighbours, each with a state, and when the last probe finished on this machine's clock; answers from what this machine already knows and asks the LAN behind the answer. Every row carries `alias`, `name`, `url` (where a browser opens), `probe_url` (where this rig asked), `opens_at`, `state`, `version`, `detail`, `where`, `start_how`, `start` and `here` — starting is two keys and not one, the plain words and the literal line |
| `GET /api/neighbours?fresh=1` | the same, with the cached answer thrown away first: every row comes back `checking` and the probe runs behind the reply, so the press never waits for the LAN |
| `GET /api/roster` | `{"names": [...]}` — the lab's operator names this machine holds a copy of, empty when it holds none |
| `GET /api/state` | latest values, setpoints, run facts, freshness, what the rig is doing (`operating: {state, outputs}`), the Remote switch, the zeros, who has control, whether this machine asks for the lab's word and whether this browser has typed it (`fence`), when this machine's copy of the roster last refreshed (`roster`, or `null` for never), and the last command; polled once a second, or four times a second under Poll: fast |
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
| `POST /api/fence` | `{"word": "..."}` — the lab's word; `200 {"fenced": true}` and a cookie when it matches, `200 {"fenced": false}` where this machine has no word, `403` when it does not match |
| `POST /api/take-over` | take control of the rig from whoever holds it; `200` either way, `403` without the switch |
| `POST /api/stop-all` | every output to zero; always allowed |
| `POST /api/acquisition/start` | begin a run; `409` when one is already running |
| `POST /api/acquisition/stop` | end the run, close the data file, drop every output |
| `POST /api/sampling` | `{"seconds": 10\|1\|0.1\|0.01}` — the sampling times the Settings dock offers |
| `POST /api/mfc/<1\|2>` | `{"mv": 0..5000}` — a gas flow setpoint; `0` is the Zero button |
| `POST /api/plasma-current` | `{"a": 0..3}` or `{"off": true}` — the plasma-current PID, which moves the cathode DAC for you |
| `POST /api/cathode` | `{"mv": 0..5000}` or `{"off": true}` — the cathode DAC held at a millivolt value with the PID off; whole millivolts, gated exactly as the PID setpoint is |
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
  The left rail chooses the window, an axis for each pressure panel and the
  smoothing (one card, **Lines**), the readout size and the poll rate
  (**Readouts**), and what shape the page itself is in (**View**: a preset
  and a mode); the right rail states the run and explains how the page is
  read.

    **Two pills at the head of the column, and no third.** The left one is
    the apparatus — `stopped`, `measuring`, or `outputs live` with the
    outputs named beside it — and the right one is how fresh the numbers
    below are: `live`, `stale` (no sample for five sampling periods, never
    less than two seconds) or `idle` (acquisition off). They state; the
    right rail's *Reading this page* card explains them once, for the whole
    surface. The apparatus pill is never read off the acquisition flag: the
    rig can hold gas open and the cathode driven with nothing recording at
    all, which is what the 2026-08-19 reader death left behind.

    **Each chart carries its own curves' switches.** A legend entry under
    the chart head is the switch for that curve, in that curve's own pen.
    The five switches used to stand together in the left rail, away from the
    lines they turned off, and were the ones the owner could not find
    (2026-09-07: "all the little toggles on the Live view, hard to find the
    one I need"). A switch beside its own curve needs no hunting, and the
    choice is still remembered per browser.

    **A curve that says nothing is left off its panel, and says why.** A
    switched-off curve reads `off`; one with nothing in the window reads
    `no data`; one whose whole excursion over the window is smaller than its
    own last useful digit reads `flat` — under a twentieth of a decade on a
    log axis, under 2% of its own value on a linear one. A collapsed curve
    is out of the panel's range as well as off it, which is the point: the
    broken upstream gauge sits at 1e-5 while the downstream one reads 1e-8,
    and on one axis the owner "can't see either" (2026-09-07). Collapsing
    only ever happens while another curve on the same panel is still moving,
    so a panel never empties itself, and turning the moving one off brings
    the flat one back. The last value is not printed in the legend: it is in
    that channel's readout card above, where every number on this page is
    read.

    **A panel's height and its backing buffer are two facts, and the code
    reads only the one nothing writes.** `data-height` on each `<canvas>` is
    how tall the panel stands on the page; the `height` attribute beside it
    is the drawing buffer, which the page sizes for the screen's own pixel
    density. Setting `canvas.height` writes that attribute, so reading it
    back as the layout height and multiplying by the device pixel ratio
    again grows the panel on every redraw — harmless at ratio 1, which is
    every screen in this lab, and on the owner's Retina Mac on 2026-09-07 it
    reached a height attribute of 1,802,240 px and a document of
    2,540,001 px before the plot failed white. The buffer is also bounded at
    8192 px a side, because a browser refuses a canvas past that and hands
    back a context that draws nothing; a panel with no context is left blank
    rather than throwing on every poll.

    **The browser keeps its own history.** The page fills once from the ring
    and then asks `since` (above), appending into a per-channel store capped
    at a day. The window buttons cut that store and redraw without asking the
    rig anything, so `Full` is what this browser has seen — said once, as an
    aside on the Window card's heading. A new run — a different start time or
    a different file — empties the store and refills it from the ring.

    **Readouts.** A card is a name, a signed number and a unit, and the
    number is never replaced by words. A value reads as `1.22×10⁻⁵`,
    mantissa and a real superscript exponent, never `1.22e-5`; zero reads
    `0`; a current in amperes stays plain. Each card is washed with its own
    pen at 14% and bordered with it at 45%, so the eye finds a channel
    before it reads the name. Small is two rows of content and the padding
    around them — no reserved blank line and no minimum height past what
    those rows need — so the strip stands at about half the height it did
    through 4.11 (measured at 1280px: a card 104px tall became 52px).

    One tag rides in the name row, on every card: `zeroed` while the rig
    holds a baseline for that channel, `below zero` while the value is
    negative, `zeroed · below zero` when both. It is empty otherwise, and
    empty it takes no room, so no card changes height between polls.
    Whatever it says, it stays on the line it shares — the narrowest card
    this page makes, five across the Operate column at 1280px, leaves the
    tag about 50px, and `paintState` measures that box and keeps `below
    zero`, the word that changes how the number is read, rather than
    clipping. What a zero is is explained once, in the right rail's Data
    card; a readout card never explains itself.

    The line that used to stand under every zeroable card — `zero -0.345 A`,
    or `as measured` — is gone, with the two lines of room it held open.
    "as measured" said nothing that was not true of every signal on this
    page (queezz, 2026-09-10, on 4.11.0: "It's all as measured. We are in
    physics, we know what signals are"), and the height it reserved was the
    "large boxes small font" that defeated the point of the small size.

    **Smoothing** is a centred moving median over `off | 5 | 15 | 51`
    samples, applied to every line and to the five readouts, for the plasma
    current's spikes until the hardware RC filter arrives. A median and not a
    mean: it drops a spike without smearing the step when a setpoint really
    moves.

    `big`, beside the readouts, makes the five readouts the column's lead, for reading
    the rig from a metre away, and is remembered per browser. `Poll: fast`, in the same card,
    asks for state and series four times a second instead of once a second and once every two seconds,
    for watching a value settle while a gauge is zeroed at the rig; it keeps
    whatever window is chosen, and it is deliberately forgotten on reload so a
    page left open overnight stops asking. Every other choice in that rail is
    remembered.

    **A preset sets the page for a kind of work.** `Show: All | Vacuum |
    Plasma`, in the View card, is a named set of exactly the per-curve
    switches described above and nothing more: it changes what this browser
    draws, never one byte of what the rig records, and it is remembered the
    same way the switches are. **Vacuum** shows both ion gauges and both
    Baratrons and turns the current off; **Plasma** shows the current and the
    two Baratrons, which are what read the gas pressure a discharge actually
    sits at, and turns the ion gauges off — a vacuum instrument, off scale or
    switched off by then. Which preset is pressed is *derived* from the
    switches rather than stored beside them, so turning one curve off by hand
    simply leaves no preset claimed. A panel whose every curve is off keeps
    its heading and its legend and gives up only its drawing area, so the
    switches that bring it back are exactly where the reader left them; its
    span line reads `no curves shown`. The two curve lists are
    `server.py`'s `PRESETS` and are one edit to change.

    **Monitor mode gives the charts the window.** queezz, 2026-09-07:
    *"Monitor: plots only, even hide the rails. Only keep some indicator
    pills about status and all."* `Operate | Observe | Monitor` in a fixed header switch,
    and `?mode=monitor` in the address, so the second laptop propped up
    beside the rig can bookmark its own screen — the server renders that
    shape on the first paint rather than flashing the other one, and Back,
    Forward and a reload all land where a reader expects. The tab bar and
    both rails leave the page and the reading column grows from 673px to
    1225px at a 1280px window, so the charts roughly double in width. The two
    pills stay exactly where they were, at the head of the column they
    describe, because whether the rig is holding gas is what that screen
    exists to say; beside them the strip carries the way back to each rail,
    a **Full screen** press (the browser's own Fullscreen API, silent where a
    browser refuses it) and **Leave monitor**.

    The rails in that mode are the same elements summoned from their own
    edge, in the drawer shape the PIHTI diagram already uses below its rail
    breakpoint — same DOM, different placement, nothing duplicated. One
    drawer at a time, dismissed by its Close, by the backdrop, or by Escape;
    Escape with no drawer open leaves the mode, so a mode is never a room
    without a door. An unknown `?mode=` is the ordinary page and never an
    error.
- **Log** — the same message log the Qt Log dock shows, newest first, with a
  Find and an order switch.
- **Lab** — the lab ensemble's own board, built in the PIHTI diagram's shape
  so the three surfaces read the same (owner decision 2026-09-07, "I like the
  pihti-diagram way for the services, and we need to sync that in all 3
  siblings"). Three cards stand across the reading column, in the ensemble's
  one order on every machine — **PIHTI diagram, PIHTI Log, ControlUnit** —
  this program's own card third rather than first, so a person who learned
  the board on the journal finds the same card in the same place here (owner
  direction 2026-09-07, from the three surfaces side by side: "they should be
  identical"). Stacked full width, the third service used to sit below a
  Mac's viewport and had to be hunted for. Each card carries a head with the
  name and the state, then three facts — **Version**, **Says** (what the
  service's own health report said) and **Start** (how it is started on the
  machine it runs on) — then either an Open button with the address it
  opens beneath it, the sentence *"This is the service you are reading."*, or
  *"No address on this machine."*

    **The board's own arithmetic is the reference's, to the pixel.** 16rem
    rails, a 20px page gap, 260px cards and 14px between them — the numbers
    the diagram and the journal carry, so all three break at the same window
    widths: two cards across and the third below at 1280px (cards at x 296,
    640 and 296), three across from about 1415px, which the owner's Mac has.
    A surface that picks its own numbers breaks somewhere else, which is
    what happened for one release. At the reference's card width the fact
    labels stand beside their values, as they do on the other two.

  The left rail holds the one control this tab has,
  **Ask again now**, with a line beneath it reading *"Not checked yet."* or
  *"Checked 14:02:57."*; the right rail holds one card, **The ensemble**,
  which is where a state is explained, once, for the whole page. Every chip
  elsewhere states its word and nothing more.

    **A chip and a link answer for two different machines.** The state was
    measured from the rig; the Open link is the reader's own browser's to
    follow, and the address it goes to is printed under it. Where a machine
    holds two names for the same service — the Pi knows `pihti`, a Mac knows
    `pihti.local` — `neighbours.yml` says both and the card opens the one a
    browser can use. The rail's lead line says that distinction once, for the
    whole surface.

    **Start says the meaning and keeps the machinery behind a toggle**
    (fleet's WEBUI.md, "Meaning first"). The row leads with plain words — for
    this program, *"From the rig's own screen: the desktop shortcut starts
    the whole program, web view included."*, because ControlUnit starts with
    its own GUI and there is no `lab controlunit` to type — and a
    `show`/`hide` button of one fixed width sits beside them, with the
    literal command hidden beneath until it is pressed. A card whose entry
    gives a command and no words for it says *"Started by a command on its
    own machine."*; a card with no command shows no toggle and no line at
    all, and the row simply ends at the words. **A refresh never closes an
    open disclosure**: which commands are open is kept per service in the
    page and mirrored to `sessionStorage`, and every repaint re-applies it,
    so the two-second poll of a still-checking board cannot shut a line
    under the reader.

    **The right rail teaches at a glance** (owner report 2026-09-07, "too
    long and too quiet... I love to see it all at a glance. With possible
    expansions if more is really needed", and the readers beside him whose
    English is a second language). One lead line — *"What this machine can
    reach right now."* — then the six chips the cards themselves wear, each
    followed by three or four plain words, then a **More** button which
    reveals the two remaining paragraphs beneath it. The button keeps one
    position and nothing above it moves when it is pressed, and its state is
    remembered for the browser tab. The six meanings live once, in
    `STATE_LEGEND` in `controlunit/web/server.py`, and the card renders from
    it.

    **The six states.** `ok`, `degraded` and `down` are what a service said
    of itself, and `down` covers a refused connection too — a machine that
    is there with nothing listening on the port answered the knock.
    `unreachable` is nothing answering from this machine at all: the two
    seconds ran out, or the name never resolved. `degraded` also covers an
    answer that was not a health report. `not configured` means this machine
    has no address for that service, and `checking` means it is asking now
    and has not heard back. The three surfaces word these the same way.

    **What this rig says about itself.** `ok` whenever the program is up,
    and that includes doing nothing: an idle rig is a rig waiting for
    somebody to press Start, and calling it degraded turned the lab's shared
    board amber all night (owner correction 2026-09-07: "It's up and not
    doing a thing, not degraded"). The detail says *"idle, not recording"*.
    `degraded` is kept for a capability that is actually impaired, and there
    are two this record can see today: a run whose last sample is older than
    the stale bound — the reader died between two of them, which is what
    happened on 2026-08-19 — and a process standing dummy devices in for the
    instruments, which is honest about what it cannot do rather than an
    invented failure, and never happens on the Pi. Nothing is called degraded
    before it has been measured: a run whose first sample has not landed yet
    is `ok`, because at ten seconds a sample that gap is ordinary.

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
- **Operation on Live** — from 4.7.0, operation controls and their held/measured
  outputs stand beside the same live readouts and charts used by Live.
  **The left rail is the gas and the plasma**, from 4.12.0: Start/Stop with
  its access line, Gas flow, Cathode, Stop all outputs, and nothing else.
  QMS sync, Sampling and Gauges stood there too until the owner looked at
  4.11.2 on the rig (2026-09-10): *"Left rail got a bit crowded. QMS signal,
  sampling, and IG panel can stay on the right, and I don't use those often.
  And then the left becomes gas/plasma real control."* The three moved,
  whole, into the right rail — the same elements, not copies, so the wiring
  and the gate still find one of each — and their anchors moved with them,
  so `#sec-sync`, `#sec-acquisition` and `#sec-gauge` still land.

  **The Cathode group offers the two ways the rig can drive its filament**
  (owner direction 2026-09-09, "I want two modes"). *PID* is the plasma-current
  loop: a setpoint in amperes, and the loop moves the DAC. *Manual* is the knob:
  a millivolt value the DAC holds with the PID off, typed or nudged by
  ±1000/100/10/1 mV like a gas line, sent only on Set. The Mode buttons are a
  view choice remembered in the browser — they send nothing, and only one
  setter row is shown at a time. Which of the two is actually holding the
  cathode is read from `setpoints.plasma_a` and `setpoints.cathode_mv` and
  stated once, on the group's own feedback line, so the buttons never move on
  their own when somebody else sets the rig. Baseline zero buttons sit in the corresponding plot headers (4.7.2). Stop all outputs remains independently available.

  The right rail holds four folded groups, in this order: **Operator and
  access**, **Display**, **Settings** and **This run**. Access starts open
  when the browser needs a name, the lab word, or the rig's Remote switch.
  Name and word remain outside the gated setters. Readout size sits beside
  the readouts. Display retains window, median, fast polling and
  presets; each pressure chart retains its own axis switches and pills.

  **Settings** is the group the three moved setters live in from 4.12.0 —
  QMS sync with its own state pill, Sampling, and Gauges with mode and
  range. It is folded by default, because a shift does not touch it, and
  whether this reader left it open is remembered in their own browser
  (`controlunit.settings.open`, wrapped in try/catch: a browser that stores
  nothing simply starts folded every time). A deep link into one of its
  sections still wins over that memory — `revealSection` opens every
  `<details>` between the page and the target, so `#sec-gauge` inside the
  Gauges fold inside the Settings fold inside the rail lands with both open.
  Observe hides Settings, being the mode that hides what drives the rig;
  Monitor keeps it, because there the whole right rail is a drawer summoned
  from its own edge and that drawer is the only way to reach those three.
  Since 4.8.0 this is the unified Live surface: Operate shows the controls,
  Observe hides hardware controls, and Monitor gives readings the window.
  Modes switch in place without clearing browser history or changing outputs.
  `/control` remains an Operate alias; old `?mode=normal` means Observe.

  Both surfaces render a shared template partial and use the same drawing
  implementation. On Control, the Live script owns the state and series
  polling; Control receives that state through an event and requests an
  immediate refresh after a command. There is no second periodic state
  request. Commands still pass through the existing queue and rig gates.

  A flat curve normally steps out of the scale while another curve moves.
  Clicking its `flat` pill now restores it explicitly and remembers that
  choice. Off/on also restores it; a preset resets explicit overrides to
  automatic behavior. Nonpositive values on a log axis remain unplottable.

## Machine-local configuration

Neighbour addresses live in `~/.controlunit/neighbours.yml` on the machine
that serves the page, never in the repository:

```yaml
pihti-diagram:
  url: http://pihti:5000
  open_url: http://pihti.local:5000
  where: on this Pi, as a system service
  start_how: on the Pi itself, as a system service
  start: sudo systemctl start pihti.service
pihti-log:
  url: http://ak-office.local:4310
  where: on the office Windows PC
  start_how: from the office PC, as lab pihti-log
  start: lab pihti-log
```

`url` is required. `start_how` and `start` are optional and become the
**Start** fact on that service's card: `start_how` is the plain words a
reader understands without a shell, and `start` is the literal line that
starts it *there*, copied onto the card exactly as this file writes it and
kept behind the card's `show`/`hide` toggle. Neither is ever guessed — a
card whose entry says nothing shows an em dash rather than a command
invented from the service's name, because a line that does not work on that
machine is worse than no line at all. An entry that gives `start` and no
`start_how` leaves the words to the card, which says *"Started by a command
on its own machine."* rather than putting the command where the meaning
belongs. `where` is still read and still carried by `/api/neighbours`; it is
no longer a row on the card, because the start words already name the
machine and three cards across the reading column have no room to say it
twice.

`open_url` is optional and exists because two different machines follow that
link. **`url` is the address this rig asks from; `open_url` is the address
the reader's browser opens.** They are usually the same and the field is
usually absent. They were not the same on 2026-09-07: the diagram's card
said `ok`, because the Pi resolves the bare name `pihti` on its own network,
and the Open link did nothing on a Mac, which resolves `pihti.local` and the
numeric address but not the bare name. A green chip is the rig's own
measurement and was never a promise about the laptop reading the page, so
where the two names differ the file says both, the card opens the one a
browser can use, and it prints that address under the link. This
is a separate file on purpose: the program
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
since the log prints display names — except where two people in the roster
are spelled the same, when each of them is offered as *"Display Name
(username)"*, because a list showing one word twice tells nobody which
colleague the log will name. Nothing is merged and no identity is renamed;
a name nobody shares is untouched, and a colliding entry with no username is
left as it stands rather than given an invented one. The file is reread whenever its
modification time or size changes, and never looked at more than once a
second. A missing, unreadable or malformed file means no names, and the
Acting-as field stays the free-text box it has always been.

The Pi has no Dropbox and no vault, so the copy comes over the LAN. PIHTI
Log serves the vault's roster at `GET /api/roster` on the same origin this
rig already asks `/api/health` of, and whenever the neighbour probe finds
that service answering, the rig fetches the roster behind it and rewrites
its own copy. The ask rides on that probe and keeps no clock of its own, so
the rig asks the office PC for names exactly as often as it already asks it
how it is — at most once in ten seconds, with the same two-second
patience — and never more.

Three rules that copy holds to. It is never written in halves: the file is
written beside itself and moved into place in one step, so a reader sees
the whole old roster or the whole new one. A copy that already says the
same thing is left alone, so an unchanged roster costs no write. And the
last copy stands whenever the answer is anything but a complete roster — no
answer, a `404` from a vault with no roster, a body that is not a roster, an
empty list — because a name the log has been spelling correctly for a month
should not disappear because the office PC is off. When this machine's copy
was last confirmed is on the Control tab, on the Acting-as card's own
heading line: *"· PIHTI Log 14:02:57"*, or *"· names not read yet"*.

The push script stays. It is what a brand-new Pi needs once, and what a
machine that cannot reach the office PC uses. Names are
people, so the file itself never enters git; the script does. Run it again
whenever the roster changes and the rig cannot reach the journal, and the
Control tab picks the new list up
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

### The lab's word

One more rail on the same fence. The machine serving the page may hold a
word in `~/.controlunit/fence.txt`:

```
plasmabox
```

One line, the word, surrounding whitespace stripped. **An absent or empty
file means no fence** — every off-rig dummy run and every test behaves
exactly as it did before — and the file is reread on the same terms as the
roster: whenever its modification time or size changes, and never more than
once a second, so a word changed in the lab takes effect within a second
and closes the fence again on every browser that had passed the old one.

It is a fence, not a secret. It keeps "oh, I found this webui, let's push
some buttons" from becoming a gas line moving, and nothing more: it is
compared as plain text, it is stored on the machine in the clear, the
browser carries it in a cookie, and it is **never anybody's password** — do
not put one there. Like the roster, the file itself never enters git.

## Off-rig development

The dummy hardware stubs let the whole program, web view included, boot on
Windows and macOS from the shared `hardware-dev` environment. A scratch run
binds loopback on a confirmed-free port with `HOME` redirected, so the data
folder and log file land outside the owner's own folders:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -m controlunit.main --web --host 127.0.0.1 --port 48937
```


### Baratron readings near zero

A negative displayed value stays a number: the signed reading in the value
slot, in the value's own size, with its unit, and the `below zero` tag in
the name row beside it. Through 4.11 the card replaced the number with the
words "Below zero" and added a `Residual …` line, so a Baratron sitting on
its own baseline swapped between words and digits from one poll to the next
and grew a line while it did — "terrible", and the reason both are gone
(queezz, 2026-09-10). Linear plots keep signed data. Log plots omit
nonpositive values, label that exclusion separately from missing data, and
leave gaps across excluded samples. With no positive values, the chart
explains the log constraint instead of displaying an arbitrary pressure
axis.

No system detection limit is characterized in the channel registry. Full
scale and transducer resolution do not establish a validated detection
limit for the installed transducer, electronics, zero drift and acquisition
chain. Positive near-zero readings are not censored using an invented
cutoff. Establish a documented per-channel limit before replacing those
readings with a less-than-limit indication. This page is where that
reasoning lives: the Baratron panel used to carry a paragraph of it under
its own legend, which is the lecture the fleet's `WEBUI.md` Teaching
section forbids — a data surface states, and the reading room explains.


Monitor (4.8.5) uses the viewport width and shares available height among
active plots, with a minimum usable plot height on short screens. Window
and Median move from the display panel onto Monitor without duplication.
Monitor defaults to big readouts and remembers its own small/big choice;
Operate and Observe retain their existing size preference.

Pressure plots can be grouped by gauge type or by vessel (Pu with Bu, Pd with Bd). The browser remembers the grouping and separate axes for each grouping. Vessel plots share one pressure axis per pair and retain the measured or zero-subtracted values: no alignment offset or normalization is applied. Channel visibility, smoothing, and baseline commands keep their existing meaning. Nonpositive values remain omitted only on logarithmic axes.

Mass-flow click steps edit only the local draft, bounded by the server-declared limit. Set sends a validated integer millivolt value; Zero remains an immediate zero command. The applied and measured displays come from rig state, never the queued request. Polls initialize the draft once and do not overwrite an edited value.

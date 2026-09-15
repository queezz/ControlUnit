# Directions

Open work only. A session records what it did in `.agents/log/`; this file
holds what is still undecided or unbuilt.

## Decisions waiting on queezz

- Should the Live tab's Plasma preset keep an ion gauge beside the two
  Baratrons, or is the current plus the Baratrons the right set? — the
  owner's call. 4.6.0 shipped two presets over the per-curve switches and
  this session chose their curve lists, because the design did not name
  them: **Vacuum** shows Pu, Pd, Bu and Bd and hides the current chart, and
  **Plasma** shows Ip, Bu and Bd and hides both ion gauges — on the reading
  that during a discharge the chamber sits at a pressure the Baratrons read
  while the ion gauges are off scale or switched off.
  Stakes: only which curves are on screen after one press; a wrong list
  costs an extra press and never a measurement.
  Recommendation: run a discharge once with Plasma pressed and say whether
  you missed the downstream gauge Pd.
  Safe default: the lists stand as they are. Either way it is one line in
  `PRESETS` in `controlunit/web/server.py`.

## Work only queezz can do

- Restart the rig onto 4.18.0 from its desktop shortcut — owner work
  pending. On 2026-09-15, on your word "fix then deploy", master was pushed
  and the Pi's checkout at `~/work/aktest` pulled while the program was
  not running; 4.18.0 (the upstream gauge `Pu2` on channel 16, with its
  own exponent selector) followed the same way. `~/.controlunit/kikusui.yml`
  on the Pi now names the supply at its lab address (copied over scp on
  your word, and the supply answered one read-only identity query with
  output off), so the first Start after the restart records
  `kikusui_*.csv` beside the ADC file and shows the supply's V and I on
  the Cathode dock and the WebUI. Everything from
  4.6.0 up is new to the rig, which last ran 4.14.1. From 4.6.0: the Live
  charts stop growing on a Retina
  Mac; an idle rig reads `ok` instead of `degraded` on all three service
  boards; the rig says whether it is stopped, measuring only, or holding
  gas or the cathode, on its own Live tab and on all three service boards;
  the Lab tab breaks where the other two boards break; each chart carries
  the switches for its own curves and a flat curve steps out of the way of
  the one that is moving; the Log's counts stop contradicting each other;
  two colleagues spelled the same way are told apart; the lab's names
  refresh themselves from the journal instead of waiting for the push
  script; the Live tab has a Monitor mode that gives the charts the whole
  window, and a Vacuum and a Plasma preset over the curve switches; and the
  Control tab's presses stand in one faceplate with their numbers beside
  them.
  Done when: `http://pihti:4187/api/health` reports 4.18.0 and, with
  acquisition off and every output at zero, `status` reads `ok` with the
  detail "idle, not recording".
- Add the Mac-reachable address to the Pi's neighbours file — owner work
  pending. On your Mac the Pi's bare name `pihti` does not resolve, while
  `pihti.local` and the numeric address do, so the diagram's Open link on
  the Lab tab did nothing even though its card said `ok`: the chip is what
  the rig reached, the link is what your browser tries. 4.4.0 lets the two
  be different. On the Pi, in `~/.controlunit/neighbours.yml`, add one line
  under `pihti-diagram` beside its `url`:

      open_url: http://pihti.local:5000

  and the same for `pihti-log` if the office PC's name behaves the same way
  from the Mac. Nothing else changes; the rig keeps probing the name it
  already uses.
  Done when: the diagram's Open link on the rig's Lab tab opens the diagram
  from your Mac, and the address printed under that link is the one that
  worked.
- Push the lab's roster to the rig once, from the office PC — owner work
  pending. `scripts\push_roster.ps1` copies the vault's
  `People\operators.json` to the Pi's `~/.controlunit/`. Only once now: from
  4.5.0 the rig refreshes its own copy from PIHTI Log whenever that service
  answers, so this is the first copy on a Pi that has none, and the fallback
  for a day the office PC is unreachable.
  Done when: the Control tab's Acting-as field is a list of names rather
  than a text box, and its heading says "· PIHTI Log" with a time.

## Ready to build

- Kikusui follow-up after the first read-only recorder (owner decision
  2026-09-14): collect ordinary manual discharges and bakes before fixing PID
  or setting filament-condition alarm thresholds. 4.15.0 records a separate
  timestamped Kikusui CSV, including manual command, with explicit LAN-loss
  rows and recovery. Setup is in docs/hardware/kikusui-lan.md. Deployed
  2026-09-15: the Pi's checkout is at 4.18.0 (4.17.1 fixed a stale
  recorder reference that blocked every later Start after one slow stop);
  its `kikusui.yml` names the supply. First manual discharge recorded
  2026-09-15 (`cu_20260915_184419.csv` and its sidecar): the owner's
  assessment, "full manual gas and cathode ... Very good plasma, 15 min.
  Constant current" — 18:54 to 19:10, 0.77–0.79 A on the Hall sensor,
  the supply flat at about 16.5 A and 7.7 V, drive and gas untouched.
  That is the baseline the PID rebuild starts from. The cable/address are
  established in the lab record and read-only SCPI was verified with
  output off.
  4.17.0 publishes fresh Kikusui V/I in Qt, full WebUI cards and a separate
  `/api/state` `kikusui` object. Later: retire
  the unwired analog placeholders with a versioned data contract, and make
  PID engage on an already ignited discharge with a smooth handover from
  manual filament current. Do not silently redefine the old ADC columns.
  Fix elapsed-manual-time integral saturation, the post-limit 1000 mV offset,
  and manual-command CSV metadata before relying on that loop; define a
  telemetry-dependent PID's loss/hold/off response before implementation.
  Filament monitoring should compare measured V/I and VI at matched operating
  conditions, with a healthy baseline and no automatic thinning diagnosis.
  Evidence: docs/diagnostics/2026-09-14-run-and-kikusui.md.

- The PID rebuild, for the week queezz is away (his ask, 2026-09-15:
  "What about my PID? Can it pick up from running plasma?" — today it
  cannot: enabling it after a manual stretch neither resets its clock nor
  starts from the held drive, its integral arrives saturated and the
  first command is 5500 mV, which on 2026-09-14 put the plasma out; and
  "for the PID, we need to log the success/failure, a way to improve the
  tuning ... if it's not painful, maybe we do it anyways. Cause plasma
  changes, things change"). One packet, a backend build with no UI law
  to route through beyond the two buttons it already has:
  - Bumpless pickup on a lit discharge: at engage the integrator is
    preset so the first output equals the cathode drive already held, the
    loop's clock starts at engage, the integral does not wind while the
    output sits at a clamp, and the post-limit 1000 mV offset is removed.
    Engage is refused, with its reason in the log and on the page, while
    Ip is below an ignition threshold (a number queezz sets; a safe
    default well above the -0.33 A off-plasma baseline plus its noise),
    so the loop never tries to light the plasma. Hand-back to Manual
    leaves the drive where the loop last put it.
  - The held quantity is a choice, not a rebuild: plasma current as now
    (Ip from the ADC), or the cathode current, or the cathode power U·I
    from the Kikusui reading — item (a) above is his to settle by trying
    them. In the two Kikusui modes a stale or lost telemetry holds the
    last output and says so, never drives on a stale number (the
    telemetry-loss policy the Kikusui item asked for).
  - A tuning log, always on, as cheap as the Kikusui sidecar: one file
    beside each run, `pid_<stamp>.csv`, one row per loop step — time,
    mode, held quantity, setpoint, measured, error, P, I and D terms, raw
    and clamped output in mV, and one row for every engage, hand-back and
    refusal with its reason. Gains and period in the header. Nothing in
    the ADC file changes.
  - Tests drive the loop offline with a recorded run (the 2026-09-14 file
    reproduces the 5500 mV) and prove the first command after engage
    equals the held drive.
  Evidence for the defects: docs/diagnostics/2026-09-14-run-and-kikusui.md.

- Coordinate a PIHTI Log action to attach all known ControlUnit parameters as
  an immutable instant snapshot, a table and optionally a picture; a clearly
  labelled short averaging window is an option, not a fixed owner choice.
  Request posted on the owner's explicit word, 2026-09-14, as
  `20260914-86630ead-525f3f` to `code/pihti-log`. The Kikusui snapshot now rides in
  `/api/state` under `kikusui` (4.17.0),
  with independent freshness; never present legacy Ci/Cv as PSU measurements.

- A command line for the rig, over the web API it already has (queezz,
  2026-09-09: "Do you have cli to drive the ControlUnit? I think not. I
  think that'd be useful for tests and diagnosis"). Nothing exists today:
  the only ways in are the rig's screen and a browser. Every setter is
  already a `POST /api/...` gated by the Remote switch, the operator lock
  and the lab's word, and `/api/state`, `/api/series` and `/api/log`
  carry everything a browser reads — so a CLI is a thin client of those,
  never a second path into the workers. Shape: `controlunit-cli state`,
  `watch` (state and new log lines as they arrive, for a session
  watching him drive), `log --since`, and the setters (`gas 1 1500`,
  `plasma 0.5`, `cathode 1900`, `off`, `zero Ip`, `start`, `stop`),
  each printing the rig's own applied/refused answer; the name and the
  lab's word from a machine-local file, never git. Off-rig it drives the
  dummy instance, which is what the tests want. Not urgent beside the
  mobile view: "Good mobile view is best. But still, some cli is good."
- Put upstream pressure Pu beside the gas controls on a phone during manual
  Ar let-in (owner request 2026-09-09). Operate still stacks readouts below
  the controls. The 4.12.2 mobile pass makes gas lines fold independently
  and removes the mode selector overlay; colocating Pu remains open.
- Keep the pressure grouping display choice available when Remote is off.
  Browser QA on 2026-09-10 found By gauge / By vessel disabled by the gate
  although they change only the local plot arrangement. Setter gating must
  remain intact.

- The owner accepted the fused Control layout on 2026-09-09. The five
  follow-up corrections ship in 4.7.1 (see the dated log): aligned navigation,
  open gauges, group colors, useful empty-plot hints and clear saved identity
  and access. These and the earlier fused-layout/Bu work in the brief below
  are implemented. Remaining requests in that brief still need review.

- The 4.18.0 review (queezz, 2026-09-15, first run on the restarted rig,
  with six screenshots; "Don't just jump on to it. Log it, analyze the UI
  and design improved version, then build it"). His words, then the
  design this session drew from them, which is what gets built next.

  What he saw:
  - "Big is somewhat smaller than small. The cards and all. It's very
    inconsistent." "in big it got a bit better, but that text overshadowing
    numbers? Big means BIG NUMBERS first. And recognizable."
  - "I restarted acquisition, and I had to press 1e-6 for pu2 for it to
    take affect, but it was already selected. So it's a UI lie." (A real
    defect: Start pushed only the first gauge's settings into the new
    worker. Fixed in 4.18.1, pull pending an idle rig.)
  - "the IGs controls bundled with 'settings' is bad. Moreover, the
    sampling time and the 'QMS sync' which is my LED + signal out I use
    for marking experiments sometimes, take too much. I guess we can make
    it tiny, recognizable, and put it somewhere near the 'measuring' and
    'live' at the top. Visible, not intrusive, easy to find and change."
  - On Window: "It's copied from qt GUI, and it's somewhat ok to use, but
    I can't help but feel a bit uneasy about this in WebUI. Feels wrong."
  - On a chart with every curve off (the stub with "Click a pill to show
    a curve"): "we now have two states for 'collapsed'. And I think it's
    useful to hide a curve in a plot, but collapsed plot should be, well,
    collapsed. So the pill of a curve selects/deselects a line to be
    plotted or not, and a card collapse is its own. We already have that."
  - "Kikusui readouts. Why separate? It's a control panel, maybe we don't
    separate that. Well, it is special, but it is the Cathode voltage
    current. That it happens to be kikusui and read differently is
    irrelevant for operation. Operation means we can see as much as I
    connect via hardware to our GUI/WebUI control panel."
  - "I like the size and style of the Kikusui, though. feels better and
    bigger and more readable then, well, my first complaint, the 'big' in
    the main numbers panel."

  The design (this session, 2026-09-15; built as 4.19.0 unless he cuts at
  it first):
  - One readout card for every measured value, drawn as a panel meter
    (his sketch, 2026-09-15): the name small in the top-left corner with
    a state tag after it, the unit small in the bottom-right corner, both
    placed on the card's border and out of the flow, and the digits alone
    across the middle — sign always shown, mantissa large, a small "×10⁻"
    and then the exponent digit at the mantissa's full height ("Like
    5.00E-3, but nicer"). "big" sizes the digits from the card's width;
    "small" is the same card scaled down to about three rem. The "below
    zero" tag is dropped (owner decision 2026-09-15: "We have a sign for
    it"); "zeroed" and the cathode cards' freshness tags stay.
  - The Kikusui voltage and current join the strip as two more cards,
    Cathode V and Cathode I, in the cathode's own colour, with the same
    freshness rule they have now (stale, unavailable or stopped shows a
    dash and the tag says why). The separate Kikusui panel goes; the
    folded row carries eight values.
  - Sampling and QMS sync leave the rail. They stand on the status line
    beside the measuring and live pills as two small controls: Sampling as
    one compact segmented pill of its four times, QMS sync as one pill
    with a sliding thumb (the house's two-state control). Gated exactly as
    before (Remote, the lab's word, the operator lock; sampling needs a
    run). The Settings fold dissolves; Gauges becomes its own rail card
    titled "Ion gauges", its blocks headed "Upstream · Pu2" and
    "Downstream · Pd" (owner decision 2026-09-15: "Pu2 is ok for a short
    name, but in the gauges card... Ion Gauges: upstream/downstream is
    better"; the short name stays beside so it matches the readout cards),
    each gauge's place named once in settings.yml and read from there by
    the web card and the rig's own dock rows.
    The anchors #sec-sync, #sec-acquisition, #sec-gauge keep landing.
  - The Window card leaves the rail too: one compact choice, "last 5 m",
    on the Pressure plots toolbar line beside By gauge / By vessel, the
    same eight spans, remembered as now. Whether the WebUI should instead
    zoom by dragging on a chart is his call, below.
  - A chart whose curves are all off keeps its canvas and axes, empty,
    with its pills; the hint sentence goes. Folding is the one way a
    chart collapses.
  - The Cathode card carries the supply's OUTPUT lamp (queezz, 2026-09-15:
    "Make it good size green circle, as on the physical PSU. So it's 'in
    sync'. Green when on, grayed a bit when off"): a large circle on the
    card's heading line, green while the Kikusui telemetry is fresh and
    says output on, grey while it says off, and dim with no colour while
    the telemetry is stale, stopped or not configured, with the word
    beside it. It is a lamp: it reads the supply and presses nothing.
  - Nothing here changes what is recorded.

- Design directions from queezz, 2026-09-15, during the first 4.18.0 run
  with the Kikusui recording live (1.078 V, 5.050 A, output on, beside a
  599 mV manual drive) — "write it down while I'm on it":

  a) The plasma PID's variable. His words: "I need PID for keeping cathode
     current constant... I think. Or maybe the power. Cause filament
     thinning out results in less current at the same voltage.. ah.. well,
     less electrons, so plasma current drops. So if we simplify PID from
     keeping plasma current constant to keeping cathode power constant,
     most likely the plasma current will follow and stay constant. We can
     test some of it out. I need to work out which one it is. Yeah, power
     ~ U^2/R, R ~ L/A... and rho depends on the temp... so maybe power
     it is." Not a build order yet: which quantity the loop holds —
     cathode current, cathode power, or plasma current as now — is his to
     work out, and the Kikusui record is what he works it out from. What
     software can do meanwhile: keep recording U and I at 2 Hz beside
     every manual discharge, and offer both I and U·I as candidate
     process variables when the PID is rebuilt (the directions item on
     PID handover above already says the loop engages on an established
     discharge and never at ignition).
  b) The cathode current joins the plasma current chart: "so it'll be
     obvious when plasma is on. Data would be there for post processing,
     but this way it's obvious what's happening. Is it the Hall sensor
     drifting or the plasma died." Build: the Kikusui current as a second
     curve on the Plasma current panel, in the cathode colour, with its
     own legend pill, on its own axis or scale where amperes of filament
     current would swamp a plasma current of tenths — its samples carry
     their own timestamps at 2 Hz from the sidecar, so the web ring
     records them as their own series beside the ADC rows and `/api/series`
     serves them by name. Nothing recorded changes; the sidecar file stays
     the record. Queued after the 4.19.0 readouts and rail work.
  c) A letter to the PIHTI Diagram about its plotter: "to update the
     plotter properly. To include new data, and to manage it properly and
     maybe arrange lines and log/lin as we already do here. And of course
     export all data. Since cathode current now lives in a separate file."
     What the letter carries: the ADC file's new columns (`Pu2`, `Pu2_c`,
     `IGmode_Pu2`, `IGscale_Pu2`), the separate `kikusui_<stamp>.csv`
     beside each `cu_<stamp>.csv` with its own `date` column and 2 Hz
     cadence (schema `controlunit-kikusui/v1`, fields in
     docs/hardware/kikusui-lan.md), the ask that its plotter draw both
     files on one time axis with per-curve switches and log/lin as this
     Live tab does, and that its export carry every column of both files.
     Posted 2026-09-15 evening as `20260915-ec9708ab-ef1123` to
     `code/2024-interactive-diagram`, on his "does the diagram know about
     the new data"; it also carries the consult-not-overwrite shape and
     the coming `<name>_off` marks. A reply is welcome, nothing blocks.
  d) Backup of the rig's data to the NAS, the share now named: "We would
     backup to \\10.249.254.52\Public\Kuzmin\<pihti-data> (or similar).
     But I need to ask for credentials, I always forget." This answers the
     first of the NAS item's questions below (the address and share); the
     others stand (push from the Pi or pull from the office PC, how often,
     marking a finished run). Credentials are never in git: a machine-local
     file on whichever side does the copying.
- Ask the NAS's keeper for credentials for `\\10.249.254.52\Public\Kuzmin`
  — owner work pending. Nothing about the backup can be built or tried
  until the copying machine can open that share.
  Done when: the share opens from the Pi (or the office PC, whichever
  will copy) with a saved credential, and the credential lives in a
  machine-local file named in the NAS item, never in git.

- The two ion gauges are shown as IGu and IGd, and the file explains
  itself (queezz, 2026-09-15: "now yes, we have two of Pu. One is Pirani,
  another is IG. So we can say IGu IGd. And.. I don't want to change the
  saved files header because of this... But we can always make a good
  header comment explaining which one is which, what units, and all that,
  the provenance"). Build, after the 4.19.0 readouts slice:
  - A display name per channel in settings.yml (`Label`), read once and
    set in type (queezz: "Pu2 is a terrible UI. Like we have no
    typography, no superscripts.."): the label is written plainly with an
    underscore before the subscript — `I_p`, `P_u` for the Pirani, `IG_u`,
    `IG_d`, `B_u`, `B_d` — and every screen renders the part after the
    underscore as a real subscript, the web page with `<sub>` markup and
    the rig's Qt labels with rich text; the plain form is what the file
    header and any typed reference use. Everywhere a person reads a
    channel name — the readout cards and the folded row, the legend pills
    and chart titles ("Upstream · P_u + IG_u + B_u", typeset), the Ion
    gauges card ("Upstream · IG_u"), the rig's dock rows and value
    browser — shows the label. Everywhere a machine reads
    one — the CSV columns (`Pu2`, `Pu2_c`, `IGmode_Pu2`, `IGscale_Pu2`,
    `Pd`, ...), `/api/state` and `/api/series` keys, `/api/gauge` bodies,
    the browser's remembered choices — keeps the channel name. Nothing
    recorded changes and no column is renamed.
  - The ADC file's comment header grows a provenance block, one line per
    signal column: channel name, label, what it is (the settings'
    Description), ADC channel and gain, conversion function and unit, and
    for an ion gauge the two columns that carry its mode and exponent —
    plus one line saying the Kikusui sidecar's file name pattern and that
    it carries the cathode supply's own measurements on its own clock.
    The `# Columns` and `# Signals` lines stay exactly as they are so
    every old reader still works; a test reads a written header back.
    The descriptions in settings.yml are corrected on the way: `Pu` is
    "Pfeiffer PKR251 full-range gauge, upstream; its Penning stage does
    not ignite, so it reads as a Pirani" (queezz, 2026-09-15), not the
    misspelt "Pfeffer Single Gauge".
  - PIHTI Log and the Diagram are told by letter, because their tables
    and plots will want the labels too.

- A device can be declared off, so the record knows a number is nonsense
  (queezz, 2026-09-15, after turning every PSU off with the rig still
  logging: "the rig still searches for it. We need a toggle. Thing off.
  Also for IGs. So we don't collect nonsense signal. Or at least know when
  it is from the log file, without looking at pihti-vacuum"). Design:
  - One "off" switch per instrument that can be off while the rig logs —
    the cathode supply (Kikusui) and each ion gauge — on the rig's dock
    and on the web Cathode card and Ion gauges card, the house's sliding
    pill, gated like every setter. These switches alone decide what the
    file marks (queezz, 2026-09-15: "ControlUnit NEEDS a switch. Why
    depend on a separate server?"). The flow between the two runs the
    other way, on his word the same night: "we can rather ping control
    from diagram to check upon values, pressures and on/off. We still
    operate it as is. And tell what the control actually sees." So
    `/api/state` carries each instrument's off mark beside its value, and
    the PIHTI Diagram reads ControlUnit — values, pressures, on/off — and
    shows what the rig sees; a letter to the Diagram once the switches
    exist. ControlUnit may consult the Diagram's vacuum state as advice
    and never overwrites it ("control doesn't overwrite diagram. It
    consults"). "PSUs off" in his words means the plasma power supplies.
  - Heuristics suggest, the operator decides (queezz, 2026-09-15: "An
    off IG unit usually reads low values.. we note those, and suggest").
    An ion gauge whose raw volts sit near the floor for a minute gets a
    "looks off?" note beside its readout and a log line, never an
    automatic off mark; today's file has the example (Pu2 raw 0.0003–
    0.0009 V from 18:49:55 while the plasma ran, converting to 3e-10
    Torr). The same shape for "time to zero the Baratrons": a note when
    a Baratron reads steady and negative, or when the chamber is known
    to be far below its range, suggesting Zero, never pressing it.
  - Validity floors per channel, the first one given: Bd is meaningful
    above 1e-5 Torr and reads its offset below that — tonight's −0.8
    mTorr is a chamber near 1e-9 Torr, far under what it can read
    ("historically we know when that one works. Above 1e-5"). Below its
    floor a channel's readout says so in its tag and its curve steps out
    of the way, the way a flat curve already does; the number is still
    recorded. The other floors (Ip without plasma, Bu) are still his to
    name in the noise-floor item below.
  - Declared off, the Kikusui recorder stops polling and writes one
    `status=off` row (no LAN-lost warnings, no retries every 5 s); an ion
    gauge declared off keeps its raw volts in the file but its converted
    column is written as NaN, its readout reads "off", and its curve is
    not drawn. Every change is one event line in the log with the time.
  - The ADC file learns it: one more appended metadata column per
    instrument, `<name>_off` (0/1) — appended after the existing columns,
    never inserted — so a reader of the file alone knows which stretches
    to discard. PIHTI Log and the Diagram are told by letter with the
    other column news.
  - The toggles rest on "on" at Start; a rig started with an instrument
    already off should say so within the first minute (a warning when a
    gauge reads at its floor for a minute, later).
- Monitor mode wastes the top of the screen (queezz, 2026-09-15, on a
  1920×1080 monitor: the mode switch, the two pills, Display and Leave
  full screen, then the Window and Median rows take about 220 px before
  the first readout). Design: one slim strip — the pills at the left, the
  Window and Median choices as compact segmented pills in the middle,
  small/big, Display and Leave full screen at the right, the mode switch
  folded into the same line — so the readouts start about 60 px from the
  top and the charts get the rest. Same family as the status-line
  Sampling and QMS sync controls in the 4.19 design above; build them
  together.
- May a session stop and start the rig's program, and under what
  conditions? — the owner's call. Today the rule is that the restart is
  his, always (AGENTS.md); he asked on 2026-09-15 whether agents could
  "stop the app and start anew in the rig ... shift towards a process",
  and wants "an option to just kill the app so nothing is talking to my
  hardware".
  Stakes: killing the process does not zero the DACs — the cathode DAC
  holds its last voltage after the program dies (2026-08-19, the plasma
  ran on after the reader died), so a kill leaves the hardware driven
  with nobody watching. Only a stop that turns the outputs off first is
  a safe stop; a physical off is the only guarantee.
  Recommendation: build the two pieces below first, then allow a session
  to stop (never merely kill) and to start when the rig is idle and no
  output is live, as the pull rule already reads, and keep the first
  start of a day and any start with a person at the rig his.
  Safe default: the rule stands; sessions pull and never restart.
- A stop the process cannot skip, and the program as a process (design
  for the question above; no UI law involved beyond the existing Stop):
  - On SIGTERM (and SIGINT) the program runs the same path Stop does —
    outputs to zero, recorders closed, workers joined, hardware first —
    before it exits; a test sends the signal to a dummy-hardware instance
    and reads the DAC setters' last commands. `POST /api/stop-all` already
    exists for the outputs; a `POST /api/quit` behind the same gates asks
    the program to stop that way, so a session's "stop" is a request the
    program honours, never a kill.
  - `scripts/run_controlunit.sh` becomes a systemd user unit on the Pi
    under the desktop session (DISPLAY set; PyQt needs the display it
    already has, nothing more), registered with the Pi's own lab helm, so
    start/stop/restart/status are commands with a log over SSH; the
    desktop shortcut stays and calls the same unit. A dead program can
    then be restarted by a watchdog with the same graceful path.
  - Splitting acquisition from the Qt window into a headless service the
    window and the web view both attach to is the larger step; not
    needed for this and not proposed now.

- Should the OUTPUT lamp on the Cathode card also press — switch the
  Kikusui supply's output on and off from a browser — or only show?
  — the owner's call. He asked for "the output on/off button ... in
  sync"; the lamp alone is what 4.19.0 builds.
  Stakes: pressing crosses the 2026-09-14 rule that the Kikusui link is
  read-only (its client refuses every command but four measurement
  queries, and the recorder never drives an output); it would be the
  first browser control that switches the cathode supply itself, behind
  the same gates as every setter.
  Recommendation: the lamp now; if it must press, off-only first, as a
  second Stop-all-outputs kind of press, and on only after that has been
  used for a while, because switching a filament supply on from a phone
  is a different press from switching it off.
  Safe default: it shows and never presses.

- Should the time window stay a set of fixed spans (now a compact choice
  on the charts' toolbar) or become direct: drag across a chart to zoom,
  double-press to go back to live? — the owner's call. He said the fixed
  spans, copied from the Qt window, "feel wrong" in a browser without
  saying what would feel right.
  Stakes: only how the eye chooses a span; nothing recorded changes.
  Recommendation: keep the fixed spans on the toolbar for now and try
  drag-to-zoom on one chart in a later release, because a phone thumb
  drags badly and the spans still have to exist for it.
  Safe default: the compact fixed spans stand.

- The 4.6.0 review (queezz, 2026-09-08, first look at the restarted rig;
  "log this and design, don't dev" — he is taking the design to GPT too,
  so this item is the brief and the record, not a build order). What he
  saw, in his words, then a proposal.

  Defects and complaints:
  - "Bu is not visible. There's data, but it's not showing." The 4.5.0
    rule that a flat curve steps out of the way hides a channel that has
    data; the legend reads `Bu flat` and he reads it as gone.
  - "log/lin in a card far from the plots is bad. We have space in the
    plot cards." The Lines card's two scale rows belong on the charts.
  - "View card. Don't need tiny explainer text. And the card reads
    crowded. There are two jobs, but they read as one with 5 options."
  - "Window has 'full...' explained. Only that. No need. Also full
    doesn't work. Which is fine-ish." (Full still shows what the ring
    gave; the browser's own history is not reaching the window cut.)
  - Control: "The name selector and password are inside Operation. Bad.
    We have rails for that. Main window is for operation."
  - "On this page has no meaning on my big screen. Maybe on mobile or
    maybe on a laptop. Not here, definitely."
  - "General layout reads as broken. There are numbers and names trying
    to organize. And they fail. They just crowd the page, hide the work
    surface."
  - "Start/Stop are big buttons. They warn before stopping. But they
    should be loud. STOP is stop! Not a casual button. Not a tiny pill.
    Same with the start. Don't have to be huge. But they have to be
    special and visible at a glance. Not 'where do I stop this thing???'
    Stop all outputs is crying in the mean time. Maybe stop/start are
    bigger on that rail? Stop all outputs should get quieter."
  - "The top bar is full width, while the view is not. Maybe not the
    best UX."
  - "There's still no mixed mode to control and see the current values
    and plots. And why not? Especially on a big monitor???"

  What the screenshot shows behind those words: the left rail holds one
  card, Stop all outputs, and nothing else; the gate (switch, holder,
  reason, Take over), Start and Stop, the name and the lab's word all
  live inside the faceplate's own column, above and below the setters;
  the readings stand in four separate cards to the right of it; the
  right rail is the index. So the page has a control rail with no
  controls in it and a work surface carrying the controls that belong
  in the rail.

  Proposal (a session's design, for him and GPT to cut at):
  - Every switched-on curve is drawn, always. A panel with two curves of
    different size gets a second y axis on the right in the second pen's
    colour, so Bu and Bd both read; "flat" as a state goes away.
  - The log | lin switch moves into each chart's legend row, beside its
    curve switches (the WEBUI.md amendment of 2026-09-07 already allows a
    chart's own controls in its legend). The Lines card keeps only the
    median, retitled Median; no aside text anywhere in the rail.
  - View becomes two plain rows with their own labels and no aside:
    "Show  All | Vacuum | Plasma" and "Screen  Normal | Monitor |
    Operate"; or two cards if a row cannot stay on one line.
  - Window: drop the aside; either make Full cut the browser's own
    history (the 4.1.0 promise) or remove the button.
  - Operate, the mixed mode, for the big monitor: the Control faceplate
    as a wide left column, the five readouts and the three charts on the
    right, the gate and the name in a narrow rail beyond them; on a
    laptop the same DOM stacks. Reached from the Screen row and from the
    Control tab.
  - Control: the main column is the faceplate only, groups titled in
    plain words with no numbers, no index card at any width above the
    rail breakpoint (keep it as a fold on phones only). The left rail is
    the gate (switch, holder, one reason), then Start and Stop as one
    pair of large bordered buttons — Stop in the stop colour, Start in
    the live colour, both full-width and unmissable — then the name and
    the lab's word, then Stop all outputs as a quiet full-width bordered
    button with red text, no fill.
  - The tab bar's contents align to the page's own max width so the
    brand sits over the left rail and nothing spans past the content;
    the bar's background may still run edge to edge.

- The alarm when the reader is lost, and raising the dead (owner
  decision 2026-09-07, "Hold and alarm!"). The first part shipped in
  4.11.0: the reader retries a failed I²C read instead of dying, the main
  thread logs "Reader lost" when samples stop and "Reader back" with the
  gap, and the launcher keeps the program's error output beside the data.
  What is still open: the rig's own alarm — blink the indicator LED the
  rig already has (or a new one; queezz has an easy spot to wire it) and
  buzz the display's buzzer, briefly, not continuously; the web view's
  alarm — a visible blink on the page when the data chip goes `stale` and
  spoken words through the browser's own speech synthesis ("reader lost
  on the rig"), no server-side audio; a Restart reader press (queezz,
  2026-09-07: "an option to undead the dead reader mid flight"), on the
  rig's control dock and the Control tab's Acquisition group, that spawns
  a fresh ADC worker while the DAC workers and every output stay exactly
  as they are, and keeps writing the same data file with one log line
  marking the gap — the watchdog's "Reader lost" is what makes that press
  meaningful, and the retry inside the reader is what should make it
  rare; and, later, the plasma box thermocouple (queezz, 2026-09-07): it
  is not on the Pi at all — the MAX6675 worker in the code was the old
  membrane heater's — and reading it needs a thermocouple amplifier
  module wired in first, his hardware work. Once it reads, two warnings
  join the same alarm: "no thermocouple signal" and "temperature rising",
  the second against a slope over a few minutes rather than a threshold.
- What upsets the I²C bus when the plasma arcs (queezz, 2026-09-09: "I
  need to look inside RasPi for some voltage/heating issues. Cause things
  break when we have plasma"). Measured that evening: the Pi's own supply
  is clean — `vcgencmd get_throttled` reads `0x0` twelve days after boot,
  so no under-voltage or throttling ever, core at 50 °C, and the kernel
  log carries no I²C line at all. So the fault is on the I²C wires, not
  the Pi's power: both deaths of 2026-09-09 (18:20:36 and 18:27:27) came
  while the preanode was dumping current to ground and Ip was jumping by
  amperes, and the ADC board (ADS1115 at 0x49 with its PCA9554 multiplexer
  at 0x3E) and the cathode DAC (MCP4725 at 0x60) share bus 1. Since 4.11.0
  a fault there is a logged retry rather than a death, and the stderr file
  will carry the exception's own words next time. Hardware side, his: a
  ground path for the arc that does not run through the Pi's ground, and
  shorter or shielded I²C leads to the two boards.

- A diagnostics tab for the ADC and the DACs (queezz, 2026-09-07: "it'd be
  nice to have a diagnostic tab for ADC/DAC. ADC one showing all channels"):
  every ADC channel as its raw voltage beside its converted value, the two
  DAC outputs as held, and a raw-voltage switch on Live for a channel under
  diagnosis (his other ask that day: "an option to show raw voltages for
  diagnosis"). Needs the ring to carry raw volts beside converted values
  (`_publish_step` has both; the CSV already writes both columns).
- Control and the plots side by side, the second step of the Control tab's
  density (queezz, 2026-09-07: "Ideally control plus plots should live side
  by side. Like in the GUI. For real operation. But that's maybe too
  crowded"). 4.6.0 built the first step — every press in one 384px faceplate
  with its readings beside it — and shipped Monitor mode, so the machinery
  the second step needs already exists: a mode in the address, the rails as
  edge drawers, and `MODES` in `controlunit/web/server.py` takes a third
  entry. The shape: `?mode=control` on the Control tab, the faceplate in its
  fixed narrow column and the Live charts filling the rest, rails in the
  drawer.
  What is measured, so nobody re-measures it: with both rails away the
  reading column is 1225px of a 1280px window, which is the faceplate's
  384px and 827px of charts. The faceplate itself is 840px tall, against
  644px of usable height at 1280×700 and 844px at 1280×900 — so the mode
  fixes the width and not the height, and on a short window the faceplate
  still scrolls beside the charts. Two things would have to be settled
  first: whether the charts in that mode are the Live tab's three or a
  chosen one, and whether the faceplate scrolls on its own or with the page.
  It also wants the plotting code on the Control page, which today only
  Live loads.
- Why "at a glance at 1280×700" was not reached on Control, for whoever
  wants the last of it: the faceplate is 840px of presses against 644px of
  window. What is left to cut is structural, not cosmetic — the gauge and
  baseline groups behind a disclosure (about 180px, at the cost of hiding
  controls), or dropping the left rail on Control so the faceplate's groups
  can run two-up (about 360px, at the cost of the reading column's left edge
  jumping between tabs, which the house's rail law warns against). Both are
  worth queezz's eye before anyone builds them; neither is worth doing
  quietly.
- A noise study of every channel with the rig doing nothing (queezz,
  2026-09-15, looking at 33 minutes of quiet Ip and Bu at 10 Hz: "one of
  these times one should look at our signals when doing nothing and
  identify the noise. So we might filter it better. And know the noise
  from signal"). Analysis, not code, first: take a quiet stretch of a real
  10 Hz file (2026-09-15's `cu_20260915_170626.csv` has one: Ip at about
  -0.33 A with roughly ±0.03 A of fast noise, Bu at 3e-4 Torr with a
  visible band), and for each channel report the standard deviation, the
  autocorrelation and the spectrum up to the 5 Hz Nyquist of 10 Hz
  sampling, looking in particular for mains-related lines folded down by
  the sampling and for anything the I²C reads share across channels; then
  say per channel which filter separates the noise from the signal at
  the least cost in delay (the browser's median, a running mean over the
  period as the ≥1 s sampling already does, or a proper low-pass in the
  worker), and what the noise floor is, which is the number the item
  below has been waiting for. Result goes to the vault's Troubleshooting
  folder and to docs/diagnostics/, with the numbers; any filter change is
  a separate, versioned build afterwards, never a silent change to what
  is recorded.
- Findings of the 2026-09-15 evening analysis (docs/diagnostics/
  2026-09-15-plasma-run-and-noise.md; vault note "Plasma run and noise
  2026-09-15"), each with what it asks of the code:
  - The ADC file's `PresetV_cathode`, `PresetV_mfc1` and `PresetV_mfc2`
    were 0 in all 24,708 rows of the plasma run: the manual cathode drive
    reaches the record only through the Kikusui sidecar's
    `commanded_cathode_mv`, and the gas was opened outside ControlUnit.
    The manual drive must write `PresetV_cathode` (the 2026-09-14 note
    named this; still open), and the file header should say what those
    columns carry.
  - Ip noise is the instrument's, not the plasma's: sd 0.018 A quiet and
    0.021 A at 0.79 A. Two lines on Ip only: 0.1333 Hz (7.5 s, 13–18 mA,
    present before the Kikusui was configured) and 3.3333 Hz = fs/3
    (lag-3/6/9 autocorrelation 0.72/0.60/0.52). A 3-sample boxcar puts an
    exact zero on fs/3 where a 3-median does not; 21 samples (1 s) for the
    rest; Bu and Pu want 11; Bd cannot usefully be filtered (a 109 s
    wander and a −0.8 mTorr standing offset). Whether fs/3 is the read
    schedule needs a run at another sampling rate. This is the filter
    build the noise-study item asked for.
  - The "1 A by the PSU" is not in any file: the Kikusui read 16.5 A
    (filament heating current); the discharge supply's own readout is a
    separate instrument ControlUnit does not log. Ip followed filament
    power (97 W → 0.12 A, 105 W → 0.26 A, 116 W → 0.42 A, ignition at
    18:54:14 in two samples), gas moving 0.7 % across the staircase —
    evidence for his item (a) on holding power. Inside the settled
    discharge Ip and Ic are uncorrelated (r = 0.006).
  - Off states are not self-evident in the analogue channels. Correction
    from queezz the same night: the ion gauge controllers were on all
    evening ("Imagining things. IGs are on"), so Pd's steady 1e-8 Torr is
    a live downstream reading and the 3e-10 Torr stretch on Pu2 is not an
    off state but whatever its controller put out then; the analysis read
    both as off and was wrong. What did switch off was the Kikusui, and
    the file shows it only late: `output_on=1` for 98 s after the drive
    went to 0 mV, then `unavailable` from 19:11:58. So the instrument-off
    flag must be operator-set or read from the controller — the toggles
    item above stands as designed, and the file alone still cannot tell.
  - Bu went electrically noisy 19:20:50–19:23:50 (sd 1.4e-4 Torr,
    negative excursions) with nothing logged; one 0.35 s gap in the main
    run; zero tracebacks.
- Confirm each instrument's valid range, minimum and maximum, from its
  manual and from real data, and keep the numbers in one place (queezz,
  2026-09-15: "The min max should be confirmed for our units from the
  manual and actual data. I forget!"). One table, in `settings.yml` beside
  each channel (`Valid Range: [low, high]` in the channel's own unit) and
  echoed in docs/hardware/channel-map.md and the file's provenance
  header, which the readout tags, the curve-steps-aside rule and any
  "looks off?" heuristic all read from. To confirm, per channel:
  - Bu: MKS 627, 1 Torr full scale; Bd: MKS 628B, 0.1 Torr full scale —
    the usable fraction of full scale from the MKS manual (the Baratron
    pages are in the vault's Hardware folder or the explainers' hardware
    write-ups), against the data: Bd's own behaviour says above 1e-5
    Torr, Bu's is to be read off a pump-down.
  - Pu: Pfeiffer PKR251 full-range gauge reading as a Pirani (the Penning
    stage does not ignite): the Pirani part's range from the PKR251
    datasheet (the explainers hold it), against what it read tonight
    (1.2e-5 Torr at a chamber near 1e-9 — that is its floor, not the
    pressure).
  - Pd and Pu2: the ion gauge controllers' model and range from the
    vault's Hardware notes, and what each reads against the Baratrons
    when the chamber is in both instruments' range.
  - Ip: the Hall sensor's model and range (settings say 5 A per volt
    about 2.52 V), against the 0.8 A plasma of tonight and the noise
    measured (docs/diagnostics/2026-09-15-plasma-run-and-noise.md).
  - Uc and Ic: the Kikusui PWR401L's own limits from the manual scans in
    the vault (`Hardware/Equipment/Kikusui Power Supplies.md`).
  A session can do the reading; where a manual is a scan, say which page
  the number came from. Result: the table, and a short note in the vault
  under Hardware saying where each number came from.
- A noise floor per channel, so the current with no plasma can step out of
  the way too (queezz, 2026-09-07: the current plot with no plasma is "a
  noisy waste of space"). 4.5.0 collapses a curve whose excursion is smaller
  than its own last useful digit, which catches the broken upstream gauge
  stuck at 1e-5 but not this one: noise around zero has a large excursion
  relative to its own size, and nothing in the browser can tell it from a
  real small current. Needs from queezz: below what current, in amperes, Ip
  is not worth a panel — and the same question for any other channel with a
  meaningful floor. One number each, and the existing rule then covers both
  cases.
- Sync the rig's data to the NAS (queezz, 2026-09-07: "we need later to
  build the sync to NAS feature. But not today"). The record is
  `~/work/cudata` on the Pi — one CSV per run, 1324 files today, plus
  `controlunit.log` — and nothing copies it anywhere. Needs from queezz
  before the first line: the NAS address and share, whether the Pi pushes
  (a timed `rsync` from the Pi, credentials in a machine-local file, never
  in git) or the office PC pulls, how often, and whether a finished run
  should be marked so a half-written file is never taken. The web view
  would then say on the Lab or Control tab when the last sync ran and
  whether it succeeded, one line, never a second state vocabulary.
- The upstream ion gauge shipped in 4.18.0 as `Pu2` on channel 16 (queezz,
  2026-09-15). Three of its four questions were answered by taking the
  downstream gauge's answers, and stay open only until the first file
  records them: is `Pu2` the name you want, is its controller the same
  0–10 V linear-times-exponent kind with a Pa log mode, and does the
  Pfeiffer `Pu` stay beside it — the owner's call. Each is one line in
  `settings.yml` and the docs today; after the first run, a rename is a
  new column name a reader has to know about.
- Rig code issues found 2026-09-04, ranked in the log entry of that night:
  the ADC gain button is a no-op; the whole run is held in memory and
  copied every step; a 9-hour offset hard-coded in the plot axis; the
  "two workers done" count against three workers; the PID period not
  following a mid-run sampling change. None is urgent at 0.1 Hz. Two more
  from 2026-09-07 for the hardware side, not this code: Bu swings wildly
  below its detection floor (queezz's guess, the MeanWell supply) and Ip
  wants an RC filter on its ADC input; the browser's median smoothing is
  the display-side stopgap.

## Reported, not reproduced

- Clicking the page logo produced an error before acquisition was started,
  and did not after (queezz, 2026-09-04, against 0.5.0 on the rig). Not
  reproduced off-rig: loading `/` before acquisition answers 200 on 0.6.0, and
  the logo now leads to Live rather than Lab. If it recurs, the browser's
  console line or the rig's terminal output is the evidence needed.

## Settled, kept here only until the next session reads them

- 4.11.0 (2026-09-09): "logging stopped" reproduced by queezz twice in
  one evening and read from the rig's records: the data file stops mid-row
  with no "stopped" line, the PID inside the dead reader stops moving the
  DAC, and Stop/Start brings both back — the same shape as Mizuno-kun's
  four "data logging interrupted" of 2026-08-19/20, which this closes. The
  reader now retries a failed read and logs it once, a row that cannot be
  recorded is dropped, a stuck conversion raises, the main thread logs
  "Reader lost"/"Reader back", and the launcher keeps stderr beside the
  data. The cathode has two modes on the rig's Cathode dock and the web
  Control tab: PID in amperes and Manual in millivolts, each turning the
  other off; the Settings dock's "Output voltage" row moved there. AGENTS.md
  names the neighbours: "see the pihti log" means the vault's journal file.
- 4.6.0 (2026-09-08): the Live tab has a Monitor mode — `?mode=monitor` in
  the address, the tab bar and both rails away, the charts across the whole
  window (673px of reading column becomes 1225px), the two status pills
  where they were, and the rails back as edge drawers in the diagram's own
  shape, with Escape leaving the drawer first and the mode second; a Vacuum
  and a Plasma preset over the per-curve switches, remembered per browser,
  changing what is drawn and nothing that is recorded, with a panel whose
  curves are all off keeping its legend; the Live rail's Scales and
  Smoothing merged into one Lines card to make room, at 604 === 604 with no
  slack left; and the Control tab's presses gathered into one 384px
  faceplate with their readings beside it, taking the page from 1248px to
  1024px at 1280×1000. The name and the lab's word stand outside the block
  the gate disables, because they are how the gate is opened.
- Finding PIHTI Log (order 2026-09-04, answered): "the IPs are quite
  static-ish for years on our Optical Lab VLAN. So writing it down." The
  Pi's `neighbours.yml` names the office PC as `AK-office.local`; if that
  name ever stops answering from the Pi, the address goes in that file by
  hand, exactly as the order says.
- Who may set from a browser (order 2026-09-04, answered): "stop the flow
  is fine. How about a password, but not for security... to avoid 'Oh, I
  found this webui, let's push some buttons'." Built as the roster: a name
  from the lab's list, the same list PIHTI Log reads, plus, since the
  evening, the lab's word typed once per browser (owner decision
  2026-09-07, live: "a fence one can walk over. Fence is enough").
- lab-cli removed the controlunit entry from its registry (its notes of
  2026-09-04, read 2026-09-07): the rig launches itself, so Lab never
  launched it and never could. Nothing here waits on lab-cli any more; a
  version for the rig on the office PC is the fleet map's to show, not
  Lab's.
- PIHTI Log's letter `20260904-39c8138b-140030` (read 2026-09-07): the
  health and neighbours shape accepted; its one ask, the first date the
  Pi's logger ran the ampere code, answered by letter 2026-09-07 — the run
  file `cu_20260905_105520.csv`, started 2026-09-05 10:55 under 4.0.0, is
  the first; every file before that date is millivolts.
- 4.2.0 (2026-09-07, evening): the lab's word `plasmabox` as a fence in
  front of setting ("not security, just a fence one can walk over"), in
  `~/.controlunit/fence.txt` on the Pi; and the Lab tab as the diagram's
  Services board with the three siblings' shared state meanings (PIHTI
  Log's letter `20260907-d526b38c-482393`, answered by
  `20260907-d1c08989-87a3b7`).
- 4.5.0 (2026-09-07, night): the Lab board's own numbers are the diagram's
  and the journal's — 16rem rails, 260px cards, a 14px gap — so all three
  break at the same window widths (two across and one below at 1280, three
  across from about 1415, which his Mac has), with the fact labels beside
  their values again; the rig says whether it is stopped, measuring only, or
  holding gas or the cathode, in `/api/health`'s detail, in `/api/state`, on
  the Live tab's own pills and in the check `AGENTS.md` now writes into the
  Pi-update recipe; the lab's names refresh themselves from PIHTI Log's
  `/api/roster` behind the neighbour probe, keeping the last copy when it
  does not answer, with the push script kept as the fallback; and every
  chart carries the switches for its own curves, with a switched-off, empty
  or flat curve saying so and stepping out of the axis's way. Letters
  `20260907-f9a313ab` and `20260907-95bde394` collected; notes
  `20260907-2e0205ef` and `20260907-6f353ea0` logged and acted on.
- 4.4.0 (2026-09-07): PIHTI Log's Mac audit and three owner directions of
  that day, all shipped — the Live charts no longer grow on a Retina screen
  (a panel's layout height and its drawing buffer are two attributes now);
  an idle rig is `ok`, with `degraded` kept for a run that stopped
  delivering samples and for dummy hardware; the Lab tab is the trio board,
  three cards across in one order on every machine, this program's card
  third; `neighbours.yml` may carry an `open_url` a browser can reach
  beside the `url` the rig probes; the Log's Retained and Shown are two
  labelled counts; and colliding roster names carry their username.
  Letters `20260907-023785d0`, `20260907-50ccf555`, `20260907-86d2c305`
  and `20260907-43cf71f7`, collected and answered.
- 4.2.1 (2026-09-07, night): the board in the diagram's 0.8.0 shape —
  start rows in plain words with the command behind a toggle that
  survives refresh, ControlUnit's own card starting from the rig's screen
  and never `lab controlunit`, the right rail a glance list of the six
  chips with a More press (letters `20260907-e7d85b5b-507a68` and
  `20260907-ad4abb91-ba7f13`, answered). The Pi's `neighbours.yml` wants a
  `start_how` line per neighbour, plain words, when queezz says.
- The quit button coming back ten seconds after Stop (queezz, 2026-09-07)
  was the ADC worker sleeping a whole sampling period before reading its
  abort flag; from 4.1.0 a worker's sleep wakes within a tenth of a second
  of an abort.
- Stopping acquisition no longer forces the Remote switch off (4.1.0): a
  browser may stop and start a run, so the switch stays as the person at
  the rig set it, and it is still the only place Remote is turned on. The
  operator lock is still released on stop.
- 4.0.1 (2026-09-05): setting from a browser is gated by the switch on the
  rig and the operator lock, and by nothing else; switch labels no longer
  clip; no tab prints its own name as a heading.
- Version 4.0.0 (owner decision 2026-09-04): the major number names an era,
  told in `docs/history.md`; `pyproject.toml` declares the package and the
  fleet reads its version from there.
- Sampling at 0.1 Hz on the rig is deliberate for long overnight runs
  (queezz, 2026-09-04); the web view's stale line follows the sampling
  time, so at 10 s it is 50 s.

- Diagnose and correct the ADC sampling cadence: the September 10 run requested 0.1 s but averaged 0.175640 s, with 46 intervals above 0.3 s and five above 0.4 s. The fast path waits a full period before doing acquisition work; slow successful reads also escape exception logging. Measure stage durations and overruns before attributing burst delays to hardware or GUI load. Evidence: docs/diagnostics/2026-09-10-plasma-reader.md, Timing follow-up.


- ADC timing follow-up implemented locally in 4.13.0: deadline scheduling, typed batch buffers, vectorized plotting, elapsed ready polling and stage summaries. Off-device benchmark and fault tests pass; obtain comparable rig timing before declaring 10 Hz resolved. Remaining concerns include unbounded history and queued tail/run identity at shutdown. See docs/diagnostics/2026-09-10-adc-timing-optimization.md.

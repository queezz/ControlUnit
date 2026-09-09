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

- Restart the rig onto 4.6.0, on a rig that is not acquiring and not
  holding gas or the cathode — owner work pending. `master` in the office
  checkout is at 4.6.0 and none of it has been pushed; say the word and a
  session pushes it, pulls the Pi's checkout at `~/work/aktest`, and leaves
  the restart to you. On restart: the Live charts stop growing on a Retina
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
  Done when: `http://pihti:4187/api/health` reports 4.6.0 and, with
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

- The owner accepted the fused Control layout on 2026-09-09. The five
  follow-up corrections ship in 4.7.1 (see the dated log): aligned navigation,
  open gauges, group colors, useful empty-plot hints and clear saved identity
  and access. These and the earlier fused-layout/Bu work in the brief below
  are implemented. Remaining requests in that brief still need review.

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
- The upstream ion gauge: per-channel ionization-gauge mode and range in the
  ADC worker instead of one shared pair, its exponent set from the web
  Control tab's Gauge group, a mode and scale column for it in the CSV, and
  a letter to `code/pihti-log` because the file's columns change. Needs from
  queezz: the ADC channel and gain it is wired to, a short name, whether
  its controller reads like the downstream one (linear 0–10 V times ten to
  the exponent), and whether the Pfeiffer gauge Pu stays beside it.
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

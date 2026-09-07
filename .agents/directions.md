# Directions

Open work only. A session records what it did in `.agents/log/`; this file
holds what is still undecided or unbuilt.

## Decisions waiting on queezz

Nothing waiting.

## Work only queezz can do

- Restart the rig onto 4.4.0, on a rig that is not acquiring — owner work
  pending. `master` in the office checkout is at 4.4.0 and has not been
  pushed; say the word and a session pushes it, pulls the Pi's checkout at
  `~/work/aktest`, and leaves the restart to you. On restart: the Live
  charts stop growing on a Retina Mac, an idle rig reads `ok` instead of
  `degraded` on all three service boards, the Lab tab is the trio board
  three cards across, the Log's counts stop contradicting each other, and
  two colleagues spelled the same way are told apart in the Acting-as list.
  Done when: `http://pihti:4187/api/health` reports 4.4.0 and, with
  acquisition off, `status` reads `ok` with the detail "idle, not
  recording".
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
  `People\operators.json` to the Pi's `~/.controlunit/`; run it again
  whenever the roster changes.
  Done when: the Control tab's Acting-as field is a list of names rather
  than a text box.

## Ready to build

- The reader that survives, and the alarm when it does not (owner
  decision 2026-09-07, "Hold and alarm!"): when the ADC worker stops
  delivering samples, the outputs stay where they are — the cathode DAC
  holding is what saved Mizuno-kun's depositions — and the rig says so
  without panic. Three parts. First, the reader itself: catch an error in
  the ADC step, write it to the message log, retry the read, and let a
  main-thread watchdog notice no sample for a few periods and log "reader
  lost". Second, the rig's own alarm: blink the indicator LED the rig
  already has (or a new one; queezz has an easy spot to wire it) and buzz
  the display's buzzer — it has one, no speakers — briefly, not
  continuously. Third, the web view: the Live tab's data chip already goes
  `stale`; add a visible blink on the page and spoken words through the
  browser's own speech synthesis ("reader lost on the rig"), which needs
  no server-side audio. Fourth, raising the dead (queezz, 2026-09-07:
  "an option to undead the dead reader mid flight"): a Restart reader
  press, on the rig's control dock and on the Control tab's Acquisition
  group, that spawns a fresh ADC worker thread while the DAC workers and
  every output stay exactly as they are, and keeps writing the same data
  file with one log line marking the gap — so a deposition that survived
  the reader's death gets its record back without a stop. The watchdog's
  "reader lost" is what makes that press meaningful; the automatic retry
  inside the reader is what makes it rare. And the launcher keeps the
  program's error output in a file beside the data, so the next death
  leaves its traceback. Fifth, later, the plasma box thermocouple (queezz, 2026-09-07): it
  is not on the Pi at all — the MAX6675 worker in the code was the old
  membrane heater's, not this one — and reading it needs a thermocouple
  amplifier module wired in first, his hardware work. Once it reads, two
  warnings join the same alarm: "no thermocouple signal" and "temperature
  rising", the second against a slope over a few minutes rather than a
  threshold.

- A diagnostics tab for the ADC and the DACs (queezz, 2026-09-07: "it'd be
  nice to have a diagnostic tab for ADC/DAC. ADC one showing all channels"):
  every ADC channel as its raw voltage beside its converted value, the two
  DAC outputs as held, and a raw-voltage switch on Live for a channel under
  diagnosis (his other ask that day: "an option to show raw voltages for
  diagnosis"). Needs the ring to carry raw volts beside converted values
  (`_publish_step` has both; the CSV already writes both columns).
- The roster over the LAN instead of by hand: if PIHTI Log exposes its
  names at `GET /api/roster`, the rig can refresh its copy from the office
  PC whenever that service answers and keep the last copy when it does
  not, so nobody runs the push script again. Asked of `code/pihti-log` by
  letter 2026-09-07; waiting on another ship.
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

- "Data logging interrupted" on 2026-08-19 (18:10, 18:18, 18:32) and
  2026-08-20 (14:43) in Mizuno-kun's PIHTI Log entries, read 2026-09-07
  from the rig's own records: at each time the data file simply stops
  (18:09:10, 18:15:08, 18:27:27, 14:43:22) with no "stopped" line in the
  message log, and the next line is "Starting acquisition" when he cycled
  the switch — the ADC worker thread died between two samples, and the
  window kept looking alive. The rows before each stop are ordinary. What
  killed it is not recorded anywhere: the acquisition loop has no error
  handling around its I²C reads, an exception there ends the thread with
  a traceback on the terminal, and the launcher keeps no terminal output.
  His notes name a loud cracking sound and a target current jumping
  between 2 and 8 mA, which is arcing, and arcing is what upsets I²C.
  Whether the plasma "continued" says nothing about this code: the current
  was under manual control (the log shows PID off pressed, in bursts, at
  each event) and the gas by hand. Ready to build, in one slice: catch an
  error in the ADC step, write it to the message log, and retry the read
  rather than let the thread die; a watchdog on the main thread that
  notices no sample for a few periods and says so in the log, the window
  and the web view; and the launcher keeping the program's error output
  in a file beside the data. Confirmed by Mizuno-kun through queezz on
  2026-09-07: gas by hand, no current PID, the Kikusui in voltage control
  from the DAC, so the plasma ran on because the DAC held its voltage
  after the reader died. What the rig does to the outputs when that
  happens is the open decision above.
- Clicking the page logo produced an error before acquisition was started,
  and did not after (queezz, 2026-09-04, against 0.5.0 on the rig). Not
  reproduced off-rig: loading `/` before acquisition answers 200 on 0.6.0, and
  the logo now leads to Live rather than Lab. If it recurs, the browser's
  console line or the rig's terminal output is the evidence needed.

## Settled, kept here only until the next session reads them

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

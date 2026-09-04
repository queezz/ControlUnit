# Directions

Open work only. A session records what it did in `.agents/log/`; this file
holds what is still undecided or unbuilt.

## Decisions waiting on queezz

- How should the rig find PIHTI Log, which runs on queezz's Windows PC rather
  than on the Pi and whose address can change — put the address in the Pi's own
  neighbours file by hand, look the machine up by name on the lab network using
  the name service Windows and the Pi already both speak, or have the rig scan
  the network for it — the owner's call.
  Stakes: by hand is ten minutes now and breaks silently whenever the PC's
  address changes. Looking it up by name keeps working across address changes
  and needs the PC to answer to a name; the diagram session reports the PC
  already answers as `AK-office.local`, which the neighbours file below uses.
  Scanning needs no setup at all and is the slowest and the least predictable,
  and it means the rig probing machines nobody asked it to touch.
  Recommendation: the name, `AK-office.local`, in the neighbours file, and a
  hand-written address only if the name stops answering from the Pi.
  Safe default: by hand, which is what the code already supports.

- Who may change a setpoint from a browser: never (view only), only while a
  Remote control switch on the rig's own screen is on, or anyone on the LAN at
  any time — the owner's call.
  Stakes: hydrogen and oxygen flow and the cathode current move on this.
  Recommendation: the switch on the rig, plus a Stop all outputs button that is
  always allowed because it only ever drives the hardware to zero.
  Safe default: view only. Slice three is being built on the recommendation
  as its default (queezz ordered control-tab work 2026-09-04 without settling
  this); saying "keep view only" or "anyone on the LAN" changes one gate.

## Work only queezz can do

- Restart the rig onto 0.7.0, on a rig that is not acquiring — owner work
  pending. Both Pi checkouts carry it; the running process is 0.6.0. On
  restart the control dock gains a Remote switch beside On/Off and the
  Scales dock an "O Bd" button beside "O Bu".
  Done when: `http://pihti:4187/api/health` reports 0.7.0, `/control` shows
  every setter disabled until the Remote switch is thrown on the rig, and
  Stop all outputs answers with "all outputs to zero" in the Log tab.

## Ready to build, once queezz answers

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
  following a mid-run sampling change. None is urgent at 0.1 Hz.

## Reported, not reproduced

- Clicking the page logo produced an error before acquisition was started,
  and did not after (queezz, 2026-09-04, against 0.5.0 on the rig). Not
  reproduced off-rig: loading `/` before acquisition answers 200 on 0.6.0, and
  the logo now leads to Live rather than Lab. If it recurs, the browser's
  console line or the rig's terminal output is the evidence needed.

## Waiting on another ship

- The helm panel cannot show a service that runs on another machine and is
  never started from here, which is what ControlUnit is: its registry entry
  is a door with no row. Letter `20260904-9138b125-d0de6d` to `code/lab-cli`
  asks for a remote-service shape (a whole-origin `www` such as
  `http://pihti:4187`, `version_url = "/api/health"`, no command, no Start
  or Stop). Until lab answers, the fleet table already shows the version
  from `pyproject.toml`, which is what queezz missed on 2026-09-04.

## Settled, kept here only until the next session reads them

- The operator lock (queezz 2026-09-04, "go"): first browser to send a
  setter holds control by name and address, Take over is deliberate and
  logged, Stop all never gated, released on stop and on Remote off, no
  idle timeout. Shipped in `436d487`.

- Version 4.0.0 (owner decision 2026-09-04): the major number names an era,
  told in `docs/history.md`; `pyproject.toml` declares the package and the
  fleet reads its version from there; `setup.py` is gone.
- Sampling at 0.1 Hz on the rig is deliberate for long overnight runs
  (queezz, 2026-09-04); the web view's stale line follows the sampling
  time, so at 10 s it is 50 s.

- 0.7.0 (2026-09-04, evening): big readouts and a fast poll on Live; zero
  baselines for Ip, Bu and Bd from the rig's Scales dock and from the
  browser; the Control tab and its command path, gated by the Remote switch
  on the rig with Stop all outputs always allowed. Acquisition start/stop
  from a browser is not built. Log entry
  `2026-09-04-webui-slice-three-control-and-live-extras.md`.

- Slice two shipped in 0.6.0 (2026-09-04): the read-only Live and Log tabs,
  `/api/state`, `/api/series`, `/api/log`, Live as the home page and Lab at
  `/lab`. Slice three, browser control, waits on the second decision above.
- The Lab tab's neighbour cards now say how a service is started only when
  the neighbours file says so, and say where it runs; the `lab <alias>` line
  is no longer assumed for every neighbour.
- PIHTI Log's letter `20260904-ec356017-5a06b4` was answered 2026-09-04 by a
  note: shape accepted, port 4187, neighbours polled server-side.
- The diagram session's note `20260904-925fa9a3-8a460b` (its address and the
  journal's) was read and acted on 2026-09-04; its addresses are in the
  neighbours file above. Notes have no receipt.
- `.agents/README.md` exists now; `simple-pid` and `PyYAML` are declared.

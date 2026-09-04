# Directions

Open work only. A session records what it did in `.agents/log/`; this file
holds what is still undecided or unbuilt.

## Decisions waiting on queezz

- How should the rig find PIHTI Log, which runs on queezz's Windows PC rather
  than on the Pi and whose address can change — put the address in the Pi's own
  settings file by hand, look the machine up by name on the lab network using
  the name service Windows and the Pi already both speak, or have the rig scan
  the network for it — the owner's call.
  Stakes: by hand is ten minutes now and breaks silently whenever the PC's
  address changes, which is the state the Lab tab is in today. Looking it up by
  name keeps working across address changes and needs the PC to answer to a
  name. Scanning needs no setup at all and is the slowest and the least
  predictable, and it means the rig probing machines nobody asked it to touch.
  Recommendation: look it up by name, and fall back to a hand-written address
  when the name does not answer, so a working lab is never blocked on name
  resolution.
  Safe default: by hand, which is what the code already supports.

- Who may change a setpoint from a browser: never (view only), only while a
  Remote control switch on the rig's own screen is on, or anyone on the LAN at
  any time — the owner's call.
  Stakes: hydrogen and oxygen flow and the cathode current move on this.
  Recommendation: the switch on the rig, plus a Stop all outputs button that is
  always allowed because it only ever drives the hardware to zero.
  Safe default: view only.

## Defects in the Lab tab

Reported by queezz 2026-09-04 against the running page; evidence gathered on
the Pi and recorded in `.agents/log/2026-09-04-rig-code-restored-and-web-on-lan.md`.

- The Pi has no `~/.controlunit/settings.yml`, so it has no `Neighbours:` block
  and both neighbour cards fall to `not configured`. The code is behaving
  correctly on absent configuration; the configuration has never been written.
- The PIHTI diagram card tells the reader to start the diagram with
  `lab pihti-diagram`, on the very machine where `pihti.service` is already
  `active`. It is wrong about the mechanism and about the state at once.
- The start-command copy assumes every neighbour is started by `lab` on the
  machine reading the page. `lab` is the Windows helm; the Pi runs systemd
  units. A card should say how that service is started on that machine, or say
  nothing at all.
- Clicking the page logo produced an error before acquisition was started, and
  did not after. Not reproduced, not diagnosed.

## Ready to build

- Slice two of the web view: the read-only Live tab, the rig's values and two
  strip charts on any laptop on the LAN. queezz's verdict on slice one standing
  alone was that he needs "a real view, not a joke", so this is the piece that
  makes the surface worth opening. Nothing needs deciding first.
- Reply to PIHTI Log's letter `20260904-ec356017-5a06b4` (received and
  collected 2026-09-04): the proposed health endpoint shape is accepted as
  written, and each service should poll its neighbours from its own server
  side, through a small `/api/neighbours` route, rather than from the browser,
  so no service opens cross-origin reads and neighbour URLs stay in each
  machine's local config. The port is settled at 4187.
- `.agents/README.md` does not exist, though this repository's cold-start
  packet requires it and names it a required read. Write it, or correct the
  packet.
- `simple_pid` and `pyyaml` are imported but declared in no requirements file;
  both had to be installed by hand before the program would boot off-rig.

## Settled, kept here only until the next session reads them

- The web view answers on the lab network by default (owner decision
  2026-09-04, "the whole point is LAN"). Recorded in `AGENTS.md` and in the
  `--host` default.
- Port 4187 is accepted, and in use on the rig.
- The warm charcoal and amber dressing is accepted; it shipped and stands.
- Slice one is merged to `master` and pushed; it is no longer waiting on the
  rig's uncommitted work, which landed in `bc0888c` and `aff0b57`.

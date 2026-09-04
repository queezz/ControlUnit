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
  Safe default: view only, which is what is built.

## Work only queezz can do

- Put web view 0.6.0 on the rig, on a rig that is not acquiring — owner work
  pending. Pull `master` into both Pi checkouts, write the neighbours file, and
  restart from the desktop shortcut:

      git -C /home/pi/work/aktest pull
      git -C /home/pi/work/ControlUnit pull
      mkdir -p ~/.controlunit
      cat > ~/.controlunit/neighbours.yml <<'EOF'
      pihti-diagram:
        url: http://pihti:5000
        where: on this Pi, as a system service
        start: sudo systemctl start pihti.service
      pihti-log:
        url: http://AK-office.local:4310
        where: on the office Windows PC
        start: lab pihti-log
      EOF

  The file is `neighbours.yml`, not `settings.yml`: a local `settings.yml` is
  a complete replacement for the packaged one and a file holding only
  neighbours would stop the rig from starting.
  Done when: `http://pihti:4187/api/health` reports version 0.6.0, `/` shows
  the Live tab with moving charts while acquiring, and `/lab` shows the
  diagram card `ok` with "Runs on this Pi, as a system service."

## Reported, not reproduced

- Clicking the page logo produced an error before acquisition was started,
  and did not after (queezz, 2026-09-04, against 0.5.0 on the rig). Not
  reproduced off-rig: loading `/` before acquisition answers 200 on 0.6.0, and
  the logo now leads to Live rather than Lab. If it recurs, the browser's
  console line or the rig's terminal output is the evidence needed.

## Ready to build

- Register the web view in the Lab registry: `www = 4187` and
  `version_url = "/api/health"` on the existing `[services.controlunit]` table
  in `lab-cli/services.toml`, and `--web` in its command, so Lab's own board
  reads the rig the way it reads the journal. A commit in another repository
  under its own contract (RULES.md §11): prove it with a scratch `lab start`
  first, and fall back to a letter to `code/lab-cli` if that file is dirty.

## Settled, kept here only until the next session reads them

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

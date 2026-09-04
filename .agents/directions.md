# Directions

Open work only. A session records what it did in `.agents/log/`; this file
holds what is still undecided or unbuilt.

## Decisions waiting on queezz

Raised by the web-UI design brief of 2026-09-04 (see
`.agents/log/2026-09-04-webui-design-brief.md`). Each has a safe default,
which is what happens if nobody answers.

- Should the ControlUnit web surface be built now, and in the brief's order —
  a Lab tab with the three services' health first, then a read-only Live tab
  with values and two strip charts, then browser Control — the owner's call.
  Stakes: the first slice is a day and answers PIHTI Log's letter; the second
  puts the rig's live values on any laptop on the LAN; the third is where gas
  and current can be moved from a browser.
  Recommendation: fund the first two now and decide the third after using
  the second.
  Safe default: nothing is built; the letter is answered by the brief alone.
- Who may change a setpoint from a browser: never (view only), only while a
  Remote control switch on the rig's own screen is on, or anyone on the LAN
  at any time — the owner's call.
  Stakes: hydrogen and oxygen flow and the cathode current move on this.
  Recommendation: the switch on the rig, and a Stop all outputs button that
  is always allowed because it only ever drives the hardware to zero.
  Safe default: view only.
- Which colours the rig's web page wears: warm charcoal with an amber accent,
  so it tells apart from the diagram and the journal at a glance, or the same
  cool dark set those two already use — the owner's call.
  Stakes: only how easily three browser tabs are told apart; the layout is
  the fleet's in either case.
  Recommendation: warm.
  Safe default: copy the diagram's stylesheet, which costs nothing.
- Is port 4187 acceptable for ControlUnit's web server, on the Pi and in the
  Lab registry — the owner's call.
  Stakes: one line in each machine's local config.
  Recommendation: yes.
  Safe default: 4187.

## Ready to build once the first decision is made

- Slice one of the web surface is built and waiting on branch `webui`: the
  `--web` flag, the health and neighbours routes, and the Lab tab, with the
  gates green and the Perimeter Walk run in a real browser (see
  `.agents/log/2026-09-04-webui-slice-one.md`). It is not on `master` and not
  pushed, because the rig still holds uncommitted isolated-DAC work; merge it
  after that push lands. Slice two, the read-only Live and Log tabs, is the
  next piece of work and needs nothing decided first.
- Reply to PIHTI Log's letter `20260904-ec356017-5a06b4` (received and
  collected 2026-09-04): the proposed health endpoint shape is accepted as
  written, and each service should poll its neighbours from its own server
  side, through a small `/api/neighbours` route, rather than from the
  browser, so no service has to open cross-origin reads and neighbour URLs
  stay in each machine's local config. Send it from the session that starts
  the first slice, with the port once it is settled.

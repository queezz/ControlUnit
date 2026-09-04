# 2026-09-04 — web UI design brief, and PIHTI Log's letter received

Design session only. No code, no venv, no service, no commit. This entry and
`.agents/directions.md` are the only files written, on queezz's live
instruction to record and collect the letter; the cold-start packet had been
orientation-only.

## The letter

`20260904-ec356017-5a06b4`, PIHTI Log → ControlUnit, "An ensemble of three".
queezz wants ControlUnit, PIHTI Log and the interactive vacuum diagram to
each grow a tab showing the health of all three, with links, so any laptop on
the lab LAN reaches all of them from any one. Proposed contract: an
unauthenticated `GET /api/health` on each service's own origin returning
`{"service", "version", "status": ok|degraded|down, "detail"}` with
`Cache-Control: no-store`, loopback by default, no paths or addresses in the
body. PIHTI Log reads only; it will never call a device mutation route. It
asks for a reply on whether the shape suits, and later the path and port.
Collected 2026-09-04 after this record was written. The reply is in
directions, ready to send with the first slice.

## The design, in short

Full brief published as the artifact "ControlUnit on the LAN" (2026-09-04).
The decisions it makes:

- Flask, not FastAPI: one plain thread beside Qt, same framework as the
  diagram, nothing async to own.
- In-process: the web thread reads a lock-protected snapshot the Qt main
  thread writes on `data_ready`, and pushes commands to a queue the main
  thread drains on a 200 ms QTimer, calling the existing slots. Thread
  ownership and the hardware-first shutdown order are untouched. Switched on
  with `--web`.
- Tabs by kind of work: Live (readouts, two canvas strip charts, window and
  scale controls in the left rail, run facts right), Control (four headed
  groups in operating order, Stop all outputs always pressable), Log, Lab
  (three service cards, four states: ok, degraded, down, unreachable).
- Precedent, per Fleet RULES.md §10 and WEBUI.md: fleet's own dashboard for
  rails, cards and badges, paperlib's rail vocabulary, and the diagram's
  `.page` grid as the same grammar already applied in this ensemble. Never
  lecturedeck.
- Plotting: live window only, thinned server-side to ≤600 points per
  channel, drawn on canvas in plain JavaScript, no CDN. History plots stay
  the diagram's job; the Live rail links to it.
- Health endpoint accepted as proposed. Neighbours polled server-side.
- Proposed address `pihti:4187`, loopback by default; LAN bind is the rig's
  registry entry. Neighbour URLs in `~/.controlunit/settings.yml`.
- Three slices: Alive (health + Lab tab), Live (read-only), Control.

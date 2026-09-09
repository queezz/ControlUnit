# Control panel placement — 4.7.2

Owner asked for small/big beside readouts, dedicated QMS sync status,
baseline actions beside plots, and spaced/tinted operation cards with
larger sampling choices. Implemented together. The shared reading partial
keeps Live/Monitor sizing; zero buttons render on Control only and retain
`.sets` gating. No hardware API or command semantics changed.

Validation: 479 pytest tests, 2 Node plot tests, strict MkDocs build passed.
Local dummy preview inspected at desktop 700/1000 heights and phone width.
Verified size persistence, Monitor toolbar, zero/sync disabled with Remote
off, Access anchor, tab navigation and no browser console errors. No rig
commands sent. Local preview stopped after review. Not pushed or deployed.

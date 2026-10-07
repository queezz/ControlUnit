# Kawabata's hydrogen runs of 10-05 and 10-06, read — 2026-10-07

Queezz, live: "look at recent Kawabata experiments (pihti-log), compare
them with some of my good hydrogen runs pressure and current wise, and
look at his data." And, of the source: "Somehow he has preanode
grounding. I need to look at the source. I suspect 2 things: 1 the
'hat' holding nuts relaxed, hat rotated. 2. The M3 rod bent cause of
plasma current heating, and sagged." The session opened
orientation-only; his ask ended that boundary (RULES.md §18).

No code changed. Nothing on the rig was set, stopped or restarted: it
was logging a vacuum at 10 s (`cu_20261006_164348.csv`, 4.25.0) and
only `/api/health`, `ls`, `scp` and `grep` over SSH touched it. Nothing
was left on the Pi.

## Done

- `data/rig/2026-10-05/` and `2026-10-06/` (git-ignored, Dropbox): his
  four run files with their Kikusui sidecars, the two days' lines of
  `controlunit.log`, and `analysis/` (episodes, endings, overview plot).
- The vault: `Experiments/Troubleshooting/Kawabata hydrogen attempts and
  preanode faults 2026-10-05.md`, one line appended to `Troubles.md`.
  The journal's own days are his and Kawabata's and were only read.
- `directions.md`: one owner decision (the PID's unlit ceiling), one
  Ready-to-build defect (the off press on a flapping LAN), and today's
  words added to the Monitor-strip item with the Display drawer.
- Mail: the packet said two letters were posted here; `fleet letters`
  shows every letter collected or logged, none posted. Nothing to
  collect.

## Found

The comparison and the reasoning are in the vault note; in short:

1. At 30–50 mTorr and 17 A his hydrogen gives 1.5–2.3 A of plasma
   current, three to four times the 2024 runs at 17–18 A and 16–20
   mTorr. Emission is not what is wrong.
2. What is wrong is September's preanode fault, back: the anode supply
   pegged at its 3 A limit (3.5 A on the provisional Hall scale) in 17 of
   32 episodes on 10-06, seven fast spikes to 4–7.5 A, abrupt deaths from
   a steady 1.5 A with the filament unchanged. 10-05 had none of the
   first two; 10-06 had them inside the first minute. One spike is inside
   the argon test he took as clearing the preanode.
3. The PID's 1900 mV unlit ceiling is below hydrogen's ignition drive of
   2030–2100 mV; the loop flipped lit/unlit six times at 1900 mV on
   10-06 18:00. Owner decision in directions.
4. The Kikusui LAN flapped 57 times on 10-05 and the output-off press
   failed twice at 16:02 on its one-second budget. Defect in directions.
5. The ADC bus: 8 Remote I/O errors over two days, 12 reader losses on
   10-05. The known item.
6. He drove the supply from its own panel at 20–23 A on 10-06 (DAC at 0
   in the file); the anode pegged for 92–95 % of those episodes.

## Also, from queezz during the session

The rig runs 4.25.0, the newest deployed; the code is not old. Two UI
observations, recorded in directions, not acted on (a UI change routes
through the fleet's UI law and the Perimeter Walk first): the Display
drawer's body sits apart from its header in the right rail, and Observe
and Monitor leave the top bar empty but for the mode switch.

agent: claude

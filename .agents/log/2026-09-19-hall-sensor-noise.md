# Hall sensor noise, its zero, and the filter for Ip

Home machine, 2026-09-19. queezz asked for the 2026-09-18 run that the
work PC's session was expected to have pulled, and for a frequency filter
on the Hall sensor's noise.

## The Friday run is not here

`data/rig/` holds only `2026-09-15/`; master's last commit is cfc9394 of
2026-09-15 23:39, no log or handoff is newer than 2026-09-15, and the
vault's newest day is 2026-09-16. Dropbox on this machine had been running
since 2026-09-18 21:09, so nothing the work PC uploaded was waiting. The
rig's name does not resolve off the lab network, so nothing could be
fetched from here. Whatever the work PC's session did, it did not reach the
repository or the vault.

## What was done

The session was started as orientation-only by the fleet's cold-start
packet (no edits, no commits). queezz's "Yep, need all of that", live in
the chat, was taken as the instruction to record the work; the notice was
given in the chat.

Analysis of the 2026-09-15 files, read-only, with throwaway scripts in the
session's scratch folder (numpy, pandas, scipy and matplotlib from an
existing analysis venv; `hardware-dev` has no scipy or matplotlib, and none
was installed). The results are in
`docs/diagnostics/2026-09-19-hall-sensor-noise.md` with one figure, and in
the vault as `Experiments/Troubleshooting/Hall sensor noise and zero
2026-09-19.md` with a line in `Troubles.md`. Headlines: the fs/3 line
follows the sample count (the batch of three), the 0.133 Hz line is 7.500 s
of clock time, both are on `Ip` alone; the zero is half of a 4.90–4.91 V
supply, which fits a ratiometric sensor on the Pi's 5 V pin; the 2 s zero
button is off by 11 mA typically; 5 A/V matches no documented sensor; a
3-sample mean and three notches take the noise from 23 to 9 mA at 0.1 s.

`directions.md` gained an owner-work item for the hardware (own supply,
supply on a spare input, RC, ferrite, calibration, and which sensor is
fitted) and a build item for the zero, scale, ratiometric conversion,
7.5 s baseline and filter; the 2026-09-15 findings bullet points to it.

## Not done

No code changed and no version bump: documentation and directions only.
The waiting letter from PIHTI Log (20260915-7d7f0cb5-fa5d91, the owner's
approved instrument panel as a design reference) was read and left posted;
it concerns the web view and was not this session's task.

Validation: strict MkDocs build passed (built into scratch, not `site/`);
no tests run, no code touched.

agent: claude opus 5

# The October 2 argon run, read and passed on — 2026-10-02

Queezz asked, live, for the day's run to be looked at, pulled to the
office PC and left in Dropbox for the home machine, read against his
journal, and for findings to go to the PIHTI agents by fleet mail; and
for the `Ip` signal in particular, which "was off compared to the anode
and preanode PSUs". The session opened orientation-only; his ask ended
that boundary (RULES.md §18), said so in the reply.

No code changed. Nothing on the rig was set, stopped or restarted: it
was recording a slow 10 s run (`cu_20261002_180530.csv`) and only
`/api/health`, `ls`, `scp` and `grep` over SSH touched it. One scratch
file was left on the Pi, `/tmp/cu_log_20261002.txt`, the day's log
lines, which a reboot clears.

## What was done

- `data/rig/2026-10-02/` (git-ignored, in Dropbox): both runs of the
  day with their Kikusui sidecars, the day's lines of `controlunit.log`,
  `controlunit.stderr.log`, the overview plot and the analysis scripts
  in `analysis/`. SHA-256 taken on the Pi and on the copy agree. The
  360 MB two-day file `cu_20260930_170412.csv` was read on the Pi and
  not copied.
- `docs/diagnostics/2026-10-02-ar-plasma-pid-run.md`, with its plot
  under `docs/assets/diagnostics/2026-10-02/` and a nav line.
- The vault: `Experiments/Troubleshooting/Ar plasma PID run and
  ControlUnit hang 2026-10-02.md` and one line appended to `Troubles.md`.
- Letters posted: `20261002-dfcaefd6-0d53d6` to
  `code/pihti-vacuum-diagram` (his two comments on the turbo warning,
  with the pressures the rig measured), `20261002-34f6322f-c925c2` to
  `code/pihti-experiment-log` (the findings against its session record).
- Letters collected: `20260915-7d7f0cb5-fa5d91` (his approved panel and
  grouping, now the named reference in the rail item of directions) and
  `20260929-2e17d3fd-15bcb4` (Hall rework reported done; reconciled —
  the item is trimmed to what is left, the calibration, the part number
  and the conductor).
- `directions.md`: one owner decision (the Hall zero ratio), two owner
  work items (which wire and the calibration; a meter on the DAC output
  for the 7.5 s step), and a 2026-10-02 block at the head of Ready to
  build.

## What was found

1. The 17:00 hang: the run started 2026-09-30 17:04 at 0.1 s; the whole
   run is copied at every delivery, the main thread fell 25.4 h behind,
   and the file ends 25 h before the kill. The old "run held in memory"
   item is now the first thing to build.
2. `Ip` un-zeroed reads −0.098 A, steady; the PID's 0.50 A was 0.60 A.
   Against 0.7 A and 0.9 A on the supplies the rest is the provisional
   5 A/V and the unknown conductor.
3. The PID holds (0.5005 A, command 1780 → 1733 mV as the source warms)
   and starts at 1000 + 40 × error × seconds since the last mode change:
   1728, 1759 and 1000 mV. The Kikusui's 7.80 V limit was reached three
   times.
4. A 0.1333 Hz step, 2.5 s low in 7.5 s, is in the filament current
   itself (37 mA peak to peak by the Kikusui's own measurement, constant
   command) and in the plasma current (25 mA). The 2026-09-15 files show
   it with no plasma, at the same 0.12–0.14 % from 5 A to 16 A, so it
   multiplies the command: the MCP4725's output following its own 5 V
   supply. The 2026-09-19 page read that line as the Hall supply alone;
   it is the rail, and the cathode DAC hangs on it too.
5. Web: takeover sent 0 mV from a stale field; the Cathode cards blinked
   with the supply answering every poll; the browser's 20,000-sample
   store cuts an hour at 0.1 s; output on/off logs the readback before
   the supply has changed.

## Left for the next session

Build the hang fix first; it loses data. The takeover fix is second: it
put a plasma out. Both are specified in `directions.md`. A web change
routes through the fleet's UI law and the Perimeter Walk.

agent: claude

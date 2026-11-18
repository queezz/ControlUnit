# The noise study, from a record that already existed — 2026-11-18

queezz, during a lab meeting after the 4.31.0 deploy: "Do we have anything
to do in the pi? No one's using it, you can do something while we are
idle".

## Chosen

The open noise study (directions, his words of 2026-09-15). It also
answers the 2026-09-19 page's question of which patterns survive a change
to the Hall sensor's supply: on 11-11 he fitted the breakout board that
splits the Meanwell 5 V.

## Not done on the rig

The first plan was 15 minutes at 0.1 s, set and restored by a script left
running on the Pi. The permission layer refused that command, and it was
not worked around. Nothing was sent to the Pi. It was not needed: a scan
of the recent files for long 0.1 s stretches found 53 minutes of
`cu_20261116_173717.csv` (17:37:17–18:30:54) with no plasma, no gas
commanded, a cathode drive of 0 mV, and the Kikusui's output off (the
supply off from 17:59). The other long fast stretches, on 11-13, were
plasma runs. The journal of 11-16 was read first, as AGENTS.md requires.

## Done

- **Data.** The run file and its Kikusui sidecar were fetched into
  `data/rig/2026-11-16/` (sizes matched the Pi's). The analysis scripts and
  their JSON output are beside them in `analysis/`.
- **First pass.** It reported every frequency a thousand times too high:
  pandas 3 parses these timestamps to microseconds, so `int64 / 1e9` is
  wrong. The pass was redone with `total_seconds()`. The second pass
  reproduced the older pages' numbers (September 23.2 mA and 40 mA peak to
  peak; October 9.6 mA) before saying anything new.
- **Docs.** `docs/diagnostics/2026-11-18-quiet-rig-noise.md`: every channel,
  the two patterns, the filters then and now, and the floor. It has a
  two-panel figure, September against October against November, in the
  validated categorical slots with one key across the top. It is in the
  mkdocs nav.
- **Vault.** The note "Quiet rig noise after the Hall breakout 2026-11-16",
  its figure under `Attachments/Diagnostics/`, and a line appended to
  Troubles.
- **Directions.** The noise-study item is removed, because its answer is
  recorded. The floor item gains the numbers, a recommendation (25 mA for
  Ip), and the question of whether to build the September notches now
  (8.6 to about 5 mA live).

## The findings, short

- **Ip noise with nothing flowing** has gone from 22.9 to 9.7 to 8.6 mA.
- **The 7.5 s pattern** is down from 40 to 7 mA peak to peak, and **the
  every-third-sample pattern** from ±12 to 3 mA peak to peak.
- **Both patterns are on the Hall sensor's 5 V (Vhall)**, not the ADC: Pu
  carries 230 times less.
- **The division by Vhall removes about half**: Ip moves 0.9 of Vhall,
  where a ratiometric sensor would move 0.5. The remaining 8 mA is the
  sensor's own noise.
- **The 7.5 s line was 40 % smaller once the Kikusui was off and the leak
  check began.** The record cannot say which of the two did it.

agent: claude

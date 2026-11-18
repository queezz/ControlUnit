# A quiet Ip steps aside, and the plasma chart folds — 2026-11-18, 4.32.0

queezz, after the noise study, on the floor it measured: "I see, yes, build
it. Number, you now know better". The item dates from 2026-09-07, when he
called the current plot with no plasma "a noisy waste of space".

## The number

My first answer, 25 mA, was a per-reading limit (three times the 8.6 mA
noise of one reading). The chart judges a whole window, so I measured the
extremes over windows on the 11-16 record before building anything:
- **At 10 Hz, raw readings reach 107 mA in any 5-minute window.** These are
  single readings about 55 mA low, 0.3 % of readings, every one downward,
  roughly every 20 s, and never on Vhall: a read glitch, not current.
- **Through a 5-point median**, which removes them, quiet Ip stays within
  42 mA zeroed and 57 mA un-zeroed (its zero sits at −17 mA). At 1 s it
  stays within 31 mA, at 10 s within 22 mA.
- **A discharge starts near 0.12 A** (the September ignition staircase).

So the floor is **60 mA, judged through a 5-point median**. Failing toward
showing is the safe direction: a zero that drifts further only leaves the
chart up.

## Built

- **Settings.** `settings.yml` has Ip `Quiet Within: 0.06`, and the
  settings version is 1.9 so that a local copy cannot mask the key.
  `AdcChannelProps.quiet_within` reads it.
- **The state.** `MainApp._web_quiet` gives the floors to `RigStatus`
  (`quiet=`), and `/api/state` carries `quiet_within` on every channel,
  `null` where a channel has none.
- **The Live tab** (`live.js`):
  - `isQuiet` gives a curve the state `quiet`, with no need for another
    curve to be moving, unlike flat.
  - A panel with nothing drawn but a quiet curve returns `quiet: true`,
    and `drawAll` folds it with `chart--collapsed`. Monitor mode leaves a
    folded panel out of its height share.
  - The pill reads `quiet`; its tooltip is "Within ±60 mA of zero, its
    noise with nothing flowing: show it anyway". A press pins it, as for
    flat.
- **Docs.** `web-ui.md` has a paragraph after the flat rule. The noise page
  gains the glitch and the built floor, and the vault note an appended
  "Built" section.
- **Directions.** The floor item is replaced by the one question still open:
  whether the live Ip should go through the September notches, now worth
  8.6 to about 5 mA.

## Verified

- **Tests.** `tests/test_quiet_floor.py` covers the settings, channel
  properties, state and main map. Six node tests cover: a quiet Ip folding
  the panel, a single glitch staying quiet, a discharge bringing it back, a
  filament current keeping it open, the pill press, and no floor meaning
  never quiet. That is 929 Python and 72 node tests.
- **Scratch instance** (`lab start controlunit-dummy --port 48937`, scratch
  roots and home; 4187 had no listener before or after). The browser pane
  was hidden, so it ran with an emulated 1440x900.
  - At 0.1 s sampling and a 20 s window, the dummy's constant Ip of
    0.0975 A was drawn.
  - After Zero Ip, once the window had passed, the pill read `quiet`, the
    chart folded to its 90 px heading with the tooltip "±60 mA", and the
    ion-gauge chart moved up.
  - Window Full, with the pre-zero 0.0975 A readings in it, brought the
    chart back. Back at 20 s it folded again.
  - The pill press brought it back at 310 px. The All preset made it quiet
    again.
  - In Monitor mode the plasma chart had 0 px and the two pressure charts
    143 px each, with no page scroll.
  - It stayed quiet and folded through a true reload and through Back to
    Operate. No console errors.
- **Cleanup.** `lab stop`: the process tree gone, 48937 free.

## Not done

Not deployed. The rig is recording, nobody is at it, and it is on 4.31.0.
Deploying takes queezz's word.

agent: claude

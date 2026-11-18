# Slim folded charts, charts that fill the window, a real quiet fold — 2026-11-18, 4.33.0

queezz, with a screenshot of the Live tab (his tab still on 4.30.1, plasma
and downstream charts folded by hand): "Collapsed views still consume a lot
of vertical spaces there...". Measured first on the rig's own page at his
window size (1644x940, read only):
- a hand-folded chart: about 42 px plus a 10 px gap;
- my 4.32.0 quiet fold: **90 px**, because it kept the legend row under the
  heading;
- the "Pressure plots" row: 47 px;
- the open charts: a fixed 200–220 px canvas, so what a fold gives up sits
  empty at the bottom.

Asked which part to change, he chose both: slimmer folded lines, and open
charts that fill the window.

## Built

- **Slim heading.** `.chart-head.fold-head` has a 28 px minimum height and
  2 px padding, in both states, so it never jumps (his rule of 2026-09-14).
  The Zero buttons are cut to fit, and a folded chart's gap is 6 px. The
  card-wide 36 px fold head is unchanged; a test pins it.
- **Filling the window** (`live.js`). Monitor's height pass is now
  `plotHeight` for every mode. Operate and Observe use it only at
  `(min-width: 1200px)`, and never below a canvas's declared height; Monitor
  keeps its 140 px floor.
- **The quiet fold is a real `<details>` fold.**
  - `quietFold` closes the chart while its only curve is quiet and reopens
    it when the curve is not.
  - `setFoldByPage` marks the state it set in `data-fold-auto`.
    `control.js`'s fold memory skips a toggle whose state matches that mark,
    so the page's own fold is never saved.
  - `watchQuietFold` treats any other toggle as the reader's. A reader
    opening a quiet fold pins the quiet curves (show anyway, until a
    preset).
  - The span reads "Ip quiet · last …".
  - 4.32.0's `chart--collapsed` path for quiet and `canvas.dataset.quiet`
    are gone.

## Verified

- **Tests.** The JS tests are rewritten around a section that is a fold.
  They cover:
  - folding;
  - the page's own toggle ignored;
  - a glitch staying quiet;
  - a discharge reopening the fold;
  - a fold the reader made never undone;
  - a filament current keeping the fold open;
  - opening by hand;
  - the pill;
  - no floor.

  Two Python source checks pin the fold-memory guard and the slim CSS.
  That is 931 Python and 75 node tests, and mkdocs strict passes.
- **Scratch instance at 1644x940** (`lab start controlunit-dummy --port
  48937`, scratch roots and home; 4187 had no listener before or after):
  - All charts open: unchanged, 220/200/200 px with the page scrolling.
  - Plasma and Baratron folded by hand: 37 px each (heading 31 px in both
    states), and the ion-gauge chart grew from 200 to 441 px.
  - Zero Ip at 0.1 s with a 20 s window: the plasma chart folded itself to
    "Ip quiet · last 20.0 s · 201 samples", and the saved fold stayed "1".
  - A reload folded it again. Opening it by hand drew Ip and it stayed open.
    The All preset folded it again. A Full window, with the pre-zero
    0.0975 A readings in it, reopened it on its own (`foldAuto` "1").
  - The right rails held an identical 76 px at 0/25/50/75/100 % scroll, at
    1644x1000 and 1644x700. At 700 px the open chart kept its declared
    200 px.
  - A phone (375x812) kept the declared heights.
  - Monitor: the open chart at 382 px with no scroll.
  - No console errors. `lab stop` left 48937 free.

The page still scrolls 73 px at both heights. That is the right rail (This
run ends at 1082 px), not the charts; the chart column ends at 921 of 940.

## Deployed, 17:24

queezz: "Push and deploy". Pushed `383d2f4..1e22a77`, and the deploy used
the same script as 4.32.0:
- **Before.** The rig was recording `cu_20261118_150922.csv` (811 samples
  at 10 s) with no outputs live.
- **Stop.** SIGTERM through the graceful stop, status 143.
- **Pull.** To `1e22a77`, and `compileall` was clean.
- **Restart.** The Log said "Restored from the last run: Pd Torr 1e-6, Pu2
  Torr 1e-5, sampling 10 s".
- **Recording again.** Take over from the Pi, then start. The new run is
  `cu_20261118_172457.csv` at 10 s. Ip `quiet_within` 0.06, reading
  −0.013 A.

**The rig's own Live page at 1644x940** (read only):
- v4.33.0;
- the plasma chart folded itself to 37 px, reading "Ip quiet · last 20.0 s ·
  3 samples";
- the two pressure charts open, sharing the window at 211 px each instead of
  200.

The chart column there ends at 955 of 940 px. The sharing overshoots by
15 px with two charts open (with one open, on the scratch instance, it fit).
That is a small remainder in the height sum, worth a look next time the
layout is touched.

queezz's own tab showed v4.30.1 in his screenshot, so it needs a reload to
show any of this.

agent: claude

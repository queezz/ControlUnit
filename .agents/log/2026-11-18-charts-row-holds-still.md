# The Charts row holds still — 2026-11-18, 4.34.1

queezz, with three screenshots of 4.34.0 (the Charts row under the plasma
chart, the pressure charts below it, then the row directly under the
plasma chart with the others folded): "So, control string now jumps below
plasma current, but others go below it. No JUMPING UI is my old and
strong rule in the fleet!"

## What moved

- **Vertically.** 4.34.0 kept the row where "Pressure plots" had been,
  between the plasma chart and the pressure charts, so its y depended on
  whether the plasma chart was open. A chip press opening the plasma chart
  pushed the row, and the chip's neighbours, down by its height.
- **Sideways.** The chips came and went, so pressing one slid the others
  sideways.

The cookbook's stable-address sampling would have caught both. I did not
run it on 4.34.0.

## Built

- **The row's place.** `_live_readings.html` renders the Charts row before
  the chart loop (for the `chart-ig` panel only, so a page without pressure
  charts has no row).
- **Switches** (`live.js`, `paintChartChips`). One `pen chart-chip` switch
  per chart, built once per set of names (By gauge and By vessel rename the
  pressure charts) and otherwise only repainted:
  - `aria-pressed` follows `open`, with the label "Fold the …" or "Show
    the …";
  - `quiet` sits in a reserved space (`visibility`) on the switch of a
    chart that has a floored curve, so its width never changes;
  - a press toggles `open`, and folding by the heading focuses the switch.
- **Tests.** In `test_quiet_floor.py`: a rendered-page test that the row
  comes before every chart and appears once, and a source test that
  switches are built once and repainted. That is 934 Python and 75 node
  tests, and mkdocs strict passes.

## Verified, the stable-address walk

Scratch instance at 1647x920 (`lab start controlunit-dummy --port 48937`,
scratch roots and home; 4187 had no listener before or after). The row's
document y, each grouping button's x, and each switch's x and width were
read after every step:

- **Start**, Baratrons folded from memory;
- **S1**, plasma folded by its heading (the focus went to its switch);
- **S2**, plasma reopened by its switch (the focus stayed on it);
- **S3**, Baratrons opened by its switch;
- **S4**, Baratrons folded by its switch (saved "0");
- **S5**, after Zero Ip and a preset, plasma folded quiet (its switch
  dimmed, `quiet` shown).

At every step the row was at y 267 with height 31, the grouping buttons at
x 490/568, and the switches at x 649/804/900 with widths 149/90/81. No
console errors. `lab stop` left 48937 free.

## Still true

When a discharge lights, the quiet plasma chart opens on its own above the
pressure charts and moves them down by its height. That is the quiet fold
working as built, not a control moving; it is the one movement left.

agent: claude

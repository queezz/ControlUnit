# Folded charts as chips, chart heights back to 4.32.0 — 2026-11-18, 4.34.0

queezz, with a screenshot of 4.33.0 on his 2000-wide screen (the plasma
chart a slim bar, the Upstream chart grown to about 690 px, the Downstream
bar at the window's edge): "Well, the collapsed bar still eats space, but
now your plots don't fit on my big screen, so they would flow out of our
laptop next to the rig..".

Two questions, two answers: the charts should always fit the window, and
folded charts should become chips in one row. Then, while it was being
built: "The plot view size was correct before your last commits, btw. So
you know a good enough reference which worked for us."

## What was built, and what was dropped

- **Chips.** A folded `<details>` chart is `display: none`. The row above
  the pressure charts is the Charts row ("Pressure plots" until now).
  `paintChartChips` builds one `pen chart-chip` per folded chart, named
  from its heading ("Plasma current", "Baratrons", "Upstream" and so on),
  with `quiet` when the page folded it. The label reads "Show the Plasma
  current chart again; its curve is quiet". The row is rebuilt only when
  the set of folded charts changes.
  - A chip press sets `open` and focuses the heading. A fold by the heading
    focuses the chip.
  - The `toggle` path, the fold memory and the quiet pin are unchanged from
    4.33.0.
- **Chart heights.** I built "always fit" first, as queezz chose, with
  charts never above their declared height and shrinking to fit (floor
  140 px). Measured in the scratch instance with all three charts open:
  - 2000x1037: all three shrank to **147 px**, well below the 220/200 px he
    had just called correct;
  - 1366x768: all three at the 140 px floor, and the page still scrolled
    328 px.

  Shrinking cost the right size and did not deliver the fit; folding is
  what makes room, and with chips a fold is free. So Operate and Observe
  are back to the declared heights (4.32.0). Monitor keeps sharing the
  window, now through `fitHeight`, which measures the column's laid-out
  extent less its canvases. The approximate sum it replaces is the one
  that ran 15 px past the window in 4.33.0.

## Verified

- **Tests.** Source tests in `tests/test_quiet_floor.py` cover the chips
  row, `display: none` for folded charts, the declared heights, and
  Monitor-only fitting. The 4.33.0 quiet-fold node tests are unchanged.
  That is 932 Python and 75 node tests, and mkdocs strict passes.
- **Scratch instance** (`lab start controlunit-dummy --port 48937`, scratch
  roots and home; 4187 had no listener before or after):
  - **Big screen, 2000x1037.** The Baratron chart folded from memory gave a
    "Baratrons" chip, with the column ending at 937. Zero Ip made a
    "Plasma current · quiet" chip. Both chips opened their charts, Ip
    pinned and drawn. After the height change, all three open draw at
    220/200/200 px, the page scrolling as at 4.32.0. Folding the Baratron
    chart by its heading moved the focus to its chip and saved the fold
    ("0").
  - **Both folded** (Baratrons by hand, Plasma quiet after a preset): the
    row reads "Charts By gauge By vessel Plasma current quiet Baratrons",
    with the ion-gauge chart at 200 px directly under it.
  - **Monitor:** 636 px and no scroll at 2000x1037; 372 px and no scroll at
    1366x768.
  - **Operate at 1366x768:** the chart at 200 px, the column ending at 592.
    The rails sit at an identical 76 px across the scroll.
  - **Phone, 375x812:** declared heights, the Charts row wrapping to two
    lines, no sideways scroll.
  - No console errors. `lab stop` left 48937 free.

## Not done

Not deployed. The rig is on 4.33.0 and recording.

agent: claude

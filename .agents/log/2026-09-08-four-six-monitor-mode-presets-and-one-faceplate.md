# 2026-09-08 — 4.6.0: a screen for watching, a screen for working

Three things, in the order the directions designed them. The Live tab can
give the charts the whole window; a preset sets the page for a kind of work
in one press; and the Control tab's presses stand together in one faceplate
instead of spread thin down a column. Verified in a browser against a scratch
view on 127.0.0.1:48962 with dummy data, a scratch `HOME` and
`CONTROLUNIT_SETTINGS_HOME` outside Dropbox. The owner's rig and its port
4187 were never touched, and the scratch port was confirmed free before and
after.

## Monitor: plots only

queezz, 2026-09-07: *"Mode. Monitor: plots only, even hide the rails. Only
keep some indicator pills about status and all."*

`Mode: Normal | Monitor` stands in a new **View** card in the Live tab's left
rail, and the mode is in the address — `?mode=monitor` — so the second laptop
propped up beside the rig bookmarks its own screen. The server writes the
shape onto `<body data-mode>` and paints it on the first request, rather than
flashing the ordinary page and then rearranging it; pressing the mode moves
the address with `pushState`, so Back, Forward and a true reload all land
where a reader expects and the charts keep the history the browser has
gathered. An unknown `?mode=` is the ordinary page and never an error: a
mistyped bookmark should still show the rig.

In that mode the tab bar and both rails leave the page. **Measured:** the
reading column goes from 673px to 1225px at a 1280px window and the plasma
canvas from 643px to 1195px, so the charts almost exactly double. The two
pills stay where they were, at the head of the column they describe, because
whether the rig is holding gas is what that screen exists to say. Beside them
the strip grows the only chrome the page has left: **Controls**, **This run**,
**Full screen** and **Leave monitor** — rendered always, shown only in that
mode, so the ordinary page never carries a second copy of a control that is
already beside the reader.

The rails come back as edge drawers **in the shape the diagram already
uses** below its own rail breakpoint (`2024-interactive-diagram`,
`styles.css`): flush and full height, hairline sections inside, a backdrop,
a Close, one at a time. They are the same elements in a different placement —
nothing is duplicated for the mode, so no control can drift from a twin.
Escape closes an open drawer; Escape with none open leaves the mode, so a
mode is never a room without a door.

One measured trap on the way: the rail's own `align-self: start` still
reaches a `position: fixed` box in Chrome and collapsed the drawer to its
content — 589px in a 700px window, stopping short of the bottom. `align-self:
stretch` in the monitor block is what makes `top: 0` and `bottom: 0` mean
what they say; measured 700 === 700 after.

**Full screen** is the browser's own Fullscreen API, one call and one event.
It is written so a refusal costs nothing — the promise's rejection is caught
and the page is left exactly as it was — and that refusal path is what was
actually verified: the embedded browser this session drove reports
`fullscreenEnabled` true and never enters, with no unhandled rejection and no
change to the page. Entering full screen has not been seen work on a real
browser and is queezz's to try.

## A preset is a named set of the switches

The Commander's suggestion of 2026-09-07, built as **Show: All | Vacuum |
Plasma** in the same View card. It is nothing but a named set of the
per-curve switches 4.5.0 put in each chart's legend: it changes what this
browser draws, never one byte of what the rig records, and it is remembered
the way those switches already are — there is no second stored value, because
**which preset is pressed is derived from the switches** rather than kept
beside them. Turn one curve off by hand and the page simply stops claiming a
preset, which is the honest answer and the one that cannot drift.

The directions item named no curve lists, so these are this session's reading
of the rig and are one edit (`server.py`'s `PRESETS`) to change:

- **Vacuum** — Pu, Pd, Bu, Bd. Pumping and leak hunting; no current chart.
- **Plasma** — Ip, Bu, Bd. A discharge running: the current, and the
  Baratrons that read the gas pressure a discharge actually sits at. The ion
  gauges are a vacuum instrument and are off scale or switched off by then.

Whether Plasma should keep the downstream ion gauge is in directions as a
question for queezz.

**A panel with every curve off keeps its heading and its legend** and gives
up only its drawing area, with `no curves shown` on its span line. Hiding the
panel entirely would have taken the switches away with it; this way the press
that sent the chart away is exactly where the reader left it. Measured with
Vacuum: the plasma panel collapsed and its legend still read `Ip: off`; with
Plasma: the ion-gauge panel collapsed and the current and Baratrons drew.

The Live rail now carries five cards where it carried six, and a 700px window
fits five. **Scales** and **Smoothing** became one card, **Lines**, with the
same three rows in the same order and nothing else changed; the median's one
non-obvious fact — that it moves the readouts as well as the lines — rides on
that card's heading line, where it costs no height. Measured at 1280×700:
604 === 604, no card clipped, the same offset of 76px the other rails hold.
There is no slack left in that rail; a sixth card will not fit and the next
one has to buy its room.

## One faceplate, and the numbers beside it

queezz, the same night: *"I don't have many controls, but they are spread
nicely but thin. Not on a glance. Need better UX."*

The tab was five bordered groups down one 673px column, each row carrying a
name, a field, a holding value, a measured value and its presses, with the
gate and the name over in the left rail. The presses now stand together in
one panel 384px wide — flat headed groups inside one bordered box, never a
frame drawn around each group inside the frame — in the same operating order,
and the numbers they are read against stand beside it in the width the window
leaves. A row is a press and a reading is a reading.

The width is fixed rather than a fraction on purpose: a press column that
grows with the window puts the same six buttons further apart, which is the
complaint and not the fix. 384px is what the widest row needs.

**Two things stayed where they were, for reasons.** *Stop all outputs* is
still the left rail's: it is allowed when nothing else is and must be
findable without reading anything. And *Acting as* and the lab's word stand
**outside the block the gate shuts** — they are how a person opens the gate,
so the blanket that disables the setting controls now names that block
(`.sets`) instead of the whole column. That was a real defect waiting: moving
them into the main column under the old selector would have disabled the
fence field exactly when the fence was closed.

**Measured.** The page fell from 1248px to 1024px at 1280×1000, and the whole
faceplate — 840px — stands above the fold there. At 1440×900 its foot is 16px
below the window. At 1280×700 it still scrolls by about 350px, which the
group index in the right rail is for; *at a glance at 1280×700* is not
reached and the directions item says what it would cost.

Every control's address is pixel-identical under the poll (292 / 400 / 727 /
799 over three seconds), and through all five gate states driven with a
patched `fetch` — switch off, fenced, idle-and-mine, not-mine, allowed — the
reservations hold at 44px and nothing moves. In every one of those five the
name field stays enabled, which is the fix above, proved.

## Measured

Scratch view at 127.0.0.1:48962, dummy hardware, `HOME` and
`CONTROLUNIT_SETTINGS_HOME` redirected to a scratch folder outside Dropbox.

Perimeter Walk at 1280×1000, 1280×700, 1440×900 and 390×844. Both rails at
exactly 76px at 0/25/50/75/100 % of the scroll range on Live, Control, Log
and Lab at both desktop heights; every rail fits its box (604 === 604 at
700px, 904 === 904 at 1000px, 804 === 804 at 1440×900). No page-width
overflow anywhere: 1265 in a 1280px window, 1425 in 1440, 390 in 390, and 390
in 390 again with a drawer open. Every tab answers 200 with `no-store` and
carries the whole tab bar. Control's six anchors land their headings 17–21px
clear of the 56px bar. Back, Forward and a true reload keep the mode; a top
tab pressed from the bottom of Control lands the destination at its own top.
At 390px the Control faceplate is one column at 366px with no row and no
reading table overflowing, and the monitor drawer is 340px of a 390px window.
No console error from the app on any tab.

The Retina guard still holds through the new mode: with `devicePixelRatio`
forced to 1, 1.25, 1.5 and 2, and three normal↔monitor round trips at each,
every panel stays 220 CSS px with a buffer of exactly 220 × ratio, and the
document stays 1186px at every ratio.

479 tests, `flake8 --select=E9,F63,F7,F82` clean (this repository carries no
flake8 config and the full default run has never passed here), strict docs
build. Version 4.6.0 in `pyproject.toml` and `controlunit/_version.py`.

The teardown flake of 4.5.0 recurred once — a full `pytest -q` crashed with a
Windows access violation after every test had passed, and did not recur in
three further runs. Qt shutdown, not this slice's code, written down again in
case it becomes a pattern.

## Deployment

Nothing is pushed. `master` is at 4.6.0 in this checkout and now stands six
commits ahead of the remote, 4.4.0's and 4.5.0's included; queezz pushes when
he says so. Then the rig: `git -C ~/work/aktest pull --ff-only` on a Pi that
is neither acquiring nor driving an output — read `/api/health` first, the
check `AGENTS.md` writes out — and his own restart from the desktop shortcut.

## Fleet

Note `20260907-0d3b6998` from PIHTI Log read and logged; it asked for nothing
and nothing here changed because of it.

Usage receipt: provider Anthropic, model Claude Opus 5, task "commander run
round 3: pihti trio / ControlUnit modes", child agents 0, provider usage
unavailable — no meter was shown to this session.

agent: claude opus 5

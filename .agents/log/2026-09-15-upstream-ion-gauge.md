# The upstream ion gauge Pu2 on channel 16 — 4.18.0

Owner, live, 2026-09-15: "I've connected upstream IG to channel 16 on
y-corp ADC", after "Same as downstream IG, it needs the exponent selector."
No name, gain or controller type was given, so this release takes the
downstream gauge's: name `Pu2`, gain 10 (a 0–10 V controller output),
the same Torr-linear / Pa-log conversion, and the Pfeiffer `Pu` stays.
Renaming is one key in `settings.yml` plus the docs, and is cheap only
until the first file records it.

## What changed

- `settings.yml` (Settings Version 1.4): `Pu2` at channel 16; every
  ionization gauge names its own record columns (`Mode Column`, `Scale
  Column`); `IGmode_Pu2` and `IGscale_Pu2` are appended after
  `PresetV_cathode`, so every column the file has always had keeps its
  position and `IGmode`/`IGscale` stay `Pd`'s.
- The ADC worker holds one mode and exponent per gauge, keyed by channel
  name, builds each row from the column list instead of fixed positions,
  and converts each gauge with the pair captured in its own row. A column
  nobody records is refused at start.
- The rig's Control dock has one row per gauge: its name, its Torr/Pa
  box, its exponent. `IGmode`/`IGrange` remain the first pair's names.
- The web Control tab's Gauges group has one block per gauge under its
  name, with a folded line per gauge ("Pd Pa 1e-6 · Pu2 Torr 1e-4").
  `/api/gauge` takes `gauge`; a body without one still means `Pd`.
  `/api/state` carries `setpoints.gauges` by name beside the unchanged
  `ig_mode`/`ig_range`.
- Live: `Pu2` on the ion-gauge chart, in the readouts strip and the
  folded row, in All and Vacuum, in the By vessel grouping (upstream).
  The folded row's font ramp is lowered to fit six values on a 320 px
  phone. The web pens and the Qt graph's pens are held equal by a test.
- Letter `20260915-6ecab9a7-b05cf2` to `code/pihti-log` says what the
  file's columns become.

## Gates

pytest 576 passed (offscreen, no cache written into the repository);
31 JavaScript behaviour tests passed; strict MkDocs build outside
Dropbox; `git diff --check` clean.

## Perimeter Walk

Scratch `lab start controlunit-dummy --port 48937` under scratch
LAB_RUNTIME_ROOT/LAB_LOG_ROOT, LAB_VENV_ROOT at the real venvs, HOME and
USERPROFILE redirected outside Dropbox; the listener was confirmed by
owning process (`python -m controlunit.main --web --host 127.0.0.1
--port 48937`); the owner's 4187 had no listener before or after. Live
DOM read through the in-app browser.

1. Pressed Log, Lab and the ControlUnit brand from the Live surface;
   each landed at its own top (scrollY 0) with the right title.
2. Every link the changed surfaces render: the three tabs and Access.
3. `#sec-gauge` lands open, 388 px below the top at 1280×1000 (the
   group sits in the right rail); no new anchors were added.
4. Back, Back, Forward walked Live → Lab → Log → Lab as expected.
5. `location.reload()` on `/?mode=observe#sec-gauge` restored Observe,
   the open group and both gauge lines.
6. 1280×1000 and 1280×700: left and right rails at 76 px at 0/25/50/75/
   100 % of the scroll range, identical, both heights; at 700 the right
   rail (604 px) scrolls inside its own box. Phones 390×844 and 320×700:
   no horizontal overflow; the folded readouts row with worst-case
   numbers measures scrollWidth == clientWidth (345 == 345, 275 == 275)
   and does not wrap; the Gauges group fits its rail.
7. As 6, sampled by `getBoundingClientRect().top`.
8. Used the page for several minutes across modes, folds, tabs and widths.
9. Structure: the Gauges group reads as two named blocks each with Mode
   and Range; nothing is explained twice. With Remote off every gauge
   button is disabled, as before.
10. Gauge painting was proven with the cookbook's debug-hook: `fetch`
    patched to answer `setpoints.gauges = {Pd: Pa/-6, Pu2: Torr/-4}`,
    the folded line read "Pd Pa 1e-6" and "Pu2 Torr 1e-4" and exactly
    those four buttons were pressed; the page was reloaded clean after.
    A real press from a browser needs the Remote switch on the Qt
    window, which this session did not reach; the command path is
    covered by tests.

`lab stop` confirmed: process gone, 48937 free. No console errors.

## The Remote switch (same release, second commit)

Owner, mid-session, with a screenshot of the new dock: "can you fix the
remote/local button in GUI?" — LOCAL rendered as ".OCAL". Delegated to a
subagent (Opus) with a bounded packet; inspected here. Cause: MySwitch
painted a 148 px track whatever width the layout gave (111 px in the
dock's top row), and Qt clips at the widget's edge; the 4.0.1 fix only
shrank the font to the sliding part, which itself hung off the widget.
Fix in `controlunit/ui/buttons/toggles.py`: track, sliding part and word
are measured from the widget's real rect, the word shrinks to a 6 pt
floor and is narrowed rather than clipped below it, and `hitButton` is
the painted track. `tests/test_switch_labels.py` holds every top-row
switch's two words inside it at a 480 px dock. Before/after renders with
the real font engine were compared (`.OCAL` reproduced, then whole).
Gate after the fix: pytest 581 passed.

## The evening: 4.18.1, 4.18.2 and the readouts rebuilt (4.19.0)

Owner's first run on 4.18.0 (screenshots): the Kikusui sidecar recorded
1.078 V / 5.050 A with output on beside a 599 mV manual drive — first
evidence of the recorder on the rig. His review of the UI is in
directions ("The 4.18.0 review", his words, and the design drawn from
them). Shipped tonight, each by a subagent with this session inspecting:

- 4.18.1: Start pushed only the first gauge's settings into a new worker,
  so Pu2 ran at 1e-3 while the page showed 1e-6 ("a UI lie"); every
  gauge's pair is pushed now, with a test. Pull to the Pi pending an idle
  rig (it was acquiring all evening).
- 4.18.2: the Ion gauges card names each gauge by place beside its short
  name; the dock keeps the short name alone.
- 4.19.0: the readouts as panel meters from his sketch, the cathode V/I
  cards in the strip, the Kikusui panel gone, "below zero" dropped.
  Inspected live on a scratch instance (48937, scratch roots, owner's
  port untouched) with a patched state feed: small cards 53 px with 24 px
  digits, three per row at 1280 (strip 176 px); big cards 83 px with
  45.6 px digits, two per row at 1280 (strip 356 px); at an 800 px window
  big is one card per row at 65 px digits. Both rails at 76 px at every
  scroll depth at 1280×1000 and ×700; the folded row with eight values
  fits 320/390/1280 without wrapping (256/275, 317/345, 513/572 px). The
  builder's own Perimeter Walk is in its report; the ten steps were
  re-run here on the strip and the tabs.

Recorded for later this week, not built: the rail/status-line/window/
chart-empty-state/OUTPUT-lamp slice, the IG_u/IG_d typeset labels with
the self-explaining file header, the cathode current on the plasma
chart, the PID rebuild packet, the noise study, the NAS backup. The PID
builder was started and stopped before it changed a file ("give me
something finished now, PID later this week").

Gates for 4.19.0: pytest, node behaviour tests, strict MkDocs, diff
--check, all clean; see the commit.

agent: claude fable 5.1

# The Live strip, the Display card and the pulldowns — 2026-10-07, 4.26.0

Queezz, live, three things in an afternoon: "Observe and monitor waste a
lot of top bar space by showing there... nothing!" (a 2000 px Monitor
screenshot: the mode switch alone on a row, the pills and sampling under
it, Display and Full screen under those, Window and Median under those);
"the display items are hidden uncomfortably there" (the right rail's
Display drawer: a header box over four separate cards); and "we don't
have to make all the buttons for all the samplings. We can use a pulldown
selector. So it shows what's selected, and all the options don't crowd
our UI". Then: "you can fix UI".

Read first, completely: fleet `RULES.md` §10, `WEBUI.md`,
`WEBUI-COOKBOOK.md`. The implementation was dispatched to an Opus
subagent with the design as a packet (his standing word the same day:
"for dev use Opus or Sonnet if needed"); the review, one fix, the
docking change and the Perimeter Walk are this session's.

## What shipped

- One strip heads the Live page: pills, the status sentence, Sampling,
  QMS sync, and in Monitor also Window, Median, Display and Full screen
  and the mode switch, all one flex row. Monitor at 1280 px: the strip is
  28 px tall at 14 px from the top, the readouts fold starts at 50 px and
  the first number at 86 px, where it was about 180.
- The mode switch has three homes and one element: Monitor keeps it on
  the strip (no tab bar); Operate and Observe on a desktop dock it into a
  new empty slot at the tab bar's right end (`tab-tools` in
  `topbar.html`), a row already on the screen; a phone in Operate and
  Observe keeps it in the Menu. The desktop docking was added after the
  first measurement: with the switch on the strip, Operate at 1280 px
  wrapped the strip to two rows (59 px), a row the switch never cost
  before.
- Sampling is a `select`, gated through `.sets select`; Window, Median
  and Show are selects in one Display card with Polling as a seg-toggle;
  This run is one card too. The folded Display line says the choices.
- Fixed in passing (found by the subagent): the ion-gauge Torr/Pa buttons
  carry `data-mode`, and live.js bound every `[data-mode]` to the view
  mode, so a Torr press in Monitor's drawer sent the page to Operate.
  Scoped to the switch's own buttons, looked up from the document.

Gates: pytest 698 passed; `mkdocs build --strict`; `node --test` on the
five behaviour files, 53 passed (three new). Version 4.26.0, changelog,
`docs/architecture/web-ui.md` updated.

## Perimeter Walk

Scratch `lab start controlunit-dummy --port 48937` under scratch
`LAB_CONFIG`, `LAB_RUNTIME_ROOT`, `LAB_LOG_ROOT`, `HOME` and `USERPROFILE`
in the session's scratch folder, `QT_QPA_PLATFORM=offscreen`, a
`kikusui.yml` with `dummy: true` there. The listener's process was read
by `OwningProcess` and its command line (`python -m controlunit.main
--web --host 127.0.0.1 --port 48937`), 4187 had no listener before,
during or after; restarted once for the tab-bar slot (templates are not
reloaded live), stopped at the end: process gone, 48937 free. Live DOM
through the in-app browser pane.

1. From Live: Log and Lab landed at scrollY 0 with their titles; the
   brand from Lab landed on Live at 0 in Operate with the switch in the
   tab bar. The `tab-tools` slot is empty and `display: none` on Log and
   Lab.
2. The surface's own doors: the Display drawer button in Monitor opened
   the right rail; Torr pressed inside it left the mode at Monitor and
   the drawer open.
3. `#sec-acquisition` and `#sec-sync` land at 72 px, `#sec-who` 133,
   `#sec-gas` 180, `#sec-gauge` 208, `#sec-plasma` 665, at 1280×1000,
   below the 56 px bar and on screen.
4. Back from Observe to Monitor to Operate, Forward to Monitor: each the
   expected mode, the switch in the right home each time.
5. `location.reload()` on `/?mode=monitor` after Window 1 h, Median 15
   and Show Plasma: all three restored, Pu, Pu2 and Pd hidden, the
   folded line "1 h · median 15 · Plasma", Window and Median docked on
   the strip; a hand-picked Pu then read "custom". Reload on
   `/#sec-plasma`: Operate, the card open, the anchor at 665, Window
   back in the Display card.
6. and 7. Both rails at 76 px at 0, 25, 50, 75 and 100 % of the scroll
   range at 1280×1000 (range 367 px) and at 1280×700 (667 px). At 700 the
   right rail's content (1159 px) scrolls inside its own 604 px box; the
   page does not scroll for it.
8. As an operator: name saved, Start (run `cu_20261007_135335.csv` in
   the scratch home), the Sampling pulldown disabled before the run and
   live after; chose 1 s, "done: sampling 1 s", the pulldown and This run
   both read 1 s after the poll; QMS sync on; Polling fast; the Display
   card folds to a 42 px row reading "1 h · median 15 · fast"; Escape
   closed the drawer, a second Escape walked Monitor to Observe. At
   375×812: no horizontal overflow, the switch and Stop all outputs in the
   Menu in Operate, the switch on the strip in Monitor, the readouts at
   171 px there.
9. Nothing on the page explains itself twice; the labels are the four
   words Sampling, QMS sync, Window, Median in the rail's own voice, and
   a pulldown shows its value.
10. Console: only the connection-refused lines from the restart, no
    script error.

Not walked: 320 px (the pane does not emulate below 375), and the Stop
button's confirmation, which a scripted press does not answer.

## Left

In `directions.md`: his next ask, a press on a readout card to hide it
so a phone shows the two or three a regime needs, with a design. The rig
runs 4.25.0; nothing was pushed or pulled.

agent: claude

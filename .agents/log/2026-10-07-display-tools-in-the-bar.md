# The four display tools, out on the bar — 2026-10-07, 4.28.0

Queezz, live, after 4.27.0 had gone to the rig: "Don't we have space
somewhere on the top bar-ish for keeping 4 display pills there
permanently? normal/fast is a toggle. And we don't need big
descriptors.. Some small one or an icon would do, I think."

Third slice of the day; the same shape as the first two: design here,
implementation on an Opus subagent, review, two fixes and the Perimeter
Walk here. Fleet's UI law read in full for the first slice.

## What shipped

- Window, Median, fast polling and Show are one group of four small
  controls, each named by a hand-drawn inline SVG icon (a clock, a
  smoothed wave, a bolt, an eye; strokes in the text's colour, nothing
  fetched) with the word as its tooltip and label. Polling is one
  press: pressed is fast.
- Three homes, one element, like the mode switch: on a desktop in
  Operate and Observe the group docks into the tab bar's right-end slot
  before the switch (`displayToolsHost`); in Monitor, which has no bar,
  and on any phone it stands on the status strip after Sampling and QMS
  sync. Never in the phone's Menu: it is not navigation.
- The right rail's Display card is gone with its folded line; the four
  controls are in one place only. Remembered choices carry over.
- Two labels fixed here after the subagent flagged them: Monitor's
  drawer button says "Gauges", which is what the rail holds there now
  (Ion gauges and This run), and the rail's label is "Access and
  gauges".
- One measurement, one fix: at 1280 px Monitor's strip came to 1182 px
  of controls in a 1225 px column and twelve-pixel gaps wrapped it by
  17 px to two rows. The gap is ten and the switch's buttons 5 rem; one
  row again, the first number at 86 px.

Gates: pytest 700 passed; `mkdocs build --strict`; `node --test` 62
passed (three new). Version 4.28.0, changelog, `docs/architecture/web-ui.md`.

## Perimeter Walk

Scratch `lab start controlunit-dummy --port 48937` under scratch roots
and a scratch home, the listener read by `OwningProcess` and its command
line, 4187 without a listener throughout, `lab stop` at the end with the
port confirmed free. Live DOM through the in-app browser pane.

1.–2. Operate at 1280×1000: the bar reads brand, Log, Lab, then the four
   tools (330 px) and the switch (246 px) from x = 659 to 1245, the Lab
   link ending at 280. The strip under it is 28.5 px, the readouts at
   112.5. Observe: the same slot, the same order. Monitor: the slot
   empty, the strip carrying pills, Sampling, QMS sync, the tools, Gauges
   and Full screen and the switch, one row of 28.5 px after the gap fix,
   the readouts at 50.5 and the first number at 86.5. The drawer button
   reads "Gauges"; the rail's cards are Operator and access, Ion gauges,
   This run.
3. `#sec-acquisition` and `#sec-sync` at 72 px, `#sec-gauge` 128,
   `#sec-plasma` 232, `#sec-who` 293: below the 56 px bar and on screen.
4. Back and Forward were walked for 4.26.0 on the same mode mechanism
   and nothing in this slice touches the address or the history.
5. `location.reload()` on `/?mode=monitor` after Window 30 m, Median 51,
   Show Vacuum and fast pressed: the three choices restored and fast
   back to normal, which is its rule (fast resets on reload).
6.–7. Both rails at 76 px at 0, 50 and 100 % of the scroll range at
   1280×1000. The 700 px height was sampled for 4.26.0 and 4.27.0 today
   and this slice changes nothing above the rails' resting offset.
8. From the bar in Operate: Window 30 m redrew the charts ("last 30 m"
   in the span), Median 51 followed, Show Vacuum hid Ip and Ic, the bolt
   pressed read fast and the store held window 1800 and smooth 51. The
   icons are 14 px and the four controls stand 23–24 px tall on one
   line. At 375×812: the tools on the strip row under the pills
   (clock 30 m, wave 51, bolt, eye Vacuum), the switch and Stop all
   outputs in the Menu, no horizontal overflow.
9. Four icons with their words in the tooltip, said nowhere else; what
   to do first is unchanged.
10. Console: only connection-refused lines from the restarts between
    slices, no script error.

Not walked: 320 px (the pane does not emulate below 375).

## Left

Nothing new in `directions.md`. The rig runs 4.27.0; 4.28.0 is committed
and not pushed. Pushing and deploying it is his to say.

agent: claude

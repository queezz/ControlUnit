# A press hides a readout card — 2026-10-07, 4.27.0

Queezz, live, during the walk of 4.26.0: "when operating, I wanted a
click to toggle the big digit screens for gauges and ADC readings. For
some regimes I only need 2-3, so others get in the way on mobile."

Built as the second slice of the afternoon, the design settled by this
session and dispatched to an Opus subagent; the review and the
Perimeter Walk are this session's. Fleet's UI law was read in full for
the first slice the same day.

## What shipped

- In Operate and Observe a press on a readout card hides it. The card
  keeps its place in the grid (only `hidden` changes), and comes back
  there. Each hidden card is one pill at the grid's end, in the card's
  pen, named as the folded row names it (`Uc`, `Ic` for the supply's two),
  in the legend's own vocabulary: a dimmed pill is something switched
  off, and pressing it brings it back. Focus follows: to the pill on
  hide, to the card on show; Enter and Space press a card.
- Monitor shows every card and no pills, and a press there does nothing
  (the cards are `aria-disabled`, out of the tab order). The two other
  modes share one hidden set, `hiddenReadouts` in the remembered view;
  an older store reads as nothing hidden.
- The folded row keeps every value, hidden or not. Nothing recorded
  changes.
- The card is a `div` with the button role, not a `<button>`: the
  digits are sized from the card as a container (`cqi`), and a button is
  not a size container every browser honours. The verb is an sr-only
  "Hide" before the card's own name and number.

Gates: pytest 699 passed; `mkdocs build --strict`; `node --test` 59
passed (six new). Version 4.27.0, changelog, `docs/architecture/web-ui.md`.

## Perimeter Walk

Same scratch recipe as the first slice (`lab start controlunit-dummy
--port 48937` under scratch roots and a scratch home, listener read by
`OwningProcess`, 4187 without a listener throughout, `lab stop` at the
end with the port confirmed free). Live DOM through the in-app browser.

1.–4. The surface adds no link and no anchor; tabs, Back and Forward
   were walked for 4.26.0 an hour earlier on the same page and nothing
   in this slice touches them. Operate, Observe and Monitor were each
   entered from the switch with the hidden set in place.
5. `location.reload()` with Pu, Pd, Bd and Cathode V hidden: the four
   stayed hidden, four pills, the folded row still eight values.
6. and 7. Both rails at 76 px at 0, 50 and 100 % of the scroll range at
   1280×1000 with four cards hidden (the range shrank to 80 px).
8. As an operator, a run going: a real pointer press on the Pu card hid
   it, left one pill "Pu" in `#c9004d` at 50 % opacity with the focus on
   it, and wrote `["Pu"]` to the store; the folded row still read Pu
   `3.2e-5`. Three more presses hid Pd, Bd and Cathode V (pill "Uc"),
   four cards standing. The Pu pill brought Pu back at its own place,
   index 1, with the focus on the card. Observe: the same three hidden,
   three pills. Monitor: all eight shown, the pill row hidden, a press
   on Ip changed nothing, cursor `default`, the store untouched. Back in
   Operate the three were hidden again. At 375×812: five cards at 172 px
   each, two a row, the pills under them at 195 px from the top of the
   strip, no horizontal overflow; big pressed, one card a row at 79 px.
9. Nothing on the page explains itself: a card is a card and a pill is
   the legend's pill. What to do first is unchanged (Start); the next
   round is a press on a pill.
10. Console: nothing.

Not walked: 320 px (the pane does not emulate below 375).

## Left

`directions.md` is lighter by the item this built. The rig runs 4.25.0;
4.26.0 and 4.27.0 are committed and not pushed, which is his to say.

agent: claude

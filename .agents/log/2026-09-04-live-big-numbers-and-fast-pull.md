# 2026-09-04 — Live reads big, and pulls fast when asked

Two things queezz asked for in his own words: "Can we add a BIG NUMBERS
toggle, so I CAN SEE PRESSURES AND ALL REAL BIG AND NICE?" and "Can we have
a fast pull for the plot, so I can take the laptop to, say below the desk and
adjust Baratron zero? Short view window, but as fast as we can pull... We
don't need that normally." Built off-rig on the dummy hardware, 0.7.0. The
rig was not touched: no SSH, nothing started or stopped on the Pi.

## What shipped

- **Display: normal | big**, a new left-rail card. Big adds one class to the
  page, `.live--big`; no element appears, moves parent or leaves, so the
  rails and the charts stay exactly where they are and only the readout row's
  own height changes. The cards grow until only as many fit a row as have
  room for the number, and the rest wrap. The value is sized from the card it
  stands in — `min(3.6rem, 19cqi)` — so the widest a pressure ever reads,
  `-5.00e-3`, keeps one line at every width, from a phone to the two-rail
  desktop. Remembered per browser under the existing `controlunit.live` key,
  a convenience and never a fact.
- **Poll: normal | fast**, beside it. Normal is what it was, state every
  second and series every two. Fast asks for both four times a second, so the
  five readouts move with the chart rather than a second behind it, and keeps
  whatever Window the reader chose rather than forcing a short one. The
  charts say `· fast` beside their span while it runs. It is deliberately not
  remembered: the card's own heading says `Poll · forgotten on reload`, and a
  page left open overnight goes back to asking once a second.
- **The series route stopped copying the ring.** `RigStatus.series` used to
  copy both deques to lists on every call and then bisect. It now walks
  backwards from the newest sample and stops at the first one outside the
  window, so twenty seconds costs two hundred rows however long the ring has
  grown — which is what makes a 4 Hz poll fair on a Pi holding two hours of
  10 Hz samples. `Full` still copies everything, because everything is what
  it asked for.

## Measured, in a real DOM

Scratch instance on `127.0.0.1:48940`, `HOME` redirected into the session
scratchpad, dummy hardware, the ADC patched in the driver to return slow
waves. Numbers, not impressions:

- **Big at 1280×1000:** value 53.3 px (3.33 rem), one line in every card;
  the worst case `-5.00e-3` measures 249.8 px inside a 280.5 px card, 30.7 px
  to spare; cards 314.5 × 118.4, laid out 2 + 2 + 1. Normal in the same
  window: 16 px, five across, `-5.00e-3` 75 px inside 94.2 px.
- **Big at 900×700:** 45.5 px (2.85 rem), 3 + 2, worst case 213.4 px inside
  239.7 px, 26.3 px to spare. At 375×812 it is one column at the 3.6 rem cap,
  270 px inside 317 px. No horizontal scroll at any of the three
  (`scrollWidth === clientWidth`: 1265, 885, 375).
- **Nothing moves when the mode changes.** Both rails read 76 px before,
  during and after pressing big and normal again, and every rail card's own
  top is identical across all three states (left 76/211/345/470/568, right
  76/341). Rail offsets are 76 px at 0/25/50/75/100 % of the scroll range at
  1280×1000 and at 1280×700, in both modes.
- **The rail still fits a short window.** The left rail's natural content is
  575.5 px in a 604 px box at 700 px tall — 28.5 px of room. It did not at
  first: the Poll card's explanatory paragraph put the content at 605 px, one
  pixel over, and the rail's `overflow: hidden` would have cut the last card
  silently on a shorter screen. The sentence moved onto the card's own
  heading line, where teaching costs the rail no height at all.
- **The rates are what they claim.** Over six seconds each: normal, state
  every 999.2 ms and series every 1997 ms; fast, both every 250.5 ms (24
  requests each); normal again, 1000 ms and 2000 ms. Under fast the Ip
  readout took eight distinct values in 2.5 s, so the numbers move at the
  fast rate and not the old one. The series request follows the reader's
  Window: pressing `20 s` under fast asks `?window=20` and the span reads
  `last 20.0 s · 179 samples · fast`. The Data card's age still reads to one
  decimal (`0.2 s ago`). Server side under a 4 Hz poll: `/api/series` median
  13.9 ms, max 50.6 ms; `/api/state` median 10.1 ms.
- **Reload:** big comes back, the window comes back, fast does not — the
  rates measured 4 state and 2 series requests in four seconds after a
  reload, and the span carried no `· fast`.
- Log and Lab still render with both rails at 76 and no horizontal scroll;
  returning to Live lands at scroll 0. No console messages of any kind, and
  all 19 requests went to `127.0.0.1:48940` — nothing to the internet.

## Gates

From the worktree root with the shared `hardware-dev` interpreter and
`QT_QPA_PLATFORM=offscreen`, exit codes captured, nothing piped: `pytest -q`
77 passed (6 new), exit 0; `mkdocs build --strict` exit 0; `flake8
--select=E9,F63,F7,F82` exit 0.

The new tests: one proves a short window never walks the old rows, by
swapping the ring for a deque that counts what an iteration touches — 72 000
rows in, at most 210 visited for a 20 s window; one proves the backwards walk
cuts where the old bisect did; three cover the two new cards, the single
class, and that `fast` is not in what gets written to the browser's store.

## Left

- 2 + 2 + 1 rather than 3 + 2 at 1280 px wide is a real trade, not an
  oversight: between two 17 rem rails the reading column is 641 px, and three
  cards across it cap the number at about 2.3 rem. Big was worth more than
  one fewer row. Below the rail breakpoint, where the column is the whole
  page, it is 3 + 2.
- The teardown killed the launcher as a tree (the Python 3.14 launcher's
  child holds the port); 48940 held no listener afterwards.
- Nothing was deployed. The Pi's checkouts and the running process are
  untouched, and this branch has not been pushed.

agent: claude opus 5

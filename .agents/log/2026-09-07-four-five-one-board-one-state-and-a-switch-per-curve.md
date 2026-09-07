# 2026-09-07 — 4.5.0: one board, one state, and a switch per curve

Four things, in the order they were asked for. The trio's board now breaks
where the other two boards break; the rig says whether anything is actually
being driven; the lab's names arrive over the LAN instead of by hand; and
each chart carries the switches for its own curves. Verified in a browser
against a scratch view on 127.0.0.1:48957 with dummy data, a scratch
settings home and neighbours pointing at ports nothing listens on. The
owner's rig and its port 4187 were never touched, and the scratch port was
confirmed free before and after.

## The board's numbers are the reference's now

4.4.0 put three cards across at 1280 px, because the commission said three
across at 1280. The reference does not do that, and the Commander said so
the same night: the diagram's board lays two cards across and one below at
1280 and goes three-across from about 1415 px, which the owner's Mac has.
Following the wording instead of the reference cost this surface a 203 px
card, fact labels stacked above their values, and the **Runs** row dropped
to make room.

Four numbers decide where a board breaks and all four are shared now: 16rem
rails (they were 17rem here, which took 32 px more out of the reading column
than the other two and pushed the three-across threshold past his Mac),
260 px cards, a 14 px gap between them and the 20 px page gap. Measured, at
1280 px: cards at x 296 / 640 / 296 — the diagram's own numbers to the pixel
— 330 px wide, in a 673 px reading column. Three across from between 1400
and 1415 px; three across at 1440. At 330 px the fact labels stand beside
their values again, so the card-only list shape is gone; the **Runs** row
stays out, because the reference has no fourth row either.

The rail width is not only the board's. Both rails on every tab are 16rem
now, and the two that were measured against 17rem were re-measured: both
rails hold one identical offset of 76 px at 0/25/50/75/100 % of the scroll
range at 1280×1000 and 1280×700, and every rail fits its box at 700 px
(604 === 604 on both, on all four tabs).

## Is the rig running, and is anything on

queezz, relayed the same night: *"If the rig is running. And if it's
measuring only or have some gas/plasma on."* The report said `acquiring` or
`idle`, which is not the same question. On 2026-08-19 the ADC reader died
mid-run and the plasma kept going, because the cathode DAC held the voltage
it had been given: nothing recording, apparatus driven. "Not acquiring" was
never "safe to restart".

`status.py` answers it in three words — `stopped`, `measuring`, `outputs
live` — and outputs outrank the acquisition flag, because that is the whole
point. What counts as an output is a list of setpoints the main thread
already records, each with the plain words that name it: gas flow H₂, gas
flow O₂, cathode drive, plasma current PID. Names only, never a value: this
answer travels into the health report the other two surfaces render.

One of those four was not being recorded at all. `plasma_a` is the PID's
setpoint, and the rig's own output-voltage box drives the cathode DAC
directly with the PID off — the exact pair that killed Mizuno-kun's
depositions — so `main.py` now records `cathode_mv` beside it at all five
places that move that DAC, the PID's own feedback step included.

It reaches three surfaces without a new contract. `/api/health`'s `detail`
says `idle, not recording`, `acquiring 9 channels at 10 Hz`, or, whether or
not anything is recording, `outputs live:` and the names — so the trio
boards show it as they already show that sentence. `/api/state` carries
`operating: {state, outputs}`. And the Live tab leads with two pills: the
apparatus on the left, the freshness on the right, at the head of the column
they describe. The data chip moved out of the rail to join it, so neither
pill is on the page twice, and the rail card that used to hold it now only
explains — `measuring`, `outputs live`, `stale`, `idle`, each once.

Idle is still `ok`. Outputs live with nothing recording is still `ok` too:
it is not a fault of this program's, nobody pressed Start, and the owner's
correction about amber boards stands. What changed is that the rig now says
it.

`AGENTS.md` grew the check a session runs before pulling to the Pi, and
`.agents/README.md` points at it: read `/api/health` first, refuse while it
says `outputs live:`, name the outputs it listed, and leave the rig alone.

## The names come over the LAN

PIHTI Log 0.38.0 serves the vault's roster at `GET /api/roster` on the same
origin this rig already asks `/api/health` of. `RosterMirror` reads it
behind the neighbour probe — it keeps no clock of its own, so the rig asks
the office PC for names exactly as often as it already asks it how it is,
at most once in ten seconds, with the same two-second patience.

Three rules, all tested. The copy is never written in halves: it is written
beside itself and moved into place with one `os.replace`. A copy that
already says the same thing is left alone, so an unchanged roster costs no
write and does not disturb the `(mtime, size)` fingerprint the reader
watches. And the last copy stands for every kind of no answer — silence, a
404 from a vault with no roster, a body that is not a roster, an empty list
— because a name spelled correctly for a month should not vanish because
the office PC is off.

`scripts/push_roster.ps1` stays: it is what a new Pi needs once and what a
machine that cannot reach the journal uses. When the copy was last confirmed
is on Control, on the Acting-as card's heading line — *"· PIHTI Log
14:02:57"*, or *"· names not read yet"*.

That line was nearly a defect. As a line of its own it took the left rail
2 px past its box at a 700 px window, which clips the Stop-all note; that
rail carries three cards and, on the rig, the fence row, and it fitted with
nothing to spare. On the heading's own line it costs no height, which is
what that pattern is for. 604 === 604 again, measured with a roster and a
fence both present, which is the rig's own shape.

Proved end to end over a real socket as well as with a fake opener: fetch,
atomic write, and the Acting-as list reading the new names; then a dead
address, and the names still there.

## A switch beside its own curve

queezz: *"all the little toggles on the Live view, hard to find the one I
need"*, and *"we need toggles, like in GUI, to show/hide plots"*. The five
channel switches stood together in a rail card, away from the lines they
turned off. Each one now stands in the legend of the chart that draws that
curve, in that curve's own pen, and the rail card is gone — one control, in
one place, still remembered per browser.

**This crosses a house rule and is worth saying plainly.** Fleet's WEBUI.md
says the main view is content and the rail is controls, and a chart legend
is in the main view. The reasons for crossing it: the owner asked for the
GUI's own arrangement, where a curve's switch is beside its plot; a legend
is part of a chart rather than a control panel added to the reading column;
and nothing is duplicated, because the rail card was removed rather than
kept beside it. If queezz would rather have the rail card back, it is a
small change in one direction or the other, and it is his call, not this
session's.

**And a curve that says nothing now leaves its panel.** His complaint: the
broken upstream gauge sits at 1e-5 while the downstream one reads 1e-8,
both on one log axis, and *"can't see either"*. A curve whose whole
excursion over the drawn window is smaller than its own last useful digit —
under a twentieth of a decade on a log axis, under 2 % of its own value on a
linear one — is left out of the panel's range as well as off the panel, and
its legend entry says `flat`. The axis then belongs to the curve that is
actually moving. A switched-off curve says `off` and an empty one says
`no data`; a curve that is drawn says nothing at all. Collapsing only ever
happens while another curve on the same panel is still moving, so a panel
never empties itself, and turning the moving one off brings the flat one
back — measured, both ways, in the browser. No value is printed in the
legend: every number on this page is read in its readout card above.

The current with no plasma — his other *"noisy waste of space"* — is **not**
collapsed by this rule, and deliberately: noise around zero has a large
excursion relative to its own size, and telling it from a real small current
needs a per-channel floor the rig has never been asked for. It is in
directions with that question attached.

## Measured

Scratch view at 127.0.0.1:48957, dummy hardware, `HOME` and
`CONTROLUNIT_SETTINGS_HOME` redirected to a scratch folder outside Dropbox.

Perimeter Walk at 1280×1000, 1280×700, 1440×900 and 390×844. Both rails at
exactly 76 px at 0/25/50/75/100 % of the scroll range on every tab at both
desktop heights; every rail 604 === 604 at 700 px and 904 === 904 at 1000 px.
No page-width overflow anywhere (document 1265 px in a 1280 px window,
1425 in 1440, 390 in 390). Every tab answers 200 with `no-store` and carries
the whole tab bar; back, forward and a true reload land where a reader
expects, and the Lab tab's opened Start disclosure survived the reload.
Control's five anchors land their headings at 72 px, 16 px clear of the
56 px bar. At 390 px the pills wrap to two lines, each legend keeps one, and
the three service cards stack in order.

The Retina guard still holds after the drawing code was reworked: with
`devicePixelRatio` forced to 1, 1.25, 1.5 and 2 in turn, every buffer is
exactly its panel's CSS height times the ratio, once, and the document stays
1248 px at every ratio — through all eight window buttons, a smoothing
change, big readouts and the fast poll.

The three operating states were driven with a patched `fetch` (the
cookbook's debug-hook-and-remove), each rendering its own chip: `stopped`
dotted and dim, `measuring` green, `outputs live` in the page's accent with
the outputs named beside it. The chip holds one width across all three, so
nothing beside it moves. Each concept on the Live page is explained exactly
once, counted on the rendered page.

461 tests, `flake8 --select=E9,F63,F7,F82` clean (this repository carries no
flake8 config and the full default run has never passed here), strict docs
build. Version 4.5.0 in `pyproject.toml` and `controlunit/_version.py`.

One flake worth naming: a full `pytest -q` run crashed once at teardown with
a Windows access violation after every test had passed, and did not recur in
three further runs. Qt shutdown, not this slice's code, but it is written
down in case it comes back.

## Deployment

Nothing is pushed. `master` is at 4.5.0 in this checkout and queezz pushes
when he says so; the office checkout also still holds 4.4.0's three commits
unpushed. Then the rig: `git -C ~/work/aktest pull --ff-only` on a Pi that
is neither acquiring nor driving an output — read `/api/health` first, which
is now the check `AGENTS.md` writes out — and his own restart from the
desktop shortcut.

Nothing else is needed for the roster: the Pi already reaches the office PC,
and the copy refreshes itself the first time the journal answers. The
`open_url` and `start_how` lines in the Pi's `neighbours.yml` are still his,
and still separate from the pull.

## Fleet

Four letters collected after their substance was recorded here:
`20260907-f9a313ab` (the board's breakpoints), `20260907-95bde394` (the
rig's operating state), `20260907-2e0205ef` (PIHTI Log's roster route) and
`20260907-6f353ea0` (the owner's notes on Live and Control). All four are
action mail — the last two were described as notes in this session's own
packet and Fleet refused `--logged` for both, which is the store being
right and the packet being loose.

Notes posted: `20260907-87a6d0f9` to `code/pihti-log` (the roster consumer
is built), `20260907-db04b74c` to `code/2024-interactive-diagram` (the
board's numbers are theirs now), and `20260907-13caa10a` to `code/fleet`
(the rail-law crossing above, and what the Live and Control work still
owes).

Usage receipt: provider Anthropic, model Claude Opus 5, task "commander run
round 2: pihti trio / ControlUnit", child agents 0, provider usage
unavailable — no meter was shown to this session.

agent: claude opus 5

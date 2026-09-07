# 2026-09-07 — 4.4.0: the Retina runaway, idle is ok, and the trio board

queezz read the three PIHTI surfaces side by side on his Mac and had PIHTI
Log audit this one from there. Six things came back; all six are fixed. This
session did the whole slice itself, in this checkout, against a scratch web
view on 127.0.0.1:48951 with dummy neighbours and a scratch settings home.

## The charts that ran away on his Mac

`live.js`'s `prepare()` read `canvas.getAttribute("height")` as the panel's
layout height and then wrote `canvas.height = height × devicePixelRatio` —
and `canvas.height` **is** that attribute. At ratio 1, which is every screen
in this lab, the second pass reads back the same number and nothing moves. At
ratio 2 the panel doubles on every redraw, and the Live tab redraws on every
poll. PIHTI Log measured it from his Mac: the plasma panel's height attribute
at 1,802,240 px, the document at 2,540,001 px, doubling once more when the
20 s window was chosen, then a white failed plot.

A panel's height and its drawing buffer are two facts now, and they live in
two attributes. `data-height` on each `<canvas>` is the layout height and
nothing writes it; the buffer is computed from it once per width, height or
ratio change, bounded at 8192 px a side because a browser refuses a canvas
past that and hands back a context that draws nothing, and a panel whose
`getContext` returns nothing is left blank rather than throwing on every
poll. Three pytest cases pin the shape by reading the source: the attribute
is never read back, the bound and both null guards are present, and all
three panels declare their own height.

Measured in a real browser, forcing `devicePixelRatio` to 1, 1.25, 1.5 and 2
in turn: the buffer is exactly 220/200/200 × the ratio, once, and it holds
there through continued polling, all eight window buttons, six resize events
and a smoothing change. The CSS heights stay 220/200/200 and the document
stays 1098 px at every ratio. Leaving Live for Control and coming back is
clean.

## Idle is not degraded

`healthy = acquiring and not dummy` made a rig that was up and waiting paint
the lab's shared board amber all night. queezz: "It's up and not doing a
thing, not degraded." `health_status` now answers `ok` for that, with the
detail *"idle, not recording"*.

`degraded` is kept for a capability that is actually impaired, and this
record can see exactly two today. First, a run whose last sample is older
than the stale bound — the reader died between two of them, which is what
happened to Mizuno-kun's depositions on 2026-08-19, and it is the only real
failure this report can name until the watchdog in directions is built; the
detail names the gap in seconds. Second, dummy devices standing in for the
instruments, which is honest about what the process cannot do rather than an
invented failure, and never happens on the Pi. Nothing is called degraded
before it has been measured: a run whose first sample has not landed is `ok`,
because at ten seconds a sample that gap is ordinary and degrading through it
would cry wolf on every Start.

## The Lab tab is the trio board

queezz, from three screenshots: "Three link tabs, and all different. They
should wear different colors so we know which one is which, but they should
be identical. The diagram is doing the best job here on mac."

The board already had the diagram's rails; what it did not have was the
diagram's geometry or its order. Three cards now stand across the reading
column — 203 px each at a 1280 px window — in the ensemble's one order on
every machine: **PIHTI diagram, PIHTI Log, ControlUnit**, this program's own
card third rather than first. Stacked full width, the third service sat below
his viewport and had to be hunted for.

Two adaptations to a 203 px card, both measured rather than guessed. The
**Runs** row is gone: `start_how` already names the machine ("from the office
PC, as lab pihti-log"), and the card had no room to say it twice; `where` is
still read and still carried by `/api/neighbours`. And inside a card the fact
labels stand above their values instead of beside them — a two-column list at
that width left the value about a hundred pixels and broke every sentence
after two words. The card title wraps to two lines on the two longer names,
because the state chip reserves 9.5ch so a state change never nudges anything
beside it; that reservation is worth more than the second line costs.

Everything 4.2.1 had is intact: plain-words start rows with the command
behind a toggle whose state survives a reload and the board's own refresh,
the six-chip legend with More, `checking`, the 2 s probe and 10 s cache, and
the warm palette.

## A green chip is not a promise about your laptop

On his Mac the diagram's card said `ok` and its Open link did nothing: the Pi
resolves the bare name `pihti` on its own network and a Mac does not, though
it resolves `pihti.local` and the numeric address. The chip was the rig's own
measurement and was never a promise about the browser reading the page.

`neighbours.yml` takes an optional `open_url` beside `url`. `url` stays the
address this rig asks from; `open_url` is what a browser opens, and the card
prints that address under the link so a reader can see which name is about to
be tried. Absent, they are the same and nothing changes. The rail's lead line
says the distinction once for the whole surface — "What this rig reached just
now. An Open link is your own browser's to follow." — and the More panel
elaborates it. No deployment address is in the repository; the example in the
docs is `pihti.local`.

**This is queezz's to finish.** The Pi's `neighbours.yml` needs the
`open_url` line before his Mac's Open link works; it is in directions as
owner work.

## Two counts, two labels

With seven messages held, searching "sampling" left two rows, the Find card
said "2 of 7 lines" and the right card still said "Lines shown 7" — one word
for two numbers. It is **Retained** and **Shown** now, both current on every
keystroke and every new line. A filter that matches nothing says so, in its
own sentence, because an empty column looks exactly like a log with nothing
in it and they are not the same fact.

Measured: 7/7 at rest; "sampling" → Retained 7, Shown 2, "2 of 7 lines", 2
rows; a word nothing holds → Shown 0 and the sentence; cleared → 7/7. With
the filter open, a synthetic poll carrying two new lines (one matching) moved
Retained 7→9 and Shown 2→3.

## Two colleagues spelled the same way

The Acting-as list offered one word twice, so choosing the second told you
nothing about which colleague the log would name. A display name two people
in the roster share is now offered as "Display Name (username)"; a name
nobody shares is untouched, nothing is merged, no identity is renamed, and a
colliding entry with no username is left as it stands rather than given an
invented one. Verified on the page and through `/api/roster`.

## Measured

Scratch web view at 127.0.0.1:48951, dummy data, `CONTROLUNIT_SETTINGS_HOME`
and `HOME` redirected to a scratch folder outside Dropbox; the owner's rig
and its port 4187 were never touched, and the port was confirmed free before
and after.

Perimeter Walk at 1280×1000, 1280×700 and 390×844. Both rails at exactly
76 px at 0/25/50/75/100 % of the scroll range on Live, Control, Log and Lab,
at both desktop heights; both rails fit their box at 700 px (604 === 604);
the ensemble card 446 px collapsed and 604 px open inside that same 604, with
the More button at 484 px in both states. No page-width overflow anywhere
(document 1265 px in a 1280 px window). At 390 px the three cards stack in
order, Check above and the legend below, no horizontal scroll. Every tab
answers 200 with `no-store` and carries the whole tab bar; back, forward and
a true reload all land where a reader expects, and the opened Start
disclosure survived both. Control's five anchors land their group at 57 px,
the bar's own bottom edge, unchanged. No console error from the app on any
tab.

433 tests, `flake8 --select=E9,F63,F7,F82` clean (this repository carries no
flake8 config and the full default run has never passed here), strict docs
build. Version 4.4.0 in `pyproject.toml` and `controlunit/_version.py`.

## Deployment

Nothing is pushed. `master` is at 4.4.0 in this checkout and queezz pushes
when he says so. Then the rig: `git -C ~/work/aktest pull --ff-only` on a Pi
that is not acquiring, and his own restart from the desktop shortcut. The
`open_url` line in the Pi's `~/.controlunit/neighbours.yml` is separate from
the pull and is his; without it the board is correct and the diagram's Open
link still fails from a Mac.

## Fleet

Letters `20260907-023785d0` (the Mac audit), `20260907-50ccf555` (Lab links
show availability), `20260907-86d2c305` (idle is ok) and `20260907-43cf71f7`
(identical trio boards) collected after their substance was recorded here;
note `20260907-d7bfa5df` logged. Replies posted to `code/pihti-log` and
`code/2024-interactive-diagram`.

Usage receipt: provider Anthropic, model Claude Opus 5, task "commander run:
pihti trio / ControlUnit", child agents 0, provider usage unavailable — no
meter was shown to this session.

agent: claude opus 5

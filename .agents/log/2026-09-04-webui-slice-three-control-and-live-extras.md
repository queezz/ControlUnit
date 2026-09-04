# 2026-09-04 — big readouts, a fast poll, baselines, and the Control tab

The evening's orders from queezz, in his words: "a BIG NUMBERS toggle, so I
CAN SEE PRESSURES AND ALL REAL BIG AND NICE"; "a fast pull for the plot, so
I can take the laptop to, say below the desk and adjust Baratron zero";
"Plasma current, baratrons. Can we have the adjust zero from the baseline
in UI?"; and "when you are ready, start the control tab dev. And use
subagents, then review." Version 0.7.0, on `master` at `5d591fa` plus the
walk's fixes.

Rig state throughout: acquiring on 0.6.0; the mass-flow controllers powered
but their valves closed, plasma power off, so no command could move
anything. The rig was not touched beyond the pulls it already had.

## How it was built

Two Opus subagents in isolated worktrees, in parallel, each with a
self-contained packet, each walking its own work live before committing on
its branch; then reviewed here and merged. The Live branch (`e0a0e61`) and
the control branch (`a9c90ff`) both bumped to 0.7.0 and both touched the
version file, the stylesheet, the status record, the docs page and the page
tests; three conflicts, resolved by keeping both sides. A third Opus agent
walked the merged tree, since nobody had seen both branches' stylesheet
and templates on one page. This was queezz's instruction ("use subagents,
then review"), and it is also what the fleet's tier rule asks for.

## What shipped

- **Big readouts** (Live, left rail, Display: normal | big). One class on
  the page; the five values lead the column at up to 3.6 rem, one line
  each, laid out 2 + 2 + 1 between the two rails at 1280 px and 3 + 2 below
  the rail breakpoint. Remembered per browser.
- **Fast poll** (Live, left rail, Poll: normal | fast). State and series
  every 250 ms instead of 1 s and 2 s; the reader's window is kept. Not
  remembered on reload, on purpose: it is for a few minutes under the desk,
  and a page left open overnight must not hammer the Pi. The series route
  now walks the ring backwards only as far as the window needs, so a 20 s
  answer costs 200 rows however long the ring has grown; measured on the
  scratch instance at 13.9 ms median under 4 Hz polling.
- **Baselines.** One path for Ip, Bu and Bd: the main thread averages the
  last two seconds of the run it holds, hands the worker the value over one
  `set_zero(channel, value)` slot, and the worker reports all three zeros
  back; the display, the plots and the web subtract them; the CSV never
  does. (As first built the worker averaged its own three-sample buffer;
  the walk found what that cost and it was changed, below.) The Scales dock's "O Bu" button, which existed and had
  never been wired, is wired; "O Bd" stands beside it. A latent bug went
  with it: the old `is not np.nan` guard never caught an empty buffer, so a
  zero could be set to NaN.
- **The Control tab** and the command path. A browser's request becomes a
  small record on a `queue.Queue`; the Qt main thread drains it on a 200 ms
  timer created only under `--web` and calls the very methods its own
  buttons call, after setting the Qt widget so the screen agrees. Setting
  needs two things: a name chosen in the browser (a cookie, a label, never
  a credential) and a **Remote** switch on the rig's own screen, beside the
  on/off switch, resting off and forced off whenever acquisition stops.
  **Stop all outputs** is always allowed. Routes: `/api/identify`,
  `/api/stop-all`, `/api/mfc/<n>`, `/api/plasma-current`, `/api/gauge`,
  `/api/sync`, `/api/zero`; `202` with an id when queued, `403` with the
  reason when the gate refuses, `409` when nothing is acquiring, `400` on a
  bad body. Every command is logged with name, value, origin address and
  time, so it shows in the Qt Log dock, the log file and the Log tab, and
  `/api/state` carries the last command's outcome so the browser learns
  the truth rather than assuming it. Acquisition start/stop from the
  browser is not built.

The gate is the brief's recommendation built as the default; the owner
question stays open in directions and changing the answer is one function.

## Review notes

Read in full after the merge: `commands.py`, the `main.py` and `adc.py`
diffs, the dock changes. Nothing crosses a thread it should not; the drain
records a failing command as refused and moves on, so a bad request cannot
stop the loop; the origin address goes into the log on the packet's own
order, which the docs now state as the one exception to "no address in a
response". One thing for queezz to look at on the rig's small screen: the
control dock's top row now holds four switches, so each is narrower.

## Gates on the merged tree

`pytest -q` 175 passed; `mkdocs build --strict` clean; `flake8
--select=E9,F63,F7,F82` clean. Exit codes captured, nothing piped.

## The walk of the merged tree

A third Opus agent, all ten steps on all four tabs, at 1280×1000, 1280×700
and 900×700, Live in both display modes. Bar 56 px everywhere; both rails
76 px at 0/25/50/75/100 % of every scroll range on every tab, and never a
second scrollbar (904 = 904, 604 = 604). Anchors on Control land 16.0,
15.7 and 15.9 px clear of the bar. Twenty tab presses from scrolled pages,
own tab included, all at scroll 0. Reload restores big, window, channels
and axis and not fast; Control restores the name from its cookie. Fast
measured at 249 ms for both routes with the pane visible (a hidden pane
clamps timers; that is the browser, not the page), normal at 998 and
2006 ms. Every command left every row and card at the same address and the
status line changed in place. Switch off: 22 setters disabled and still
bordered, the reason stated once, Stop all still 202, the others 403.
Zero console messages, every request to loopback.

Six defects found and fixed, all in the stylesheet and `live.js`:

1. Live showed gas setpoints a thousand times too large: `mfc1_v` is
   already millivolts and `live.js` multiplied again. A merge defect, two
   branches reading one field two ways.
2. The gate's reason had no reserved height, so the cards under it jumped
   21 px when the switch was thrown.
3. The command status line reserved two lines against three-line answers,
   a 26 px jump on a refusal.
4. The Find count reserved less than one line, 2.8 px on every keystroke.
5. A service card's detail reserved 43.5 px against 45 px of two lines.
6. The reading column in Control rows was too narrow for `-5.00e-3 Torr`,
   so the three Zero now buttons sat at three addresses and moved with the
   baselines.

Two it found in Python and left, fixed here afterwards:

- **A baseline could be silently not taken while reported as applied.** The
  worker averaged its own buffer, which is emptied every three samples, so
  it was often empty and the mean NaN; the zero was kept and the command
  still said applied. Now the main thread takes the mean of the last two
  seconds of the run it holds (twenty samples above the Hall sensor's
  noise instead of at most three), refuses with "no samples to take a
  baseline from yet" when there is nothing, and hands the worker the value
  over a `(channel, value)` signal. Smoke-run on the real program: refused
  before acquisition and in the first instant after it starts, taken two
  seconds later, the worker's own `zero_ip` matching the web's.
- The log line said "set baseline of Bu taken"; the summary is a whole
  clause, so nothing is prefixed to it now: "Remote: queezz from 10.0.0.5:
  baseline of Bu taken".

Gates after that: 177 tests, strict docs, flake8, all clean.

## Left

- The rig runs 0.6.0 until queezz restarts it; both Pi checkouts carry
  0.7.0 once pulled. The Remote switch will appear in the control dock on
  that restart.
- Acquisition start/stop from the browser.
- The `lab-cli` registry entry, still in directions.

agent: claude fable 5.1

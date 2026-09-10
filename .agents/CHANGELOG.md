## 4.13.0 — 2026-09-10

- ADC sampling follows monotonic deadlines, including processing in the requested period. Overruns skip and count missed slots without fabricating rows or catch-up bursts.
- Prepare one typed DataFrame per batch, retain numeric history types, and vectorize plot timestamps. Off-device three-row preparation fell from 20.8 to 0.84 ms; rig timing still needs validation.
- Log bounded timing summaries for ADC stages and main-thread delivery, including slow successful reads and the slowest channel. Ready-bit polling yields and uses an elapsed timeout.
- Emit completed buffered rows at worker Stop; discard partial scans and averages. Initial batch size follows configured sampling. Application-exit queue flushing remains a separate lifecycle issue.
- Save the ADC investigation and add an off-device reproducible benchmark. No rig deployment in this session.

## 4.12.2 — 2026-09-10

- Phone navigation puts Log and Lab behind Menu; the view-mode selector starts the page and scrolls away instead of covering the readings.
- H₂ and O₂ fold independently, remember their folds, and keep applied/measured feedback visible. Draft values survive closing and reopening.
- Fully collapsed phone plots keep only the title and curve switches, about 71 px high. The curve press restores the plot controls.
- Reloading an Access deep link now lands its heading below the header.
- Recorded the September 10 plasma run analysis: 20,257 complete rows through a deliberate Stop, no reported ADC failures or recoveries. Continued acquisition is confirmed; a retry rescue and the earlier I²C fault hypothesis are not established by this run.

## 4.12.1 — 2026-09-10

- The Cathode group's heading is one line, "Cathode" with a PID | Manual switch beside it: one pill with a sliding thumb, not two buttons linked in code (queezz, 2026-09-10: "for toggles I like visual toggles"). Built as a reusable component for the page's other two-state choices.
- Settings in the right rail is open by default and still folds, remembered per browser ("I don't like IGs hidden by default").
- The "Reading this page" card is gone; its sentences live in the Web View docs ("the towel of explanation text belongs in docs or in pihti-log, not in a card of control UI").

## 4.12.0 — 2026-09-10

- The left rail is the real control: Start/Stop, Gas flow, Cathode, Stop all outputs. QMS sync, Sampling and Gauges moved into a folded Settings group in the right rail, after Display, folded by default and remembered per browser (queezz, 2026-09-10: "I don't use those often"). Observe hides it; Monitor reaches it through the right-rail drawer. Deep links to the moved sections still land and open the fold.

## 4.11.2 — 2026-09-10

- Small readouts are small: a card is one compact row of name, number and unit with nothing reserved beneath, about half its former height; big keeps the large figure. "as measured" is gone.
- A readout is always a number: a Baratron below zero shows its signed value in the value's own size, with a small "below zero" tag beside the name instead of words in the number's place and a residual line. A held baseline shows a "zeroed" tag the same way. No card changes height between polls. The detection-limit paragraph under the Baratron chart is gone; the reasoning lives in the docs.

## 4.11.1 — 2026-09-10

- The web view no longer prints a line per request to stderr: on the rig, 4.11.0's new stderr file was filling with the browser's polls at one line every two seconds. Werkzeug's request log is set to warnings only; a real error still reaches the file.

## 4.11.0 — 2026-09-09

- The ADC reader survives a board that stops answering: a failed I²C read is logged once, retried every half second and logged again every 30 s until the board answers, instead of ending the thread silently; a row that cannot be recorded is dropped and the loop goes on; a conversion that never finishes raises instead of spinning forever. The main thread says "Reader lost" in the log when samples stop for twice the stale line, and "Reader back" with the gap when they resume. The launcher keeps the program's error output in `~/work/cudata/controlunit.stderr.log`.
- Two ways to drive the cathode, side by side on the rig's Cathode dock and on the web Control tab: the plasma current PID in amperes, and a Manual drive in millivolts held on the cathode DAC with the PID off. Setting either turns the other off. The manual drive used to be the Settings dock's "Output voltage" and was not on the web at all. `POST /api/cathode` takes `{"mv": 0..5000}` or `{"off": true}`.
- AGENTS.md names the rig's neighbours and where their records are read: PIHTI Log is the Obsidian vault's journal file.

## 4.10.0 — 2026-09-09

- Mass-flow drafts support direct typing and ±1000/100/10/1 mV buttons. Set applies the draft; larger red applied values and separate measured values stay tied to rig feedback.

## 4.9.0 — 2026-09-09

- Pair pressure curves by vessel: Pu + Bu and Pd + Bd, with independent log/linear axes, remembered grouping, and baseline controls beside their curves. Original gauge grouping remains available.

# Changelog

## 4.8.6 — 2026-09-09

- Compact status, command feedback and readout size into one wrapping header above the readings, removing the reserved blank feedback row.

## 4.8.5 — 2026-09-09

- Keep the mode switch at a stable top position instead of the distant bottom edge.
- Use the full viewport width in Monitor and divide available plot height between active panels.
- Default Monitor to big readouts with its own saved size preference.
- Bring Window and Median directly onto Monitor, reusing the existing controls.
- Remove the duplicate Poll label.

## 4.8.4 — 2026-09-09

- Use ControlUnit as the home tab and remove the duplicate Live link.

## 4.8.3 — 2026-09-09

- Label negative Baratron readings Below zero and retain signed residuals.
- Distinguish nonpositive log exclusions from missing data; break lines across excluded samples and avoid an arbitrary empty log axis.
- State that the detection limit is not characterized; do not fabricate a cutoff from full scale or visible noise.

## 4.8.2 — 2026-09-09

- Allow gauge mode/range preparation before acquisition, retaining Remote, access and operator gates. Publish the prepared setting immediately and apply it when ADC acquisition starts.

## 4.8.1 — 2026-09-09

- Anchor the Operate/Observe/Monitor switch at the bottom center with fixed button widths, so changing modes never moves the next target.

## 4.8.0 — 2026-09-09

- Unify Live and Control under Live with Operate, Observe and Monitor modes.
- Keep mode buttons beside readouts and preserve plot history and display preferences when switching.
- Retain `/control` as an Operate alias and old normal-mode bookmarks as Observe.
- Monitor provides a Display drawer; Observe and Monitor hide hardware setters.

## 4.7.2 — 2026-09-09

- Place small/big beside readouts on Control, Live and Monitor.
- Give QMS sync a dedicated status/control card near Run.
- Move baseline zero buttons into their corresponding Control plot headers.
- Separate sampling, gas, plasma and gauge controls into spaced, tinted cards; enlarge sampling choices.

## 4.7.1 — 2026-09-09

- Bound top navigation to the workspace width on every tab.
- Show gauge controls by default; add gas/plasma/gauge color hints and
  shorter output feedback labels.
- Give collapsed charts a hint to click their curve pills.
- Keep the selected operator visible and match normalized roster options
  to the saved identity while preserving full display names.
- Show Access saved and a Change action instead of prompting again.

## 4.7.0 — 2026-09-09

- Fuse operation controls, held/measured output feedback, live readouts and
  trends on Control. Reuse Live's rendering and a single state poll.
- Keep display choices in the right rail; expand operator/access, gauge
  settings and run details when needed. Preserve Live and Monitor.
- Let a deliberate curve restoration override flat-curve suppression;
  presets restore automatic behavior. Preserve nonpositive log handling.
- Open expandable sections when following or reloading their deep links.

## 4.6.1 — 2026-09-08

- Put each pressure chart's log/linear switches beside its curve pills.
- Give Start and Stop prominent, stable positions at the top of the Control
  rail; move control ownership, operator name and the lab's word into that rail.
- Keep the main setter panel compact, with plain group names. Keep Stop all
  outputs available as a separate outlined action.
- Preserve readout sizing, smoothing, presets, Monitor mode and curve suppression.
- Repair the existing GitHub test workflow's checkout import command.

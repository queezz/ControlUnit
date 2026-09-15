## 4.18.0 — 2026-09-15

- A second ionization gauge, `Pu2`, upstream on ADC channel 16 (queezz, 2026-09-15: "I've connected upstream IG to channel 16"), with its own Torr/Pa mode and exponent selector beside the downstream gauge's on the rig's Control dock and in the web Control tab's Gauges group, and its own curve on the ion-gauge chart, in the readouts strip and in the All and Vacuum presets.
- Each ionization gauge now records its own mode and exponent in the data file: `Pd` in `IGmode` and `IGscale` exactly as before, `Pu2` in two new columns `IGmode_Pu2` and `IGscale_Pu2` appended after the original ones. `settings.yml` names each gauge's columns (`Mode Column`, `Scale Column`) and is at Settings Version 1.4; the worker builds rows from the column list instead of fixed positions.
- `/api/gauge` takes a `gauge` name; a body without one still means `Pd`. `/api/state` carries every gauge's pair under `setpoints.gauges`, with `ig_mode` and `ig_range` still the first gauge's.

## 4.17.1 — 2026-09-15

- A Kikusui recorder whose stop outlived its 1.5 s wait left its reference behind, so every later Start of that GUI session refused with "previous logger is still stopping" although the thread had ended moments later. Start now checks whether that thread is actually alive and clears the stale reference when it is not. Recording, LAN loss and shutdown order are unchanged.

## 4.17.0 — 2026-09-14

- Give measured Kikusui filament voltage and current full WebUI readout cards in all three modes, with small/big sizing, an independently remembered fold and recording/output status. Remove the unwired analog Cv placeholder from the manual cathode measured-voltage display.
- Publish a separate Kikusui snapshot through the main-thread status record. Its freshness ages independently of ADC data; missing/stale measurements are withheld, and the browser expires readings even if a request hangs or the Pi stops answering. Recording and manual-drive behavior are unchanged.

## 4.16.0 — 2026-09-14

- Show Kikusui measured voltage/current and recording/output status below the Cathode panel's manual controls. The main thread reads a locked copy of flushed telemetry every 500 ms; unavailable, stale and stopped records never leave old measurements looking live.
- Verified six read-only polls from the Pi to the supply with output off (2.8–3.3 ms per voltage/current/output poll). Deployment and an operator-run discharge/bake remain pending while the rig is acquiring.

## 4.15.0 — 2026-09-14

- Optionally log Kikusui filament voltage, current and output-enable state at 2 Hz beside each ADC run in a separately timestamped `kikusui_*.csv`. Include software cathode command, PID target, identity and query time, so ordinary manual discharges and bakes can establish baselines before PID work.
- LAN timeout, malformed response or disconnect writes an unavailable row, warns once per outage and retries without changing manual drive or blocking ADC acquisition. Reconnect sends queries only and verifies instrument identity. Shutdown interrupts reads/waits after hardware shutdown.
- Machine-local configuration is opt-in; dummy hardware cannot contact a real supply. PID behaviour, ADC columns and live readouts remain unchanged in this first recording stage.

## 4.14.1 — 2026-09-14

- Monitor on a phone had no way out: 4.14.0 moved the mode switch into the top bar's Menu, and Monitor hides the top bar ("Observe trapped me. No tri-state toggle anywhere"). The switch now docks into Monitor's own strip beside Display and Full screen on a phone, into the Menu in Operate and Observe, and stays in the header at wider widths; one element, moved, never copied. Escape walks back one mode at a time to Operate. A test fails if any mode ever renders no mode switch again.

## 4.14.0 — 2026-09-14

- Every card on Live folds to one row that still shows its numbers, each independently, remembered per browser: Gas flow, Cathode, the readouts strip, each chart, and the right rail's groups. Start/Stop never folds (queezz: "I can simply scroll down, they are not in the way"). The header is pixel-identical folded or open; the fold mark is a chevron at the row's right end, one CSS rule. On a phone the left rail goes from about 900 px to 200 px with gas and cathode folded.
- Folded readouts are the five values in their colours on one line, no label and no size switch; folded charts are their title, Zero and span; gas lines inside Gas flow are one row each with Applied and Measured said once.
- Big readouts are one row per card, name beside the number, about half the height.
- Stop all outputs leaves the left rail: it lives at the foot of Operator and access, and in the phone's Menu together with the Operate | Observe | Monitor switch, which no longer takes a fixed row on the phone.

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

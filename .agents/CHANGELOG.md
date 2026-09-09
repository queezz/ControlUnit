# Changelog

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

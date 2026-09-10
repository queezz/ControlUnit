# 2026-09-10 — Plasma log review and mobile polish

## Rig review

Read the rig over SSH, without mutations. Checkout 4c3ca18 / 4.12.0.
The 18:14:45 run has 20,257 complete 26-column rows through 19:43:04.745302;
its Stop at 19:43:05 is deliberate. After 18:53, median interval 0.161784 s,
maximum 0.498715 s, no gap above 1 s. No ADC failure/recovery, watchdog,
step failure, or traceback for this run. Read the NUL-containing message log
as text to avoid grep's binary-file shortcut. The stderr launch marker is
present, with no later output from this run.

The operator's journal confirms repeated preanode grounding and the measured
5 ohm preanode-to-ground resistance after discharge. Continued acquisition
is established; a retry rescue is not. Today was manual cathode drive with
PID off, so yesterday's PID run is not an identical comparison. Yesterday's
I2C/EMI explanation remains a hypothesis without its original exception.

Durable report: docs/diagnostics/2026-09-10-plasma-reader.md, also copied as a
new lab-vault Troubleshooting note and linked by an append to Troubles.md.
No journal prose was modified. Rig logs and CSV remain on the rig.

## Mobile implementation, 4.12.2

- One navigation DOM: phone Menu discloses Log/Lab; Escape/outside press
  closes it. Desktop retains inline tabs. Shared version-keyed script.
- Mode selector precedes the controls in normal phone page flow and scrolls
  away. Desktop retains its fixed header position.
- Independent native gas details with persistent browser folds and always
  visible applied/measured feedback. Inputs and setter paths remain the same;
  folding is available even while the Remote gate disables the setters.
- Phone collapsed charts keep headings/pills at about 71 px, hiding the empty
  hint and inactive plot controls until a curve is restored.
- Perimeter testing reproduced the previously noted Access reload defect:
  heading y32 under a 56 px bar. Landing at start and repeating at load fixes
  it (y68.47 after reload).

## Verification

Synthetic Flask RigStatus only, via scratch lab service cu-mobile on
127.0.0.1:48976. No hardware command drain, no neighbour addresses.

Perimeter Walk: Main/Log/Lab links, own-tab return, Access, Back/Forward,
mode deep links and reload, Monitor Display drawer and Escape, and all six
section anchor targets at 390/1280 widths and 700/1000 heights. Headings
remain below the 56 px bar and visible. Mobile 320/390/412 widths have no
horizontal overflow. Menu and folds work by keyboard. Both folds persist on
reload; H2 draft 100 survives fold/unfold with O2 independently closed.
Remote-off disables setters and preserves folds and Stop all outputs.
Ordinary reading/scrolling/toggling was exercised over several minutes.

Desktop rails stay at y76: measured at page y0/175/350/525 on a 700 px
window, and y0/120/231 on a 1000 px window. Screenshots inspected at 390,
412 and 1280 widths. Collapsed plots measured 70.95 px; gas disclosure
summary 50.61 px. Mode toolbar measured above the viewport during scrolling.
Console error/warning list empty. Ordinary reload after preview restart
requests CSS and all scripts with v4.12.2.

516 pytest tests, 20 existing JS behavior tests, strict MkDocs build.
Final verification and preview shutdown recorded below.

No commit or push requested; changes are left local and unstaged. No rig
pull, restart, acquisition change, or output command.

## Remaining observations

The old mobile request to see Pu beside the gas controls still needs its
own layout work; independent folds reduce the travel but do not colocate Pu.
The existing pressure grouping buttons are disabled when Remote is off,
although they only affect display. Observed during gating QA, not changed.

agent: codex

Final verification: strict docs build and all 20 JS tests pass after the final changes. Preview process tree 44520/55592 stopped through lab; both PIDs absent and no listener on 48976. Browser viewport restored and temporary tab closed. Vault note SHA-256 matches the repository report.

Final pytest rerun: 516 passed in 20.73 s. git diff --check passes.

Owner timing challenge: extended the durable report and appended the follow-up to its vault copy. Mean fast-path interval 0.175640 s, 46 intervals above 0.3 s, five above 0.4 s; four cluster at 19:33:14–26. Confirmed full-period sleep plus acquisition overhead in source. Bursts remain unexplained without stage timing. Recorded the cadence diagnostic work in directions; no runtime changes.

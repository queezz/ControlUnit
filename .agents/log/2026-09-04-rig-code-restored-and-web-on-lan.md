# 2026-09-04 — the rig's code reaches master, and the web view reaches the LAN

Two pieces of work in one session. First, a plasma-current unit fix from the
rig was reviewed, corrected and committed, and the control code the rig
actually runs was moved onto `master`, which had never carried it. Second,
slice one of the web view was merged, defaulted to the lab network, and given
a launcher that lives in the repository. Everything below is pushed.

## The plasma current now controls in amperes

The rig held uncommitted work in `~/work/aktest` on `thread-fix-v2`, written by
the student running the setup: feed the PID the Hall-sensor conversion of Ip
instead of raw ADC volts, emit the operator's setpoint in amperes, and retune.

That change is correct and fixes a real defect. `set_zero_ip` stores
`converted_values["Ip_c"].mean()`, which is amperes, and the previous
expression subtracted that amp-valued zero from a *voltage* and then scaled by
1000 — so every "O Ip" press applied the zero at roughly 1000x its intended
weight. Both sides of the error are now amperes.

The retune reads alarming and is not. One ampere is 200 mV through the Hall
sensor (`hall_current_sensor` is `5 * (v - 2.52)`), so `0.3, 0.1` on a
millivolt error and `30, 40` on an ampere error mean the proportional gain
*halved*, 60 to 30 per ampere, while the integral gain doubled, 20 to 40. Do
not "restore" the small-looking numbers.

Committed as `bc0888c`, its own commit, so the rig's proven work stays
separable from the review that followed.

## Three defects found reviewing it, fixed in `aff0b57`

`set_cathode_current` stored its millivolt output in
`plasma_current_setpopint` — the same attribute holding the operator's ampere
setpoint — so every control cycle overwrote the setpoint. Two consequences.
The `PresetV_cathode` column logs that attribute, so it recorded **amperes
while control was idle and millivolts once it ran**; the column now always
carries the cathode voltage its name promises, in one unit. And `prep_pid`
rebuilds the controller from the same attribute, so it could read a millivolt
output as an ampere setpoint — unreachable today only because every caller
happens to hold zero when it runs, which is luck, not design. A new
`control_voltage` attribute now holds the voltage; each name has one job.

The verbose PID print still showed the pre-conversion expression, so anyone
tuning those new gains was watching a number the controller does not use.

Control behaviour is untouched: gains, baseline and output limits are exactly
as the rig proved them.

## master had never carried the rig's control code

`thread-fix-v2` is an ancestor of `master`, so the rig looked merely 16
commits behind. For `controlunit/` it was the reverse.

The tuning was added in `dfbc65c` (2026-04-23, authored by `pi`, on the rig)
on the `dev` -> `thread-fix-v2` line, and never appeared on master's
first-parent chain. It entered master's history only as the second parent of
`368c357`, "Merge archaeology-report into master" — parents `9f5b04c`
(master, no tuning) and `1120683` (archaeology-report, with tuning) — and that
merge resolved `adc.py` toward master. A MkDocs branch that happened to be
based on the rig line silently decided a hardware question. `git log -- adc.py`
hides this entirely; `--full-history` shows it.

Master's own `controlunit/` came from two Codex PRs of **2025-08-09**, queezz's
first Codex attempts and blind fixes by his own account, which had moved data
saving out of `main.py` and into the ADC thread. That code has never run on the
hardware. The rig line carries the real thread-safety work the branch is named
for — the five signal declarations, their `DirectConnection` wiring, and the
`pyqtSlot` decorators.

All four differing files were taken from the rig line **together**, in
`c6da7b8`, not merged hunk by hunk: data saving lives in `main.py` on the rig
line and in `adc.py` on master's, so any mixture keeps the program running
while silently recording nothing. `master-backup-2026-09-04` marks the state
before this.

## The web view, merged and on the LAN

Slice one merged from `webui` in `dcfa404`, cleanly — it only adds a status
object, two calls recording whether acquisition runs, and an argument parser,
while the restored code owns data saving and the control loop. 35 tests pass.

`--host` now defaults to `0.0.0.0` (owner decision 2026-09-04, "the whole
point is LAN"); `--host 127.0.0.1` narrows a run. The view stays read-only.

`scripts/run_controlunit.sh` is now the rig's launcher, called by the Pi's
`~/Desktop/aktest.sh` (original kept as `aktest.sh.bak`). It resolves its own
repository root rather than a hardcoded path and fails on a bad `cd` instead of
running from the home directory. `.gitattributes` pins `*.sh` to LF so a
Windows edit cannot break the shebang on the rig.

## The Lab tab is wrong about both neighbours

Reported by queezz against the running page, with his words: the PIHTI diagram
entry is "ENTIRELY WRONG", and the view is "a joke" rather than something to
work from. The evidence, gathered on the Pi:

- **`~/.controlunit/settings.yml` does not exist on the Pi.** With no
  `Neighbours:` block both cards fall to `not configured`, which is the code
  behaving correctly on absent configuration. This half is a config gap.
- **`pihti.service` is `active` on the Pi.** The diagram is already running,
  as a systemd unit, on the same machine that renders the card telling the
  reader to start it with `lab pihti-diagram`. The card is wrong about the
  mechanism *and* about the state.
- **PIHTI Log runs on queezz's Windows 11 box, not the Pi.** So from the rig's
  side it is on another machine whose address nothing here knows.

The deeper fault is that the start-command copy assumes every neighbour is
started by `lab` on the machine reading the page. `lab` is the Windows helm;
the Pi runs systemd units. A card should say how *that* service is started on
*that* machine, or say nothing.

Also unresolved: clicking the page logo produced an error before acquisition
was started, and did not after. Not reproduced or diagnosed.

## State

`master` at `4130906`, pushed. `thread-fix-v2` at `aff0b57`, pushed, and now
redundant — both Pi checkouts (`~/work/aktest` and `~/work/ControlUnit`) were
moved to `master` and pulled, ending the divergence that let a docs merge
overwrite hardware code. `master-backup-2026-09-04` is local only.

Gates on the final tree: `flake8 --select=E9,F63,F7,F82` clean, 35 tests
passing, both modules importing off-rig on the dummy-sensor fallback. The rig
had not yet been restarted onto this code when the session ended, so nothing
here has hardware evidence behind it.

Letter `20260904-2c879649-4d0f80` was posted to `code/pihti-log` carrying the
`PresetV_cathode` change, because it alters what recorded data means and the
students read that journal.

agent: claude opus 5

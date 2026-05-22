# ControlUnit — Software & Laboratory-System Archaeology

> Snapshot generated 2026-05-22 against `thread-fix-v2` at the tip
> of 347 commits (Feb 2020 → Apr 2026). This document is intentionally
> historical: it captures what the codebase **looks like**, what it
> **probably means**, and where interpretation **could be wrong**.

## About this document

This is an archaeological reading of the `ControlUnit` repository:
a Raspberry-Pi-based plasma-experiment control and data-acquisition
system that has accreted over six years of active research use. It is
not a code review and not a roadmap. It is a forensic reconstruction
intended to survive the MkDocs migration so that context is not lost.

### Confidence legend

Throughout the document, claims are tagged when their epistemic status
is non-obvious:

- *[confirmed]* — directly visible in code, commits, or file listings.
- *[inferred]* — strongly implied by multiple converging pieces of
  evidence but not stated anywhere.
- *[speculative]* — a working interpretation, plausible but not proven.

Sections that consist mostly of factual listing (file tree, commit
dates) are not tagged. Sections that interpret physics, intent, or
collaborator behaviour are tagged more liberally. The final section,
[Known uncertainties and possible incorrect assumptions](
#known-uncertainties-and-possible-incorrect-assumptions),
collects the most important caveats.

---

## Executive Summary

`ControlUnit` is a Raspberry-Pi-based plasma-experiment control and DAQ
application — six years of organic evolution from a 2020 student-built
prototype into a usable lab instrument. Hardware focus: an I²C 32-channel
ADC (AIO-32/0RA-IRC), two DACs (DAC8532 for mass-flow controllers,
MCP4725 for plasma-current control), a MAX6675 thermocouple, and several
pressure gauges (Pfeiffer PKR251/IKR251, MKS Baratrons, an ionization
gauge with switchable Torr/Pa scaling). *[confirmed from `settings.yml`
and `controlunit/devices/conversions.py`]*

The codebase reads like a *strata*: a 2020 monolithic `worker.py` with a
`ThreadType` enum still imprints the structure, even after a 2024 split
into `devices/`, `ui/`, and a worker base class. Three forces shaped it
*[inferred]*:

1. **Hardware reality** — the rig actually exists, so channels,
   addresses, and conversion polynomials are pinned to physical sensors
   with datasheets in comments.
2. **Multiple contributors with different conventions** — `queezz`
   (lead), `Ito-kun` (original threading, untangled later), `Kshora`,
   `leprecon-pi`, `hasuo_kuzmin.lab@outlook.jp` (the actual Pi user),
   Kurokawa (kawdev branch, serial PSU), and finally `codex/*`
   automated PRs in 2025.
3. **Solo-physicist development tempo** — long quiet periods, then
   bursts during measurement campaigns (May 2023 ADC tuning;
   Sep–Oct 2024 PID push; April 2026 isolated-DAC work).

The package compiles and runs. It is not abandoned — the latest commit
is from one month ago (`settings: debug false`). But it carries the
scars of three half-completed renames, one half-extracted core, one
stale auto-generated doc site, and several modules that exist only as
placeholders for "do this later" intentions.

---

## Repository Structure

Top-level layout (with annotation of what is alive vs fossilized):

```text
ControlUnit/
├── controlunit/                 # the actual Python package
│   ├── __init__.py              # sys.path hack — alive but a smell
│   ├── _version.py              # 0.4.0, Apache-licensed
│   ├── main.py                  # MainApp(QObject, UIWindow), 785 lines — alive
│   ├── mainView.py              # UIWindow mixin — alive
│   ├── settings.yml             # alive, the de-facto schema for the rig
│   ├── readsettings.py          # alive, YAML loader + AdcChannelProps wiring
│   ├── heatercontrol.py         # alive but unused (temperature path is dormant)
│   ├── trigger_signal.py        # IndicatorLED — alive, doubles as QMS sync
│   ├── striphtmltags.py         # alive, one-purpose helper
│   ├── start_gpio.py            # alive, sudo pigpiod orchestration
│   ├── core_logic.py            # ASPIRATIONAL stub: "TODO: move signal connection here"
│   ├── plot_data_handler.py     # ASPIRATIONAL stub: same TODO, never instantiated
│   ├── devices/                 # HAL — renamed from sensors/ on 2024-09-25
│   │   ├── device.py            # DeviceThread base class (worker super)
│   │   ├── adc.py / adc_setter.py
│   │   ├── dac8532.py / dac8532_setter.py
│   │   ├── mcp4725.py / mcp4725_setter.py
│   │   ├── max6675.py           # alive but path is currently commented out in main.py
│   │   ├── adc_channels.py      # AdcChannelProps + conversion dispatch
│   │   ├── conversions.py       # gauge polynomials with LaTeX in docstrings
│   │   └── dummy.py             # off-RasPi shims for smbus, RPi.GPIO, pigpio, spidev
│   ├── ui/                      # renamed from components/ on 2024-09-25
│   │   ├── text_shortcuts.py    # ANSI + Unicode constants
│   │   ├── docks/               # pyqtgraph DockArea panels
│   │   ├── widgets/             # graph.py (pyqtgraph wrapper) + analoggauge.py (32 KB; unused)
│   │   └── buttons/toggles.py   # hand-painted QPushButton switches
│   └── icons/
├── docs/                        # FOSSIL: pdoc3 HTML from 2022, references deleted modules
├── examples/                    # mostly fossilized notebooks; settings_template.yml is live
├── manuals/                     # one PDF (ads1113.pdf) — minimal external reference
├── images/                      # README screenshots + photos of the physical box
├── tests/                       # one example test (tests/test_sample.py: inc(3)==4)
├── kurokawa-dev/PWR.py          # quarantined: serial driver for PWR401L bench supply
├── bin/plasmacontrol            # 7-line entry-point script (broken: imports MainWidget)
├── .github/workflows/           # one CI: flake8 syntax + example pytest
├── README.md, requirements.txt, setup.py, settings.yml, .pre-commit-config.yaml
└── data/test/                   # empty placeholder
```

A few telling artifacts *[confirmed by reading the respective files]*:

- `setup.py` still declares `packages=["controlunit", "controlunit.components"]`
  — the `components` rename to `ui` (commit `c00e7fd`, 2024-09-25) was
  never carried into install metadata.
- `controlunit/__init__.py` does `sys.path.append(str(_echelle_base))`
  so that `from mainView import ...` works without the package prefix —
  a survival from the pre-package era. The variable `_echelle_base` is
  a vestigial name from a different project (`echelle`), preserved
  on purpose or by accident *[speculative — could be a template copy]*.
- Triple inconsistent import styles for the same module exist
  side-by-side: `from controlunit.devices.adc import ADC` (in
  `main.py`), `from .device import DeviceThread` (in
  `devices/adc.py`), and `from devices.dummy import pigpio`
  (fallback when not on the Pi). All three work *only because* of the
  `sys.path` hack in `__init__.py`.
- `bin/plasmacontrol` would crash today — it does `from controlunit
  import *; widget = MainWidget(app)`, but `MainWidget` was renamed to
  `MainApp` in commit `9907825 restructuring main.py` (2024-10).

---

## Documentation Archaeology

The original prompt mentioned "Sphinx remnants" — there are **no Sphinx
remnants in this repo** *[confirmed by exhaustive grep for
`sphinx|conf\.py|\.rst`, no matches]*. The fossil is `pdoc3`, not
Sphinx. The actual documentation strata are:

### 1. `docs/` — auto-generated pdoc3 HTML (FOSSIL, 2022-06-28)

Created in a single commit `4b7dcdc [REORGANIZE] make a package, add
pdoc3 docs` and never regenerated. It serves the GitHub Pages site
linked from the README at <https://queezz.github.io/ControlUnit/>.
The HTML references modules that have since been **deleted** —
`AIO.html`, `customTypes.html`, `electricCurrent.html`,
`ionizationGauge.html`, `pfeiffer.html`, `pigpioplug.html`,
`qmsSignal.html`, `smbusplug.html`, `tc.html`, `thermocouple.html`,
`timeKeeper.html`, `worker.html`. There is also a self-nested duplicate
`docs/components/components/...` from what appears to be a buggy pdoc
invocation *[speculative — could equally be a manual copy]*.

The generator itself lives in `docs/make.py`:

```python
# docs/make.py (lines 11–31)
def generatedocs():
    """ """
    import os, subprocess, shutil, time

    # subprocess.check_output('pdoc controlunit -o ./docs/ --html --force')
    bpth = "./docs/controlunit"
    npth = "./docs/"
    clear(bpth)

    subprocess.check_output(f"pdoc controlunit -o ./docs/ --html --force")
```

**Status:** stale but valuable as a *fossil snapshot* of the codebase
circa 2022 (single monolithic `worker.py`, separate `customTypes.py`,
etc.). For the MkDocs migration, keep `docs/*.html` archived as
`docs/archive/2022-pdoc/` and add a banner page in MkDocs explaining
the rename map.

### 2. `README.md` — alive, photo-centric

Two control-box photos (`ControlBlock_1.png`, `ControlBlock_2.png` —
pictures of the actual instrument box), three UI screenshots tagged by
version (`v0.2.0`, `v0.4.0`, `v0.4.0_settings`), the hardware BOM
(Raspberry Pi 3B, AIO-32/0RA-IRC, Celduc SO842074 SSR, Panasonic
JCD100V300WCG halogen heating lamp, EVICIV 7" touchscreen), and a
vestigial run instruction with a typo (`pyton -m controlunit.main`).
This is the most accurate single document about the system — the
photos make it real, and the hardware links are actual order-relevant
URLs. Preserve verbatim in MkDocs.

### 3. `controlunit/settings.yml` — the de-facto data dictionary

This file is the only place where the meaning of a signal name like
`Pu`, `Bd`, `Ip`, `MFC1` is bound to a channel number, gain, description,
and conversion function. It is also where datasheet URLs are pinned:

```yaml
# controlunit/settings.yml (lines 44–50)
# 32 channel 16-Bit ADC based on ADS1115
# https://www.y2c.co.jp/i2c-r/aio-32-0ra-irc/
# https://www.ti.com/lit/ds/symlink/ads1113.pdf
# https://www.nxp.com/docs/en/data-sheet/PCA9554B_PCA9554C.pdf
# https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf
```

The comments here are some of the best documentation in the entire
repository. Treat the YAML as canonical and generate a
"Channel Map / Conversion Catalogue" page in MkDocs from it.

### 4. `controlunit/devices/conversions.py` — LaTeX-in-docstrings

Each conversion function carries its physics inline:

```python
# controlunit/devices/conversions.py (lines 7–19)
def pfeiffer_single_gauge(voltage):
    r"""
    Calculate pressure for Pfeiffer single gauge PKR251.
    $Pressure = 10^{1.667 * voltage -11.46}\; Torr$
    ...
    """
```

These docstrings are MkDocs gold — render them with
`pymdownx.arithmatex` and you get a real "Sensor Conversion Reference"
section for free. **High preservation value.**

### 5. `manuals/ads1113.pdf` — one orphan datasheet

A single PDF sits alone. There used to be more (channel-cabling
diagrams, board layouts) judging by the photo files and the BOM
*[speculative]*, but they were never checked in. Do not migrate
`manuals/` as-is; convert it to `docs/datasheets/` and document the
*intent* of the folder (a place for canonical datasheets next to the
code that interprets them).

### 6. `examples/` notebooks — abandoned

- `imports.ipynb`: a fossil from when this package was installed via
  pip (`'c:\\…\\miniconda3\\lib\\site-packages\\controlunit'`).
  Useless today.
- `channels.ipynb`, `pandasrecap.ipynb`, `settings.ipynb`: scratch
  notebooks for working out the ADC channel multiplexing and the move
  from numpy arrays to pandas DataFrames in 2023.
- `settings_template.yml`: a *snapshot* of `controlunit/settings.yml`
  at v1.0 — useful only to see the diff (no MFCs, no cathode current,
  channels still numbered 0–4 instead of 20-something).

### What carries durable design intent worth preserving

1. The `# ===` banner blocks in `settings.yml` — they describe what
   physical instrument hangs off each chip and why certain GPIO / I²C
   addresses are used.
2. The "Conversion Function" dispatch convention (named string →
   function) in `adc_channels.py` and `conversions.py`.
3. README's BOM and control-box photos.
4. The pdoc HTML for `docs/main.html`, `docs/worker.html`,
   `docs/customTypes.html` should be kept as **historical context** —
   they document the 2022 ThreadType-enum architecture which is the
   conceptual ancestor of everything alive today.

### What is safe to drop

- `docs/components/components/*` — pure pdoc rendering duplicate
  *[inferred]*.
- `examples/imports.ipynb` and the older notebooks — they expose
  internal absolute paths from a developer's machine.
- The `[DOCS]` link in README — it currently points to an out-of-date
  doc site.

---

## Architecture Reconstruction

### Layered structure (as of today, *[confirmed]*)

```text
┌──────────────────────────────────────────────────────────────────┐
│  GUI (main thread)                                               │
│    main.MainApp(QObject, UIWindow)                               │
│    UIWindow (mainView.py)  ─►  ui/docks/* + ui/widgets/graph.py  │
└──────────────────────────────────────────────────────────────────┘
                ▲   ▲                                ▲
                │   │ Qt signals (queued)            │ direct method
                │   │ data_ready, sigDone, msg       │ calls into
                │   │                                │ ui widgets
┌───────────────┴───┴────────────────────────────────┴─────────────┐
│  Workers (one QThread per device, parented by MainApp.workers)   │
│    devices.device.DeviceThread (super)                           │
│      ├── ADC      (devices/adc.py)      ◄── simple_pid           │
│      ├── DAC8532  (devices/dac8532.py)  ── 2 MFC channels        │
│      ├── MCP4725  (devices/mcp4725.py)  ── plasma-current DAC    │
│      └── MAX6675  (devices/max6675.py)  ── currently disabled    │
└──────────────────────────────────────────────────────────────────┘
                ▲
                │ register-level I/O via *_setter.py
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  Chip drivers (synchronous, no Qt)                               │
│    AIO_32_0RA_IRC + ADS1115 + PCA9554 (adc_setter.py)            │
│    DAC8532Setter   (dac8532_setter.py)                           │
│    MCP4725Setter   (mcp4725_setter.py)                           │
└──────────────────────────────────────────────────────────────────┘
                ▲
                │ smbus, spidev, pigpio (or devices/dummy.py off-Pi)
                ▼
                  Raspberry Pi 3B + custom PCB
```

### Threading evolution (the deepest stratum)

This is the most interesting story in the repo, traceable through
commits *[confirmed where commit hashes are cited; intent of each
phase is inferred]*.

**Phase 1 (Feb 2020 – Mar 2020), pre-package, monolithic `worker.py`.**
The initial commit (`710c78f`) used *one* `Worker(QtCore.QObject)`
class for *all* devices. The same class object did temperature OR
plasma OR pressure-1 OR pressure-2, dispatched by a `ThreadType` enum
living in `customTypes.py`. Methods were named `__plotPresCur` (sic —
"plot" inside the worker, because the worker also dispatched plot
decisions) and `__plotT`. Buffers were fixed-shape numpy arrays of
`STEP` rows. Inside the worker loop the worker called
`self.__app.processEvents()` from a non-main thread — a textbook
anti-pattern, but it kept the GUI alive while `time.sleep(TIMESLEEP)`
ran per iteration. The classic Qt-newcomer shape.

**Phase 1.5 (Mar 2020), "Untangling Ito-kun's threading mess"
(`ed7cadb`).** Single commit, +161 / −107 in `worker.py`. The fix:
rename `ThreadType` → `Signals`, factor `read_settings()` out of every
constructor, rename methods to `readADC` / `readT`, give the worker a
per-instance `self.sampling`. The threading topology *did not change*
— but the language did. The intent was clearly *[inferred]*:
"first make this readable, then we'll fix the model later." That
"later" took four years.

**Phase 2 (Jun 2022), `[REORGANIZE] make a package, add pdoc3 docs`
(`4b7dcdc`).** Files moved into a `controlunit/` directory. No
structural change to the worker. pdoc generated HTML for the
then-current shape.

**Phase 3 (May 2023), ADC-thread tuning (`worker: tuning ADC thread` ×
8 commits).** The acquisition loop was rewritten to:

- read from `AdcChannelProps` populated from `settings.yml` rather
  than hard-coded `CHP1/CHP2/CHIP` constants;
- swap fixed `np.zeros(shape=(STEP, 7))` buffers for two
  `pandas.DataFrame`s (`adc_values` for raw, `converted_values` for
  unit-converted);
- introduce the `STEP` batching idea (loop N times, then emit one
  signal carrying N rows).

That last point is the most important architectural choice in the
repository and survives untouched today:

```python
# controlunit/devices/adc.py (lines 374–379)
if step % (self.STEP - 1) == 0 and step != 0:
    # self.calculate_averaged_signals()
    self.send_processed_data_to_main_thread()
    step = 0
else:
    step += 1
```

Inter-thread signalling is *amortised*. At 10 Hz sampling and `STEP=3`,
the GUI gets ~3 Hz of updates, but the data file gets all 10 Hz. This
is the right trade-off for a Pi 3B and pyqtgraph: keep the slow
component (UI) decoupled from the fast component (DAQ), while the DAQ
thread does the buffering itself.

**Phase 4 (Aug 2024), `restructure: worker super class and subclasses
are separated` (`5326e50`).** Big bang: 662 lines deleted from
`controlunit/worker.py`, replaced with
`sensors/{worker.py, worker_adc.py, worker_dac8532.py,
worker_max6675.py, worker_mcp4725.py}`. This is finally a *real* class
hierarchy — the four-year-old "later" arrives. The commit author is
`pi <hasuo_kuzmin.lab@outlook.jp>` — i.e., committed directly from the
lab Raspberry Pi *[confirmed from `git log` author field]*. That tells
you exactly *when* the refactor became unavoidable *[inferred]*: when
adding a new device (MCP4725 for the plasma-current DAC) made the
`ThreadType` enum painful enough to break.

**Phase 4.5 (Sep 2024), serial renames.**

- `4050c28 Renaming, fix FutureError in pandas.concat`: `worker_*.py`
  → `adc.py` / `dac8532.py` / etc.
- `a2f50d0 Renaming sensors to devices`: directory rename.
- `c00e7fd Rename components to ui`: directory rename.
- `b1e6fe5 rename remaining "sensor_name"s to "device_descriptor"`:
  terminology.
- `1c426d9 Restructure thread start` + `86544db streamlined threads
  and workers start` + `9907825 restructuring main.py`.

This 10-day burst is a single push toward consistent vocabulary — note
that *renaming* is the only thing happening; behaviour was deliberately
untouched. The product of this phase is the
`prep_threads → prep_worker → start_thread → connect_worker_signals`
pipeline that lives in current `main.py`.

**Phase 5 (Aug 2025), Codex-bot fixes (PRs #20 and #21).** Two
auto-generated PRs tightened two real issues:

- `1cf4611 Handle sensor data in device threads`: moved
  `update_processed_signals_dataframe` *out of* `main.py` into the
  workers (`adc.py`, `max6675.py`) so the main thread no longer does
  numeric work.
- `9f5b04c Fix CoreLogic signal declaration`: cleaned the
  (still-unused) `core_logic.py` stub and added
  `tests/test_core_logic_signal.py`.

That the Codex-PR for `CoreLogic` got merged is itself a sign — the
human author has decided `core_logic.py` *should* exist eventually but
isn't done with it yet *[inferred]*. The `plot_data_handler.py` is the
same kind of "marked intention": both files contain
`TODO: move signal connection from main.py here`.

**Phase 6 (Apr 2026), isolation hardware push.** `0b417cf add debug
for mcp4725, isolated DAC for plasma current` + `dfbc65c upd for
isolated DAC control of the plasma current`. The current branch
(`thread-fix-v2`) has these on top of `dev`. This is the latest live
work: the MCP4725 is now on an electrically *isolated* I²C bus (so
plasma-arc transients cannot fry the Pi) *[inferred from commit
message and hardware context]*. Code-side, the change was small
(MCP4725 init + a new "set output voltage" button in `SettingsDock`)
— but the hardware change behind it is the real story.

### GUI architecture (mainView + docks)

The GUI is a `QMainWindow` containing a `QTabWidget` with two tabs:

1. **Data tab** — a pyqtgraph `DockArea` with:
   - `ControlDock` ("Control"): on/off switch, full-screen toggle,
     QMS-trigger toggle, sampling-window combobox, IG-mode/range, quit
     button, and a giant HTML-`QTextBrowser` for live values.
   - `Plots` dock holding a `Graph(GraphicsLayoutWidget)` with two
     stacked plot items (plasma current top, pressures bottom; an
     obsolete temperature plot is commented out everywhere).
   - `GasFlowDock` ("Mass Flow Control"): two MFC presets, four
     spinboxes each (one per decade — a manual-set "scientific
     notation by spinbox" UI, see `_init_mfc_spin_boxes`).
   - `CalibrationDock`, `PlasmaCurrentDock`, `PlotScaleDock` —
     overlaid via `addDock("below"/"bottom")`.

2. **Settings tab** — `SettingsDock` (sampling-time combobox + direct
   output-voltage spinbox), `ADCGain` dock, `LogDock` (a styled
   `QTextEdit` that accumulates HTML log messages with timestamps).

Painted custom switches (`MySwitch`, `OnOffSwitch`, `QmsSwitch`,
`ToggleCurrentPlot`, ...) are subclasses of `QPushButton` that paint a
slider-style toggle in their `paintEvent`. There are 9 such classes —
one per visible toggle. This is a typical *touchscreen-first* design
choice *[inferred from the 7" EVICIV touchscreen listed in README and
the enlarged `hitButton` rectangles]*.

The `UIWindow` class is mixed in via multiple inheritance
(`class MainApp(QtCore.QObject, UIWindow):`). This is unusual for Qt
code but is a legitimate way to keep the layout code (in
`mainView.py`) physically separated from the controller code (in
`main.py`) without giving up direct attribute access
(`self.control_dock`, `self.graph`, etc.).

### Signal / data flow

Per acquisition cycle (taking ADC, the busiest one):

1. `ADC.acquisition_loop()` runs in its own `QThread`.
2. `time.sleep(self.sampling_time)` (default 0.1 s).
3. `collect_data()` reads N channels via
   `aio.analog_read_volt(channel, datarate, gain)`. The PCA9554 mux is
   reconfigured only if the channel range demands it (clever
   bandwidth-saver in `adc_setter.AIO_32_0RA_IRC.analog_read`).
4. Raw row appended to `adc_values` DataFrame, converted row (running
   every channel's `conversion(voltage)`) appended to
   `converted_values`.
5. If a plasma-current setpoint is non-zero: `plasma_current_control()`
   runs a `simple_pid.PID(0.3, 0.1, 0)` against `Ip` and emits
   `send_control_voltage` to `MCP4725` (via a queued signal handled in
   `main.py: _set_cathode_current`).
6. Every `STEP` ticks: `send_processed_data_to_main_thread()` emits
   `data_ready.emit([dataframe, device_name])`.
   `MainApp.on_worker_step` routes to `_adc_step`, appends to
   `self.datadict["ADC"]`, calls `save_data` (CSV append, never
   closed), and triggers a plot update.

Worker→worker signalling is also present:

```python
# controlunit/main.py (lines 288–294)
def start_cross_connections(self):
    """Connect workers signals directly"""
    mfcs_worker = self.workers["MFCs"]["worker"]
    adc_worker = self.workers["ADC"]["worker"]
    mfcs_worker.send_presets_to_adc.connect(
        adc_worker.update_mfcs, type=QtCore.Qt.DirectConnection
    )
```

The DAC8532 worker tells the ADC worker what voltage it just set so
the ADC can log the *commanded* preset alongside the *measured*
signal. `DirectConnection` here means the slot runs in the emitter's
thread — fine because `update_mfcs` only touches `self._mfc_presets`.
This is a deliberate, correct use of `DirectConnection` *[inferred —
the same flag is not misused elsewhere]*.

### DAQ and logging

Two parallel logging paths, both append-only:

1. **CSV data file** — created in `main.py: create_file()` when
   acquisition starts:

   ```text
   ~/work/cudata/cu_20260101_120000.csv
   ```

   Header block in `generate_header_adc()`:

   ```python
   # controlunit/main.py (lines 396–409)
   def generate_header_adc(self):
       """
       Generage ADC header
       """
       return [
           "# Title , Control Unit ADC signals\n",
           f"# Date , {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
           f"# Columns , {', '.join(self.config['ADC Column Names'])}\n",
           f"# Signals , {', '.join(self.config['ADC Signal Names'])}\n",
           f"# Channels , {', '.join([str(i) for i in self.config['ADC Channel Numbers']])}\n",
           "# For converted signals '_c' is added\n",
           "#\n",
           "# [Data]\n",
       ]
   ```

   That header pattern (`# Title`, `# [Data]`) is a deliberate format
   — it survives `pandas.read_csv(..., comment='#')` *and* embeds
   enough channel metadata that an old CSV can be replayed without
   `settings.yml`.

2. **Event log file** — `~/work/cudata/controlunit.log`, append-only:

   ```python
   # controlunit/main.py (lines 342–347)
   def log_to_file(self, message):
       filepath = self.config["Log File Path"]
       time_stamp = self.generate_time_stamp()
       new_line = f"{time_stamp}, {message}\n"
       with open(filepath, "a") as f:
           f.write(new_line)
   ```

   Same messages also accumulate as HTML in `LogDock` — `strip_tags()`
   is the bridge.

### PID / control logic

There are two PID implementations in the live code *[confirmed]*:

- **Plasma current (Ip) PID** — in `ADC.plasma_current_control()`,
  uses [`simple_pid`](https://pypi.org/project/simple-pid/) with
  `p=0.3, i=0.1, d=0` and `output_limits=(0, 4500)` (mV). Setpoint
  comes from the GUI, plant feedback is the Hall-effect sensor on
  channel 0, actuator is the MCP4725 DAC. Anti-windup is the library's
  job. The "baseline" of 1000 mV is the bias point of the cathode
  supply at low currents *[inferred from comment "corresponds to 16A"
  on adjacent line]*:

  ```python
  # controlunit/devices/adc.py (lines 312–319)
  def plasma_current_control(self):
      """
      PID control plasma current
      """
      baseline = 1000 #2000 #mV, corresponds to 16A
      output = self.pid((self.plasma_current - self.zero_ip) * 1000)
      output = output + baseline
      self.set_cathode_current(output)
  ```

- **Membrane heater PID** — hand-rolled in
  `MAX6675.temperature_control()`, integral-clamp by
  `if integral < -0.5: integral = 0`, asymmetric (only positive `e`
  drives output, negative just sets 0 — i.e. the heater can heat but
  not cool, which is physical). Gains `Kp=3.5, Ki=0.06, Kd=0`. The
  author *knows* this should be moved to `simple_pid` too — there is a
  literal TODO:

  ```python
  # controlunit/devices/max6675.py (lines 178–181)
  """
  Shouldn't the self.sampling_time here be 0.25, not the one for ADC?
  TODO: update to simple-pid as in TemperatureControl
  https://github.com/queezz/TemperatureControl
  """
  ```

The PID *output* is not a duty cycle but a "fraction of 10 ms"
parameter `set_heater_on_duration` that `HeaterContol.work()` uses as
`time.sleep(min(self.set_heater_on_duration, 0.01))` /
`time.sleep(max(0.01 - ..., 0))` to drive a relay-controlled halogen
lamp. The 10 ms cycle time is essentially software PWM with a hard
100 Hz floor. The choice to do PWM in software (rather than via the
Pi's hardware PWM pins) is dictated by which relay was wired up — a
Celduc SO842074 zero-cross SSR can switch at 100 Hz easily *[inferred
from datasheet linked in README]*.

### Isolation / safety design decisions

The isolation strategy is layered *[a mix of confirmed in code and
inferred from hardware context]*:

1. **GPIO isolation via SSR.** The heating-element circuit is mains
   100 V × 300 W (Panasonic JCD100V300WCG halogen). It is controlled
   through a Celduc SO842074 zero-cross SSR. The Pi never touches
   mains. *[confirmed from README BOM]*
2. **I²C isolation for the plasma DAC.** The April 2026 work
   (`dfbc65c upd for isolated DAC control of the plasma current`,
   `0b417cf add debug for mcp4725, isolated DAC for plasma current`)
   put the MCP4725 on an isolated I²C bus *[inferred from commit
   message wording; the isolator hardware is not visible in code]*.
   The plasma is the loudest thing in the lab; this protects
   everything else from arc-induced transients on the I²C lines.
3. **Software safety on quit.**

   ```python
   # controlunit/main.py (lines 316–327)
   def turn_off_voltages(self):
       """Safely turn off any DAC voltages"""
       if not self.workers:
           return

       self.workers["ADC"]["worker"].set_plasma_current.emit(0)
       self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)

       self._mfc_presets = {1: 0, 2: 0}
       self.update_current_values()
       self.workers["MFCs"]["worker"].output_voltage_signal.emit(1, 0)
       self.workers["MFCs"]["worker"].output_voltage_signal.emit(2, 0)
   ```

   `abort_all_threads` → `turn_off_voltages` *first*, then terminates
   threads. The plasma current setpoint goes to zero before the
   threads die. There is also a confirmation popup wired to the on/off
   switch (`popup_confirmation_window` in `mainView.py`) — you cannot
   accidentally stop acquisition mid-run.
4. **The QMS-sync LED is dual-purpose.** GPIO 26 drives both an
   indicator LED on the front panel *and* the sync trigger to the
   QMS (quadrupole mass spectrometer). The same edge is the
   "experiment running" signal seen by the analyser
   *[inferred from `IndicatorLED` docstring and `settings.yml`
   comment "The same pin is used to send sync signal to QMS"]*.
   `IndicatorLED.qms_calibration_indicator()` emits a known pattern
   (3 short pulses then steady) so the QMS data file can be aligned
   to the rig's calibration runs.
5. **Software-emulated hardware (`devices/dummy.py`).** Lets
   development happen on Windows by stubbing out `pigpio.pi`,
   `RPi.GPIO`, `spidev.SpiDev`, and `smbus.SMBus` to no-op classes.
   Crude (the SMBus stub returns hardcoded `0x80` and `0x1234`) but
   enough to bring up the GUI for layout work.

---

## Development Timeline

```text
2020-02 ── Initial commit (queezz). Single worker.py. ThreadType enum.
2020-03 ── "Untangling Ito-kuns therading mess". ThreadType → Signals.
            Black/pre-commit added. CodeShip CI badge added.
2020-06 ── Numpy → pandas DataFrames begin (incomplete).
2020–22 ── Long quiet period.
2022-06 ── [REORGANIZE] package layout + pdoc3 docs generated.
2023-04 ── Multiple contributors arrive (Tatsuemon, leprecon-pi).
            "hasizuka" (Hashizuka?), "B2", "B1" — measurement-campaign labels.
2023-05 ── ADC channel meta moved into AdcChannelProps + settings.yml.
            8 commits "worker: tuning ADC thread" — the buffer redesign.
2023-06 ── Logging-to-file, sampling-time-from-GUI, gain switching.
            customTypes.py, ionizationGauge.py, pfeiffer.py DELETED
            (functions absorbed into conversions.py).
2024-08 ── Worker super class split (commit by hasuo_kuzmin.lab from Pi).
2024-09 ── MFC integration (DAC8532), MCP4725 addition.
            Mass rename: sensors/→devices/, components/→ui/.
2024-09–10 PID push: Ip-zero, plasma current PID, intra-thread signalling.
            "Ip PID response detected (hardware)" — the rig actually closes loop.
2025-08 ── Two Codex automated PRs: data-handling moved INTO workers,
            CoreLogic signal fix + first non-trivial test.
2026-04 ── Isolated DAC for plasma current. Settings layout cleanup,
            Ip-PID OFF button (because you need to be able to abort PID fast).
2026-05 ── Latest: "settings: debug false". Lab still active.
```

Two clear *measurement-campaign signatures*: the 2023-05 ADC-tuning
storm (one developer fixing real hardware) and the 2024-09/10 PID
storm (closing the plasma-current loop). Each lasts 2–4 weeks of
intense commits, followed by months of quiet *[inferred from commit
density]*.

---

## Experimental Context Inference

> This entire section is more *speculative* than the architecture
> sections; the signals strongly imply a specific physics, but the
> exact experimental hypothesis is not stated anywhere in the repo.
> Tags below highlight the riskiest interpretations.

The signals being measured tell you a lot about what the rig does
*[confirmed channel-by-channel from `settings.yml`]*:

- `Ip` — plasma current via Hall sensor (`hall_current_sensor`,
  `5 * (v - 2.52) A`, calibrated against a known reference).
- `Pu` / `Pd` — upstream and downstream pressure (Pfeiffer single
  gauge + ionization gauge). Two pressures means there is a *membrane*
  in between with a known transport process being measured
  *[inferred]*.
- `Bu` / `Bd` — upstream/downstream Baratrons (MKS 627 FS = 1 Torr,
  MKS 628B FS = 0.1 Torr), the precise pressure references, spanning
  a decade apart so one is always in range.
- `MFC1` / `MFC2` — mass flow of **H₂** (20 SCCM) and **O₂**
  (10 SCCM). Two reactive gases controllable in real time
  *[confirmed from settings.yml description strings]*.
- `Ci` / `Cv` — cathode current and cathode voltage (recorded but not
  actively controlled; `Cv` is divided by 10 and multiplied by 42 to
  convert the divider).
- `T` — membrane temperature via K-thermocouple → MAX6675
  (channel-isolated by the chip), heater driven by a halogen lamp
  through an SSR.
- `QMS_signal` — a column embedded in every CSV row recording whether
  the QMS sync trigger is currently being emitted.

Putting these together: this looks like a **hydrogen-permeation /
plasma-driven permeation experiment** *[speculative — see uncertainties
section]*. A heated membrane separates two gas volumes. Plasma is
generated on one side (cathode-driven, hence the dedicated
Ip / Cv / Ci channels), gas composition is controlled by H₂ and O₂
MFCs, transport across the membrane is read by the differential
pressure pair (Bu/Bd or Pu/Pd depending on regime). A QMS analyses the
downstream species, time-aligned to this rig by the LED-flicker sync.

This interpretation, if correct, explains many engineering choices
that look weird in isolation:

- **Why two MFCs and not one?** H₂ permeates the membrane, O₂ is used
  for plasma chemistry or surface oxidation *[speculative]*. The MFCs
  need independent control.
- **Why Pu *and* Bu, Pd *and* Bd?** Different decades. The Baratron is
  accurate but limited; the Pfeiffer / ionization gauge spans many
  decades but is less accurate. Both are recorded so you can stitch a
  wide-dynamic-range pressure trace post-hoc *[inferred]*.
- **Why a Hall sensor for plasma current and not a shunt?** Hall is
  non-contact, does not drop voltage, and can handle the high cathode
  currents. The price is offset drift, which is exactly what the
  "Subzero Ip" button + `zero_adjustment["Ip"]` zero-shift mechanism
  is for — the operator zeroes the Hall sensor at the start of each
  run.
- **Why is QMS sync done by a flickering LED, not a TTL pin?** Because
  the QMS has its own opto-isolated input that *looks* at an LED
  *[speculative — the LED could equally just be a visual indicator
  with a parallel TTL line]*. Galvanic isolation by photons, if true,
  would be pragmatic and effective.
- **Why isolate the MCP4725 in April 2026?** Because plasma transients
  on the cathode bus were getting back into the I²C bus and crashing
  other devices *[speculative — the commit message says "isolated DAC"
  but does not specify what failure motivated it]*. You typically do
  this kind of work *after* you have seen the problem.
- **Why `simple_pid` with output limits (0, 4500) for plasma current?**
  Because 0 V at the DAC means no plasma; 5 V is the supply rail
  (5000 mV) but 4500 is a margin so you never saturate. The
  `baseline = 1000` mV is a no-plasma idle current bias *[inferred]*.
- **Why is the temperature path commented out everywhere in current
  `main.py`?** Because temperature is now being read on a separate
  Windows machine via National Instruments hardware (mentioned in
  `graph.py` comments: *"Currently moved thermocouples to National
  Instruments on Windows."*). The MAX6675 path is kept alive in code
  in case the integration moves back to the Pi.

---

## Strong Engineering Ideas

These are the *durable* ideas — patterns worth keeping in any rewrite.

1. **Settings-driven channel topology with named conversion functions.**

   ```python
   # controlunit/devices/adc_channels.py (lines 7–24)
   class AdcChannelProps:
       def __init__(self, *arg, **kws) -> None:
           self.name = arg[0]
           self.channel = kws["Channel"]
           self.gainIndex = kws["Gain"]
           self.description = kws["Description"]
           self.conversion_id = kws["Conversion Function"]
           self.full_scale = kws.get("Full Scale", None)
           self.set_conversion_function()
   ```

   Adding a new instance of an existing sensor type means editing YAML,
   not code. Adding a new *type* means writing one function in
   `conversions.py` and adding one entry to the dispatch dict. This is
   the right granularity.

2. **Versioned settings with per-host override.**

   ```python
   # controlunit/readsettings.py (lines 24–51)
   def select_settings(path_to_file="settings.yml", verbose=False):
       """
       Check if there is local settings file and
       if its version is same as current, load local one.
       """
       local_settings = os.path.join(
           os.path.expanduser("~"), ".controlunit", "settings.yml"
       )
       try:
           local_config = load_settings(local_settings)
           config = load_settings(path_to_file)
           if local_config["Settings Version"] == config["Settings Version"]:
               config = local_config
   ```

   The repo carries the canonical `settings.yml`, but the actual rig
   has `~/.controlunit/settings.yml` with its own channel map. The
   version-key check prevents an old local override from silently
   breaking after a schema bump. Quietly excellent.

3. **STEP-batched signalling between DAQ thread and GUI.** Already
   discussed — the cleanest way to keep a 10 Hz acquisition loop while
   protecting the GUI from per-sample IPC traffic. Adjusted dynamically
   by sampling rate:

   ```python
   # controlunit/devices/device.py (lines 47–55)
   def set_sampling_time(self, sampling_time):
       """Set sampling time"""
       self.sampling_time = sampling_time
       if sampling_time >= 0.9:
           self.STEP = 1
       if sampling_time < 0.9:
           self.STEP = 3
       if sampling_time < 0.1:
           self.STEP = 5
   ```

4. **Per-row preset logging.** Every ADC row carries the *commanded*
   `PresetV_mfc1`, `PresetV_mfc2`, `PresetV_cathode`, `IGmode`,
   `IGscale`, and `QMS_signal`. The CSV is fully self-describing —
   you can rebuild a complete state trace from one file. No "ah, but
   what setpoint was I at?" problems.

5. **CSV header that embeds channel map + signal name list.** The
   `# Title / # Date / # Columns / # Signals / # Channels` header is
   short, parseable, and lets the data outlive the code.

6. **Dual-purpose dummy modules.** `devices/dummy.py` is the
   developer-on-Windows safety net. Crude on purpose — they should
   *not* simulate real signals, only let the GUI render. This is the
   right boundary.

7. **Hand-painted touch toggles.** `MySwitch` and friends in
   `ui/buttons/toggles.py` — overkill if this were a normal desktop
   app, but exactly right for a 7" touchscreen with sticky fingers.
   Custom `hitButton` enlarges the touch target beyond the visible
   widget.

8. **The "cross-connection" between MFC and ADC workers via
   DirectConnection.** A precisely targeted use of
   `Qt::DirectConnection`: one worker tells another the value it just
   commanded, so the second one can log it alongside the next sample.
   Most Qt threading bugs come from misusing DirectConnection; here it
   is used correctly because the slot only touches a dict.

9. **Hardware-emergency-stop semantics.** `turn_off_voltages()` runs
   *before* thread termination. The act of clicking "OFF" in the GUI
   is not just "stop the program" but "drive every actuator to zero,
   then stop the program". This is operationally correct for a lab
   system.

10. **LaTeX in conversion docstrings.** Each gauge polynomial is
    documented inline with its mathematical form. When the gauge gets
    recalibrated, the next person knows exactly what was assumed.

---

## Technical Debt and Scaling Limits

Honest list, no judgement — these are debts from a real working system.

### A. Three half-completed renames

1. `setup.py` still installs `controlunit.components` (which no longer
   exists).
2. `bin/plasmacontrol` imports `MainWidget` (which is now `MainApp`).
3. `controlunit/__init__.py` says
   `https://github.com/queezz/ControlUnit/tree/pack` — a branch that
   no longer exists. The variable `_echelle_base` is a leftover from a
   different project's template *[speculative]*.

### B. The sys.path hack

```python
# controlunit/__init__.py (lines 9–11)
# temporarily add this module's directory to PATH
_echelle_base = pathlib.Path(__file__).parent.absolute()
sys.path.append(str(_echelle_base))
```

This is what makes `from mainView import UIWindow` work alongside
`from controlunit.devices.adc import ADC` in the same file. It is
robust *in practice* (one developer, one Pi) but breaks normal Python
tooling: editable installs, mypy / pyright, pytest collection from a
different cwd, importlib resource resolution. Every module that does
`from devices.dummy import pigpio` (the fallback in seven places)
depends on this hack.

### C. Module-import-time `select_settings()` calls

```python
# controlunit/heatercontrol.py (lines 5–13)
from readsettings import select_settings

config = select_settings(verbose=False)
CHHEATER = config["Heater GPIO"]
```

`heatercontrol.py`, `trigger_signal.py`, `ui/docks/control.py`,
`ui/docks/gas_flow.py` all read `settings.yml` at *import time*, then
bind constants at module scope. If a settings change happens during a
session, those constants are stale. Configuration leaks into
module-level state.

### D. Aspirational ghost classes

`controlunit/core_logic.py` and `controlunit/plot_data_handler.py`
both contain:

- A class definition.
- A `TODO: move signal connection from main.py here`.
- *No instantiation anywhere in the codebase.*

`plot_data_handler.py` even copies-and-pastes methods
(`update_plots_max6675`, `update_plots_adc`, `select_data_to_plot`,
`downsample_data`) that still live in `main.py`. Either of them being
imported by mistake would do nothing useful — they reference
`self.adc.data_ready`, `self.datadict`, `self.time_window`,
`self.graph.plot_lines` without ever taking those references in
`__init__`.

These are *intention markers*, not abstractions. They should be either
filed under `controlunit/_extract_targets/` and disabled in
`__init__.py`, or actually finished.

### E. DataFrame-append-in-loop

```python
# controlunit/main.py (lines 432–438)
self.datadict[device_name] = pd.concat(
    [
        self.datadict[device_name],
        self.newdata[device_name].astype(self.datadict[device_name].dtypes),
    ],
    ignore_index=True,
)
```

The in-memory log of an ADC run grows by `pd.concat` every STEP
cycles. At 10 Hz with STEP=3, that is ~one concat per second, and the
table grows unbounded for the duration of a run. A long experiment
(hours) will start to feel this — pyqtgraph plot updates already
compensate with downsampling, but the concat itself is O(n) each call.

### F. CSV file handles opened-and-closed per write

```python
# controlunit/main.py (lines 466–467)
data = self.newdata[device_name]
data.to_csv(savepath, mode="a", header=False, index=False)
```

Every STEP, the file is reopened for append. On a Pi with a microSD
card, that is a *lot* of fsync-equivalent traffic. Fine in practice
for 10 Hz; bad if anyone ever wants 100 Hz.

### G. Tests are essentially absent

- `tests/test_sample.py` literally tests `inc(3) == 4`.
- The Codex-PR added `tests/test_core_logic_signal.py` for a class
  that nothing else uses.
- CI runs `flake8 syntax + pytest` against the dummy file only.

The conversion functions in `conversions.py` are the single
highest-value target for actual unit tests (they encode the lab's
calibration). None of them are covered.

### H. CI is from the Python 3.8 era

`.github/workflows/pythonapp.yml` pins Python 3.8 (released 2019).
`requirements.txt` still says `numpy>=1.17.4`. The repo uses
`pd.concat` with `ignore_index=True` and `.astype(dtypes)` to dodge a
FutureWarning — but that warning is from a much newer pandas. The CI
does not catch this drift because it does not actually exercise the
GUI path.

### I. The `kurokawa-dev/` quarantine

```python
# kurokawa-dev/PWR.py (lines 24–35, tab-indented in original)
class PWR401L:
    def __init__(self):
        self.init_pwr401l()

    def init_pwr401l(self):
        write_command("SYST:COMM:RLST")
        write_command("VOLT:PROT 50")
```

A 50-line SCPI driver for a Kikusui PWR-401L bench supply
*[speculative — model number inferred from class name, not confirmed
against a datasheet]*, tab-indented, separate top-level folder. It has
never been imported by the main app. It is a *parking spot* for an
experiment that may or may not get integrated. Do not delete it — but
document its quarantined status.

### J. Inconsistent error-handling

`DAC8532.init()` does:

```python
# controlunit/devices/dac8532.py (lines 43–50)
def init(self):
    try:
        self.DAC = DAC8532Setter()
        self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, 0)
        self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, 0)
        print("High-Precision AD/DA initialised")
    except:
        GPIO.cleanup()
```

Bare-except, silent recovery, no log. If the DAC fails to initialise,
the worker will still be spawned and signals will still be connected,
leading to weird symptoms downstream.

### K. The `_init_cocnnections` typo

```python
# controlunit/main.py (line 134)
def _init_cocnnections(self):
```

A minor thing, but the kind of long-lived typo that proves no
automated symbol-rename has touched this code.

---

## Modernization Suggestions

Concrete, ordered, and respectful of the existing constraints.

### Tier 0 — zero-risk cleanup (an afternoon)

1. **Bring `setup.py` and `bin/plasmacontrol` in sync with the actual
   package.**

   ```python
   packages=["controlunit", "controlunit.devices",
             "controlunit.ui", "controlunit.ui.docks",
             "controlunit.ui.widgets", "controlunit.ui.buttons"],
   entry_points={"console_scripts":
                 ["plasmacontrol=controlunit.main:main"]},
   ```

   And in `bin/plasmacontrol`:
   `from controlunit.main import main; main()`.

2. **Pin a modern Python in CI.** Bump
   `.github/workflows/pythonapp.yml` from 3.8 to 3.11. Drop CodeShip
   badge from README (CodeShip shut down in May 2024).

3. **Rename `_echelle_base`** to `_PACKAGE_DIR` and add a docstring
   explaining what the sys.path append is buying you.

4. **Decide on `core_logic.py` and `plot_data_handler.py`.** Either
   finish them (Tier 2) or move them to `controlunit/_drafts/` and
   exclude from the package install. The Codex-PR added a test for
   `CoreLogic`; either keep them as a real extraction target or accept
   that they are dead and remove them.

### Tier 1 — MkDocs migration

Use `mkdocs-material` with `mkdocstrings[python]` for live API
generation. The structure that fits this repo's reality:

```text
docs/                            (new MkDocs source)
├── index.md                     (project intro, embeds README photos)
├── Archaeology.md               (this document)
├── hardware/
│   ├── control-box.md           (photos + BOM from README)
│   ├── channel-map.md           (generated from settings.yml)
│   └── conversions.md           (rendered from conversions.py docstrings)
├── operation/
│   ├── starting-acquisition.md
│   ├── plasma-current-pid.md
│   ├── qms-synchronisation.md
│   └── safety.md
├── architecture/
│   ├── threading.md             (the threading story from this document)
│   ├── signal-flow.md
│   └── settings-versioning.md
├── api/                         (mkdocstrings auto-generated)
├── archive/
│   └── 2022-pdoc/               (the entire current docs/*.html moved here)
│       └── README.md            (rename map: AIO → adc_setter,
│                                 customTypes → conversions+adc_channels,
│                                 worker → devices/*, etc.)
└── changelog.md                 (generated from git log of _version.py)
```

Useful migration moves:

- **Write `docs/hardware/channel-map.md` once, by hand, from
  `settings.yml`.** It will quickly drift from the YAML; that is the
  point — it should embed *why* the channels are wired this way, not
  just *that* they are. Reference the YAML.
- **Render `conversions.py` with mkdocstrings + arithmatex** so the
  LaTeX in docstrings becomes the public physics reference.
- **Move `manuals/ads1113.pdf` into `docs/datasheets/`** and add the
  missing datasheets (Pfeiffer PKR251, MKS 627/628, Celduc SO842074
  already linked from README, MAX6675 already linked).
- **Archive, do not delete, the pdoc HTML.** It is evidence of the
  2022 shape and historians (= you in 5 years) will appreciate it.
- **Add `docs/architecture/threading.md`** containing the 6-phase
  narrative from the *Architecture Reconstruction* section above.
  Cite commits.
- **Disable the link `[DOCS](https://queezz.github.io/ControlUnit/)`
  in README** until MkDocs is deployed — currently it points to an
  out-of-date doc set and is actively misleading.

### Tier 2 — finish the extractions stubbed by `core_logic.py` and `plot_data_handler.py`

The MainApp class is 785 lines doing four jobs:

- Building the Qt object graph (via `UIWindow` mixin).
- Brokering signals between workers.
- Managing the in-memory and on-disk data store.
- Driving the plots.

A minimal split that matches the intent of the existing stubs:

- `WorkerOrchestrator(QObject)` — owns `self.workers`, does
  `prep_threads`, `start_all_threads`, `start_cross_connections`,
  `terminate_existing_threads`, `turn_off_voltages`. Currently spread
  over lines 222–336 of `main.py`. The existing `core_logic.py` is the
  placeholder for this.
- `DataStore` — owns `datadict`, `newdata`, `savepaths`, `create_file`,
  `append_data`, `save_data`, `generate_header_*`,
  `select_data_to_plot`, `downsample_data`. Pure data, no Qt.
  Currently lines 366–467.
- `PlotController` — owns `update_plots_max6675`, `update_plots_adc`,
  plot toggle logic. The existing `plot_data_handler.py` is the
  placeholder.

What remains in `MainApp` is just the Qt-signal wiring and the GUI
callback handlers — natural for an "App" controller.

This is the smallest restructure that gives the next bug-hunter a
fighting chance.

### Tier 3 — DataStore performance ceiling

Two cheap wins, only do them when 100 Hz becomes a real requirement:

1. Switch `pandas.concat` per cycle to a `collections.deque` of small
   DataFrames concatenated lazily on plot request.
2. Open the CSV file once at `create_file`, hold the handle, flush on
   `STEP`. Wrap in a `with` context in `abort_all_threads`.

### Tier 4 — Testing the parts that matter

`conversions.py` is pure-function and physics-critical. Add
`tests/test_conversions.py`:

```python
def test_hall_current_sensor_zero():
    assert hall_current_sensor(2.52) == 0.0


def test_baratron_full_scale():
    assert baratron(10.0, 1.0) == 1.0  # 10 V → 1 Torr at FS=1


def test_pfeiffer_single_gauge_known_point():
    # PKR251 datasheet: 4.0 V ≈ 1e-4 mbar = 7.5e-5 Torr
    assert pfeiffer_single_gauge(4.0) == pytest.approx(7e-5, rel=0.5)
```

This is a few hours of work and freezes the calibration story so it
cannot silently regress.

### Tier 5 — Hardware abstraction unification

Promote the `_setter.py` pattern into a real interface.
`adc_setter.AIO_32_0RA_IRC.analog_read_volt`,
`dac8532_setter.DAC8532Setter.DAC8532_Out_Voltage`,
`mcp4725_setter.MCP4725Setter.set_voltage` already have analogous
shapes. A `Chip` ABC with `init()`, `read()`, `write()`, and
`cleanup()` would let `devices/dummy.py` become a real simulator
(returning configurable test signals) instead of a no-op shim. This
unlocks proper headless integration tests.

---

## Engineering Mindset Reconstruction

> This section is the most subjective in the document. Read it as
> *interpretation*, not biography. *[speculative throughout]*

Reading the commit messages, file names, and the *shape* of changes
over six years, the developer appears to:

- **Treat code as instrumentation, not product.** Commit messages like
  `[fix] currentvalues B1,P1,B2,P2 -> Bu,Bd, Pu,Pd`, `[fix] more B1s
  to Bds. Need to automate this.`, `B2`, `B1 value :.1e`,
  `B1 value :.3f` are signs of someone iterating *with the experiment
  running* — naming conventions evolve as the upstream / downstream
  meaning of channels gets clearer. The code is a notebook.

- **Defend correctness with idempotence.** Reading `_mfc_presets` to
  zero in three different places, having `turn_off_voltages()`
  callable any time including when `self.workers` is empty, the
  `if not self.workers: return` guards everywhere — this is someone
  who has been bitten by "I clicked stop but it did not actually stop".
  The system is *always safe to stop*.

- **Prefer explicit-but-ugly over clever-but-fragile.**
  `set_sampling_time` is a chain of three `if` statements deciding
  STEP. `_mfc_presets = {1: 0, 2: 0}` is a two-key dict instead of a
  list. Spinboxes-per-decade for MFC voltages instead of one float
  field. These are *fingertip-distance* designs — the operator can
  see and override every value.

- **Rename without breaking semantics.** The 2024-09 storm of renames
  moved hundreds of references but the *meaning* of the system did
  not change. That discipline is rare and shows real care for the
  next-week-me.

- **Know when to admit defeat and start a stub.** `core_logic.py` and
  `plot_data_handler.py` are not failures of focus — they are
  load-bearing TODOs. The author *deliberately* left them visible so
  the next refactor does not have to be invented from scratch.

- **Trust hardware feedback over theory.** "Ip PID response detected
  (hardware)" is a commit message and a celebration. The PID gains
  `0.3, 0.1, 0` are not derived; they were tuned against the actual
  cathode supply. The membrane PID's `Kp=3.5, Ki=0.06, Kd=0` with
  one-sided clamping is what *worked*, not what is textbook.

- **Tolerate collaborators with different styles.** "Untangling
  Ito-kun's threading mess" is a graceful — even affectionate — way
  to take over a former colleague's code. The `kurokawa-dev/` folder
  and the `kawdev` branch are quarantined, not erased. Hashizuka's
  commits ("hasizuka") sit in the history alongside Tatsuemon's.
  This is *lab citizenship*, not software engineering hygiene.

- **Use automation where it helps and ignore it where it does not.**
  Pre-commit + Black ran 2020–2022, the CI is set up but never
  extended, Codex was let near the code twice in 2025 for narrow
  surgical fixes, and pdoc was run once. None of these became dogma.

The strongest single sentence describing this mindset is the inline
comment in `controlunit/devices/adc.py`:

```python
# controlunit/devices/adc.py (lines 96–101)
def prep_adc_board(self):
    """
    Initiates an instance of AIO_32_0RA_IRC from AIO.py
    Address: 0x49, 0x3E
    Why this addresses?
    """
```

"Why this addresses?" — written by someone who is *fine* with not yet
knowing why the I²C addresses are what they are, who *will* find out
next time they wire the board, and who left the note for themselves.
That is the whole repo in one docstring: pragmatic, honest, lab-paced,
and never pretending to be anything other than a research tool.

---

## Known uncertainties and possible incorrect assumptions

This section collects the places where the archaeology depends on
interpretation rather than direct evidence. It is deliberately
defensive: if any of these are wrong, the conclusions built on them
should be re-examined.

### Physics and experimental purpose

- **The "hydrogen-permeation through a heated membrane" interpretation
  is a guess.** It is consistent with: two MFCs (H₂ and O₂), a heated
  thin object called "Membrane" in code comments, upstream / downstream
  pressure pairs with overlapping decades, a QMS in the room, and the
  presence of plasma. But the same hardware could equally support:
  - Plasma-Driven Permeation (PDP) studies — H plasma on one side, H
    permeation flux out the other.
  - Plasma-Wall Interaction studies — exposing materials to plasma and
    measuring outgassing.
  - Surface oxidation / reduction chemistry experiments where the
    membrane is a catalyst sample, not a permeation barrier.

  Where this report says "hydrogen-permeation experiment", read
  "a plasma-membrane interaction experiment of an unspecified
  flavour."

- **"Cathode" terminology.** The variables `Ci`, `Cv` are described in
  `settings.yml` as "cathode current" and "cathode volt". The
  conversion `voltage / 10 * 42` for `cathode_volt` *implies* a
  resistive divider with a known ratio, but the actual cathode
  geometry, target material, and bias scheme are not in the repo.

- **The 16 A baseline-corresponds claim** (`baseline = 1000 #2000 #mV,
  corresponds to 16A`) ties a DAC voltage to a plasma current via the
  external cathode supply's transfer function. That transfer function
  is not documented in the repo — it lives in whatever bench supply
  the rig actually uses. Changing the supply changes the meaning of
  the baseline; the code will not know.

- **"Galvanic isolation by photons" for the QMS sync.** The phrasing
  in the *Experimental Context Inference* section is interpretive.
  The repo only shows that the same GPIO pin drives an LED *and*
  emits a "trigger" signal. Whether the QMS receives the trigger via
  the LED, via a parallel TTL wire, or both, is not visible in code.

### Hardware identification

- **The Kikusui PWR-401L identification in `kurokawa-dev/PWR.py`** is
  inferred from the class name and the SCPI commands used
  (`SYST:COMM:RLST`, `VOLT:PROT`, `OUTP`). It could equally be another
  vendor's supply with compatible SCPI syntax.

- **The "isolated DAC" hardware** is referenced only in commit
  messages. The actual isolation chip (digital isolator? optoisolated
  I²C bridge? separate power domain?) is not documented in code. The
  code change to the MCP4725 path is small enough that the hardware
  could be anything from an ADuM1250 to a custom transformer-coupled
  bridge.

- **The "Plasma-Driven Permeation rig" interpretation** assumes the
  membrane is a metallic foil (typical of PDP work) but the
  `settings.yml` description of MAX6675 is just "Cold-Junction-
  Compensated K-Thermocouple". The membrane could be a ceramic sample,
  a polymer, anything thin and heatable.

### Architectural and intent claims

- **"Ito-kun wrote the initial threading"** is inferred from the
  commit message `Untangling Ito-kuns therading mess` and from the
  fact that this commit is a +161 / −107 rewrite. The original
  author's git identity is `queezz <queezz@gmail.com>` on the
  *initial* commit. Either `queezz` wrote a draft based on
  `Ito-kun`'s prior code, or `Ito-kun` wrote a draft that `queezz`
  committed, or "Ito-kun" is referring to something not in git at
  all. The exact authorship attribution is genuinely uncertain.

- **"The pdoc nested-duplicate (`docs/components/components/`) is a
  pdoc bug."** Equally plausible: someone ran `pdoc` once from the
  wrong working directory and the output was committed. Without
  replaying the 2022 build, we cannot tell.

- **"`_echelle_base` is a leftover from another project."** There is
  a `queezz/echelle` project on GitHub that uses similar terminology,
  which is *suggestive*. But the variable may also simply have been
  named cutely with no template-copy involved.

- **"The April 2026 isolation work was triggered by an observed
  failure."** The commit message says "isolated DAC for plasma
  current" and "debug for mcp4725". It does *not* say "after the I²C
  bus locked up during a plasma run". The motivation could be
  prophylactic rather than reactive.

- **"`STEP` batching is a deliberate IPC-amortisation design choice."**
  It is also possible that `STEP` was originally just an averaging
  window from the original numpy-arrays days and only later acquired
  its IPC-rate-limiting role. The two interpretations are
  observationally identical.

### Code-status claims

- **"`heatercontrol.py` is alive but unused."** It is *imported* by
  `devices/max6675.py: init_heater_control`, which is itself called
  inside `MAX6675.acquisition_loop`. If anyone uncomments the
  MembraneTemperature path in `main.py`, the heater control wakes up.
  "Unused" therefore means "currently disabled", not "dead code".

- **"`MAX6675` thermocouple path is disabled because the rig moved to
  NI hardware on Windows."** The graph.py comment supports this, but
  it is one comment. The path could equally be disabled because the
  membrane heater hardware was rewired and not yet re-tested on the
  Pi.

- **"The `analoggauge.py` widget (32 KB) is unused."** Confirmed by
  grep — but it could be intentionally retained for a future tab. The
  user prompt asked not to aggressively judge unfinished sections;
  this is one of them.

- **The "v0.4.0" version string** in `_version.py` does not align with
  any obvious feature milestone in the git history. There are no
  tagged releases. Versioning is informal.

### Migration recommendations

- The Modernization Suggestions are *opinion*, not facts.
  Specifically:
  - The Tier-1 MkDocs layout is one of several reasonable
    organisations; if there is an existing documentation tradition in
    the lab (Sphinx, MkDocs in a sibling project, etc.) that should
    take precedence.
  - "Tier 2 — finish the extractions" assumes the current author
    *wants* to finish them. The stubs may be load-bearing as
    documentation of intent and removing or completing them may both
    be wrong moves.
  - The "Tier 4 — Testing the parts that matter" calibration values
    in the example tests (e.g. `pfeiffer_single_gauge(4.0) ≈ 7e-5
    Torr`) are derived from the conversion formula itself, not from
    a manual reading of the PKR251 datasheet. They are circular until
    cross-checked against the datasheet, which is *not* present in
    `manuals/`.

---

*End of archaeological snapshot. If you correct any of the
uncertainties above, please date the correction and keep the original
claim visible — the history of what was thought is itself part of
this document's value.*

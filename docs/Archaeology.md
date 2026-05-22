# ControlUnit — Software & Laboratory-System Archaeology

> Second-pass reconciled snapshot, 2026-05-22, against `thread-fix-v2`
> at the tip of 347 commits (Feb 2020 → Apr 2026). The first pass was a
> blind archaeological reading; this version folds in first-hand
> developer corrections inline, preserves the original wrong inferences
> where they reveal real ambiguity in the codebase, and treats the
> developer's own voice as part of the historical record.

## About this document

This is an archaeological reading of the `ControlUnit` repository:
a Raspberry-Pi-based plasma-experiment control and data-acquisition
system that has accreted over six years of active research and
teaching use. It is not a code review and not a roadmap. It is a
forensic reconstruction, then partially un-done by the person who
actually wrote the code.

The document is deliberately layered:

- The **base layer** is the original first-pass archaeology — what
  the codebase looks like to someone who has never met the developer.
- **Developer Note** callouts integrate first-hand corrections.
- **Historical Evolution** callouts trace lineage back to projects
  that predate this one (notably the `Echelle` PyQtGraph application).
- **First-pass inference (preserved)** notes flag places where the
  blind reading was wrong but the codebase invited the wrong reading
  — those are evidence of real ambiguity worth keeping.

### Confidence legend

Inline epistemic tags are still used where status is non-obvious:

- *[confirmed]* — directly visible in code, commits, or file listings,
  or now confirmed by the developer.
- *[inferred]* — strongly implied by multiple converging pieces of
  evidence but not stated anywhere.
- *[corrected]* — initially inferred wrongly; the developer's
  correction has been folded in.
- *[speculative]* — still a working interpretation, plausible but not
  proven.

The final section,
[Known uncertainties and possible incorrect assumptions](#known-uncertainties-and-possible-incorrect-assumptions),
is now much shorter — most uncertainties have been resolved by the
developer's pass.

---

## Executive Summary

`ControlUnit` is a Raspberry-Pi-based laboratory instrument written,
extended, taught with, broken, rewritten, and lightly LLM-assisted by
one principal developer (Arseniy / `queezz`) over six years, with
contributions from students and lab-mates passing through. It is
**both software and infrastructure**: the box exists, has a front
panel, sits in a multi-chamber plasma lab, and is used today.

What it does today *[confirmed by developer]*:

- Logs plasma parameters and vacuum from one I²C ADC.
- Controls two MFCs (H₂ and O₂) via a DAC8532.
- Controls plasma current via a galvanically isolated MCP4725 DAC
  through a feedback PID.
- Synchronises external loggers (QMS and others) via a GPIO sync
  signal that also drives a front-panel LED.

What it has done in the past but does not do today:

- Closed-loop membrane temperature control via MAX6675 + SSR-driven
  halogen lamp. **Migrated** to a Windows machine with National
  Instruments hardware. The code path is dormant, not deleted.

What it was *originally* for *[corrected]*:

- A dedicated hydrogen-permeation rig studying the effect of oxygen
  on hydrogen transport through metals under plasma irradiation.
  The lab has since grown around it; the experiment is gone, the
  instrument is repurposed, the name `ControlUnit` is still apt.

> **Developer Note (Arseniy).**
> "I was exploring and learning. My goal with this RasPi unit was to
> learn electronics. And I think I've succeeded. And my students
> probably learned a bit or two."

The codebase reads like a *strata*: a 2020 monolithic `worker.py`
copied from an earlier project (`Echelle`) still imprints the
structure, even after a 2024 split into `devices/`, `ui/`, and a
worker base class.

> **Historical Evolution: from `Echelle`.**
> The original threading and PyQtGraph dock layout were ported from
> `Echelle`, a spectrograph-control application Arseniy wrote *before*
> `ControlUnit`. The `_echelle_base` variable in
> `controlunit/__init__.py` is a literal fossil — the sys.path-append
> idiom and the early `Worker` class were template-copies. A B4
> student (Ito-kun, also known by the commit name "Tatsuemon")
> extended that template — see Threading Evolution below.

Three forces shape the codebase *[partially corrected]*:

1. **Hardware reality.** The rig actually exists, so channels,
   addresses, and conversion polynomials are pinned to physical
   sensors with datasheet URLs in comments.
2. **Multiple contributors with different conventions.** Identified
   below in the Contributor Key.
3. **Solo-physicist tempo with breaks for development.** Not
   measurement-campaign-aligned but the *opposite* — long quiet
   periods while experiments run, intense development pushes during
   experimental downtime.

> **Developer Note (Arseniy).**
> "Development is usually NOT tied to actual experiments. More on the
> opposite side. Accumulated necessity is implemented when there is a
> break in experiments and there is time."

The package compiles and runs. It is not abandoned — the latest
commit is from one month ago (`settings: debug false`). It carries
the scars of three half-completed renames, one half-extracted core,
one stale auto-generated doc site, and several modules that exist as
placeholders for "do this later" intentions that the developer is
honest about.

### Contributor key *[corrected]*

This is the corrected mapping of git authors to humans.

- **`queezz` / Arseniy** — principal developer. Wrote and rewrote
  most of the system. Also the unifying voice across all phases.
- **Ito-kun, B4 student.** Commits authored as `Tatsuemon`. Liked C.
  Built the early multi-threaded ADC reading on top of Arseniy's
  Echelle template. Went to an AI-development master's course after
  graduating. His threading model (re-opening I²C per channel read
  and using an `Enum` to dispatch device types) was the "mess" later
  untangled.
- **Miura-kun, lab member.** Commits authored as `leprecon-pi` and
  `pi <hasuo_kuzmin.lab@outlook.jp>` — the latter directly from the
  lab Raspberry Pi. His pass through the codebase coincided with
  Arseniy's first serious effort to migrate from numpy arrays to
  pandas DataFrames.
- **Kurokawa-kun** (git handle **`Kshora`**). Lab contributor. PRs #1,
  #18, #19 — early MFC and MCP4725 work. Also left
  `kurokawa-dev/PWR.py` — a quarantined SCPI driver for a Kikusui
  PWR-401L bench supply — never integrated into `ControlUnit`.
- **Kawabata-kun.** Came *after* Kurokawa. Wrote the final
  plasma-current PID loop and helped land the isolated-DAC
  integration in April 2026 (`kawdev` branch).
- **`codex/*` automated bot.** Two LLM-authored PRs in August 2025
  (#20, #21). Arseniy's first experiment with LLM-assisted design;
  not tested on the rig at the time.

> **Developer Note (Arseniy).**
> "When Miura-kun was here I thought about transitioning to pandas
> for sanity, but I was confused by the Qt thread mess. So it took me
> a while to finish this. Exactly the kind of LLM job. But I think
> I've learned a lot. Well, got exposure to classes and signals.
> Bad code, but real. After this I actually started using classes.
> I finally got what they are: basically a box, a drawer. So you
> don't spill and lose your functions."

---

## System Status Inventory

A category-tagged inventory of what is *implemented*, *planned*,
*experimental*, *dormant*, or *migrated* in the current tip.

### Implemented and live

- ADC acquisition via I²C (`devices/adc.py` + `devices/adc_setter.py`).
  Channels driven by `settings.yml`. 10 Hz default; dynamic STEP
  batching.
- MFC control via DAC8532 (`devices/dac8532.py`).
- Plasma-current PID via MCP4725 (`devices/mcp4725.py`,
  `devices/adc.py: plasma_current_control`). Uses `simple_pid`.
- CSV data logging (self-describing header) and HTML event log.
- pyqtgraph dual-pane plot (plasma current + pressures), live.
- Per-host versioned settings override (`~/.controlunit/settings.yml`
  → falls through to the in-repo `settings.yml`).
- Galvanically isolated MCP4725 hardware path (April 2026).
- LED + sync signal on shared GPIO for external loggers (QMS and
  others).

### Planned but not yet realised

- `core_logic.py` — intended extraction of cross-worker signal wiring
  from `main.py`. Class defined, never instantiated.
- `plot_data_handler.py` — intended extraction of plot-update methods
  from `main.py`. Class defined, never instantiated, duplicates code
  still living in `main.py`.
- Tagged versioning (`v0.4.0` is in `_version.py` but no git tags
  exist; the developer wants this but has no system for it yet).
- ESP32-based dedicated heater controller reporting to an orchestrator
  — the developer's *intended* successor for the membrane-temperature
  path. Not implemented in this repo.
- "Network of instruments" model — see the Engineering Mindset
  section.

### Experimental branches (live in git, off the main line)

- `kawdev` — Kawabata's plasma-current development branch.
- `thread-fix-v2` — current development tip; isolated DAC + settings
  layout cleanup + Ip-PID OFF button.
- `dev` — long-lived integration branch.

### Dormant capabilities (alive in code, currently disabled)

- Membrane-temperature control (`heatercontrol.py`,
  `devices/max6675.py`, `MAX6675.acquisition_loop`,
  `MAX6675.temperature_control`). Imported but not started, because
  the `MembraneTemperature` entry in `MainApp.define_devices` is
  commented out.
- MFC calibration sweep (`DAC8532.do_calibration`) — wired in code,
  has a dock UI, used historically, currently not in active use.
- Cathode current and voltage logging channels (`Ci`, `Cv` in
  `settings.yml`) — channels are configured and conversion functions
  exist, but the cathode current has *never actually been measured*
  *[corrected]* — only prepared in the ADC channel map and on the
  PCB.

> **Developer Note (Arseniy) on cathode current.**
> "Never measured cathode current. Wanted to, prepped. But that is
> not that crucial."

- 7" front-panel touchscreen *[corrected]*. The physical screen is
  still on the box, but the touch interface is disabled — it was
  never well calibrated. Day-to-day operation is via VNC or a
  Bluetooth mouse plugged into the USB port exposed on the chassis.
- `analoggauge.py` widget (32 KB, LabVIEW-style analog gauge).
  Was used briefly to display membrane temperature; abandoned both
  because the temperature path moved to Windows / NI and because the
  widget was too large for the 7" screen *[corrected]*.

> **Developer Note (Arseniy) on the touchscreen.**
> "Yes, touchscreen. But I disabled the touch. Because it is terrible,
> not well calibrated. I keep the display, it's always nice to have a
> display. Now it's only for show. I usually use VNC. Or a Bluetooth
> mouse sometimes. I have a USB port exposed on the box."

> **Developer Note (Arseniy) on `analoggauge.py`.**
> "I used that widget. I wanted a LabVIEW-like appearance. Stopped
> because temp control moved out, and that widget wasn't ideal. Too
> big for the tiny screen. And in my workflow I still want the GUI
> readable on the 7" screen. Just because."

### Migrated out of this repo

- Membrane-temperature reading and PID control — moved to a Windows
  machine with National Instruments hardware. Not coming back to the
  Pi; if it returns, it will be a separate ESP32 unit.

> **Developer Note (Arseniy).**
> "Yes, moved to NI on a Windows for now. Forever 🙂.
> And even if I would come back to it, I would make a dedicated ESP32
> unit which would report to an orchestrator. I've evolved my
> understanding of a lab instrument. Into a network."

- `kurokawa-dev/PWR.py` (SCPI driver for a Kikusui PWR-401L bench
  supply *[confirmed by developer]*) — Kurokawa's quarantined
  experiment, predating Kawabata's plasma-current work. Never integrated.

---

## Repository Structure

Top-level layout (alive vs fossilised, updated with category tags):

```text
ControlUnit/
├── controlunit/                 # the actual Python package
│   ├── __init__.py              # sys.path hack — alive but a smell;
│   │                            #   _echelle_base is a literal fossil
│   ├── _version.py              # 0.4.0, Apache-licensed; informal versioning
│   ├── main.py                  # MainApp(QObject, UIWindow), 785 lines — alive
│   ├── mainView.py              # UIWindow mixin — alive
│   ├── settings.yml             # ALIVE — de-facto schema AND deliberate doc
│   ├── readsettings.py          # ALIVE — YAML loader + AdcChannelProps wiring
│   ├── heatercontrol.py         # DORMANT — temperature path is disabled
│   ├── trigger_signal.py        # ALIVE — IndicatorLED + GPIO sync signal
│   ├── striphtmltags.py         # ALIVE — one-purpose helper
│   ├── start_gpio.py            # ALIVE — sudo pigpiod orchestration
│   ├── core_logic.py            # PLANNED stub: never instantiated
│   ├── plot_data_handler.py     # PLANNED stub: never instantiated
│   ├── devices/                 # HAL — renamed from sensors/ on 2024-09-25
│   │   ├── device.py            # DeviceThread base class (worker super)
│   │   ├── adc.py / adc_setter.py
│   │   ├── dac8532.py / dac8532_setter.py
│   │   ├── mcp4725.py / mcp4725_setter.py
│   │   ├── max6675.py           # DORMANT — currently not started
│   │   ├── adc_channels.py      # AdcChannelProps + conversion dispatch
│   │   ├── conversions.py       # gauge polynomials with LaTeX in docstrings
│   │   └── dummy.py             # off-RasPi shims for smbus, RPi.GPIO, pigpio, spidev
│   ├── ui/                      # renamed from components/ on 2024-09-25
│   │   ├── text_shortcuts.py    # ANSI + Unicode constants
│   │   ├── docks/               # pyqtgraph DockArea panels
│   │   ├── widgets/             # graph.py — ALIVE; analoggauge.py — DORMANT
│   │   └── buttons/toggles.py   # hand-painted QPushButton switches
│   └── icons/
├── docs/                        # FOSSIL: pdoc3 HTML from 2022 + Archaeology.md (this file)
├── examples/                    # mostly fossilised notebooks; settings_template.yml = snapshot
├── manuals/                     # one PDF (ads1113.pdf) — minimal in-repo reference
├── images/                      # README screenshots + photos of the physical box
├── tests/                       # one example test + one Codex-added test
├── kurokawa-dev/PWR.py          # QUARANTINED (Kurokawa): serial driver for PWR401L
├── bin/plasmacontrol            # 7-line entry-point script (BROKEN: imports MainWidget)
├── .github/workflows/           # one CI: flake8 syntax + example pytest
├── README.md, requirements.txt, setup.py, settings.yml, .pre-commit-config.yaml
└── data/test/                   # empty placeholder
```

Telling artifacts *[confirmed by reading the respective files]*:

- `setup.py` still declares `packages=["controlunit",
  "controlunit.components"]` — the `components` → `ui` rename (commit
  `c00e7fd`, 2024-09-25) was never carried into install metadata.
- `controlunit/__init__.py` does
  `sys.path.append(str(_echelle_base))`. This is what lets
  `from mainView import ...` work without a package prefix. The
  variable name `_echelle_base` is a literal artifact of having
  template-copied from `Echelle`.

> **Historical Evolution: the `_echelle_base` name.**
> *[corrected]* "Echelle remnant. I made Echelle BEFORE this, using
> PyQtGraph. I used that as a template. Wow, the remnant survived.
> Well, because it doesn't break things, and I have better things to
> do than go Qt diving."

- Triple inconsistent import styles for the same module exist
  side-by-side: `from controlunit.devices.adc import ADC` (in
  `main.py`), `from .device import DeviceThread` (in
  `devices/adc.py`), and `from devices.dummy import pigpio`
  (fallback when not on the Pi). All three work *only because* of the
  sys.path hack.
- `bin/plasmacontrol` would crash today — it does `from controlunit
  import *; widget = MainWidget(app)`, but `MainWidget` was renamed
  to `MainApp` in commit `9907825 restructuring main.py` (2024-10).

---

## Documentation Archaeology

There are four parallel documentation strata in this project. Only
two of them live inside the repo.

### 1. `docs/` — auto-generated pdoc3 HTML (FOSSIL, 2022-06-28)

Created in a single commit `4b7dcdc [REORGANIZE] make a package, add
pdoc3 docs` and never regenerated. It serves the GitHub Pages site
linked from the README at <https://queezz.github.io/ControlUnit/>.
The HTML references modules that have since been **deleted** —
`AIO.html`, `customTypes.html`, `electricCurrent.html`,
`ionizationGauge.html`, `pfeiffer.html`, `pigpioplug.html`,
`qmsSignal.html`, `smbusplug.html`, `tc.html`, `thermocouple.html`,
`timeKeeper.html`, `worker.html`. There is also a self-nested
duplicate `docs/components/components/...` from what appears to be a
buggy pdoc invocation *[speculative]*.

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
etc.). For the MkDocs migration, archive as `docs/archive/2022-pdoc/`
and add a rename map.

### 2. `controlunit/settings.yml` — deliberate in-code data dictionary

This is the only place inside the repo where the meaning of a signal
name like `Pu`, `Bd`, `Ip`, `MFC1` is bound to a channel number, gain,
description, and conversion function. It is also where datasheet URLs
are pinned:

```yaml
# controlunit/settings.yml (lines 44–50)
# 32 channel 16-Bit ADC based on ADS1115
# https://www.y2c.co.jp/i2c-r/aio-32-0ra-irc/
# https://www.ti.com/lit/ds/symlink/ads1113.pdf
# https://www.nxp.com/docs/en/data-sheet/PCA9554B_PCA9554C.pdf
# https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf
```

> **Developer Note (Arseniy) — this was intentional documentation.**
> "I did that to not remember the modules. So I DID DOCUMENT THERE
> INTENTIONALLY. After years of on-and-off dev."

This is the most important single piece of documentation in the
repository. Treat `settings.yml` as canonical and generate a
"Channel Map / Conversion Catalogue" page in MkDocs from it.

### 3. `controlunit/devices/conversions.py` — LaTeX-in-docstrings

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

> **Developer Note (Arseniy) — conversions are from datasheets.**
> "All conversions are based on docs. And they are fine. I might want
> to improve current stuff, but that's for later."

Render with `pymdownx.arithmatex` in MkDocs and you get a real
"Sensor Conversion Reference" section for free.

### 4. `aklab-howto` — the *external* documentation hub

The hardware-level documentation for this rig lives **outside the
repository**, in the developer's lab-wide how-to repo:
<https://github.com/queezz/aklab-howto>. The directly relevant pages
are:

- [Control Unit overview](
  https://queezz.github.io/aklab-howto/hardware/controlunit/control-unit/)
- [High-Precision AD/DA Board](
  https://queezz.github.io/aklab-howto/hardware/controlunit/high-precision-adda-board/)
- [Y-Corp ADC board](
  https://queezz.github.io/aklab-howto/hardware/controlunit/y-corp-adc-board/)
- [FT232H USB GPIO — the moved-to-Windows-NI replacement](
  https://queezz.github.io/aklab-howto/hardware/controlunit/ft232h-usb-gpio/)

> **Developer Note (Arseniy).**
> "I have some of my module descriptions in `aklab-howto`. That's the
> hub repo."

When MkDocs is set up here, **link to `aklab-howto`, do not duplicate
it**. The hardware story belongs at lab level; this repo's docs
should be about the software that *uses* that hardware.

### 5. `manuals/ads1113.pdf` — one orphan datasheet

A single PDF sits alone. The remaining datasheets (PKR251, MKS 627/8,
Celduc SO842074, MAX6675, etc.) live in `aklab-howto` or are linked
from the README. Either centralise into `docs/datasheets/` or remove
this folder entirely.

### 6. `examples/` notebooks — abandoned

- `imports.ipynb`: a fossil from when this package was pip-installed
  (`'c:\\…\\miniconda3\\lib\\site-packages\\controlunit'`). Useless
  today.
- `channels.ipynb`, `pandasrecap.ipynb`, `settings.ipynb`: scratch
  notebooks for working out the ADC channel multiplexing and the move
  from numpy arrays to pandas DataFrames in 2023.
- `settings_template.yml`: a snapshot of `controlunit/settings.yml`
  at v1.0 — useful only to see the diff (no MFCs, no cathode current,
  channels still numbered 0–4 instead of 20-something).

### What carries durable design intent

1. The `# ===` banner blocks in `settings.yml` — the developer's
   memory aid, written deliberately as in-code documentation.
2. The named-conversion dispatch in `adc_channels.py` and
   `conversions.py`.
3. README's BOM and control-box photos.
4. The pdoc HTML for `docs/main.html`, `docs/worker.html`,
   `docs/customTypes.html` should be kept as **historical context** —
   they document the 2022 ThreadType-enum architecture.
5. The `aklab-howto` external hub for hardware.

### What is safe to drop

- `docs/components/components/*` — duplicate pdoc output.
- `examples/imports.ipynb` — exposes a developer's local paths.
- The `[DOCS](https://queezz.github.io/ControlUnit/)` link in README
  until MkDocs is deployed — it currently points to a stale doc site.

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
│      └── MAX6675  (devices/max6675.py)  ── currently dormant     │
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
                  Raspberry Pi 4 (8 GB) + custom PCB
                  — originally Raspberry Pi 3B
```

> **Historical Evolution: hardware upgrade.** *[corrected]*
> The original platform was a Raspberry Pi 3B (as still mentioned in
> the README). It has since been replaced with a Raspberry Pi 4
> 8 GB. None of the code references the model; the upgrade was
> binary-compatible and motivated by RAM headroom for pandas buffers
> and pyqtgraph rendering.

### Threading evolution (the deepest stratum)

This is the most interesting story in the repo. The first-pass
archaeology got the *shape* of the evolution right but mis-attributed
some of the authorship. The corrected story:

**Phase 0 (pre-history). The `Echelle` template.**

> **Historical Evolution: pre-`ControlUnit`.** *[corrected]*
> The original `Worker(QtCore.QObject)` class shape, the
> `ThreadType` enum dispatch, the `STEP`-batched numpy buffers, the
> `app.processEvents()` from inside the worker, and the
> `sys.path.append` package hack were all *ported from Arseniy's
> earlier project*, `Echelle` — a PyQtGraph spectrograph-control
> application. Ito-kun (Tatsuemon) inherited that template; he did
> not invent the Qt-threading shape, he extended it.

**Phase 1 (Feb 2020), pre-package, monolithic `worker.py`.**
The initial commit (`710c78f`) uses one `Worker(QtCore.QObject)`
class for all devices, dispatched by a `ThreadType` enum. Methods are
named `__plotPresCur` and `__plotT`. Buffers are fixed-shape numpy
arrays of `STEP` rows. The worker calls `self.__app.processEvents()`
from a non-main thread — anti-pattern, inherited from `Echelle`.

**Phase 1, the Ito-kun extension.** *[corrected]*
Ito-kun was a B4 student who "liked C" *[developer wording]*. He
built the device-reading logic on top of Arseniy's Echelle-port
template. Two specific decisions of his became technical debt:

1. He opened a fresh I²C connection to the ADC **on every channel
   read**. On a multi-channel scan loop this hurt acquisition
   throughput badly.
2. He extended the `ThreadType` enum to dispatch behaviour for each
   physical device — so the code path for "read ADC" lived inside a
   case of "what kind of thread am I?" rather than as its own object.
   This made it impossible to see what concrete device any given line
   of code actually talks to.

Ito-kun left the lab for an AI-development master's course shortly
after his B4. The code stayed behind.

**Phase 1.5 (Mar 2020), "Untangling Ito-kun's threading mess"
(`ed7cadb`).** Single commit, +161 / −107 in `worker.py`. The commit
is authored as `queezz` but the *help* came from another lab member
*[corrected]*. The fix: rename `ThreadType` → `Signals`, factor
`read_settings()` out of every constructor, rename methods to
`readADC` / `readT`, give the worker a per-instance `self.sampling`.
The threading topology did not yet change.

**Phase 2 (Jun 2022), `[REORGANIZE] make a package, add pdoc3 docs`
(`4b7dcdc`).** Files moved into a `controlunit/` directory. No
structural change. pdoc generated HTML for the then-current shape.

**Phase 3 (May 2023), ADC-thread tuning (`worker: tuning ADC thread`
× 8 commits).** The acquisition loop was rewritten to read from
`AdcChannelProps` populated from `settings.yml` rather than from
hard-coded `CHP1/CHP2/CHIP` constants; numpy arrays were replaced
with pandas DataFrames; and the `STEP` batching idea (loop N times,
then emit one signal carrying N rows) was kept and clarified.

The `STEP` mechanism serves **two purposes simultaneously**
*[confirmed by developer]*: it averages noisy ADC samples *and* it
amortises Qt signal-emission overhead between the worker thread and
the GUI thread. The fact that one parameter does both jobs is why it
has never needed to change:

```python
# controlunit/devices/adc.py (lines 374–379)
if step % (self.STEP - 1) == 0 and step != 0:
    # self.calculate_averaged_signals()
    self.send_processed_data_to_main_thread()
    step = 0
else:
    step += 1
```

**Phase 4 (Aug 2024), `restructure: worker super class and subclasses
are separated` (`5326e50`).** Big-bang split: 662 lines deleted from
the monolithic `controlunit/worker.py`, replaced with
`sensors/{worker.py, worker_adc.py, worker_dac8532.py,
worker_max6675.py, worker_mcp4725.py}`. This commit's author field is
`pi <hasuo_kuzmin.lab@outlook.jp>` — i.e., committed directly from
the lab Raspberry Pi, under Miura-kun's lab account *[corrected]*.

> **Developer Note (Arseniy) on Phase 4.**
> "When Miura-kun was here I thought about transitioning to pandas
> for sanity. But I was confused by the Qt thread mess. So it took
> me a while to finish this. Exactly the kind of LLM job. But I
> think I've learned a lot. Got exposure to classes and signals.
> Bad, but real. After this I started actually using classes. I
> finally got what they are: basically a box, a drawer. So you don't
> spill and lose your functions."

That last sentence is — verbatim — the moment when this codebase
stopped being a Pythonic script and started being a Python program.

**Phase 4.5 (Sep 2024), serial renames.**

- `4050c28 Renaming, fix FutureError in pandas.concat`: `worker_*.py`
  → `adc.py` / `dac8532.py` / etc.
- `a2f50d0 Renaming sensors to devices`: directory rename.
- `c00e7fd Rename components to ui`: directory rename.
- `b1e6fe5 rename remaining "sensor_name"s to "device_descriptor"`:
  terminology.
- `1c426d9 Restructure thread start` + `86544db streamlined threads
  and workers start` + `9907825 restructuring main.py`.

> **Developer Note (Arseniy).**
> "Ah, yes — I finally got up to it, improving sanity again."

A 10-day burst of renaming. Behaviour was untouched; vocabulary
became consistent.

**Phase 5 (Aug 2025), Codex-bot fixes (PRs #20 and #21).**

- `1cf4611 Handle sensor data in device threads`: moved
  `update_processed_signals_dataframe` *out of* `main.py` into the
  workers (`adc.py`, `max6675.py`).
- `9f5b04c Fix CoreLogic signal declaration`: cleaned the
  (still-unused) `core_logic.py` stub and added
  `tests/test_core_logic_signal.py`.

> **Developer Note (Arseniy) on LLM workflow evolution.**
> "Codex PRs — my first test of LLM-assisted design. Was purely
> software, not tested. After that I went full Cursor on that, and
> direct tests on RasPi. Just this year, 2026. The Codex PR workflow
> was bad."

This is meaningful: Phase 5's commits were **never tested on the
hardware** at the time they were merged. They look correct, they
*are* correct enough to not have broken anything, but the developer
explicitly considers them an experiment in workflow rather than
trusted code. Phase 6 has been different — Cursor-assisted with
direct on-rig testing.

**Phase 6 (Apr 2026), isolation hardware push.** `0b417cf add debug
for mcp4725, isolated DAC for plasma current` + `dfbc65c upd for
isolated DAC control of the plasma current`. The current branch
(`thread-fix-v2`) has these on top of `dev`. Kawabata-kun's plasma
PID work landed alongside this *[corrected]*. The isolation was
critical for plasma-current stability.

> **Developer Note (Arseniy) on Phase 6.**
> "Kawabata-kun did the final plasma current PID loop. I made and
> tested one before isolation. Isolation was critical, of course."

### GUI architecture (mainView + docks)

The GUI is a `QMainWindow` containing a `QTabWidget` with two tabs:

1. **Data tab** — a pyqtgraph `DockArea` with `ControlDock`,
   `Plots` (a `Graph(GraphicsLayoutWidget)` with stacked plasma and
   pressure plots; the temperature plot is commented out everywhere),
   `GasFlowDock` (two MFCs with per-decade spinboxes — a
   "scientific-notation-by-spinbox" UI), `CalibrationDock`,
   `PlasmaCurrentDock`, `PlotScaleDock`.
2. **Settings tab** — `SettingsDock`, `ADCGain` dock, `LogDock`.

> **First-pass inference (preserved as ambiguity-witness).**
> The first pass read the hand-painted toggle switches
> (`MySwitch`, `OnOffSwitch`, `QmsSwitch`, ...) and the enlarged
> `hitButton` rectangles as evidence of a *touchscreen-first* design
> philosophy.
>
> **Developer Note (Arseniy) — partly right, currently wrong.**
> "Yes, touchscreen — but I disabled the touch. It's terrible, not
> well calibrated. I keep the display, it's always nice to have a
> display. Now it's only for show. I usually use VNC. Or a Bluetooth
> mouse sometimes. I have a USB port exposed on the box."
>
> So the toggles *were* designed for touch; the rig pragmatically
> downgraded the input modality without removing the UI design. The
> code is a fossil of a workflow that was abandoned.

The `UIWindow` class is mixed in via multiple inheritance
(`class MainApp(QtCore.QObject, UIWindow):`). Unusual for Qt code,
but a legitimate way to keep the layout code physically separated
from the controller code without giving up direct attribute access
(`self.control_dock`, `self.graph`, etc.). This idiom is also
inherited from `Echelle`.

### Signal / data flow

Per acquisition cycle (taking ADC, the busiest one):

1. `ADC.acquisition_loop()` runs in its own `QThread`.
2. `time.sleep(self.sampling_time)` (default 0.1 s).
3. `collect_data()` reads N channels via
   `aio.analog_read_volt(channel, datarate, gain)`. The PCA9554 mux
   is reconfigured only if the channel range demands it.
4. Raw row appended to `adc_values` DataFrame, converted row appended
   to `converted_values`.
5. If a plasma-current setpoint is non-zero:
   `plasma_current_control()` runs a `simple_pid.PID(0.3, 0.1, 0)`
   against `Ip` and emits `send_control_voltage` to `MCP4725` (via a
   queued signal handled in `main.py: _set_cathode_current`).
6. Every `STEP` ticks: `send_processed_data_to_main_thread()` emits
   `data_ready.emit([dataframe, device_name])`. `MainApp.on_worker_step`
   routes to `_adc_step`, appends to `self.datadict["ADC"]`, calls
   `save_data` (CSV append), and triggers a plot update.

Worker→worker signalling:

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
signal. `DirectConnection` runs the slot in the emitter's thread —
correct here because `update_mfcs` only touches `self._mfc_presets`.

### DAQ and logging

Two parallel logging paths, both append-only:

1. **CSV data file** in `~/work/cudata/cu_<YYYYMMDD_HHMMSS>.csv` with
   a self-describing comment header:

   ```python
   # controlunit/main.py (lines 396–409)
   def generate_header_adc(self):
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

   The header survives `pandas.read_csv(..., comment='#')` and embeds
   enough channel metadata that an old CSV can be replayed without
   `settings.yml`.

2. **Event log file** — `~/work/cudata/controlunit.log`, append-only.

### PID / control logic

Two PID implementations live in the code; only one currently runs.

#### Plasma current (Ip) PID — *implemented and live*

Uses [`simple_pid`](https://pypi.org/project/simple-pid/) with
`p=0.3, i=0.1, d=0` and `output_limits=(0, 4500)` (mV). Setpoint from
the GUI, feedback from the Hall-effect sensor on channel 0, actuator
is the MCP4725 DAC.

> **Developer Note (Arseniy) on the baseline of 1000 mV.**
> *[corrected — Kawabata-kun's contribution]*
> "This looks like the minimum amps for plasma to maybe start. Again,
> probably Kawabata."
>
> The `baseline` parameter is therefore an *empirical* offset chosen
> against the external cathode supply's transfer function — not a
> derived value.

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

#### Membrane heater PID — *dormant*

Hand-rolled in `MAX6675.temperature_control()`, integral-clamp by
`if integral < -0.5: integral = 0`, asymmetric (only positive `e`
drives output). Gains `Kp=3.5, Ki=0.06, Kd=0`. The output is
*on-time fraction of a 10 ms cycle*, software-PWMed by
`HeaterContol.work()` against an SSR.

```python
# controlunit/devices/max6675.py (lines 178–181)
"""
Shouldn't the self.sampling_time here be 0.25, not the one for ADC?
TODO: update to simple-pid as in TemperatureControl
https://github.com/queezz/TemperatureControl
"""
```

> **Developer Note (Arseniy) on the heater path.**
> "The heater is moved out currently. But I keep the capability.
> I won't have time to come back to it. And even if I would, I would
> make a dedicated ESP32 unit which would report to an orchestrator.
> I've evolved my understanding of a lab instrument. Into a network.
> I've made a single TC logger but haven't had a chance to move to
> proper network instruments yet."

This is the most important *philosophical* movement in the project:
from a monolithic instrument that does everything in one box to a
**network of small instruments that report to an orchestrator**.

### Isolation / safety design decisions

The isolation strategy *as it actually exists*:

1. **GPIO isolation via SSR.** The heating circuit was mains 100 V ×
   300 W controlled through a Celduc SO842074 zero-cross SSR. The Pi
   never touched mains. *[confirmed]*
2. **I²C isolation for the plasma DAC.** The MCP4725 sits behind a
   galvanic I²C isolator on a separate bus. April 2026 work
   (`dfbc65c`, `0b417cf`). Critical because plasma transients on the
   cathode bus were affecting the rest of the I²C tree. *[confirmed
   by developer]*
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

   `abort_all_threads` → `turn_off_voltages` first, then thread
   termination. The plasma setpoint goes to zero before threads die.

4. **The QMS-sync LED is *only* a sync signal.** *[corrected]*

> **First-pass inference (preserved as ambiguity-witness).**
> The first pass speculated that the LED + GPIO output was a clever
> "galvanic isolation by photons" — the QMS receiving the sync via an
> opto-isolated input watching the LED.
>
> **Developer Note (Arseniy) — just wrong.**
> "I send a sync signal for different loggers, that's it."
>
> So GPIO 26 emits a digital sync edge consumed by various external
> data loggers. The LED is a *visual indicator* on the front panel,
> not an isolation strategy. The shared GPIO was always a wiring
> convenience.

5. **Software-emulated hardware (`devices/dummy.py`).** Stubs out
   `pigpio.pi`, `RPi.GPIO`, `spidev.SpiDev`, and `smbus.SMBus` to
   no-op classes so the GUI boots on Windows.

---

## Development Timeline

Reframed as **development campaigns during experimental downtime**,
not measurement-campaign signatures.

```text
2019 (pre-history) Echelle PyQtGraph application written.
                   Becomes the template for ControlUnit.

2020-02 ── Initial commit (queezz). Echelle-ported Worker + ThreadType.
2020-03 ── "Untangling Ito-kuns therading mess". Renames, structural
            clean-up while learning Qt. Black/pre-commit added.
2020-06 ── First numpy → pandas attempt (incomplete; will sit for years).
2020–22 ── Long quiet period. Rig is running, dev is teaching.
2022-06 ── [REORGANIZE] package layout + pdoc3 docs generated.
2023-04 ── Multiple contributors arrive (Kurokawa-kun/`Kshora`, leprecon-pi/Miura-kun).
            Measurement-campaign labels in commits ("hasizuka", "B2",
            "B1") reflect channels being renamed live during runs.
2023-05 ── ADC channel meta moved into AdcChannelProps + settings.yml.
            8 commits "worker: tuning ADC thread" — the buffer redesign.
            *Development push during downtime.*
2023-06 ── Logging-to-file, sampling-time-from-GUI, gain switching.
            customTypes.py, ionizationGauge.py, pfeiffer.py DELETED
            (absorbed into conversions.py).
2024-08 ── Worker super class split (commit by Miura-kun from the Pi).
            Pandas migration finally lands.
2024-09 ── MFC integration (DAC8532), MCP4725 addition.
            Mass rename: sensors/→devices/, components/→ui/.
            *Development push.*
2024-09–10 First plasma-current PID by Arseniy. "Ip PID response
            detected (hardware)" — the rig actually closes loop.
2025-08 ── Two Codex automated PRs: data-handling moved INTO workers,
            CoreLogic signal fix. *Untested on hardware at merge time.*
2026-04 ── Isolated DAC for plasma current (Kawabata-kun's final PID
            integration). Settings layout cleanup, Ip-PID OFF button.
            *Cursor-assisted with direct on-rig testing.*
2026-05 ── Latest: "settings: debug false". Lab still active.

Hardware: Raspberry Pi 3B → Pi 4 (8 GB), transparent to software.
```

Two dev-campaign signatures are clear in commit density: the
2023-05 ADC-tuning burst and the 2024-09 / 2024-10 PID burst.

> **Developer Note (Arseniy).**
> "Two clear measurement-campaign signatures — no, probably two clear
> *dev* campaigns. 'One developer fixing real hardware'. Haha. Me.
> Arseniy. One developer. But true enough."

---

## Experimental Context

The first pass guessed at the physics from the signal list. The
developer has now told us directly. This section is now mostly
confirmed, with the original inference preserved as historical
context.

### What the rig was originally for *[corrected]*

A dedicated **hydrogen-permeation experiment**: the effect of oxygen
on hydrogen transport through metals under plasma irradiation. A
heated thin metal membrane separated upstream (plasma + gas mixture)
from downstream (vacuum + permeation flux). Pressure pairs (Pfeiffer
+ Baratron, upstream and downstream) read the transport. The QMS
analysed downstream species and was time-aligned via the GPIO sync.

### What the rig is today *[corrected]*

A **multi-purpose plasma laboratory** with three chambers:

- A plasma-irradiation chamber.
- A thin-film plasma-deposition chamber.
- A pulsed-laser-deposition (PLD) chamber with laser diagnostics.

The ControlUnit *box itself* is used as:

- a logger for plasma parameters and vacuum across the lab;
- a basic gas-control panel (MFCs);
- a basic plasma-current controller.

The membrane temperature path is gone (moved to NI on Windows). The
permeation experiment is no longer the primary application. The
name `ControlUnit` is still apt because the box still controls and
logs the basic gas / plasma stack.

> **Developer Note (Arseniy).**
> "I measure plasma parameters and vacuum. I control gas (MFCs) and
> now plasma current. I WAS controlling the membrane temp. It was
> only a permeation experiment. Investigation of the oxygen effect
> on hydrogen transport through metals under plasma irradiation. Now
> it's a multi-purpose device with 3 chambers: plasma irradiation,
> thin-film plasma deposition, laser diagnostics, and a PLD chamber.
> But I use this block as a logger and basic gas/plasma control. So
> 'Control Unit' is still a valid name."

### Signal channel map

Channel-by-channel confirmation from `settings.yml`:

- `Ip` — plasma current via Hall sensor (`hall_current_sensor`,
  `5 * (v - 2.52) A`).
- `Pu` / `Pd` — upstream / downstream pressure (Pfeiffer single gauge
  and ionization gauge). The Pfeiffer gauge currently cannot ignite
  its cold-cathode discharge, so it is operating mostly in Pirani mode
  *[developer addendum]*.
- `Bu` / `Bd` — upstream / downstream Baratrons (MKS 627 FS = 1 Torr,
  MKS 628B FS = 0.1 Torr).
- `MFC1` / `MFC2` — H₂ (20 SCCM) and O₂ (10 SCCM).
- `Ci` / `Cv` — cathode current and cathode voltage **channels exist
  in code and on the PCB, but the cathode current has never actually
  been measured.** *[corrected]* The conversion functions exist for
  consistency; the measurement was prepped but not deployed.
- `T` — membrane temperature (now read off-Pi).
- `QMS_signal` — boolean column logging whether the sync trigger is
  currently active.

### Why the original "hydrogen-permeation" inference was correct

The first-pass interpretation was directly correct for the rig's
original purpose. The signal list invited that reading because the
rig *was* literally that.

> **First-pass inference (preserved).**
> The first pass concluded: "two MFCs (H₂ and O₂) + heated membrane +
> upstream/downstream pressure pairs + QMS + cathode-driven plasma
> = plasma-driven hydrogen permeation experiment". This was correct
> as historical interpretation. The codebase has outlived its
> original purpose without changing its signal vocabulary — the
> archaeology was reading the rig's *origin*, not its *current*
> deployment.

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

   Adding a new instance of an existing sensor type means editing
   YAML, not code. Adding a new *type* means writing one function in
   `conversions.py` and adding one entry to the dispatch dict.

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

   The repo carries the canonical `settings.yml`; the rig has
   `~/.controlunit/settings.yml` with its own channel map; the
   version-key check prevents silent drift after a schema bump.

3. **STEP-batched signalling — averaging *and* IPC amortisation.**

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

   > **Developer Note (Arseniy).**
   > "Both — averaging and amortisation. That worked, never touched
   > this."

4. **Per-row preset logging.** Every ADC row carries the commanded
   `PresetV_mfc1`, `PresetV_mfc2`, `PresetV_cathode`, `IGmode`,
   `IGscale`, and `QMS_signal`. The CSV is fully self-describing.

5. **CSV header that embeds channel map.** Outlives the code that
   wrote it.

6. **Dual-purpose dummy modules.** `devices/dummy.py` lets the GUI
   boot on Windows. Crude on purpose.

7. **Hand-painted touch toggles.** Designed for a 7" touchscreen
   that is no longer touched — but kept because the GUI still has
   to be readable at 7" over VNC, and the toggles read clearly at
   that size.

8. **Settings.yml as deliberate documentation.** The developer wrote
   the long header-comments as a memory aid for future-self after
   long gaps in work. The file is therefore both schema and prose
   documentation.

9. **Hardware-emergency-stop semantics.** `turn_off_voltages()` runs
   before thread termination.

   > **Developer Note (Arseniy).**
   > "Reading `_mfc_presets` to zero in three different places,
   > having `turn_off_voltages()` callable any time including when
   > `self.workers` is empty — yes, guilty. It may still be somewhere
   > in the Qt signals. But probably the last LLM edits fixed this.
   > At least during my short tests I've seen no issues."

10. **LaTeX in conversion docstrings.** Physics inline with the code
    that uses it.

---

## Technical Debt and Scaling Limits

### A. Three half-completed renames

1. `setup.py` still installs `controlunit.components`.
2. `bin/plasmacontrol` imports `MainWidget` (now `MainApp`).
3. `controlunit/__init__.py` references `tree/pack` (a deleted
   branch) and the variable `_echelle_base` (from `Echelle`).

### B. The sys.path hack

```python
# controlunit/__init__.py (lines 9–11)
# temporarily add this module's directory to PATH
_echelle_base = pathlib.Path(__file__).parent.absolute()
sys.path.append(str(_echelle_base))
```

Inherited from `Echelle`. Makes `from mainView import UIWindow` work
alongside `from controlunit.devices.adc import ADC`. Robust in
practice; breaks editable installs, type-checkers, and pytest
collection from a different cwd.

### C. Module-import-time `select_settings()` calls

```python
# controlunit/heatercontrol.py (lines 5–13)
from readsettings import select_settings

config = select_settings(verbose=False)
CHHEATER = config["Heater GPIO"]
```

`heatercontrol.py`, `trigger_signal.py`, `ui/docks/control.py`,
`ui/docks/gas_flow.py` all read `settings.yml` at import time.
Configuration leaks into module-level state.

### D. Aspirational ghost classes

`core_logic.py` and `plot_data_handler.py` are *planned* extractions
that have never been instantiated. The Codex-PR added a test for
`CoreLogic`. The developer is honest about these being intentions,
not abstractions. The first pass said: "either finish them or move
them aside." The developer is comfortable with their current limbo
state; it serves as documentation of next-refactor intent.

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

O(n) per cycle. Fine at 10 Hz, painful at 100 Hz.

### F. CSV file handles opened-and-closed per write

```python
# controlunit/main.py (lines 466–467)
data = self.newdata[device_name]
data.to_csv(savepath, mode="a", header=False, index=False)
```

Fine in practice; bad if anyone ever wants 100 Hz.

### G. Tests are essentially absent

- `tests/test_sample.py` literally tests `inc(3) == 4`.
- `tests/test_core_logic_signal.py` covers a class that nothing else
  uses.
- CI runs `flake8 syntax + pytest` against the dummy file only.

> **Developer Note (Arseniy) on calibration tests.**
> *[corrected]*
> The first pass said: "the example calibration tests against the
> PKR251 datasheet are circular because the datasheet isn't in
> `manuals/`."
>
> "Tested, haha. It *is* from a manual. Just not in the code. And
> it's fine. Anyway, my old gauge can't ignite cold-cathode discharge.
> So that one is mostly Pirani now."
>
> So the conversion polynomials are not circular; they were
> hand-fitted against real datasheets that simply live outside this
> repo (in `aklab-howto`).

### H. CI is from the Python 3.8 era

`.github/workflows/pythonapp.yml` pins Python 3.8 (2019).
`requirements.txt` says `numpy>=1.17.4`. The repo dodges a pandas
FutureWarning with `astype(dtypes)` — from a much newer pandas. CI
doesn't see the drift because it doesn't exercise the GUI path.

### I. The `kurokawa-dev/` quarantine (Kurokawa)

A 50-line SCPI driver for a Kikusui PWR-401L bench supply
*[confirmed]*, tab-indented, in its own top-level folder. Kurokawa's
work — earlier than Kawabata's `kawdev` / plasma-current PID pass.
Never imported. A parking spot for an integration that may or may not
happen.

### J. Inconsistent error-handling

`DAC8532.init()` has a bare `except: GPIO.cleanup()`. Silent
recovery, no log. If the DAC fails to initialise, the worker is
still spawned and signals are still connected.

### K. The `_init_cocnnections` typo

A long-lived typo. Proof that no automated symbol-rename has touched
this code.

---

## Modernization Suggestions

These remain *opinion*. The developer has indicated that the LLM
workflow has shifted (Codex-PR experience was "bad"; Cursor-assisted
on-rig testing is now standard) and that the philosophical direction
is **toward a network of small instruments**. Read the suggestions
through that lens.

### Tier 0 — zero-risk cleanup (an afternoon)

1. **Bring `setup.py` and `bin/plasmacontrol` in sync.**

   ```python
   packages=["controlunit", "controlunit.devices",
             "controlunit.ui", "controlunit.ui.docks",
             "controlunit.ui.widgets", "controlunit.ui.buttons"],
   entry_points={"console_scripts":
                 ["plasmacontrol=controlunit.main:main"]},
   ```

   And in `bin/plasmacontrol`:
   `from controlunit.main import main; main()`.

2. **Pin a modern Python in CI.** Bump from 3.8 to 3.11. Drop the
   CodeShip badge (CodeShip shut down May 2024).

3. **Rename `_echelle_base`** to `_PACKAGE_DIR`. Or — and this is
   more honest — keep the name and add a single-line comment saying
   it's a fossil from the `Echelle` predecessor project. The name
   itself becomes a tiny piece of in-code documentation.

4. **Decide on `core_logic.py` and `plot_data_handler.py`.** Leave
   them; document them as planned extractions in this file (now done).

5. **Adopt git tags.** Tag the current tip as `v0.4.0` to match
   `_version.py`. Tag future commits when they touch hardware
   integration or change the on-disk CSV schema.

> **Developer Note (Arseniy) on versioning.**
> "Yes, I have no idea how to iterate versions. So it's just there.
> I would benefit from better versions now, and from some tags in
> git."

### Tier 1 — MkDocs migration

Use `mkdocs-material` + `mkdocstrings[python]`. Proposed layout:

```text
docs/                            (MkDocs source)
├── index.md                     (project intro + README photos)
├── Archaeology.md               (this document)
├── status-inventory.md          (extracted/expanded from this file)
├── hardware/
│   └── overview.md              (link out to aklab-howto, do NOT duplicate)
├── operation/
│   ├── starting-acquisition.md
│   ├── plasma-current-pid.md
│   ├── sync-signal.md
│   └── safety.md
├── architecture/
│   ├── threading-evolution.md   (the 6-phase narrative from this file)
│   ├── signal-flow.md
│   ├── echelle-lineage.md       (the pre-history)
│   └── settings-versioning.md
├── reference/
│   ├── channel-map.md           (hand-curated from settings.yml)
│   └── conversions.md           (auto-rendered from conversions.py)
├── api/                         (mkdocstrings auto-generated)
├── archive/
│   └── 2022-pdoc/               (the entire current docs/*.html)
│       └── README.md            (rename map: AIO → adc_setter,
│                                 customTypes → conversions+adc_channels,
│                                 worker → devices/*)
└── changelog.md
```

Notes:

- **Do not duplicate hardware docs.** Hardware lives in `aklab-howto`.
  This repo's docs are about the software that uses that hardware.
- **Archive, do not delete**, the 2022 pdoc HTML.
- Disable the stale `[DOCS]` link in README until MkDocs is up.

### Tier 2 — finish the extractions stubbed by `core_logic.py` and `plot_data_handler.py`

Optional. The current `main.py` works. The extractions would benefit
the next major refactor — not the day-to-day.

### Tier 3 — DataStore performance ceiling

Only do these when 100 Hz becomes a real requirement:

1. Replace per-cycle `pd.concat` with a `deque` of small DataFrames
   concatenated lazily on plot request.
2. Open the CSV file once at `create_file`, hold the handle.

### Tier 4 — Testing the parts that matter

`conversions.py` is pure-function and physics-critical. Calibration
constants come from external datasheets *[confirmed]*. Add a
`tests/test_conversions.py` whose *fixtures cite the datasheet source*
(URL or page reference) rather than re-deriving from the conversion
formula itself.

### Tier 5 — Hardware abstraction unification

Promote the `_setter.py` pattern into a real interface. A `Chip` ABC
with `init()`, `read()`, `write()`, `cleanup()` would let
`devices/dummy.py` become a real configurable simulator. Unlocks
headless integration tests.

> **Developer Note (Arseniy) on tool choice.**
> "Still learning. Use whatever makes me happy. The Codex PR
> workflow was bad."

---

## Engineering Mindset Reconstruction

> This section is the most subjective. It is also the section where
> the developer's first-hand voice changes the most. *[partially
> corrected and partially confirmed]*

Reading the commit messages, file names, and the *shape* of changes
over six years, plus the developer's own reflections, the working
mindset has these features:

### Code as instrumentation, not product

Commit messages like `[fix] currentvalues B1,P1,B2,P2 -> Bu,Bd,
Pu,Pd`, `[fix] more B1s to Bds. Need to automate this.`, `B2`, `B1
value :.1e`, `B1 value :.3f` are signs of someone iterating *with the
experiment running* — channel names evolve as the upstream /
downstream meaning gets clearer.

### Idempotent stop semantics ("I clicked stop, did it actually stop?")

Reading `_mfc_presets` to zero in three different places, having
`turn_off_voltages()` callable any time including when `self.workers`
is empty, `if not self.workers: return` guards everywhere — this is
someone who has been bitten.

> **Developer Note (Arseniy).**
> "Haha — yes, guilty. It may still be somewhere in the Qt signals.
> But probably the last LLM edits fixed this."

### Explicit-but-ugly, *trending toward more Pythonic*

The first pass said: "prefers explicit-but-ugly over
clever-but-fragile" — `set_sampling_time` is a chain of three `if`
statements; `_mfc_presets = {1: 0, 2: 0}` is a two-key dict instead
of a list; spinboxes-per-decade for MFC voltages. The developer's
own qualification:

> **Developer Note (Arseniy).**
> "Yes and no. I wrote what I could. I prefer understanding, and yes,
> transparency. But I always disliked a lot and tried to get more
> Pythonic. Now LLMs can fix and guide me. I only welcome that.
> Still, like with Ito-kun, I don't want too much of what I don't
> really understand. Some of that is still required, but I'd like to
> minimise the fog."

This is the operative principle: **understanding > cleverness, but
not at the cost of being ugly forever**. LLMs are tools for raising
the floor of style without raising the fog.

### Rename without breaking semantics

The 2024-09 storm of renames moved hundreds of references; meaning
didn't change. That discipline is rare.

### Learning by building (and now: teaching by enforcing)

The first pass said: "Tolerates collaborators with different styles."
The developer added:

> **Developer Note (Arseniy).**
> "Yes — but now I educate. And enforce my style, or close enough."

So: Phase 1 was *tolerance for variety while learning*; today is
*style enforcement while teaching*. That is a real evolution and it
explains why Phase 4.5 (the renames) had to happen.

### Trust hardware feedback over theory

"Ip PID response detected (hardware)" was a commit message and a
celebration. PID gains `0.3, 0.1, 0` are not derived; they were
tuned. The membrane PID's one-sided clamping is what worked, not
what's textbook.

### From monolithic instrument to network of instruments

The membrane temperature path was migrated to NI on Windows.

> **Developer Note (Arseniy).**
> "Even if I would come back to it, I would make a dedicated ESP32
> unit which would report to an orchestrator. I've evolved my
> understanding of a lab instrument. Into a network. I've made a
> single TC logger, but didn't have a chance to move to proper
> network instruments yet."

`ControlUnit` was the developer's *electronics-learning project*. It
worked. The next iteration of the same philosophy will not be a
single Pi-with-everything box but a small constellation of
ESP32-class devices reporting upward.

### Tool use without dogma

Pre-commit + Black ran 2020–2022. CI was set up but never extended.
Codex was let near the code twice in 2025, deemed a bad workflow
afterwards. pdoc was run once. Cursor was adopted in 2026 with direct
on-rig testing. None of these became dogma — they were experiments
in workflow alongside experiments in physics.

> **Developer Note (Arseniy).**
> "Still learning. Use whatever makes me happy."

### The "Why this addresses?" mindset

```python
# controlunit/devices/adc.py (lines 96–101)
def prep_adc_board(self):
    """
    Initiates an instance of AIO_32_0RA_IRC from AIO.py
    Address: 0x49, 0x3E
    Why this addresses?
    """
```

> **Developer Note (Arseniy).**
> "Me again. Arseniy. I can't know it all. I need papers to publish,
> lectures to teach, kids to raise."

That single sentence is the whole repo's epistemic position. The
code is good *enough* to do the work; the work is the experiment,
not the code; the developer is one human with a finite working
budget and is honest about it. The "Why this addresses?" docstring
is not a bug — it is a hand-written tag saying "I will return to
this question if I ever need to; meanwhile, the experiment runs."

---

## Known uncertainties and possible incorrect assumptions

This section is now much shorter. Most of the first-pass uncertainties
have been resolved by the developer's pass. The remaining open
items below are flagged because they still depend on interpretation
or external knowledge.

### Still open (or partially open)

- **The exact authorship line on `ed7cadb` "Untangling Ito-kuns
  threading mess".** The commit is signed `queezz`. The developer
  has indicated that "another lab staff helped to untangle". Whether
  that means a third person co-authored, that Arseniy committed work
  done by someone else, or that the help was advisory only, is not
  recorded.

- **The exact physical isolator chip used for the MCP4725 in Phase
  6.** The commit message says "isolated DAC" and the developer
  confirms the isolation is real and critical. The chip identity
  itself is not in the repo; it lives in the hardware build of the
  rig. (Likely documented in `aklab-howto`; should be linked once
  the MkDocs migration runs.)

- **The current state of `core_logic.py` and `plot_data_handler.py`.**
  The developer is comfortable leaving them as planned-extraction
  documentation. Whether they will ever be filled in is genuinely
  unresolved.

- **Whether the membrane-temperature path will ever return to the
  Pi.** The developer says "forever 🙂" but also describes an ESP32
  network successor. The honest answer is: not in this repo.

- **The exact behaviour of the Pfeiffer gauge in its current
  Pirani-only mode.** The conversion function in `conversions.py`
  assumes full PKR251 operation (cold-cathode + Pirani crossover).
  If the gauge can no longer ignite the cold-cathode discharge, the
  conversion is only correct over the Pirani range. This is a
  *known unknown* that the developer has signalled but has not yet
  encoded in `conversions.py`.

### Resolved by developer pass (preserved for context)

- The "hydrogen-permeation experiment" inference was historically
  correct; the rig has since become a multi-purpose plasma lab.
- The "QMS galvanic isolation by photons" inference was wrong; the
  shared LED+GPIO is just a sync signal for various loggers.
- The "touchscreen-first design" inference was historically correct
  but currently disabled; VNC and Bluetooth mouse are the primary
  input.
- The "Kikusui PWR-401L" identification was correct.
- The `_echelle_base` variable is a literal artifact of the
  predecessor `Echelle` project — not a name collision, not
  template-copy ambiguity.
- The "Ito-kun wrote the initial threading" attribution was wrong:
  Arseniy ported the Worker shape from `Echelle`; Ito-kun extended
  it (and introduced the I²C-per-channel-read bottleneck).
- The "Phase 4 commit by hasuo_kuzmin.lab" was Miura-kun committing
  from the lab Pi during a pandas-migration push.
- **Kurokawa** (git handle `Kshora`) and **Kawabata** are two separate
  contributors in sequence: Kurokawa submitted PRs #1, #18, #19 as
  `Kshora` (early MFC / MCP4725 work) and left `kurokawa-dev/PWR.py`;
  Kawabata came later with `kawdev` and the plasma-current PID /
  isolated-DAC work.
- The "Kawabata" name attached to the plasma-current PID and
  isolation work is correct.
- The "baseline = 1000 mV corresponds to ~16 A" value reflects an
  empirical minimum-ignition setpoint, likely Kawabata-kun's.
- The calibration tests proposed in Tier 4 are *not* circular: the
  polynomials come from datasheets that simply live outside this
  repo.

---

## A closing note in the developer's voice

The first-pass archaeology ended with:

> *"If you correct any of the uncertainties above, please date the
> correction and keep the original claim visible — the history of
> what was thought is itself part of this document's value."*

To which the developer's reply was, quite reasonably:

> **Developer Note (Arseniy).**
> "I'm generating this now. And I'm the dev, I can correct now,
> can't I 😁"

Yes. And the fact that the developer is doing so — actively,
voluntarily, with humour, and with substantive memory about
contributors going back six years — is exactly what makes this
codebase a **living laboratory instrument** rather than a software
artefact. The document above is therefore not a report on a dead
system. It is a snapshot of an instrument and of the person who
keeps it running.

The next archaeological pass will find things this one missed. That
is good. Until then, this is what we know.

*End of second-pass reconciled snapshot. Ecosystem context follows.*

---

## Related Projects and Ecosystem Evolution
> The first two passes treated `ControlUnit` as if it were an island.
> It is not. It sits in a small constellation of repositories that
> share the same author, the same lab, overlapping hardware, and a
> visibly evolving philosophy of *what a laboratory instrument
> should look like*. Reading those repositories alongside this one
> turns several "loose ends" of the archaeology into "edges that
> point outside the frame". This section adds that context without
> rewriting the previous archaeology — those edges were always there,
> we just did not name them.

### Why this section exists
A repeated pattern in the first two passes was: "this looks
half-finished" → developer correction: "yes, because the rest moved
elsewhere." The membrane temperature path, the hardware documentation,
the in-code datasheet links, the half-stubbed extraction classes, the
quarantined `kurokawa-dev/PWR.py` — each is a place where the local
archaeology hit a dead end that turned out to be a *gate* into a
neighbouring project.

Naming the gates:

- The `Echelle` references and the `_echelle_base` variable point
  *backward* to a predecessor.
- The MAX6675 heater path and its `TemperatureControl` link in a
  TODO comment point *sideways* to a migration target.
- The `aklab-howto` URLs the developer has mentioned point
  *outward* to an external documentation hub.
- The developer's stated "network of instruments" goal and his
  "single TC logger" remark point *forward* to `tclogger`.
- A second project running on the same Pi (`pihtivacuum`) points
  *adjacent* — a peer process on shared hardware.

The constellation is small but it is a real lineage. The rest of this
section reconstructs it.

### The constellation
#### 1. `echelle_spectra` — the predecessor (≈ 2018–2019)
Repository: <https://github.com/queezz/echelle_spectra>

A spectroscopic GUI and data-processing application developed during
the developer's work at NIFS on the LHD (Large Helical Device). It
predates `ControlUnit` and is the direct ancestor of several of this
project's most stubborn architectural fossils.

What `Echelle` gave `ControlUnit`:

- **pyqtgraph + DockArea layout.** The dual-pane plot,
  `GraphicsLayoutWidget`, the `Dock`-per-panel pattern, and the
  custom-painted toggle aesthetic all originate here.
- **Threading template.** A `QtCore.QObject` subclass parameterised
  by an `Enum`, driven by an `app.processEvents()`-from-the-worker
  loop, communicating with the main thread via `pyqtSignal`. The
  shape of `Worker` in the first-pass `controlunit/worker.py` was
  template-copied from this.
- **Package-init sys.path hack.** The `sys.path.append(__file__'s
  parent)` idiom that lets `from mainView import UIWindow` work
  alongside `from controlunit.devices.adc import ADC`. The variable
  name `_echelle_base` is, literally, the original variable name from
  `Echelle` — preserved unchanged across the copy.
- **General "Qt application as scientific instrument" feel.** Big
  fonts, large hit areas, single-tab + a `Settings` tab,
  HTML-formatted log dock, datetime-axis plots. The visual grammar.

> **Historical Evolution (Echelle → ControlUnit).** *[confirmed]*
> The `_echelle_base` variable, the `Worker` shape, the touch-sized
> toggle aesthetic, and the multiple-inheritance `UIWindow` mixin all
> descend from `echelle_spectra`. When Ito-kun took the template and
> extended it for the ADC, he extended *Echelle code in ControlUnit
> clothing*. The first-pass archaeology read those fossils as
> "Qt-newcomer choices" — they are, but the newcomer was the
> developer himself two projects ago, not the B4 student.

`Echelle` is also where the developer first hit Qt threading, first
used `pyqtgraph` seriously, and first built a real GUI for an
experiment. The "I finally understood what classes are: drawers" line
in the Phase 4 Developer Note is, in retrospect, a delayed payment on
patterns that were *imported* in `Echelle` and only *understood* in
`ControlUnit` Phase 4.

#### 2. `pihtivacuum` — the co-resident peer (concurrent with `ControlUnit`)
Repository: <https://github.com/queezz/pihtivacuum>

A companion project running on **the same Raspberry Pi as
ControlUnit**, dedicated to vacuum-system orchestration for the PIHTI
rig. Its presence is invisible inside `ControlUnit`'s git history but
materially shapes how `ControlUnit` actually runs on the lab Pi.

Implications for the archaeology of *this* repo:

- The Pi is *not* a `ControlUnit`-exclusive box. It is a small
  multi-process orchestrator on which `ControlUnit` is one of at
  least two long-running processes.
- Several decisions in `ControlUnit` that look defensive in isolation
  make sense when you remember another process is sharing the box:
  - The unique CSV filename per run
    (`cu_<YYYYMMDD_HHMMSS>.csv`) avoids collision with another
    writer.
    *[inferred]*
  - The `~/work/cudata/` data path is *configurable* via
    `~/.controlunit/settings.yml` precisely because another process
    might own a different path on the same disk. *[inferred]*
  - The `start_gpio.py: start_pigpiod()` routine kills any existing
    `pigpiod` and restarts it. That is aggressive for a
    single-tenant app — and exactly what you need on a multi-process
    Pi where another program might have left `pigpiod` in a bad
    state. *[inferred]*

> **Historical Evolution (peer process).** *[inferred from
> ecosystem; flagged for developer confirmation]*
> The `pihtivacuum` project shares the Pi with `ControlUnit`. They
> coexist by convention rather than by IPC: each owns its GPIO pins
> and its CSV namespace. There is no shared bus or message broker —
> the orchestration is human-managed and file-system-mediated. This
> is "network of instruments, no network protocol yet".

`pihtivacuum` is the first sign that the *box* (the physical Pi) had
already begun to function as a small operating environment hosting
*multiple* instrument processes — even before the developer
articulated the "network of instruments" philosophy. The intent
arrived after the practice.

#### 3. `TemperatureControl` — the migration target (≈ 2024 onward)
Repository: <https://github.com/queezz/TemperatureControl>

A Windows + National Instruments DAQ implementation of the
thermocouple-reading and heater-control logic that used to live in
`ControlUnit`'s `MAX6675 + HeaterControl` path. Referenced inline in
this repo as a TODO target:

```python
# controlunit/devices/max6675.py (lines 178–181)
"""
Shouldn't the self.sampling_time here be 0.25, not the one for ADC?
TODO: update to simple-pid as in TemperatureControl
https://github.com/queezz/TemperatureControl
"""
```

What `TemperatureControl` represents in the constellation:

- **A migration, not a refactor.** The heater PID was not
  re-implemented in place. It was lifted out of the Pi and rebuilt
  on a platform with stronger analogue front-ends (NI DAQ) and a
  different OS (Windows). The `ControlUnit` MAX6675 path was left in
  place as a dormant capability rather than deleted.
- **A first deliberate decoupling.** Before `TemperatureControl`, the
  Pi did everything. After, the Pi did plasma + gas + vacuum and a
  Windows machine did temperature. The boundary was drawn along a
  *physical-signal-class* line (the thermocouple), not along a
  software-architecture line.
- **A reference implementation of the "use `simple_pid` properly"
  move.** The TODO comment makes it explicit: when the Pi heater
  PID eventually returns (or is replaced by ESP32), it will look
  like `TemperatureControl`, not like the hand-rolled
  `MAX6675.temperature_control()` integral-clamped loop.

> **Historical Evolution (heater path).** *[confirmed by developer
> in §System Status Inventory]*
> Heater migration is described elsewhere in this document as
> "forever 🙂". `TemperatureControl` is the *destination* of that
> migration — the project that absorbed a capability `ControlUnit`
> used to own. Reading the `ControlUnit` repository alone gives you
> only the *departure*; the constellation gives you the arrival.

#### 4. `aklab-howto` — the external documentation hub
Repository: <https://github.com/queezz/aklab-howto>
Live site: <https://queezz.github.io/aklab-howto/>

A lab-wide knowledge base. The pages directly relevant to
`ControlUnit`:

- [Control Unit overview](
  https://queezz.github.io/aklab-howto/hardware/controlunit/control-unit/)
- [High-Precision AD/DA Board](
  https://queezz.github.io/aklab-howto/hardware/controlunit/high-precision-adda-board/)
- [Y-Corp ADC board](
  https://queezz.github.io/aklab-howto/hardware/controlunit/y-corp-adc-board/)
- [FT232H USB GPIO (the moved-to-Windows-NI replacement)](
  https://queezz.github.io/aklab-howto/hardware/controlunit/ft232h-usb-gpio/)

What it does for the archaeology of `ControlUnit`:

- **It explains what is missing from `manuals/`.** The first-pass
  said "one orphan datasheet" and recommended a `docs/datasheets/`
  folder. The correct reading is: the datasheets *do* live somewhere,
  but somewhere *else*. The repository's apparent thinness in
  hardware docs reflects a deliberate externalisation, not neglect.
- **It absorbs hardware build notes that have no place in the
  Python code.** Board layouts, signal-conditioning circuitry,
  cabling, pin numberings, panel layouts — all of these are
  hardware artefacts that change on a different timescale than the
  software does. Keeping them in `aklab-howto` lets `ControlUnit`'s
  git history stay focused on software.
- **It is itself an MkDocs site.** When `ControlUnit` migrates to
  MkDocs, the natural pattern is **cross-link, do not duplicate**.

> **First-pass inference (corrected).** *[corrected]*
> The first pass said the `manuals/` folder was sparse and
> recommended populating it. With `aklab-howto` in the picture, the
> correct recommendation is the opposite: empty `manuals/` further,
> migrate `ads1113.pdf` *out* into `aklab-howto`, and replace the
> in-repo folder with a one-line pointer.

#### 5. `tclogger` — the future-direction successor (recent)
Repository: <https://github.com/queezz/tclogger>

An ESP32-based thermocouple-logging project. The "single TC logger"
the developer mentioned in the Phase 4 / heater-path Developer Notes.

What it represents:

- **A break with the Pi-as-everything model.** ESP32 is small,
  cheap, single-purpose, and natively network-aware. A `tclogger`
  unit is not a control panel — it is a *sensor that publishes*.
- **A first move toward "the orchestrator does not own the
  sensors".** In `ControlUnit`, the Pi owns the ADC, the DACs, the
  thermocouple, the GPIO sync line — *everything* is wired into the
  one box. In a `tclogger`-style architecture, the orchestrator is
  decoupled from the sensors by a network boundary; sensors can be
  added, removed, or replaced without touching orchestrator code.
- **A different software shape entirely.** Not PyQt5 + pyqtgraph +
  pandas. Different language likely, different deployment model
  (firmware flash, not `python -m`), different update cadence.

> **Historical Evolution (forward arrow).** *[confirmed]*
> The "network of instruments" philosophy that appears verbatim in
> the Engineering Mindset section of this document is operationalised
> for the first time in `tclogger`. The membrane-temperature-via-ESP32
> design the developer described is the natural next step from
> `tclogger`. `ControlUnit` is therefore the *terminal* form of the
> "single Pi does everything" lineage; `tclogger` is the *initial*
> form of the lineage that replaces it.

### Cross-repository timeline
Anchoring `ControlUnit`'s development against the others gives a
fuller chronology:

```text
≈ 2018–2019 Echelle Spectra at NIFS / LHD.
            pyqtgraph + Qt threading + the "scientific Qt app"
            visual grammar. The template-source.

2019        Worker / mainView / __init__.py patterns template-copied
            forward into a successor lab.

2020-02 ─── ControlUnit initial commit. Echelle-ported Worker.
2020-03 ─── Ito-kun's I²C-per-read extension and the "Untangling"
            commit. Numpy buffers, ThreadType enum, custom toggles.

2020–22     ControlUnit running. Long quiet period. Lab in operation.
            (pihtivacuum likely co-resident on the Pi; precise dates
             would come from that repo's history.)

2022-06 ─── ControlUnit pdoc3 docs generated. Visual snapshot of
            "old" architecture preserved.

2023-05 ─── ControlUnit ADC-thread tuning storm. settings.yml
            becomes deliberate documentation.

2024-08 ─── ControlUnit worker super class split (Miura-kun's
            pandas-migration commit from the lab Pi).
2024-09 ─── ControlUnit serial renames. sensors→devices, components→ui.

2024 onward TemperatureControl on Windows + NI.
            Heater path migrates *out* of ControlUnit.
            ControlUnit MAX6675 path becomes dormant.

2025-08 ─── ControlUnit Codex PRs. Software-only experiment in
            LLM-assisted development.

≈ 2025–2026 tclogger experiments.
            ESP32-based single-sensor instruments. First operational
            move toward a "network of instruments" architecture.

2026-04 ─── ControlUnit isolated DAC for plasma current
            (Kawabata-kun). The latest serious in-repo work.
2026-05 ─── ControlUnit "settings: debug false" — the present.

aklab-howto runs continuously alongside all of this as the
documentation hub. Its pages on ControlUnit hardware predate and
postdate any single commit in this repo.
```

The dates inside `ControlUnit` are precise (git-confirmed). The dates
*outside* `ControlUnit` are approximate from the user's descriptions
*[speculative on exact years]* — the corresponding repo histories
would tighten them.

### Philosophical evolution across the constellation
Reading the five repos as one body of work, four trajectories are
visible.

#### From inherited patterns to chosen patterns
`Echelle` → `ControlUnit` (early phases) → `ControlUnit` (Phase 4 onward).
The early `ControlUnit` *inherited* Qt-application patterns it did
not yet understand (the `Worker` shape, the sys.path hack, the
`app.processEvents()` from a worker thread). Through 2024–2026, the
developer's commit notes and the structural changes show those
patterns moving from *received* to *chosen* — kept because they
work, modified where they do not, named in vocabulary the developer
controls.

#### From "one machine does everything" to "boundary along signal class"
`ControlUnit` → `TemperatureControl`. The first major decoupling cut
the lab apparatus along the boundary of *thermocouple measurement +
heater control*. Not because the software architecture demanded it,
but because the *physical signal class* deserved better hardware (NI
DAQ for accuracy, Windows for driver maturity). The boundary is
*physical*, not architectural.

#### From "in-code datasheet links" to "external documentation hub"
`settings.yml` URLs → `aklab-howto` pages. Early `ControlUnit`
captured hardware knowledge as comments. `aklab-howto` later
absorbed that knowledge into its own MkDocs site, leaving
`ControlUnit` free to focus on software. This is *the same migration
strategy* as `TemperatureControl`, applied to documentation rather
than to thermocouples.

#### From "monolithic control panel" to "network of single-purpose nodes"
`ControlUnit` + `pihtivacuum` (multiple processes, one Pi) →
`tclogger` (one process, one ESP32, network-facing). The first step
was multi-process on one box; the second step is multi-box. The
"network of instruments" philosophy is therefore not a sudden
insight — it is *the next deliberate step in a trajectory that
already started* when `pihtivacuum` began running alongside
`ControlUnit` on the same Pi.

> **Developer Note (Arseniy) — paraphrased from earlier in this
> document, restated here for the trajectory.**
> "I've evolved my understanding of a lab instrument. Into a network."

What the constellation shows is that the *understanding* came after
the *practice* — `pihtivacuum` was already a peer process on the Pi
before the developer named the pattern; `TemperatureControl` was
already off-loading a physical signal class before the developer
articulated the principle; `tclogger` is the first project where the
principle was clear before the code was written.

### What this means for reading `ControlUnit` itself
Several characteristics of this repository now have *external*
explanations rather than *local* ones:

| Local observation                                    | External explanation                                       |
|------------------------------------------------------|------------------------------------------------------------|
| `_echelle_base` variable name                        | Direct fossil from `echelle_spectra`                       |
| `Worker` / `ThreadType` / sys.path hack              | Inherited from `echelle_spectra`                           |
| Custom-painted touch toggles                         | Visual grammar from `echelle_spectra`                      |
| Sparse `manuals/` folder                             | Hardware docs deliberately live in `aklab-howto`           |
| `MAX6675` path dormant                               | Capability migrated to `TemperatureControl`                |
| `simple-pid` TODO reference                          | Points at `TemperatureControl`'s reference implementation  |
| Aggressive `pigpiod` restart in `start_gpio.py`      | Coexists with `pihtivacuum` on the same Pi *[inferred]*    |
| "Network of instruments" intent in code comments     | First realised in `tclogger`, not in this repo             |
| `kurokawa-dev/PWR.py` quarantine                     | Kurokawa's PWR-401L driver; predates Kawabata's plasma work   |

The right MkDocs structure for `ControlUnit` therefore is *not*
a self-contained encyclopedia. It is a **regional documentation**:
deep on this repository's software, thin where the constellation
already provides the answer, and cross-linked to:

- `aklab-howto` for hardware,
- `echelle_spectra` for visual / threading lineage,
- `TemperatureControl` for the heater migration,
- `tclogger` for the network-of-instruments direction,
- `pihtivacuum` for the Pi-as-orchestrator peer context.

### Open questions about the ecosystem
Items where the ecosystem reading is itself uncertain and would
benefit from the developer's pass:

- **Exact temporal overlap between `pihtivacuum` and `ControlUnit`.**
  The peer-on-the-same-Pi reading is strongly suggested by the
  developer's description, but the precise time at which the two
  began co-residing is not in this repository.
- **Whether `TemperatureControl` consumed `ControlUnit`'s old
  thermocouple data format.** A direct CSV-compatibility check
  against `controlunit/main.py: generate_header_temperature()` would
  tell us whether the migration preserved historical data continuity
  or restarted it.
- **Whether `tclogger` is intended to *replace* the `MAX6675` path
  inside `ControlUnit` or to *bypass* it entirely.** The Developer
  Note in §PID stops short of committing — "even if I would come
  back to it, I would make a dedicated ESP32 unit". Whether that
  ESP32 reports *to* `ControlUnit` or *around* it is a design
  question yet to be answered.
- **What "PIHTI" precisely names.** The acronym recurs in
  `pihtivacuum` and in the developer's lab vocabulary. Resolving it
  would help orient the documentation. *[speculative — likely a rig
  / facility designation rather than a technique]*

These are not internal questions of `ControlUnit`. They are
questions about *the lab as a software ecosystem*. They are listed
here so that the next archaeological pass — whether against
`tclogger`, `pihtivacuum`, or the lab as a whole — has a starting
list of edges to chase.

*End of ecosystem context. The instrument is, and has always been,
embedded.*

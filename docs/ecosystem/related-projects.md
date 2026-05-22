# Related Projects

`ControlUnit` is not an island. It sits in a small constellation of
repositories sharing the same author, the same lab, overlapping hardware,
and a visibly evolving philosophy of what a laboratory instrument should be.

Several local observations that looked "half-finished" in isolation have
external explanations in these neighbours.

## The constellation

### `echelle_spectra` — the predecessor (≈ 2018–2019)

<https://github.com/queezz/echelle_spectra>

A spectroscopic GUI and data-processing application developed at NIFS on the
LHD. It predates `ControlUnit` and is the direct ancestor of several of this
project's most stubborn architectural fossils.

What `Echelle` gave `ControlUnit`:

- **pyqtgraph + DockArea layout.** The dual-pane plot,
  `GraphicsLayoutWidget`, the `Dock`-per-panel pattern, and the
  custom-painted toggle aesthetic all originate here.
- **Threading template.** A `QtCore.QObject` subclass parameterised by an
  `Enum`, driven by an `app.processEvents()` loop, communicating via
  `pyqtSignal`. The `Worker` shape in `controlunit/worker.py` was
  template-copied from this.
- **Package-init `sys.path` hack.** The variable `_echelle_base` is the
  original variable name from `Echelle` — preserved unchanged across the copy.
- **"Qt application as scientific instrument" feel.** Big fonts, large hit
  areas, single main tab + Settings tab, HTML-formatted log dock,
  datetime-axis plots.

When Ito-kun extended the Worker for the ADC, he was extending *Echelle code
in ControlUnit clothing*. The first-pass archaeology read those fossils as
"Qt-newcomer choices" — they are, but the newcomer was the developer himself
two projects earlier.

---

### `pihtivacuum` — the co-resident peer

<https://github.com/queezz/pihtivacuum>

A companion project running on **the same Raspberry Pi as ControlUnit**.
Dedicated to vacuum-system orchestration for the PIHTI rig.

What it does:

- Interactive vacuum state visualization
- Operational logging
- Plotly dashboard and export layer
- Multi-user valve activity logging
- Companion infrastructure on the same Pi

Implications for understanding `ControlUnit`:

The Pi is *not* a ControlUnit-exclusive box. It is a small multi-process
orchestrator on which `ControlUnit` is one of at least two long-running
processes. Several decisions that look defensive in isolation make sense here:

- Unique CSV filename per run (`cu_<YYYYMMDD_HHMMSS>.csv`) — avoids
  collision with another writer.
- Configurable data path via `~/.controlunit/settings.yml` — another process
  owns a different path on the same disk.
- `start_gpio.py: start_pigpiod()` kills any existing `pigpiod` and restarts
  aggressively — exactly what you need if another program may have left
  `pigpiod` in a bad state.

`pihtivacuum` is the first sign that the Pi had already begun functioning as
a small operating environment hosting *multiple* instrument processes — even
before the developer articulated the "network of instruments" philosophy. The
intent arrived after the practice.

---

### `TemperatureControl` — the migration target (≈ 2024 onward)

<https://github.com/queezz/TemperatureControl>

A Windows + National Instruments DAQ implementation of the
thermocouple-reading and heater-control logic that used to live in
`ControlUnit`'s `MAX6675 + HeaterControl` path.

Referenced inline in this repo:

```python
# controlunit/devices/max6675.py
"""
TODO: update to simple-pid as in TemperatureControl
https://github.com/queezz/TemperatureControl
"""
```

What it represents:

- **A migration, not a refactor.** The heater PID was not re-implemented in
  place. It was lifted out and rebuilt on a platform with stronger analogue
  front-ends (NI DAQ). The `ControlUnit` MAX6675 path was left dormant, not
  deleted.
- **A first deliberate decoupling.** Before this, the Pi did everything.
  After, the Pi handles plasma + gas + vacuum; the Windows machine handles
  temperature. The boundary is *physical* (thermocouple), not architectural.
- **A reference implementation.** The TODO in `max6675.py` makes it explicit:
  when the Pi heater path returns (or is replaced by ESP32), it will use
  `simple_pid` properly, like `TemperatureControl` does.

> *"Moved to NI on Windows. Forever 🙂. And even if I would come back to it,
> I would make a dedicated ESP32 unit which would report to an orchestrator."*
> — Arseniy

---

### `aklab-howto` — the external documentation hub

<https://github.com/queezz/aklab-howto>  
Live: <https://queezz.github.io/aklab-howto/>

A lab-wide knowledge base. The directly relevant pages:

- [Control Unit overview](https://queezz.github.io/aklab-howto/hardware/controlunit/control-unit/)
- [High-Precision AD/DA Board](https://queezz.github.io/aklab-howto/hardware/controlunit/high-precision-adda-board/)
- [Y-Corp ADC board](https://queezz.github.io/aklab-howto/hardware/controlunit/y-corp-adc-board/)
- [FT232H USB GPIO](https://queezz.github.io/aklab-howto/hardware/controlunit/ft232h-usb-gpio/) (the moved-to-Windows-NI replacement)

This is where hardware build notes, datasheets, board layouts, cabling, and
pin numberings live. `ControlUnit`'s apparent thinness in hardware docs
reflects a deliberate externalisation, not neglect.

**Cross-link to `aklab-howto`; do not duplicate it.**

---

### `tclogger` — the forward direction

<https://github.com/queezz/tclogger>

An ESP32-based thermocouple-logging project. The "single TC logger" the
developer mentioned.

What it represents:

- **A break with the Pi-as-everything model.** ESP32 is small, cheap,
  single-purpose, and natively network-aware. A `tclogger` unit is not a
  control panel — it is a *sensor that publishes*.
- **First move toward "the orchestrator does not own the sensors".** In
  `ControlUnit`, the Pi owns the ADC, the DACs, the thermocouple, the GPIO
  sync line — everything is wired into one box. In a `tclogger`-style
  architecture, sensors can be added, removed, or replaced without touching
  orchestrator code.

`ControlUnit` is the *terminal* form of the "single Pi does everything"
lineage. `tclogger` is the *initial* form of what replaces it.

> *"I've evolved my understanding of a lab instrument. Into a network."*
> — Arseniy

---

## Cross-repository observations

| Local observation in ControlUnit | External explanation |
|---|---|
| `_echelle_base` variable name | Direct fossil from `echelle_spectra` |
| `Worker` / `ThreadType` / sys.path hack | Inherited from `echelle_spectra` |
| Custom-painted touch toggles | Visual grammar from `echelle_spectra` |
| Sparse `manuals/` folder | Hardware docs deliberately live in `aklab-howto` |
| `MAX6675` path dormant | Capability migrated to `TemperatureControl` |
| `simple-pid` TODO reference | Points at `TemperatureControl`'s reference impl |
| Aggressive `pigpiod` restart in `start_gpio.py` | Coexists with `pihtivacuum` on the same Pi |
| "Network of instruments" intent in code comments | First realised in `tclogger`, not here |
| `kurokawa-dev/PWR.py` quarantine | Kurokawa's PWR-401L driver; predates Kawabata's plasma work |

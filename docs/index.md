# ControlUnit

A Raspberry Pi–based plasma-experiment control and data-acquisition system,
built and operated by one principal developer (Arseniy / `queezz`) over six
years, with contributions from students and lab-mates.

The box exists. It sits in a multi-chamber plasma lab. It is used today.

## What it does now

- Logs plasma parameters and vacuum via one I²C ADC (AIO-32/0RA-IRC).
- Controls two MFCs (H₂ 20 SCCM, O₂ 10 SCCM) via a DAC8532.
- Controls plasma current via a galvanically isolated MCP4725 DAC,
  with a `simple_pid` feedback loop.
- Emits a shared GPIO sync signal (and front-panel LED) to time-align
  external loggers — QMS and others.

## What it no longer does from this repo

- Membrane temperature control. That path (`MAX6675` + SSR-driven halogen
  lamp) is **dormant, not deleted** — the code is there, the device is
  commented out. The measurement and PID moved to a Windows machine with
  National Instruments hardware ([TemperatureControl](https://github.com/queezz/TemperatureControl)).

## Hardware

Runs on a **Raspberry Pi 4 (8 GB)** with a custom PCB. The README still
mentions the original Pi 3B; the hardware was upgraded transparently — no
code references the model. The RAM headroom helped pandas buffers and
pyqtgraph rendering.

Hardware documentation lives in the lab-wide knowledge base:
[aklab-howto](https://queezz.github.io/aklab-howto/). Do not expect it here.

## Navigation

- [Archaeology](Archaeology.md) — the primary source of truth: a
  forensic reconstruction of the entire codebase history, reconciled with
  the developer's own voice.
- [History](history.md) — development timeline.
- [Architecture](architecture/qt-threading.md) — threading evolution and
  signal flow.
- [Hardware / Channel Map](hardware/channel-map.md) — ADC channel table,
  signal names, conversion functions.
- [Ecosystem](ecosystem/related-projects.md) — the constellation of related
  repositories this project sits inside.

## Historical note

This repository originally used [pdoc3](https://pdoc3.github.io/pdoc/)-generated
HTML documentation, last regenerated 2022-06-28. Those artifacts are preserved
under [`archive/pdoc3/`](https://github.com/queezz/ControlUnit/tree/main/archive/pdoc3).
The MkDocs infrastructure was introduced in 2026.

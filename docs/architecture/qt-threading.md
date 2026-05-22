# Qt Threading Evolution

The threading model is the deepest stratum in the codebase — a six-phase
story from a template-copied monolith to a proper per-device worker hierarchy.

## Layered structure (current)

```
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

## Six phases

### Phase 0 — The Echelle template (pre-2020)

The `Worker(QtCore.QObject)` shape, the `ThreadType` enum dispatch, the
`STEP`-batched numpy buffers, the `app.processEvents()` from inside the
worker, and the `sys.path.append` package hack were all **ported from
`echelle_spectra`** — Arseniy's earlier spectrograph-control application.
Ito-kun did not invent this shape; he extended it.

The `_echelle_base` variable in `controlunit/__init__.py` is a literal
fossil — the variable name was never changed after the copy.

### Phase 1 — Monolithic worker (Feb 2020)

Initial commit: one `Worker(QtCore.QObject)` class for all devices,
dispatched by a `ThreadType` enum. Methods named `__plotPresCur` and
`__plotT`. Buffers are fixed-shape numpy arrays of `STEP` rows.

**Ito-kun's extension** (B4 student) introduced two patterns that became
technical debt:

1. A fresh I²C connection opened **on every channel read** — hurt acquisition
   throughput badly on a multi-channel scan.
2. Device behaviour dispatched by `ThreadType` enum, not by separate objects
   — impossible to trace which code path talked to which physical device.

### Phase 1.5 — Untangling (Mar 2020)

Commit `ed7cadb`: +161/−107 in `worker.py`. Renames `ThreadType` → `Signals`,
factors `read_settings()` out of every constructor, renames methods to
`readADC` / `readT`. Threading topology unchanged; vocabulary becomes
consistent.

### Phase 2 — Package + pdoc3 docs (Jun 2022)

Commit `4b7dcdc`: files moved into `controlunit/` directory. No structural
change. pdoc3 generates HTML for the then-current shape. That snapshot is
archived under `archive/pdoc3/`.

### Phase 3 — ADC tuning storm (May 2023)

Eight commits rewrite the acquisition loop to read from `AdcChannelProps`
populated from `settings.yml` instead of hard-coded constants. Numpy arrays
replaced with pandas DataFrames. `STEP` batching clarified.

The `STEP` mechanism serves **two purposes simultaneously**: it averages noisy
ADC samples *and* it amortises Qt signal-emission overhead between worker and
GUI threads. One parameter does both jobs — which is why it has never needed
to change.

### Phase 4 — Worker superclass split (Aug 2024)

Commit `5326e50`: 662 lines deleted from `controlunit/worker.py`, replaced
with `sensors/{worker.py, worker_adc.py, worker_dac8532.py, …}`. Committed
by Miura-kun directly from the lab Raspberry Pi (`pi <hasuo_kuzmin.lab@…>`).

> *"When Miura-kun was here I thought about transitioning to pandas for sanity.
> I finally got what classes are: basically a box, a drawer. So you don't spill
> and lose your functions."* — Arseniy

Phase 4.5 (Sep 2024): 10-day burst of renames — `sensors/` → `devices/`,
`components/` → `ui/`, terminology unified. Behaviour untouched; vocabulary
became consistent.

### Phase 5 — Codex PRs (Aug 2025)

Two LLM-authored PRs (#20, #21):
- Moved `update_processed_signals_dataframe` out of `main.py` into workers.
- Cleaned the (still-unused) `core_logic.py` stub.

These were **not tested on hardware** at merge time. The developer considered
the Codex PR workflow an experiment, and moved to Cursor + direct on-rig
testing afterward.

### Phase 6 — Isolation hardware push (Apr 2026)

Commits `0b417cf` and `dfbc65c`: galvanic I²C isolation for the MCP4725
plasma-current DAC. Kawabata-kun's plasma PID work landed alongside.

The isolation was critical: plasma transients on the cathode bus were
affecting the rest of the I²C tree.

> *"Kawabata-kun did the final plasma current PID loop. I made and tested
> one before isolation. Isolation was critical, of course."* — Arseniy

## The `UIWindow` multiple-inheritance idiom

```python
class MainApp(QtCore.QObject, UIWindow):
    ...
```

Unusual for Qt code. Inherited from `echelle_spectra`. Keeps layout code in
`mainView.py` physically separated from controller code without giving up
direct attribute access (`self.control_dock`, `self.graph`, etc.).

## Worker→worker signalling

```python
# controlunit/main.py
def start_cross_connections(self):
    mfcs_worker.send_presets_to_adc.connect(
        adc_worker.update_mfcs, type=QtCore.Qt.DirectConnection
    )
```

The DAC8532 worker tells the ADC worker what voltage it just set, so the ADC
can log the *commanded* preset alongside the *measured* signal.
`DirectConnection` runs the slot in the emitter's thread — correct because
`update_mfcs` only touches `self._mfc_presets`.

# Signal Flow and Data Pipeline

## ADC acquisition cycle (per 0.1 s tick)

1. `ADC.acquisition_loop()` runs in its own `QThread`.
2. `self.pause(self.sampling_time)` (default 0.1 s) — an abort-aware sleep.
3. `collect_data()` reads N channels via
   `aio.analog_read_volt(channel, datarate, gain)`.
   The PCA9554 mux is reconfigured only when the channel range demands it.
4. Raw row appended to `adc_values` DataFrame; converted row appended to
   `converted_values`.
5. If a plasma-current setpoint is non-zero:
   `plasma_current_control()` runs `simple_pid.PID(0.3, 0.1, 0)` against `Ip`
   and emits `send_control_voltage` → `MCP4725`.
6. Every `STEP` ticks: `send_processed_data_to_main_thread()` emits
   `data_ready([dataframe, device_name])`.
   `MainApp.on_worker_step` routes to `_adc_step`, appends to
   `self.datadict["ADC"]`, calls `save_data` (CSV append), triggers plot update.

## Averaging at slow sampling

A period of one second or longer is not read once. From
`AVERAGE_FROM_SECONDS = 1.0` upwards (`controlunit/devices/adc.py`) the
reader converts every `INNER_SECONDS = 0.2` seconds through the period and
records one row at the period's end whose raw voltages are the mean of those
readings — fifty of them fill the rig's ten-second setting. Below the
threshold nothing changed: one conversion per period, because fast sampling
is for watching transients and the instant is the point. Slow sampling is an
overnight or weekend log, where a single ~1 ms conversion records whatever
noise sat on the line at that instant and the period's mean is the truer
number (owner decision 2026-09-07).

The mean is taken over the *raw* voltages and converted afterwards, exactly
as one reading is converted, so a row stays self-consistent: converting the
raw column of the CSV reproduces the converted column beside it. The columns,
the timestamp (the period's end) and the one-row-per-period shape are
unchanged, so the CSV, the web ring and PIHTI Log see nothing new. The period
is measured with `time.monotonic()` and each inner conversion is due at a
fixed offset from its start, so the conversions' own time comes out of the
waits and ten seconds of sampling still take ten seconds. Both the inner
cadence and the period wait through `DeviceThread.pause`; an abort mid-period
ends the loop at once and the half-measured period records nothing. The
plasma-current PID runs once per recorded row, on the averaged value.

## STEP batching

```python
# controlunit/devices/adc.py
if step % (self.STEP - 1) == 0 and step != 0:
    self.send_processed_data_to_main_thread()
    step = 0
else:
    step += 1
```

`STEP` serves two purposes simultaneously: averages noisy ADC samples *and*
amortises Qt signal-emission overhead. One parameter, two jobs.

`STEP` is set dynamically by sampling rate:

```python
# controlunit/devices/device.py
def set_sampling_time(self, sampling_time):
    if sampling_time >= 0.9:  self.STEP = 1
    if sampling_time < 0.9:   self.STEP = 3
    if sampling_time < 0.1:   self.STEP = 5
```

## Plasma current PID

Live. Uses [`simple_pid`](https://pypi.org/project/simple-pid/).

- `p=0.3, i=0.1, d=0`, `output_limits=(0, 4500)` mV.
- Setpoint from GUI; feedback from Hall-effect sensor on channel 0.
- Actuator: MCP4725 DAC behind galvanic I²C isolator (Apr 2026).
- `baseline = 1000` mV — empirical minimum for plasma ignition (Kawabata-kun).

## Membrane heater PID

**Dormant.** Code exists in `MAX6675.temperature_control()`.
Hand-rolled: integral-clamped (`if integral < -0.5: integral = 0`),
asymmetric (only positive `e` drives output). Gains `Kp=3.5, Ki=0.06, Kd=0`.
Output is on-time fraction of a 10 ms cycle, software-PWMed against an SSR.

The measurement and PID have migrated to a Windows machine with NI hardware.
Not returning to the Pi; if it returns at all, it will be a dedicated ESP32
unit reporting to an orchestrator.

## GPIO sync signal

GPIO 26 emits a digital sync edge consumed by various external data loggers
(QMS and others). The front-panel LED is a **visual indicator only** — not an
isolation strategy, not opto-isolated triggering. The shared GPIO was always a
wiring convenience.

`QMS_signal` in the CSV is a boolean column logging whether the sync trigger
is currently active during each ADC row.

## Safety stop semantics

```python
# controlunit/main.py
def turn_off_voltages(self):
    self.workers["ADC"]["worker"].set_plasma_current.emit(0)
    self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
    self._mfc_presets = {1: 0, 2: 0}
    self.update_current_values()
    self.workers["MFCs"]["worker"].output_voltage_signal.emit(1, 0)
    self.workers["MFCs"]["worker"].output_voltage_signal.emit(2, 0)
```

`abort_all_threads` → `turn_off_voltages` first, thread termination second.
Plasma setpoint goes to zero before any thread dies.

## Logging

Two parallel append-only paths:

1. **CSV** at `~/work/cudata/cu_<YYYYMMDD_HHMMSS>.csv` with a self-describing
   comment header. Header embeds enough channel metadata that an old CSV can
   be replayed without `settings.yml`.
2. **Event log** at `~/work/cudata/controlunit.log`.

Every ADC row carries commanded presets alongside measured signals:
`PresetV_mfc1`, `PresetV_mfc2`, `PresetV_cathode`, `IGmode`, `IGscale`,
`QMS_signal`.

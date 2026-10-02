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
   `plasma_current_control()` steps the cathode loop (`CathodeLoop`, below)
   against `Ip` and emits `send_control_voltage` → `MCP4725`.
6. Every `STEP` ticks: `send_processed_data_to_main_thread()` emits
   `data_ready([dataframe, device_name])`.
   `MainApp.on_worker_step` routes to `_adc_step`, which calls `save_data`
   (CSV append) first, then adds the rows to the bounded
   `self.datadict["ADC"]` (`RunHistory`) and redraws the plots.

## What the main thread remembers of a run

The file is the record; `self.datadict["ADC"]` is only what the window
draws and what a baseline averages. It is a `RunHistory`
(`controlunit/history.py`): plain column arrays filled in place, at most
200,000 rows. When full, the older half is thinned to every second row, so
a long run stays on the screen whole at a resolution that falls with age.
A delivery costs what it brings and no more, however long the run.

It was one pandas frame concatenated at every delivery until 4.22.3. Two
days into the 0.1 s run of 2026-09-30 a delivery cost 1.3 s against 0.3 s
between deliveries, the main thread was 25 hours behind, and the rows
waiting behind it were lost when the frozen program was killed
([the October 2 run](../diagnostics/2026-10-02-ar-plasma-pid-run.md)).

Three things now stand between a slow window and the record. The file is
written before anything is drawn. Each batch carries the moment the reader
handed it over, and a delivery that arrives more than `BEHIND_SECONDS = 2`
late is not redrawn, so the thread catches up; the Log says so once each
way. And the lag travels in the web record: `/api/state` carries it as
`data.behind`, and `/api/health` answers `degraded` with "screen N s behind
the reader" while it lasts, so a surface can no longer say `live` over
readings that are hours old.

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

Live. `CathodeLoop` in `controlunit/devices/cathode_loop.py`, held by the
ADC worker.

- Gains `PID_GAINS = (30, 40, 0)`: 30 mV per ampere of error and 40 mV per
  ampere-second, almost purely integral. Output is the cathode drive,
  limited to 0–5000 mV, all of the DAC.
- Setpoint from the GUI or a browser; feedback from the Hall-effect sensor
  on channel 0, with the `Ip` zero subtracted.
- Actuator: MCP4725 DAC behind galvanic I²C isolator (Apr 2026).
- **Engaging takes over from the drive already held.** Going from off to a
  setpoint starts the loop's clock and sets its integral so that the first
  command equals the manual drive the cathode holds; from there it moves at
  the integral's pace, 40 mV/s per ampere of error. The main thread tells
  the reader the manual value (`set_manual_drive`), which is also what the
  file records in `PresetV_cathode` while the cathode is held by hand.
- **A cold start begins at 1000 mV.** Engaged with the cathode off, or held
  below that, the loop starts there. This is the old loop's fixed base
  (Kawabata-kun's empirical floor), kept as the cold start only.
- **With no discharge the loop walks; it does not regulate** (4.25.0; owner
  decision 2026-10-02: "Since PID could light a cold plasma, that means we
  should try and improve it"). While the current is below 0.1 A the drive
  goes up at 25 mV/s, whatever the setpoint, and never past 1900 mV; at
  that ceiling it holds and says so in red. The integral is kept where a
  regulating step would carry on from the drive reached, so when the
  plasma lights the loop takes over with only its proportional answer to
  the current appearing (30 mV per ampere). A PI loop on an unlit source
  integrates an error that tells it nothing: its pace was the setpoint's,
  and nothing stopped it short of the supply's own voltage setting.
- **An arc is not the plasma going out.** The loop counts the discharge
  unlit only after the current has stayed below 0.1 A for two seconds; the
  0.2 to 0.3 s dropouts of an arc are regulated straight through. A plasma
  that does go out under the loop brings the drive down to the ceiling,
  from which the loop lights it again.
- The five numbers are the `Plasma Current PID` block of `settings.yml`:
  `Cold Start mV`, `Unlit Ramp mV per s`, `Unlit Ceiling mV`, `Lit Above A`
  and `Unlit After s`.
- Changing the setpoint of a running loop moves the setpoint and nothing
  else. The Log carries a line per engagement with the starting drive, and
  one each time the loop changes between walking, holding at the ceiling
  and regulating.
- The integral stops at the limits. It does not know when the Kikusui is
  regulating voltage instead of current (its own voltage setting, 7.80 V on
  2026-10-02), where the command has no effect.

Until 4.23.0 this was a `simple_pid.PID` whose clock ran from the last
time anything touched it: its first step integrated the error over the
whole manual stretch before, on top of the 1000 mV base. On 2026-10-02
three engagements started at 1728, 1759 and 1000 mV; the third put the
plasma out.

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
`IGmode_Pu2`, `IGscale_Pu2` (one mode and exponent pair per ionization
gauge, named by the gauge's `Mode Column` and `Scale Column` in
`settings.yml`),
`QMS_signal`.

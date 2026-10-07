"""
ADC communication

I2C アナログ入力ボード AIO-32/0RA-IRC

https://www.y2c.co.jp/i2c-r/aio-32-0ra-irc/
"""

import pandas as pd
import math
import time, datetime
from PyQt5 import QtCore

from controlunit.devices.adc_setter import AIO_32_0RA_IRC as adc
from .cathode_loop import CathodeLoop
from .device import DeviceThread
from .timing import SampleClock, TimingDiagnostics


#: The sampling time at which the reader starts averaging. Below it one
#: conversion per period is the right measurement: fast sampling is for
#: watching transients, and the instant is the point. At and above it the
#: period is long enough that a single ~1 ms conversion records whatever
#: noise sat on the line at that instant, while the run is an overnight or
#: weekend log where the period's mean is the truer number (owner decision
#: 2026-09-07).
AVERAGE_FROM_SECONDS = 1.0

#: An ionization gauge's mode code when it is declared off: the third item of
#: the Control dock's box, after Torr (0) and Pa (1). Its row keeps the raw
#: volts and records NaN as the pressure (queezz, 2026-10-07).
IG_MODE_OFF = 2

#: How often the reader converts inside an averaged period. Fifty readings
#: fill the rig's ten-second period; five fill a one-second one.
INNER_SECONDS = 0.2

#: How long the reader waits after a failed read before trying again. The
#: reader used to die on the first I²C error between two samples, with the
#: outputs held and nothing on the screen saying the file had stopped
#: (2026-08-19, 2026-09-09: every death coincided with the plasma arcing).
#: Now it waits this long and reads again, for as long as the run lasts.
RETRY_SECONDS = 0.5

#: How often a reader that keeps failing repeats itself in the message log,
#: so a bus that is down for an hour is one line a minute, not one a second.
COMPLAIN_EVERY_SECONDS = 30.0

#: The plasma-current loop's gains: millivolts of cathode drive per ampere
#: of error, and per ampere-second. Almost purely integral, as it has been
#: since the loop was written.
PID_GAINS = (30.0, 40.0, 0.0)

#: The range the loop may command, in millivolts: all of the cathode DAC.
DRIVE_LIMITS_MV = (0.0, 5000.0)

#: Where the loop starts when it is engaged with the cathode not driven (or
#: driven below this): well under what lights a discharge, so the integral
#: walks the filament up from here. It is the old loop's fixed 1000 mV base,
#: kept as the cold start because the one cold start that began there, on
#: 2026-10-02 at 17:47:58, lit the plasma without overshoot.
COLD_START_MV = 1000.0

#: While there is no discharge the loop does not regulate, it walks: up at
#: this many millivolts a second, the pace of that same cold start (24 mV/s),
#: whatever setpoint was asked for.
UNLIT_RAMP_MV_PER_S = 25.0

#: And never past this without a discharge. 1800 to 1830 mV is what lights
#: the source by hand; a filament that has not lit by 1900 mV is not going to
#: be helped by more, and the only other thing between an unlit loop and the
#: top of the DAC is the supply's own voltage setting.
UNLIT_CEILING_MV = 1900.0

#: A discharge is lit above this current, and unlit once it has stayed below
#: it for `UNLIT_AFTER_S`: an arc takes the current to zero for 0.2 to 0.3 s
#: and is not the plasma going out.
LIT_ABOVE_A = 0.1
UNLIT_AFTER_S = 2.0


def mean_of_readings(readings):
    """The per-channel mean of one period's raw voltage readings.

    Each reading is a dict of channel name to voltage, all with the same
    keys and in the same order; the order is kept, because the recorded row
    is built from `self.adc_voltages.values()`. A single reading averages to
    itself. An empty list returns None: a period that recorded nothing has
    no sample to offer, and the caller records no row.
    """
    if not readings:
        return None
    count = len(readings)
    return {
        name: sum(reading[name] for reading in readings) / count
        for name in readings[0]
    }


# MARK: ADC
class ADC(DeviceThread):
    send_control_voltage = QtCore.pyqtSignal(float)
    send_zero_adjustment = QtCore.pyqtSignal(dict)
    set_plasma_current = QtCore.pyqtSignal(float)
    # The drive the main thread is holding by hand, in mV: the loop is off.
    set_manual_drive = QtCore.pyqtSignal(float)
    # The gauge's channel name, then the setting: each ionization gauge has
    # its own mode and exponent, set from its own selector.
    set_ig_mode_signal = QtCore.pyqtSignal(str, int)
    set_ig_range_signal = QtCore.pyqtSignal(str, int)
    set_trigger_signal_signal = QtCore.pyqtSignal(int)
    set_adc_gain_signal = QtCore.pyqtSignal(int)
    set_zero_ip_signal = QtCore.pyqtSignal()
    # One signal for all three baselines: the channel's name and the zero the
    # main thread measured for it over the last seconds of the run.
    set_zero_signal = QtCore.pyqtSignal(str, float)

    def __init__(self, device_name, app, startTime, config, pi):
        super().__init__(device_name, app, startTime, config, pi)
        self.__app = app
        self.device_name = device_name
        self.__startTime = startTime
        self._abort = False
        self.config = config
        self.init()

    # MARK: init
    def init(self):
        """
        Initiate ADC thread parameters

        adc_columns
        -----------
        date: datetime.datetime
        time: float, seconds from start of recording
        adc_voltage_columns: ADC raw signals
        <gauge's Mode Column>: int, 0 Torr linear, 1 Pa log or 2 off, per gauge
        <gauge's Scale Column>: int, the exponent in linear mode, per gauge
        QMS_signal: int, "trigger" on or off. When on emits a signal from GPIO
        """
        self.prep_adc_board()
        self.adc_signals_columns = self.config["ADC Signal Names"]
        self._additional_columns = list(self.config["ADC Additional Columns"])
        self.adc_values_columns = self._additional_columns + self.adc_signals_columns
        # Where the signal voltages start in a raw row: after every
        # additional column, however many the settings list.
        self._signal_offset = len(self._additional_columns)

        # One mode and one exponent per ionization gauge, keyed by the
        # gauge's channel name, each resting at Torr and 1e-3 until its
        # selector says otherwise; and where in a raw row each pair is
        # recorded, so conversion reads the settings captured with the row.
        self._gauge_settings = {
            name: {"mode": 0, "scale": -3} for name in self.config["Ion Gauges"]
        }
        self._gauge_columns = {}
        for name in self._gauge_settings:
            ch = self.config["Adc Channel Properties"][name]
            self._gauge_columns[name] = (
                self._additional_columns.index(ch.mode_column),
                self._additional_columns.index(ch.scale_column),
            )
        known = {"date", "time", "QMS_signal", "PresetV_mfc1", "PresetV_mfc2",
                 "PresetV_cathode"}
        for mode_index, scale_index in self._gauge_columns.values():
            known.add(self._additional_columns[mode_index])
            known.add(self._additional_columns[scale_index])
        unknown = [c for c in self._additional_columns if c not in known]
        if unknown:
            raise ValueError(f"ADC Additional Columns nobody records: {unknown}")

        self._raw_rows = []
        self._converted_rows = []
        self.__qmsSignal = 0
        self._mfc_presets = {1: 0.0, 2: 0.0}
        self.plasma_current_setpopint = 0
        self.control_voltage = 0
        self.plasma_current = 0
        self.plasma_current_converted = 0
        self.zero_ip = 0
        self.zero_bu = 0
        self.zero_bd = 0
        self.set_sampling_time(self.config["Sampling Time"])
        self.pid_verbose = self.config.get("Verbose.Plasma Current PID", False)
        self._pid_clock = time.monotonic
        tuning = self.config.get("Plasma Current PID") or {}
        self.cold_start_mv = float(tuning.get("Cold Start mV", COLD_START_MV))
        self.unlit_ramp = float(tuning.get("Unlit Ramp mV per s", UNLIT_RAMP_MV_PER_S))
        self.unlit_ceiling = float(tuning.get("Unlit Ceiling mV", UNLIT_CEILING_MV))
        self.lit_above = float(tuning.get("Lit Above A", LIT_ABOVE_A))
        self.unlit_after = float(tuning.get("Unlit After s", UNLIT_AFTER_S))
        self._unlit_since = None
        self._loop_state = None
        self.prep_pid()
        self._read_failures = 0
        self._failing_since = None
        self._last_complaint = None
        self._cadence = None
        self._scan_seconds = 0.0
        self._slowest_channel = ("none", 0.0)
        self._last_sample_clock = None
        self._hall_reference_invalid = False

        self.connect_signals()

    def connect_signals(self):
        """connect signals"""
        self.set_plasma_current.connect(
            self._set_plasma_current, type=QtCore.Qt.DirectConnection
        )
        self.set_manual_drive.connect(
            self._set_manual_drive, type=QtCore.Qt.DirectConnection
        )
        self.set_ig_mode_signal.connect(
            self.set_ig_mode, type=QtCore.Qt.DirectConnection
        )
        self.set_ig_range_signal.connect(
            self.set_ig_range, type=QtCore.Qt.DirectConnection
        )
        self.set_trigger_signal_signal.connect(
            self.set_trigger_signal, type=QtCore.Qt.DirectConnection
        )
        self.set_adc_gain_signal.connect(
            self.set_adc_gain, type=QtCore.Qt.DirectConnection
        )
        self.set_zero_ip_signal.connect(
            self.set_zero_ip, type=QtCore.Qt.DirectConnection
        )
        self.set_zero_signal.connect(self.set_zero, type=QtCore.Qt.DirectConnection)

    def prep_adc_board(self):
        """
        Initiates an instance of AIO_32_0RA_IRC from AIO.py
        Address: 0x49, 0x3E
        Why this addresses?
        """
        self.aio = adc(0x49, 0x3E)

        self.gain_definitions = {
            10: self.aio.PGA.PGA_10_0352V,
            5: self.aio.PGA.PGA_5_0176V,
            2: self.aio.PGA.PGA_2_5088V,
            1: self.aio.PGA.PGA_1_2544V,
        }

        self.adc_channels = self.config["Adc Channel Properties"]
        for _, j in self.adc_channels.items():
            j.gain = self.gain_definitions[j.gainIndex]

    # MARK: Setters
    @QtCore.pyqtSlot(str, int)
    def set_ig_mode(self, gauge: str, IGmode: int):
        """
        Sets one Ionization Gauge's mode from GUI
        0: Torr
        1: Pa
        2: Off — the gauge is switched off at its controller, so its channel
           carries noise: the raw volts are kept and the converted value is NaN
        """
        self._gauge_settings[gauge]["mode"] = IGmode
        return

    @QtCore.pyqtSlot(str, int)
    def set_ig_range(self, gauge: str, IGrange: int):
        """
        Sets one Ionization Gauge's range (scale) from GUI
        range: -8 ~ -3
        """
        self._gauge_settings[gauge]["scale"] = IGrange
        return

    @QtCore.pyqtSlot(int)
    def set_trigger_signal(self, signal: int):
        """
        Sets "trigger" signal from GUI for syncing QMS and RasPi data
        waiting: 0
        running: 1
        """
        self.__qmsSignal = signal
        return

    def set_mfc_preset(self, voltage_preset, mfc_num):
        """
        Sets Preset Voltage of Mas Flow Control for H2 from GUI
        range: 0 - 5000
        unit: mV
        """
        self._mfc_presets[mfc_num] = voltage_preset / 1000
        return

    @QtCore.pyqtSlot(list)
    def update_mfcs(self, arg):
        mfc_num, voltage_preset = arg
        self.set_mfc_preset(voltage_preset, mfc_num)

    @QtCore.pyqtSlot(int)
    def set_adc_gain(self, gain):
        """
        Set gain for Baratron channel on ADC
        Parameters
        ----------
        value: int
            gain, values [1,2,5,10] (in V)
        """
        allowed = [1, 2, 5, 10]
        if not gain in allowed:
            gain = 10
            print(f"{gain} is not supported, gain set to 10. Choose from {allowed}")
        else:
            print(f"update ADC gain to {gain}")

        # TODO: use AdcChannelsProps instead
        # self.adc_channels[CHB1] = self.gain_definitions[gain]
        # self.adc_channels[CHB2] = self.gain_definitions[gain]

    def set_adc_datarate(self):
        """
        Communicate with ADC
        """
        self.adc_datarate = [self.aio.DataRate.DR_860SPS]

    # MARK: Data append
    @property
    def adc_values(self):
        """Compatibility snapshot; the acquisition path buffers plain rows."""
        return pd.DataFrame.from_records(self._raw_rows, columns=self.adc_values_columns)

    @property
    def converted_values(self):
        return pd.DataFrame.from_records(
            self._converted_rows, columns=self.config["ADC Converted Names"]
        )

    def _additional_values(self, now):
        """The row's metadata, in the order the settings list the columns."""
        values = {
            "date": now,
            "time": (now - self.__startTime).total_seconds(),
            "QMS_signal": self.__qmsSignal,
            "PresetV_mfc1": self._mfc_presets[1],
            "PresetV_mfc2": self._mfc_presets[2],
            "PresetV_cathode": self.control_voltage,
        }
        for name, (mode_index, scale_index) in self._gauge_columns.items():
            values[self._additional_columns[mode_index]] = self._gauge_settings[name]["mode"]
            values[self._additional_columns[scale_index]] = self._gauge_settings[name]["scale"]
        return [values[column] for column in self._additional_columns]

    def put_new_data_in_dataframe(self):
        """Capture one raw row and its metadata, without allocating a table."""
        now = datetime.datetime.now()
        self._raw_rows.append([
            *self._additional_values(now),
            *[self.adc_voltages[name] for name in self.adc_signals_columns],
        ])

    def update_processed_signals_dataframe(self):
        """Convert exactly the voltages and gauge settings captured in the row."""
        raw = self._raw_rows[-1]
        voltages = dict(zip(self.adc_signals_columns, raw[self._signal_offset:]))
        converted = []
        debug = self.config.get("Debug.Raw ADC", False)
        for name, value in zip(self.adc_signals_columns, raw[self._signal_offset:]):
            conversion = self.adc_channels[name].conversion
            if debug:
                converted.append(value)
            elif self.adc_channels[name].conversion_id == "Hall Sensor":
                converted.append(self.adc_channels[name].convert_hall(voltages))
            elif conversion.__name__ == "ionization_gauge":
                mode_index, scale_index = self._gauge_columns[name]
                if raw[mode_index] == IG_MODE_OFF:
                    # Declared off: the volts are noise, never a pressure.
                    converted.append(float("nan"))
                else:
                    converted.append(conversion(value, raw[mode_index], raw[scale_index]))
            else:
                converted.append(conversion(value))
        self._converted_rows.append(converted)

    def calculate_averaged_signals(self):
        """
        Calculate averages for the calibrated signals to show them in GUI
        """
        self.averages = self.converted_values.mean().values

    # MARK: Data send
    def send_processed_data_to_main_thread(self):
        """
        Sends processed data to main thread in main.py
        Clears temporary dataframes to reset memory consumption.
        """
        if not self._raw_rows:
            return
        if len(self._raw_rows) != len(self._converted_rows):
            raise ValueError("ADC raw and converted batch lengths differ")
        newdata = pd.DataFrame.from_records(
            [raw + converted for raw, converted in zip(self._raw_rows, self._converted_rows)],
            columns=self.adc_values_columns + self.config["ADC Converted Names"],
        )
        newdata.attrs["adc_emitted_at"] = time.monotonic()
        newdata.attrs["adc_period"] = self.sampling_time
        self.data_ready.emit([newdata, self.device_name])
        self.clear_datasets()

    # MARK: Data clear
    def clear_datasets(self):
        self._raw_rows.clear()
        self._converted_rows.clear()

    # MARK: plasma current

    #: The baseline channels, and the worker attribute each one's zero lives
    #: in. A zero changes how a signal is read on the screen, in the plots and
    #: on the web, and never what is written to the CSV. The main thread
    #: measures it over the last seconds of the run it holds; this buffer is
    #: emptied every few samples and is too short to average anything.
    ZEROS = {"Ip": "zero_ip", "Bu": "zero_bu", "Bd": "zero_bd"}

    @QtCore.pyqtSlot(str, float)
    def set_zero(self, channel, value):
        """Hold `value` as one channel's zero and report every zero back."""
        attribute = self.ZEROS.get(channel)
        if attribute is None:
            return
        if value == value:  # never a NaN, which would silence the channel
            setattr(self, attribute, float(value))
        self.send_zero_adjustment.emit(self.zeros())

    def zeros(self):
        """Every baseline the main thread should subtract, by channel."""
        return {name: getattr(self, attr) for name, attr in self.ZEROS.items()}

    @QtCore.pyqtSlot()
    def set_zero_ip(self):
        """The old worker-side zero: the mean of this short buffer."""
        self.set_zero("Ip", self.converted_values["Ip_c"].mean())

    def set_cathode_current(self, control_voltage):
        """Send cathode control voltage to main thread"""
        self.control_voltage = control_voltage
        self.send_control_voltage.emit(control_voltage)

    @QtCore.pyqtSlot(float)
    def _set_plasma_current(self, plasma_current_setpopint):
        """The loop's setpoint in amperes; zero turns the loop off.

        Going from off to a setpoint is an engagement: the loop takes over
        from the drive the cathode already holds. Changing the setpoint of
        a loop that is already running moves the setpoint and nothing else.
        """
        if plasma_current_setpopint == 0:
            self.plasma_current_setpopint = 0
            self.reset_current_control()
            return
        if self.plasma_current_setpopint:
            self.pid.setpoint = float(plasma_current_setpopint)
            self.plasma_current_setpopint = plasma_current_setpopint
            return
        # The reader steps the loop from its own thread as soon as the
        # setpoint is not zero, so the engaged loop is in place first.
        self._engage_pid(float(plasma_current_setpopint))
        self.plasma_current_setpopint = plasma_current_setpopint

    def _engage_pid(self, setpoint):
        """Start the loop from what the cathode is driven with right now."""
        held = float(self.control_voltage or 0.0)
        start = max(held, self.cold_start_mv)
        measured = None
        if math.isfinite(self.plasma_current_converted):
            measured = self.plasma_current_converted - self.zero_ip
        lit = measured is not None and measured > self.lit_above
        if not lit:
            start = min(start, self.unlit_ceiling)
        loop = self._new_loop(setpoint)
        loop.engage(start, measured)
        self.pid = loop
        # Engaged on no discharge, the loop is unlit from its first step
        # rather than after the two seconds an arc is forgiven for.
        self._unlit_since = None if lit else self._pid_clock() - self.unlit_after
        self._loop_state = None
        origin = "the drive already held" if held >= self.cold_start_mv else "a cold start"
        reading = "unavailable" if measured is None else f"{measured:.3f} A"
        self.send_message.emit(
            f"Plasma current PID engaged at {start:.0f} mV ({origin}),"
            f" Ip {reading}, setpoint {setpoint:.2f} A"
        )

    @QtCore.pyqtSlot(float)
    def _set_manual_drive(self, millivolts):
        """The cathode is held by hand at `millivolts`; the loop is off.

        The main thread writes the DAC itself. What it tells the reader is
        only the number, for two uses: the row records it in
        `PresetV_cathode`, which read 0 through every manual stretch before,
        and a later engagement starts from it.
        """
        self.plasma_current_setpopint = 0
        self.prep_pid()
        self.control_voltage = float(millivolts)

    def reset_current_control(self):
        self.prep_pid()
        self.set_cathode_current(0)

    def update_pid_coefficients(self, pid_coefficients):
        """update pid"""
        self.pid.tunings = pid_coefficients

    def _new_loop(self, setpoint):
        return CathodeLoop(
            *PID_GAINS,
            setpoint=setpoint,
            limits=DRIVE_LIMITS_MV,
            sample_time=self.sampling_time * self.STEP,
            clock=self._pid_clock,
        )

    def prep_pid(self):
        """A fresh loop: output is the cathode drive in mV."""
        self.pid = self._new_loop(self.plasma_current_setpopint)

    def set_sampling_time(self, sampling_time):
        """The loop steps once per delivery, so it follows the sampling."""
        super().set_sampling_time(sampling_time)
        loop = getattr(self, "pid", None)
        if loop is not None:
            loop.sample_time = self.sampling_time * self.STEP

    def plasma_current_control(self):
        """
        PID control plasma current
        """
        if not math.isfinite(self.plasma_current_converted):
            return  # Hold the command; never feed a missing reference to PID.
        measured = self.plasma_current_converted - self.zero_ip
        if self._discharge_lit(measured):
            output = self.pid(measured)
            state = "lit"
        else:
            output = self.pid.ramp(measured, self.unlit_ramp, self.unlit_ceiling)
            state = "ceiling" if output >= self.unlit_ceiling else "unlit"
        if not self.plasma_current_setpopint:
            return  # turned off while this step ran: the hand holds the DAC
        self._say_loop_state(state, output)
        self.set_cathode_current(output)
        if self.pid_verbose:
            print(
                self.pid.setpoint,
                output,
                self.plasma_current_converted - self.zero_ip,
            )
    def _discharge_lit(self, measured):
        """Whether there is a discharge for the loop to regulate.

        Lit the moment the current is above the threshold; unlit only once
        it has stayed below for `unlit_after` seconds, so the 0.2 to 0.3 s
        an arc takes the current away for is regulated straight through.
        """
        if measured > self.lit_above:
            self._unlit_since = None
            return True
        now = self._pid_clock()
        if self._unlit_since is None:
            self._unlit_since = now
        return now - self._unlit_since < self.unlit_after

    def _say_loop_state(self, state, output):
        """One Log line each time the loop changes what it is doing."""
        if state == self._loop_state:
            return
        previous, self._loop_state = self._loop_state, state
        if state == "lit":
            if previous is not None:
                self.send_message.emit(
                    f"Plasma current PID: discharge lit at {output:.0f} mV; regulating"
                )
        elif state == "unlit":
            self.send_message.emit(
                f"Plasma current PID: no discharge; walking the drive up at"
                f" {self.unlit_ramp:g} mV/s from {output:.0f} mV, ceiling"
                f" {self.unlit_ceiling:.0f} mV"
            )
        else:
            self.send_message.emit(
                f"<font color='red'>Plasma current PID: no discharge at the"
                f" {self.unlit_ceiling:.0f} mV ceiling</font>; holding there."
                " Check gas and the anode supplies, or turn the PID off"
            )

    # MARK: start
    @QtCore.pyqtSlot()
    def start(self):
        """
        Start acquisition loop
        """
        self.acquisition_loop()

    # MARK: read voltages
    def read_all_channels(self):
        """
        One raw voltage per channel, straight from the board.
        Can change ADC gain at any time by updating self.adc_channels
        """
        values = {}
        started = time.monotonic()
        try:
            for name in self.adc_signals_columns:
                if self._abort:
                    return None
                ch = self.adc_channels[name]
                before = time.monotonic()
                try:
                    values[name] = self.aio.analog_read_volt(
                        ch.channel, *self.adc_datarate, ch.gain
                    )
                finally:
                    elapsed = time.monotonic() - before
                    if elapsed > self._slowest_channel[1]:
                        self._slowest_channel = (name, elapsed)
            return values
        finally:
            self._scan_seconds += time.monotonic() - started

    def collect_data(self):
        """Read every channel, and keep trying until the board answers.

        A read that raises — an I²C error under an arc, a conversion that
        never finishes — is reported once, retried every `RETRY_SECONDS`,
        and repeated in the log every `COMPLAIN_EVERY_SECONDS` while it
        goes on. The thread never ends on a read error: a dead reader with
        the outputs held is what the rig did three times this month, and
        the person at it could not tell from the screen. Returns False only
        when the run was aborted while waiting.
        """
        while not self._abort:
            try:
                voltages = self.read_all_channels()
            except Exception as error:
                self._note_read_failure(error)
                self.pause(RETRY_SECONDS)
                continue
            if self._abort or voltages is None:
                return False
            self._note_read_recovered()
            self.hold_voltages(voltages)
            return True
        return False

    def _note_read_failure(self, error):
        now = time.monotonic()
        self._read_failures += 1
        if self._failing_since is None:
            self._failing_since = now
            self._last_complaint = now
            self.send_message.emit(
                f"<font color='red'>ADC read failed</font>: {error!r}."
                f" Retrying every {RETRY_SECONDS:g} s; outputs are held where"
                " they were"
            )
        elif now - self._last_complaint >= COMPLAIN_EVERY_SECONDS:
            self._last_complaint = now
            self.send_message.emit(
                f"ADC still not answering after {now - self._failing_since:.0f} s"
                f" ({self._read_failures} failed reads); still retrying"
            )

    def _note_read_recovered(self):
        if self._failing_since is None:
            return
        gap = time.monotonic() - self._failing_since
        self.send_message.emit(
            f"<font color='#1cad47'>ADC answering again</font> after {gap:.0f} s"
            f" and {self._read_failures} failed reads; the rows in between are"
            " missing from the file"
        )
        self._read_failures = 0
        self._failing_since = None
        self._last_complaint = None

    def _note_step_failure(self, error):
        """A row that could not be recorded, said once per complaint period."""
        now = time.monotonic()
        if (
            self._last_complaint is not None
            and now - self._last_complaint < COMPLAIN_EVERY_SECONDS
        ):
            return
        self._last_complaint = now
        self.send_message.emit(
            f"<font color='red'>ADC step failed</font>: {error!r}. The rows"
            " in hand were dropped and the reader goes on"
        )

    def hold_voltages(self, voltages):
        """Hold one set of raw voltages as the sample about to be recorded.

        One reading and a period's mean both arrive here, so the plasma
        current the PID sees is taken from whichever of the two is going
        into the row.
        """
        self.adc_voltages = voltages
        self.plasma_current = self.adc_voltages["Ip"]
        self.plasma_current_converted = self.adc_channels["Ip"].convert_hall(voltages)
        invalid = not math.isfinite(self.plasma_current_converted)
        if invalid != self._hall_reference_invalid:
            self.send_message.emit(
                "Hall supply reference invalid: Ip unavailable; PID output held"
                if invalid else "Hall supply reference recovered: Ip available"
            )
        self._hall_reference_invalid = invalid

    def collect_one_reading(self):
        """Wait until the next scan deadline, with processing inside the period."""
        wait = self._cadence.remaining(time.monotonic()) if self._cadence else self.sampling_time
        if not self.pause(wait):
            return False
        self.set_adc_datarate()
        return self.collect_data()

    def collect_period_average(self, period, deadline=None):
        """Convert every `INNER_SECONDS` through `period` and hold the mean.

        The mean of the *raw* voltages becomes `self.adc_voltages`, and is
        then converted exactly as a single reading is. Averaging the raw
        voltages and converting the mean, rather than converting each
        reading and averaging the results, keeps a recorded row
        self-consistent: converting the raw column of the CSV reproduces the
        converted column beside it, which is what anyone re-analysing the
        file will do. The other order would break that wherever the
        conversion is not linear, and the ion gauges are logarithmic.

        The period is measured with `time.monotonic()` and each conversion is
        due at a fixed offset from the period's start, so the conversions'
        own time comes out of the waits: N inner readings plus their
        overhead still sum to `period`, not to `period` plus overhead.

        Returns False if an abort cut the period short. Nothing is recorded
        then: a partial mean is not the sample the period promised.
        """
        started = time.monotonic()
        end = started + period if deadline is None else deadline
        readings = []
        while not self._abort:
            self.set_adc_datarate()
            if not self.collect_data():
                return False
            readings.append(dict(self.adc_voltages))
            now = time.monotonic()
            if now >= end:
                break
            due = min(started + INNER_SECONDS * len(readings), end)
            if due > now and not self.pause(due - now):
                return False
            if time.monotonic() >= end:
                break
        if self._abort:
            return False
        mean = mean_of_readings(readings)
        if mean is None:
            return False
        self.hold_voltages(mean)
        return True

    # MARK: main loop
    def acquisition_loop(self):
        """
        Reads ADC raw signals in a loop.
        Convert voltage to units.
        Send data back to main thread for ploting ad saving.

        One row per period either way. Below `AVERAGE_FROM_SECONDS` a period
        is one conversion; at and above it the period is filled with
        conversions and the row holds their mean.
        """
        if not self.plasma_current_setpopint:
            self.prep_pid()
        self._cadence = None
        self._last_sample_clock = None
        diagnostics = TimingDiagnostics("ADC timing", self.send_message.emit, clock=time.monotonic)
        try:
            while not self._abort:
                period = self.sampling_time
                now = time.monotonic()
                if self._cadence is None or self._cadence.period != period:
                    self._cadence = SampleClock(period, now)
                    self._last_sample_clock = None
                self._scan_seconds = 0.0
                self._slowest_channel = ("none", 0.0)
                if period >= AVERAGE_FROM_SECONDS:
                    collected = self.collect_period_average(period, self._cadence.due)
                else:
                    collected = self.collect_one_reading()
                if not collected:
                    break
                sampled = time.monotonic()
                interval = None if self._last_sample_clock is None else sampled - self._last_sample_clock
                self._last_sample_clock = sampled
                try:
                    self.put_new_data_in_dataframe()
                    self.update_processed_signals_dataframe()
                    if self.plasma_current_setpopint:
                        self.plasma_current_control()
                    if len(self._raw_rows) >= self.STEP:
                        self.send_processed_data_to_main_thread()
                except Exception as error:
                    self._note_step_failure(error)
                    self.clear_datasets()
                finished = time.monotonic()
                missed = self._cadence.advance(finished)
                diagnostics.observe(
                    {"period": period, "interval": interval,
                     "read": self._scan_seconds, "process": finished - sampled,
                     "cycle": finished - now},
                    missed=missed,
                    slow=bool(missed) or (interval is not None and interval > 1.5 * period),
                    channel=self._slowest_channel,
                )
            # Preserve completed rows when Stop interrupts the next wait/read.
            # A partial averaged period never entered these buffers.
            try:
                if self._raw_rows:
                    self.send_processed_data_to_main_thread()
            except Exception as error:
                self._note_step_failure(error)
                self.clear_datasets()
        finally:
            diagnostics.report()
            self.sigDone.emit(self.device_name)


if __name__ == "__main__":
    pass

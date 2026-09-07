"""
ADC communication

I2C アナログ入力ボード AIO-32/0RA-IRC

https://www.y2c.co.jp/i2c-r/aio-32-0ra-irc/
"""

import numpy as np
import pandas as pd
import time, datetime
from PyQt5 import QtCore
from simple_pid import PID

from controlunit.devices.adc_setter import AIO_32_0RA_IRC as adc
from .device import DeviceThread


#: The sampling time at which the reader starts averaging. Below it one
#: conversion per period is the right measurement: fast sampling is for
#: watching transients, and the instant is the point. At and above it the
#: period is long enough that a single ~1 ms conversion records whatever
#: noise sat on the line at that instant, while the run is an overnight or
#: weekend log where the period's mean is the truer number (owner decision
#: 2026-09-07).
AVERAGE_FROM_SECONDS = 1.0

#: How often the reader converts inside an averaged period. Fifty readings
#: fill the rig's ten-second period; five fill a one-second one.
INNER_SECONDS = 0.2


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
    __IGmode = 0  # Torr
    __IGrange = -3
    send_control_voltage = QtCore.pyqtSignal(float)
    send_zero_adjustment = QtCore.pyqtSignal(dict)
    set_plasma_current = QtCore.pyqtSignal(float)
    set_ig_mode_signal = QtCore.pyqtSignal(int)
    set_ig_range_signal = QtCore.pyqtSignal(int)
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
        IGmode: int, log o linear mode for Ionization Gauge measurements
        IGscale: range (scale) of Ionization Gauge in linear mode
        QMS_signal: int, "trigger" on or off. When on emits a signal from GPIO
        """
        self.prep_adc_board()
        self.adc_signals_columns = self.config["ADC Signal Names"]
        self.adc_values_columns = (
            self.config["ADC Additional Columns"] + self.config["ADC Signal Names"]
        )

        self.adc_values = pd.DataFrame(columns=self.adc_values_columns)
        self.converted_values = pd.DataFrame(columns=self.config["ADC Converted Names"])
        self.__qmsSignal = 0
        self._mfc_presets = {1: 0.0, 2: 0.0}
        self.plasma_current_setpopint = 0
        self.control_voltage = 0
        self.plasma_current = 0
        self.plasma_current_converted = 0
        self.zero_ip = 0
        self.zero_bu = 0
        self.zero_bd = 0
        self.sampling_time = self.config["Sampling Time"]
        self.pid_verbose = self.config.get("Verbose.Plasma Current PID", False)

        self.connect_signals()

    def connect_signals(self):
        """connect signals"""
        self.set_plasma_current.connect(
            self._set_plasma_current, type=QtCore.Qt.DirectConnection
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
    @QtCore.pyqtSlot(int)
    def set_ig_mode(self, IGmode: int):
        """
        Sets Ionization Gauge mode from GUI
        0: Torr
        1: Pa
        """
        self.__IGmode = IGmode
        return

    @QtCore.pyqtSlot(int)
    def set_ig_range(self, IGrange: int):
        """
        Sets Ionization Gauge range (scale) from GUI
        range: -8 ~ -3
        """
        self.__IGrange = IGrange
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
    def put_new_data_in_dataframe(self):
        """
        Put new data from ADC and GUI into pandas dataframe
        """
        now = datetime.datetime.now()
        dSec = (now - self.__startTime).total_seconds()
        new_data_row = pd.DataFrame(
            np.atleast_2d(
                [
                    now,
                    dSec,
                    self.__IGmode,
                    self.__IGrange,
                    self.__qmsSignal,
                    self._mfc_presets[1],
                    self._mfc_presets[2],
                    self.control_voltage,
                    *self.adc_voltages.values(),
                ]
            ),
            columns=self.adc_values_columns,
        )

        # self.adc_values = pd.concat([self.adc_values, new_data_row], ignore_index=True)
        # adjusting the dtypes to remove it FutureWarning
        self.adc_values = pd.concat(
            [self.adc_values.astype(new_data_row.dtypes), new_data_row],
            ignore_index=True,
        )

    def update_processed_signals_dataframe(self):
        """
        Update processed dataframe with new values
        """
        converted_values = []
        raw_adc_debug = self.config.get("Debug.Raw ADC", False)
        for name, value in self.adc_voltages.items():
            conversion = self.adc_channels[name].conversion
            if raw_adc_debug:
                converted_values.append(value)
            elif conversion.__name__ == "ionization_gauge":
                converted_values.append(
                    conversion(value, self.__IGmode, self.__IGrange)
                )
            else:
                converted_values.append(conversion(value))

        converted_values = pd.DataFrame(
            np.atleast_2d(converted_values), columns=self.config["ADC Converted Names"]
        )

        # self.converted_values = pd.concat([self.converted_values, converted_values], ignore_index=True)
        # Fixing FutureError
        self.converted_values = pd.concat(
            [self.converted_values.astype(converted_values.dtypes), converted_values],
            ignore_index=True,
        )

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
        newdata = self.adc_values.join(self.converted_values)
        self.data_ready.emit([newdata, self.device_name])
        self.clear_datasets()

    # MARK: Data clear
    def clear_datasets(self):
        """
        Remove data from temporary dataframes
        """
        self.adc_values = self.adc_values.iloc[0:0]
        self.converted_values = self.converted_values.iloc[0:0]

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
        """set dac voltage, controlling cathode current"""
        self.plasma_current_setpopint = plasma_current_setpopint
        self.pid.setpoint = self.plasma_current_setpopint
        if plasma_current_setpopint == 0:
            self.reset_current_control()
        return

    def reset_current_control(self):
        self.prep_pid()
        self.set_cathode_current(0)

    def update_pid_coefficients(self, pid_coefficients):
        """update pid"""
        # self.pid.Ki = 1.0
        self.pid.tunings = pid_coefficients
        # self.signal_send_pid.emit(self.pid.tunings)

    def prep_pid(self):
        """
        Set PID parameters
        ouptput is control voltage, from 0 to 5000 V.
        """
        p, i, d = 30, 40, 0
        self.pid = PID(p, i, d, setpoint=self.plasma_current_setpopint)
        self.pid.output_limits = (0, 4500)
        # self.pid.integral_limits = (-1250, 1250)
        self.pid.sample_time = self.sampling_time * self.STEP
        # self.signal_send_pid.emit(self.pid.tunings)

    def plasma_current_control(self):
        """
        PID control plasma current
        """
        baseline = 1000 #2000 #mV, corresponds to 16A
        output = self.pid(self.plasma_current_converted - self.zero_ip)
        output = output + baseline
        self.set_cathode_current(output)
        if self.pid_verbose:
            print(
                self.pid.setpoint,
                output,
                self.plasma_current_converted - self.zero_ip,
            )

    # MARK: start
    @QtCore.pyqtSlot()
    def start(self):
        """
        Start acquisition loop
        """
        self.acquisition_loop()

    # MARK: read voltages
    def collect_data(self):
        """
        Read ADC voltages for selected channels
        Can change ADC gain at any time by updating self.adc_channels
        """
        self.adc_voltages = {
            ch.name: self.aio.analog_read_volt(ch.channel, *self.adc_datarate, ch.gain)
            for _, ch in self.adc_channels.items()
        }
        self.hold_voltages(self.adc_voltages)

    def hold_voltages(self, voltages):
        """Hold one set of raw voltages as the sample about to be recorded.

        One reading and a period's mean both arrive here, so the plasma
        current the PID sees is taken from whichever of the two is going
        into the row.
        """
        self.adc_voltages = voltages
        self.plasma_current = self.adc_voltages["Ip"]
        self.plasma_current_converted = self.adc_channels["Ip"].conversion(
            self.plasma_current
        )

    def collect_one_reading(self):
        """The fast path's whole measurement: wait a period, convert once."""
        if not self.pause(self.sampling_time):
            return False
        self.set_adc_datarate()
        self.collect_data()
        return True

    def collect_period_average(self, period):
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
        end = started + period
        readings = []
        while not self._abort:
            self.set_adc_datarate()
            self.collect_data()
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
        totalStep = 0
        step = 0

        self.prep_pid()
        # self.set_cathode_current(325)

        while not (self._abort):
            # Read afresh, so a sampling time changed mid-run through
            # `set_sampling_time` takes effect at the next period.
            period = self.sampling_time
            # Either path wakes within a tenth of a second of an abort,
            # however long the period; a stop must not wait one out.
            if period >= AVERAGE_FROM_SECONDS:
                if not self.collect_period_average(period):
                    break
            elif not self.collect_one_reading():
                break
            self.put_new_data_in_dataframe()
            self.update_processed_signals_dataframe()

            if self.plasma_current_setpopint:
                self.plasma_current_control()

            if self.STEP == 1:
                self.send_processed_data_to_main_thread()
                continue

            if step % (self.STEP - 1) == 0 and step != 0:
                # self.calculate_averaged_signals()
                self.send_processed_data_to_main_thread()
                step = 0
            else:
                step += 1
            totalStep += 1
        else:
            # self.calculate_averaged_signals()
            self.send_processed_data_to_main_thread()

        self.sigDone.emit(self.device_name)
        return


if __name__ == "__main__":
    pass

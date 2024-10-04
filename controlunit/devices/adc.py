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


# MARK: ADC
class ADC(DeviceThread):
    __IGmode = 0  # Torr
    __IGrange = -3
    send_control_voltage = QtCore.pyqtSignal(float)
    send_zero_adjustment = QtCore.pyqtSignal(dict)
    set_plasma_current = QtCore.pyqtSignal(float)

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
        self.plasma_current = 0
        self.zero_ip = 0
        self.zero_bu = 0
        self.sampling_time = self.config["Sampling Time"]

        self.connect_signals()

    def connect_signals(self):
        """connect signals"""
        self.set_plasma_current.connect(self._set_plasma_current)

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
    def set_ig_mode(self, IGmode: int):
        """
        Sets Ionization Gauge mode from GUI
        0: Torr
        1: Pa
        """
        self.__IGmode = IGmode
        return

    def set_ig_range(self, IGrange: int):
        """
        Sets Ionization Gauge range (scale) from GUI
        range: -8 ~ -3
        """
        self.__IGrange = IGrange
        return

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
                    self.plasma_current_setpopint,
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
        for name, value in self.adc_voltages.items():
            conversion = self.adc_channels[name].conversion
            if conversion.__name__ == "ionization_gauge":
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

    def set_zero_ip(self):
        """set zero Ip"""
        if self.converted_values["Ip_c"].mean() is not np.nan:
            self.zero_ip = self.converted_values["Ip_c"].mean()
        self.send_zero_adjustment.emit({"Ip": self.zero_ip, "Bu": self.zero_bu})

    def set_cathode_current(self, control_voltage):
        """Send cathode control voltage to main thread"""
        self.plasma_current_setpopint = control_voltage
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
        p, i, d = 1, 0, 0
        self.pid = PID(p, i, d, setpoint=self.plasma_current_setpopint)
        self.pid.output_limits = (0, 2600)
        self.pid.sample_time = self.sampling_time * self.STEP
        # self.signal_send_pid.emit(self.pid.tunings)

    def plasma_current_control(self):
        """
        PID control plasma current
        """
        output = self.pid(self.plasma_current - self.zero_ip)
        self.set_cathode_current(output)
        #print(self.pid.components)

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
        self.plasma_current = self.adc_voltages["Ip"]

    # MARK: main loop
    def acquisition_loop(self):
        """
        Reads ADC raw signals in a loop.
        Convert voltage to units.
        Send data back to main thread for ploting ad saving.
        """
        totalStep = 0
        step = 0

        self.prep_pid()
        # self.set_cathode_current(325)

        while not (self._abort):
            time.sleep(self.sampling_time)
            self.set_adc_datarate()
            self.collect_data()
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
            self.__app.processEvents()
        else:
            # self.calculate_averaged_signals()
            self.send_processed_data_to_main_thread()

        self.sigDone.emit(self.device_name)
        return


if __name__ == "__main__":
    pass

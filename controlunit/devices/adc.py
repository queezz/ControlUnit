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

    def __init__(self, device_name, app, startTime, config):
        super().__init__(device_name, app, startTime, config)
        self.__app = app
        self.device_name = device_name
        self.__startTime = startTime
        self._abort = False
        self.config = config
        self.prep_adc_board()
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
        self.adc_signals_columns = self.config["ADC Signal Names"]
        self.adc_values_columns = (
            self.config["ADC Additional Columns"] + self.config["ADC Signal Names"]
        )

        self.adc_values = pd.DataFrame(columns=self.adc_values_columns)
        self.converted_values = pd.DataFrame(columns=self.config["ADC Converted Names"])
        self.__qmsSignal = 0
        self.__PresetV_mfc1 = 0
        self.__PresetV_mfc2 = 0
        self.plasma_current_setpopint = 0
        self.plasma_current = 0
        self.zero_ip = 0
        self.zero_bu = 0
        self.sampling_time = self.config["Sampling Time"]

    # MARK: IG mode
    def setIGmode(self, IGmode: int):
        """
        Sets Ionization Gauge mode from GUI
        0: Torr
        1: Pa
        """
        self.__IGmode = IGmode
        return

    def setIGrange(self, IGrange: int):
        """
        Sets Ionization Gauge range (scale) from GUI
        range: -8 ~ -3
        """
        self.__IGrange = IGrange
        return

    def setQmsSignal(self, signal: int):
        """
        Sets "trigger" signal from GUI for syncing QMS and RasPi data
        waiting: 0
        running: 1
        """
        self.__qmsSignal = signal
        return

    def setPresetV_mfc1(self, voltage: int):
        """
        Sets Preset Voltage of Mas Flow Control for H2 from GUI
        range: 0 ~ 5000 mV
        """
        self.__PresetV_mfc1 = voltage / 1000
        return

    def setPresetV_mfc2(self, voltage: int):
        """
        Sets Preset Voltage of Mas Flow Control for H2 from GUI
        range: 0 ~ 5000 mV
        """
        self.__PresetV_mfc2 = voltage / 1000
        return

    # MARK: start
    @QtCore.pyqtSlot()
    def start(self):
        """
        Start acquisition loop
        """
        self.acquisition_loop()

    def setGain(self, gain):
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

    def set_adc_datarate(self):
        """
        Communicate with ADC
        """
        self.adc_datarate = [self.aio.DataRate.DR_860SPS]

    # MARK: read voltages
    def read_adc_voltages(self):
        """
        Read ADC voltages for selected channels
        Can change ADC gain at any time by updating self.adc_channels
        """
        self.adc_voltages = {
            ch.name: self.aio.analog_read_volt(ch.channel, *self.adc_datarate, ch.gain)
            for _, ch in self.adc_channels.items()
        }
        self.plasma_current = self.adc_voltages["Ip"]

    # MARK: Data
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
                    self.__PresetV_mfc1,
                    self.__PresetV_mfc2,
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

    # MARK: send data
    def send_processed_data_to_main_thread(self):
        """
        Sends processed data to main thread in main.py
        Clears temporary dataframes to reset memory consumption.
        """
        newdata = self.adc_values.join(self.converted_values)
        self.send_step_data.emit([newdata, self.device_name])
        self.clear_datasets()

    # MARK: Clear Data
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

    def set_plasma_current(self, plasma_current_setpopint: int):
        self.plasma_current_setpopint = plasma_current_setpopint
        self.pid.setpoint = self.plasma_current_setpopint
        return

    def update_pid_coefficients(self, pid_coefficients):
        """update pid"""
        # self.pid.Ki = 1.0
        self.pid.tunings = pid_coefficients
        # self.signal_send_pid.emit(self.pid.tunings)

    def prep_pid(self):
        """
        Set PID parameters
        ouptput is control voltage, from 0 to 5 V.
        """
        p, i, d = 0.1, 0, 0
        self.pid = PID(p, i, d, setpoint=self.plasma_current_setpopint)
        self.pid.output_limits = (0, 5)
        self.pid.sample_time = self.sampling_time * self.STEP
        # self.signal_send_pid.emit(self.pid.tunings)

    def plasma_current_control(self):
        """
        PID control plasma current
        """
        self.set_cathode_current(self.pid(self.plasma_current - self.zero_ip))

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
            self.read_adc_voltages()
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

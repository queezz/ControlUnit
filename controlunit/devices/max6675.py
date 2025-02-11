"""
MAX6675 communication

Thermocouple sensor with a thermistor.

https://www.analog.com/media/en/technical-documentation/data-sheets/max6675.pdf
"""

import numpy as np
import pandas as pd
import time, datetime
from PyQt5 import QtCore

from .device import DeviceThread
from heatercontrol import HeaterContol
from controlunit.ui.text_shortcuts import RED, RESET


try:
    import pigpio
except ImportError as e:
    print(RED + "worker_max6675.py Error: " + RESET + f"{e}")
    from devices.dummy import pigpio


# MARK: MAX6675
class MAX6675(DeviceThread):

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, device_name, app, startTime, config, pi):
        super().__init__(device_name, app, startTime, config)
        self.__app = app
        self.device_name = device_name
        self.__startTime = startTime
        self.config = config
        self.__abort = False
        self.pi = pi
        self.init()

    def init(self):
        """
        needs pigpio daemon
        """
        self.columns = ["date", "time", "T", "PresetT"]
        self.data = pd.DataFrame(columns=self.columns)
        self.temperature_setpoint = 0
        self.sampling_time = self.config["Sampling Time"]
        if self.sampling_time < 0.25:
            self.sampling_time = 0.25

        # self.pi = pigpio.pi()
        self.__sumE = 0
        self.__exE = 0

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.device_name)
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True

    def setPresetTemp(self, newTemp: int):
        self.temperature_setpoint = newTemp
        return

    @QtCore.pyqtSlot()
    def start(self):
        """
        Start data acquisition
        """
        self.acquisition_loop()

    def init_heater_control(self):
        self.membrane_heater = HeaterContol(self.pi, self.__app)
        self.thread = QtCore.QThread()
        self.thread.setObjectName("heater current")
        self.membrane_heater.moveToThread(self.thread)
        self.thread.started.connect(self.membrane_heater.work)
        self.sigAbortHeater.connect(self.membrane_heater.setAbort)
        self.thread.start()

    def init_thermocouple(self):
        """
        Select MAX6675 sensor on the SPI
        Need to start PIGPIO daemon
        """
        self.sensor = self.pi.spi_open(self.config["MAX6675 Channel"], 1000000, 0)

    def read_thermocouple(self):
        """
        Read MAX6675 sensor output
        """
        self.temperature = -1000  # If reading fails

        c, d = self.pi.spi_read(self.sensor, 2)  # if c==2: ok else: not good
        if c == 2:
            word = (d[0] << 8) | d[1]
            if (word & 0x8006) == 0:  # Bits 15, 2, and 1 should be zero.
                self.temperature = (word >> 3) / 4.0
            else:
                print("MAX6675: bad reading {:b} (read_thermocuple())".format(word))

    def send_processed_data_to_main_thread(self):
        """
        Send processed data to main.py
        """
        self.data_ready.emit([self.data, self.device_name])

    def clear_datasets(self):
        """
        Remove data from temporary dataframes
        """
        self.data = self.data.iloc[0:0]

    def update_dataframe(self):
        """
        Append new reading to dataframe
        """
        now = datetime.datetime.now()
        dSec = (now - self.__startTime).total_seconds()
        # ["date", "time", "T", "PresetT"]
        new_row = pd.DataFrame(
            np.atleast_2d([now, dSec, self.temperature, self.temperature_setpoint]),
            columns=self.columns,
        )
        self.data = pd.concat([self.data, new_row], ignore_index=True)

    def calculate_average(self):
        """
        Average signal
        """
        self.average = self.data["T"].mean()

    # MARK: main loop
    @QtCore.pyqtSlot()
    def acquisition_loop(self):
        """
        Temperature acquisition and Feedback Control loop
        """
        self.init_thermocouple()
        self.init_heater_control()

        step = 0

        while not (self.__abort):
            time.sleep(self.sampling_time)
            self.read_thermocouple()
            self.update_dataframe()

            if step % (self.STEP - 1) == 0 and step != 0:
                self.calculate_average()
                self.temperature_control()
                self.send_processed_data_to_main_thread()
                self.clear_datasets()
                step = 0
            else:
                step += 1
            self.__app.processEvents()
        else:
            # ABORTING
            self.calculate_average()
            self.send_processed_data_to_main_thread()
            self.sigAbortHeater.emit()
            self.__sumE = 0
            self.thread.quit()
            self.thread.wait()
            self.pi.spi_close(self.sensor)
            # self.pi.stop()

        self.thread = None
        self.sigDone.emit(self.device_name)

    # MARK: PID
    def temperature_control(self):
        """
        Shouldn't the self.sampling_time here be 0.25, not the one for ADC?
        TODO: update to simple-pid as in TemperatureControl
        https://github.com/queezz/TemperatureControl
        """
        e = self.temperature_setpoint - self.average
        integral = self.__sumE + e * self.sampling_time
        derivative = (e - self.__exE) / self.sampling_time

        # TODO: 調整 (Adjustment)
        Kp = 3.5
        Ki = 0.06
        Kd = 0

        # TODO: 調整 (Adjustment)
        if integral < -0.5:
            integral = 0

        if e >= 0:
            output = Kp * e + Ki * integral + Kd * derivative
            output = output * 0.0002
            self.membrane_heater.setOnLight(max(output, 0))
        else:
            self.membrane_heater.setOnLight(0)
        self.__exE = e
        self.__sumE = integral


if __name__ == "__main__":
    pass

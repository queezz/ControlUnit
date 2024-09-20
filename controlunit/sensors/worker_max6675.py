"""
MAX6675 worker
"""
import numpy as np
import pandas as pd
import time, datetime
from PyQt5 import QtCore

from .worker import Worker
from heatercontrol import HeaterContol

STEP = 3

RED = "\033[1;31m"
GREEN = "\033[1;32m"
BLUE = "\033[1;34m"
RESET = "\033[0m"
GOOD = "\U00002705"
BAD = "\U0000274C"


try:
    import pigpio
except ImportError as e:
    print(RED + "worker_max6675.py Error: " + RESET + f"{e}")
    from sensors.dummy import pigpio


# MARK: MAX6675
class MAX6675(Worker):

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, sensor_name, app, startTime, config):
        super().__init__(sensor_name, app, startTime, config)
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.config = config
        self.__abort = False

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.sensor_name)
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True

    def setTempWorker(self, presetTemp: int):
        """
        needs pigpio daemon
        """
        self.columns = ["date", "time", "T", "PresetT"]
        self.data = pd.DataFrame(columns=self.columns)
        self.temperature_setpoint = presetTemp
        self.sampling = self.config["Sampling Time"]
        if self.sampling < 0.25:
            self.sampling = 0.25


        self.pi = pigpio.pi()
        self.__sumE = 0
        self.__exE = 0

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
        self.send_step_data.emit([self.data, self.sensor_name])

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
            np.atleast_2d([now, dSec, self.temperature, self.temperature_setpoint]), columns=self.columns
        )
        self.data = pd.concat([self.data, new_row], ignore_index=True)

    def calculate_average(self):
        """
        Average signal
        """
        self.average = self.data["T"].mean()

    @QtCore.pyqtSlot()
    def acquisition_loop(self):
        """
        Temperature acquisition and Feedback Control loop
        """
        self.init_thermocouple()
        self.init_heater_control()

        step = 0

        while not (self.__abort):
            time.sleep(self.sampling)
            self.read_thermocouple()
            self.update_dataframe()

            if step % (STEP - 1) == 0 and step != 0:
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
            self.pi.stop()

        self.thread = None
        self.sigDone.emit(self.sensor_name)

    def temperature_control(self):
        """
        Shouldn't the self.sampling here be 0.25, not the one for ADC?
        TODO: update to simple-pid as in TemperatureControl 
        https://github.com/queezz/TemperatureControl
        """
        e = self.temperature_setpoint - self.average
        integral = self.__sumE + e * self.sampling
        derivative = (e - self.__exE) / self.sampling

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

    def __controlTemp1(self, aveTemp: float, steps: int):
        if steps <= 0:
            d = self.temperature_setpoint - aveTemp[0, 1]
            if d <= 1.5:
                return -1
            elif d >= 15:
                return int(d * 10)
            else:
                return int(d + 1)
        else:
            return steps
    
if __name__ == "__main__":
    pass

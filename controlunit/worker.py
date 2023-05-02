"""
Worker threads

Constants, such as channel for ADC, GPIO on RasPi, column names for dataframes,
are specified in channels.py. Adjust values there to affect the whole of Contorlunit.
"""
from channels import *
import time, datetime
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from customTypes import Signals  # import for now, then get rid of Signals
from heatercontrol import HeaterContol
from readsettings import read_settings

# Converting raw signals to data
from conversions import ionization_gauge, hall_current_sensor, pfeiffer_single_gauge

TEST = False
PRINTTHREADINFO = False
# Number of data points for collection, steps%STEP == 0
STEP = 3

try:
    from AIO import AIO_32_0RA_IRC as adc
    import pigpio
except:
    print("no pigpio or AIO")
    TEST = True
    import pigpioplug as pigpio

# must inherit QtCore.QObject in order to use 'connect'
class Worker(QtCore.QObject):
    """
    send_message usage:
    self.send_message.emit(f"Your Message Here to pass to main.py")
    """

    send_step_data = QtCore.pyqtSignal(list)
    sigDone = QtCore.pyqtSignal(str)
    send_message = QtCore.pyqtSignal(str)

    def __init__(self, sensor_name, app, startTime):
        super().__init__()

        self.__id = id
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime

    def print_checks(self):
        attrs = vars(self)

        if PRINTTHREADINFO:
            print("Thread Checks:")
            print(", ".join(f"{i}" for i in attrs.items()))
            print("ID:", self.__id)
            print("End Thread Checks")

    def set_thread_name(self):
        """Set Thread name and ID, signal them to the log browser"""
        threadName = QtCore.QThread.currentThread().objectName()
        print(threadName)
        return

    def getStartTime(self):
        return self.__startTime

    def setSampling(self, sampling):
        """Set sampling time for ADC"""
        self.sampling = sampling
        print(f"Updated sampling to {sampling}")

    def enable_pigpio(self):
        """
        pigpiod is needed to acces RasPi GPIO
        Used in, i.e., temperature control
        https://raspberrypi.stackexchange.com/questions/70568/how-to-run-pigpiod-on-boot
        """
        from os import system

        system("sudo pigpiod")


class MAX6675(Worker):

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, sensor_name, app, startTime):
        super().__init__(sensor_name, app, startTime)
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.__abort = False

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.sensor_name)
        self.send_message.emit(message)
        print(message)
        self.__abort = True

    def setTempWorker(self, presetTemp: int):
        """
        needs pigpio daemon
        """
        self.columns = ["date", "time", "T", "PresetT"]
        self.data = pd.DataFrame(columns=self.columns)
        self.temperature_setpoint = presetTemp
        self.sampling = read_settings()["samplingtime"]

        if TEST:
            print("needs pigpio to access SPI")
            return

        self.enable_pigpio()

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
        self.sensor = self.pi.spi_open(CHT, 1000000, 0)

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

    def calc_average(self):
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
            # Temperature sampling time. For MAX6675 min read time = 0.25s
            time.sleep(0.25)
            self.read_thermocouple()
            self.update_dataframe()

            if step % (STEP - 1) == 0 and step != 0:
                self.calc_average()
                self.temperature_control()
                self.send_processed_data_to_main_thread()
                self.clear_datasets()
                step = 0
            else:
                step += 1
            self.__app.processEvents()
        else:
            # ABORTING
            self.calc_average()
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


class ADC(Worker):
    def __init__(self, sensor_name, app, startTime):
        super().__init__(sensor_name, app, startTime)
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.__abort = False

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.sensor_name)
        self.send_message.emit(message)
        print(message)
        self.__abort = True

    def init_adc_worker(self, IGmode: int, IGrange: int):
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
        self.adc_voltage_columns = ADCSIGNALS
        self.adc_processed_columns = ADCCONVERTED
        self.adc_columns = ADCCOLUMNS

        self.__adc_data = pd.DataFrame(columns=self.adc_columns)
        self.__calcData = pd.DataFrame(columns=self.adc_processed_columns)
        self.__IGmode = IGmode
        self.__IGrange = IGrange
        self.__qmsSignal = 0
        self.sampling = read_settings()["samplingtime"]

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

    @QtCore.pyqtSlot()
    def start(self):
        """
        Set Thread ID and name, then run corresponding "plot" function.
        "plot" functions in the main.py are main data acquisition loops (threads).
        """
        self.set_thread_name()
        self.acquisition_loop()

    def set_adc_channels(self):
        """
        Setup ADC channels: numbers, voltages, etc.

        Results
        -------
        self.adc_channels: dict
            dictionary of channels with their voltage scales
        """
        self.CHNLS = [CHP1, CHP2, CHIP]
        scale10 = [CHP1, CHP2]
        scale5 = [CHIP]
        self.adc_channels = {CH: {"pga": self.aio.PGA.PGA_10_0352V} for CH in scale10}
        for CH in scale5:
            self.adc_channels[CH] = {"pga": self.aio.PGA.PGA_5_0176V}

    def adc_init(self):
        """
        Initiates an instance of AIO_32_0RA_IRC from AIO.py
        Address: 0x49, 0x3E
        Why this addresses?
        """
        self.aio = adc(0x49, 0x3E)

    def get_adc_datarate(self):
        """
        Communicate with ADC
        """
        self.adc_datarate = [self.aio.DataRate.DR_860SPS]

    def read_adc_voltages(self):
        """
        Read ADC voltages for selected channels
        """
        self.adc_voltages = [
            self.aio.analog_read_volt(CH, *self.adc_datarate, **self.adc_channels[CH]) for CH in self.CHNLS
        ]

    def put_new_data_in_dataframe(self):
        """
        Put new data from ADC and GUI into pandas dataframe
        """
        now = datetime.datetime.now()
        dSec = (now - self.__startTime).total_seconds()
        new_data_row = pd.DataFrame(
            np.atleast_2d([now, dSec, *self.adc_voltages, self.__IGmode, self.__IGrange, self.__qmsSignal,]),
            columns=self.adc_columns,
        )
        self.__adc_data = pd.concat([self.__adc_data, new_data_row], ignore_index=True)

    def update_processed_signals_dataframe(self):
        """
        Update processed dataframe with new values
        TODO: add a list of signals with their calc functions somewhere
        to make this automatc
        """
        p1_v, p2_v, ip_v = self.adc_voltages
        new_calc_row = pd.DataFrame(
            np.atleast_2d(
                [
                    ionization_gauge(p1_v, self.__IGmode, self.__IGrange),
                    pfeiffer_single_gauge(p2_v),
                    hall_current_sensor(ip_v),
                ]
            )
        )
        self.__calcData = pd.concat([self.__calcData, new_calc_row], ignore_index=True)

    def calculate_averaged_signals(self):
        """
        Calculate averages for the calibrated signals to show them in GUI
        """
        self.averages = self.__calcData.mean().values

    def send_processed_data_to_main_thread(self):
        """
        Sends processed data to main thread in main.py
        Clears temporary dataframes to reset memory consumption.
        """
        newdata = self.__adc_data.join(self.__calcData)
        print(self.__calcData)
        self.send_step_data.emit([newdata, self.sensor_name])
        self.clear_datasets()

    def clear_datasets(self):
        """
        Remove data from temporary dataframes
        """
        self.__adc_data = self.__adc_data.iloc[0:0]
        self.__calcData = self.__calcData.iloc[0:0]

    def acquisition_loop(self):
        """
        Reads ADC raw signals in a loop.
        Convert voltage to units.
        Send data back to main thread for ploting ad saving.
        """
        self.adc_init()
        self.set_adc_channels()
        totalStep = 0
        step = 0

        while not (self.__abort):
            time.sleep(self.sampling)
            self.get_adc_datarate()
            self.read_adc_voltages()
            self.put_new_data_in_dataframe()
            self.update_processed_signals_dataframe()

            if step % (STEP - 1) == 0 and step != 0:
                self.calculate_averaged_signals()
                self.send_processed_data_to_main_thread()
                step = 0
            else:
                step += 1
            totalStep += 1
            self.__app.processEvents()
        else:
            self.calculate_averaged_signals()
            self.send_processed_data_to_main_thread()

        self.sigDone.emit(self.sensor_name)
        return


if __name__ == "__main__":
    pass

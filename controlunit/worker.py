"""
Worker threads

Constants, such as channel for ADC, GPIO on RasPi, column names for dataframes,
are specified in channels.py. Adjust values there to affect the whole of Contorlunit.
"""
# from channels import *
import time, datetime
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from heatercontrol import HeaterContol

# Converting raw signals to data
from conversions import ionization_gauge, hall_current_sensor, pfeiffer_single_gauge, baratron

TEST = False
PRINTTHREADINFO = False
# Number of data points for collection, steps%STEP == 0
STEP = 3

try:
    from AIO import AIO_32_0RA_IRC as adc
    from DAC import DAC8532
    import pigpio
    import RPi.GPIO as GPIO
except:
    print("no pigpio or AIO")
    TEST = True
    import pigpioplug as pigpio
    import RPi.GPIO as GPIO

# must inherit QtCore.QObject in order to use 'connect'
class Worker(QtCore.QObject):
    """
    send_message usage:
    self.send_message.emit(f"Your Message Here to pass to main.py")
    """

    send_step_data = QtCore.pyqtSignal(list)
    sigDone = QtCore.pyqtSignal(str)
    send_message = QtCore.pyqtSignal(str)

    def __init__(self, sensor_name, app, startTime, config):
        super().__init__()

        self.__id = id
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.config = config

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
        """Set sampling time"""
        self.sampling = sampling
        # print(f"Updated sampling to {sampling}")


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

        if TEST:
            print("needs pigpio to access SPI")
            return

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

class DAC8532(Worker):

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
        self.dac_init()

    def init_dac_worker(self, presetVoltage: int):
        pass

    def dac_init(self):
        try:
            print("DAC started correctry\r\n")
            
            self.DAC = DAC8532.DAC8532()
            self.DAC.DAC8532_Out_Voltage(DAC8532.channel_A, 0)
            self.DAC.DAC8532_Out_Voltage(DAC8532.channel_B, 0)
        

        except :
            self.DAC.DAC8532_Out_Voltage(DAC8532.channel_A, 0)
            self.DAC.DAC8532_Out_Voltage(DAC8532.channel_B, 0)
            GPIO.cleanup()
            print ("\r\nProgram end     ")
            exit()

    def output_voltage(self, channel, voltage):
        if channel == 1:
            self.DAC.DAC8532_Out_Voltage(DAC8532.channel_A, voltage)
        elif channel == 2:
            self.DAC.DAC8532_Out_Voltage(DAC8532.channel_B, voltage)
        else:
            print("wrong channel")


class ADC(Worker):
    def __init__(self, sensor_name, app, startTime, config):
        super().__init__(sensor_name, app, startTime, config)
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.__abort = False
        self.config = config
        self.adc_init()

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.sensor_name)
        # self.send_message.emit(message)
        # print(message)
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
        self.adc_signals_columns = self.config["ADC Signal Names"]
        self.adc_values_columns = self.config["ADC Additional Columns"] + self.config["ADC Signal Names"]

        self.adc_values = pd.DataFrame(columns=self.adc_values_columns)
        self.converted_values = pd.DataFrame(columns=self.config["ADC Converted Names"])
        self.__IGmode = IGmode
        self.__IGrange = IGrange
        self.__qmsSignal = 0
        self.sampling = self.config["Sampling Time"]

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

    def adc_init(self):
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

    def read_adc_voltages(self):
        """
        Read ADC voltages for selected channels
        Can change ADC gain at any time by updating self.adc_channels
        """
        self.adc_voltages = {
            ch.name: self.aio.analog_read_volt(ch.channel, *self.adc_datarate, ch.gain)
            for _, ch in self.adc_channels.items()
        }

    def put_new_data_in_dataframe(self):
        """
        Put new data from ADC and GUI into pandas dataframe
        """
        now = datetime.datetime.now()
        dSec = (now - self.__startTime).total_seconds()
        new_data_row = pd.DataFrame(
            np.atleast_2d(
                [now, dSec, self.__IGmode, self.__IGrange, self.__qmsSignal, *self.adc_voltages.values()]
            ),
            columns=self.adc_values_columns,
        )
        self.adc_values = pd.concat([self.adc_values, new_data_row], ignore_index=True)

    def update_processed_signals_dataframe(self):
        """
        Update processed dataframe with new values        
        """
        converted_values = []
        for name, value in self.adc_voltages.items():
            conversion = self.adc_channels[name].conversion
            if conversion.__name__ == "ionization_gauge":
                converted_values.append(conversion(value, self.__IGmode, self.__IGrange))
            else:
                converted_values.append(conversion(value))

        converted_values = pd.DataFrame(
            np.atleast_2d(converted_values), columns=self.config["ADC Converted Names"]
        )

        self.converted_values = pd.concat([self.converted_values, converted_values], ignore_index=True)

    def calculate_averaged_signals(self):
        """
        Calculate averages for the calibrated signals to show them in GUI
        """
        self.averages = self.converted_values.mean().values

    def send_processed_data_to_main_thread(self):
        """
        Sends processed data to main thread in main.py
        Clears temporary dataframes to reset memory consumption.
        """
        newdata = self.adc_values.join(self.converted_values)
        self.send_step_data.emit([newdata, self.sensor_name])
        self.clear_datasets()

    def clear_datasets(self):
        """
        Remove data from temporary dataframes
        """
        self.adc_values = self.adc_values.iloc[0:0]
        self.converted_values = self.converted_values.iloc[0:0]

    def acquisition_loop(self):
        """
        Reads ADC raw signals in a loop.
        Convert voltage to units.
        Send data back to main thread for ploting ad saving.
        """
        totalStep = 0
        step = 0

        while not (self.__abort):
            time.sleep(self.sampling)
            self.set_adc_datarate()
            self.read_adc_voltages()
            self.put_new_data_in_dataframe()
            self.update_processed_signals_dataframe()

            if step % (STEP - 1) == 0 and step != 0:
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

        self.sigDone.emit(self.sensor_name)
        return


if __name__ == "__main__":
    pass

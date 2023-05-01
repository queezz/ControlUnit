import time, datetime
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from customTypes import Signals  # import for now, then get rid of Signals
from electricCurrent import ElectricCurrent, hall_to_current
from readsettings import read_settings

# Converting raw signals to data
from ionizationGauge import maskIonPres, calcIGPres
from pfeiffer import maskPfePres, calcPfePres

TEST = False

# Specify cable connections to ADC
CHP1 = 0  # 15, Ionization Gauge
CHP2 = 1  # 16, Pfeiffer single gauge
CHIP = 2  # 5, Plasma current, Hall effect sensor
CHT = 0  # 0 -> CS0, 1 -> CS1
PRINTTHREADINFO = False

# Make Worker superclass
# Make separate class for each sensor, keep it clean!

# Number of data points for collection, steps%STEP == 0
STEP = 3

try:
    from AIO import AIO_32_0RA_IRC as adc
    import pigpio
except:
    print("no pigpio or AIO")
    TEST = True
    import pigpioplug as pigpio

# TT - if gets into setting up membrane heater current
TT = True  # What is this? Used in Temperature Feedback Control


# must inherit QtCore.QObject in order to use 'connect'
class Worker(QtCore.QObject):
    # Change to a dictionary. Trancparency!
    sigStep = QtCore.pyqtSignal(np.ndarray, np.ndarray, np.ndarray, dict, datetime.datetime)
    sigDone = QtCore.pyqtSignal(int, dict)
    sigMsg = QtCore.pyqtSignal(str)

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, id, app, sensor_name, startTime):
        super().__init__()

        self.__id = id
        self.__app = app
        self.__sensor_name = sensor_name
        self.__startTime = startTime
        self.__abort = False

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

        self.sigMsg.emit("Running worker #{} from thread '{}' (#{})".format(self.__id, threadName))

    # MARK: - Getters
    def getStartTime(self):
        return self.__startTime

    def setSampling(self, sampling):
        """Set sampling time for ADC"""
        self.sampling = sampling
        print(f"Updated sampling to {sampling}")

    @QtCore.pyqtSlot()
    def abort(self):
        self.sigMsg.emit("Worker #{} aborting acquisition".format(self.__id))
        self.__abort = True


class MAX6675(Worker):
    def __init__(self, id, app, sensor_name, startTime):
        super().__init__(id, app, sensor_name, startTime)
        self.__id = id
        self.__app = app
        self.__sensor_name = sensor_name
        self.__startTime = startTime
        self.__abort = False

    # set temperature worker
    def setTempWorker(self, presetTemp: int):
        self.__rawData = np.zeros(shape=(STEP, 4))
        self.__presetTemp = presetTemp
        self.sampling = read_settings()["samplingtime"]

        # PID control
        if not TEST:
            self.pi = pigpio.pi()
            self.__onLight = 0.1
            self.__sumE = 0
            self.__exE = 0
        else:
            print("needs pigpio to access SPI")

    # MARK: - Setters
    def setPresetTemp(self, newTemp: int):
        self.__presetTemp = newTemp
        return

        # MARK: - Methods

    @QtCore.pyqtSlot()
    def start(self):
        """Set Thread ID and name, then run corresponding "plot" function.
        "plot" functions are main data acquisition loops.
        """
        # self.__setThread()
        self.readT()

    # temperature plot
    @QtCore.pyqtSlot()
    def readT(self):
        """Temperature acquisition and Feedback Control function"""
        # Select MAX6675 sensor on the SPI
        sensor = self.pi.spi_open(CHT, 1000000, 0)
        if TT:
            eCurrent = ElectricCurrent(self.pi, self.__app)
            thread = QtCore.QThread()
            thread.setObjectName("heater current")
            eCurrent.moveToThread(thread)
            thread.started.connect(eCurrent.work)
            self.sigAbortHeater.connect(eCurrent.setAbort)
            thread.start()
        else:
            pinNum = Signals.getGPIO(Signals.TEMPERATURE)
            self.pi.set_mode(pinNum, pigpio.OUTPUT)
            controlStep = -1

        totalStep = 0
        step = 0

        while not (self.__abort):
            # Temperature sampling time. For MAX6675 min read time = 0.25s
            time.sleep(0.25)
            temp = -1000  # Temperature.

            # READ DATA
            c, d = self.pi.spi_read(sensor, 2)  # if c==2: ok else: ng
            if c == 2:
                word = (d[0] << 8) | d[1]
                if (word & 0x8006) == 0:  # Bits 15, 2, and 1 should be zero.
                    temp = (word >> 3) / 4.0
                else:
                    print("bad reading {:b}".format(word))

            # Pass data on its way
            now = datetime.datetime.now()
            dSec = (now - self.__startTime).total_seconds()
            # TODO: fix data shape
            self.__rawData[step] = [dSec, dSec, temp, self.__presetTemp]

            if step % (STEP - 1) == 0 and step != 0:
                # average 10 points of data
                ave = np.mean(self.__rawData[:, 1], dtype=float)
                average = np.array([[Signals.TEMPERATURE, ave]])

                # CONTROL
                if TT:
                    self.__controlTemp(average, eCurrent)
                else:
                    controlStep = self.__controlTemp1(average, controlStep)

                # Send Temperature back to main loop
                # MAX6675 returns temperature in degree C, no need for formula
                self.sigStep.emit(
                    self.__rawData,  # raw dat
                    self.__rawData,  # calculated
                    average,
                    self.__sensor_name,
                    self.__startTime,
                )
                self.__rawData = np.zeros(shape=(STEP, 4))
                step = 0
            else:
                step += 1
            totalStep += 1
            if not TT:
                self.pi.write(pinNum, controlStep > 0)
                controlStep -= 1
            self.__app.processEvents()

        else:
            # On ABORT. Now renders some strange behavior and numpy errors.
            if self.__rawData[step][0] == 0.0:
                step -= 1
            if step > -1:
                ave = np.mean(self.__rawData[:, 1], dtype=float)
                average = np.array([[Signals.TEMPERATURE, ave]])
                self.sigStep.emit(
                    self.__rawData[: step + 1, :],
                    self.__rawData[: step + 1, :],
                    average,
                    self.__sensor_name,
                    self.__startTime,
                )
            self.sigMsg.emit(f"Worker #{self.__id} aborting work at step {totalStep}")
            if TT:
                self.sigAbortHeater.emit()
                self.__sumE = 0
                thread.quit()
                thread.wait()
            self.pi.spi_close(sensor)
            self.pi.stop()

        self.sigDone.emit(self.__id, self.__sensor_name)

    # MARK: - Control
    def __controlTemp(self, aveTemp: np.ndarray, eCurrent: ElectricCurrent):
        """
        Shouldn't the self.sampling here be 0.25, not the one for ADC?
        """
        e = self.__presetTemp - aveTemp[0, 1]
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
            eCurrent.setOnLight(max(output, 0))
        else:
            eCurrent.setOnLight(0)
        self.__exE = e
        self.__sumE = integral

    def __controlTemp1(self, aveTemp: float, steps: int):
        if steps <= 0:
            d = self.__presetTemp - aveTemp[0, 1]
            if d <= 1.5:
                return -1
            elif d >= 15:
                return int(d * 10)
            else:
                return int(d + 1)
        else:
            return steps


class ADC(Worker):
    def __init__(self, id, app, sensor_name, startTime):
        super().__init__(id, app, sensor_name, startTime)
        self.__id = id
        self.__app = app
        self.__sensor_name = sensor_name
        self.__startTime = startTime
        self.__abort = False

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
        self.adc_voltage_columns = ["P1", "P2", "Ip"]
        self.adc_processed_columns = [i + "_c" for i in self.adc_voltage_columns]
        self.adc_columns = (
            ["date", "time"] + self.adc_voltage_columns + ["IGmode", "IGscale", "QMS_signal",]
        )
        # self.__adc_data = np.zeros(shape=(STEP, len(self.adc_columns)))
        self.__adc_data = pd.DataFrame(columns=self.adc_columns)
        # self.__calcData = np.zeros(shape=(STEP, 4))
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

    # MARK: - Methods
    @QtCore.pyqtSlot()
    def start(self):
        """
        Set Thread ID and name, then run corresponding "plot" function.
        "plot" functions in the main.py are main data acquisition loops (threads).
        """
        self.set_thread_name()
        self.acquisition_loop()

    # MARK: - Plot

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
            np.atleast_2d(calcIGPres(p1_v, self.__IGmode, self.__IGrange)),
            calcPfePres(p2_v),
            hall_to_current(ip_v),
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
        self.sigStep.emit(
            self.__adc_data, self.__calcData, self.averages, self.__sensor_name, self.__startTime,
        )
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
            # On ABORT
            if self.__calcData[step][0] == 0.0:
                step -= 1
            if step > -1:
                self.calculate_averaged_signals()
                self.send_processed_data_to_main_thread()

            self.sigMsg.emit(f"Worker #{self.__id} aborting work at step {totalStep}")

        self.sigDone.emit(self.__id, self.__sensor_name)
        return


if __name__ == "__main__":
    pass

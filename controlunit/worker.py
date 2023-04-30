import time, datetime
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from customTypes import Signals  # import for now, then get rid of Signals
from electricCurrent import ElectricCurrent, hall_to_current
from readsettings import read_settings

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

    def __init__(self, id, app, ttype, startTime):
        super().__init__()

        self.__id = id
        self.__app = app
        self.__ttype = ttype
        self.__startTime = startTime
        self.__abort = False

    def print_checks(self):
        attrs = vars(self)

        if PRINTTHREADINFO:
            print("Thread Checks:")
            print(", ".join(f"{i}" for i in attrs.items()))
            print("ID:", self.__id)
            print("End Thread Checks")

    def setThread(self):
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
    def __init__(self, id, app, ttype, startTime):
        super().__init__(id, app, ttype, startTime)
        self.__id = id
        self.__app = app
        self.__ttype = ttype
        self.__startTime = startTime
        self.__abort = False

    # set temperature worker
    def setTempWorker(self, presetTemp: int):
        self.__rawData = np.zeros(shape=(STEP, 3))
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
            self.__rawData[step] = [dSec, temp, self.__presetTemp]

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
                    self.__ttype,
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
                    self.__ttype,
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

        self.sigDone.emit(self.__id, self.__ttype)

    # MARK: - Control
    def __controlTemp(self, aveTemp: np.ndarray, eCurrent: ElectricCurrent):
        """Shouldn't the self.sampling here be 0.25, not the one for ADC?"""
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
    def __init__(self, id, app, ttype, startTime):
        super().__init__(id, app, ttype, startTime)
        self.__id = id
        self.__app = app
        self.__ttype = ttype
        self.__startTime = startTime
        self.__abort = False

    def setPresWorker(self, IGmode: int, IGrange: int):
        self.adc_columns = [
            "date",
            "time",
            "P1",
            "P2",
            "Ip",
            "IGmode",
            "IGscale",
            "QMS_signal",
        ]
        self.__adc_data = np.zeros(shape=(STEP, len(self.adc_columns)))
        # TODO: change append to concat for pandas (deprecation)
        #self.__adc_data = pd.DataFrame(columns=self.adc_columns)
        self.__calcData = np.zeros(shape=(STEP, 4))
        self.__IGmode = IGmode
        self.__IGrange = IGrange
        self.__qmsSignal = 0
        self.sampling = read_settings()["samplingtime"]

    def setIGmode(self, IGmode: int):
        """
        0: Torr
        1: Pa
        """
        self.__IGmode = IGmode
        return

    def setIGrange(self, IGrange: int):
        """
        range: -8 ~ -3
        """
        self.__IGrange = IGrange
        return

    def setQmsSignal(self, signal: int):
        """
        waiting: 0
        running: 1
        """
        self.__qmsSignal = signal
        return

    # MARK: - Methods
    @QtCore.pyqtSlot()
    def start(self):
        """Set Thread ID and name, then run corresponding "plot" function.
        "plot" functions are main data acquisition loops.
        """
        self.setThread()
        self.readADC()

    # MARK: - Plot
    def readADC(self):
        """Reads ADC raw signals, converts it, sends it back to main loop
        to plot ad save data.
        """

        aio = adc(0x49, 0x3E)  # instance of AIO_32_0RA_IRC from AIO.py
        # Why this addresses?

        totalStep = 0
        step = 0

        while not (self.__abort):
            time.sleep(self.sampling)

            # READ DATA
            CHNLS = [CHP1, CHP2, CHIP]
            scale10 = [CHP1, CHP2]
            scale5 = [CHIP]
            kws = {CH: {"pga": aio.PGA.PGA_10_0352V} for CH in scale10}
            for CH in scale5:
                kws[CH] = {"pga": aio.PGA.PGA_5_0176V}

            # Communitcate with ADC

            arg = [aio.DataRate.DR_860SPS]
            p1_v, p2_v, ip_v = [aio.analog_read_volt(CH, *arg, **kws[CH]) for CH in CHNLS]

            # Process values
            now = datetime.datetime.now()
            dSec = (now - self.__startTime).total_seconds()
            self.__adc_data = self.__adc_data.append(
                [
                    dSec,
                    p1_v,
                    p2_v,
                    ip_v,
                    self.__IGmode,
                    self.__IGrange,
                    self.__qmsSignal,
                ]
            )

            # TODO: get rid of the enumerator class Signals.
            # Define calculations inside individual subclass right here.
            # Why Ito-kun hid this somewhere? Not helpful.
            #  calculate DATA
            p1_d = Signals.getCalcValue(Signals.PRESSURE1, p1_v, IGmode=self.__IGmode, IGrange=self.__IGrange)
            p2_d = Signals.getCalcValue(Signals.PRESSURE2, p2_v)
            ip_d = hall_to_current(ip_v)  #

            self.__calcData[step] = [dSec, p1_d, p2_d, ip_d]

            if step % (STEP - 1) == 0 and step != 0:
                # get average
                ave_p1 = np.mean(self.__calcData[:, 1], dtype=float)
                ave_p2 = np.mean(self.__calcData[:, 2], dtype=float)
                ave_ip = np.mean(self.__calcData[:, 3], dtype=float)
                average = np.array(
                    [
                        [Signals.PLASMA, ave_ip],
                        [Signals.PRESSURE1, ave_p1],
                        [Signals.PRESSURE2, ave_p2],
                    ]
                )

                # SEND ADC data back to main loop

                self.sigStep.emit(
                    self.__adc_data,
                    self.__calcData,
                    average,
                    self.__ttype,
                    self.__startTime,
                )

                # Reset temporary data arrays
                self.__adc_data = np.zeros(shape=(STEP, 8))
                self.__calcData = np.zeros(shape=(STEP, 4))
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
                # get average
                ave_p1 = np.mean(self.__calcData[:, 1], dtype=float)
                ave_p2 = np.mean(self.__calcData[:, 2], dtype=float)
                ave_ip = np.mean(self.__calcData[:, 3], dtype=float)
                average = np.array(
                    [
                        [Signals.PLASMA, ave_ip],
                        [Signals.PRESSURE1, ave_p1],
                        [Signals.PRESSURE2, ave_p2],
                    ]
                )
                self.sigStep.emit(
                    self.__rawData[: step + 1, :],
                    self.__calcData,
                    average,
                    self.__ttype,
                    self.__startTime,
                )
            self.sigMsg.emit(f"Worker #{self.__id} aborting work at step {totalStep}")

        self.sigDone.emit(self.__id, self.__ttype)
        return


if __name__ == "__main__":
    pass

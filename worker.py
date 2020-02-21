import time, datetime
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui
from typing import Callable
from customTypes import ThreadType
from electricCurrent import ElectricCurrent
from readsettings import get_datafolderpth

TEST = False

# Specify cable connections to ADC
CHP1 = 0 # 15, Ionization Gauge
CHP2 = 1 # 16, Pfeiffer single gauge
CHIP = 2 # 5, Plasma current, Hall effect sensor
CHT  = 0 # 0 -> CS0, 1 -> CS1

# Raspi outputs

TIMESLEEP = get_datafolderpth()[2]
# Number of data points for collection, steps%STEP == 0
STEP = 5

try:
    from AIO import AIO_32_0RA_IRC as adc
    import pigpio
except:
    print("no pigpio or AIO")
    TEST = True
TT = True
# must inherit QtCore.QObject in order to use 'connect'
class Worker(QtCore.QObject):

    sigStep = QtCore.pyqtSignal(np.ndarray, np.ndarray, np.ndarray, ThreadType, datetime.datetime)
    sigDone = QtCore.pyqtSignal(int, ThreadType)
    sigMsg = QtCore.pyqtSignal(str)

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

    def setWorker(self, id: int, app: QtGui.QApplication,
                  ttype:ThreadType, startTime: datetime.datetime):
        self.__id = id
        self.__app = app
        self.__abort = False
        self.__startTime = startTime
        self.__ttype = ttype

    # set temperature worker
    def setTempWorker(self, presetTemp: int):
            self.__rawData = np.zeros(shape=(STEP, 3))
            self.__presetTemp = presetTemp

            # PID control
            if not TEST:
                self.pi = pigpio.pi()
                self.__onLight= 0.1
                self.__sumE = 0
                self.__exE = 0

    # set pressure worker
    def setPresWorker(self, IGmode: int, IGrange: int):
        self.__rawData = np.zeros(shape=(STEP, 7))
        self.__calcData = np.zeros(shape=(STEP, 4))
        self.__IGmode = IGmode
        self.__IGrange = IGrange
        self.__qmsSignal = 0

    # MARK: - Getters
    def getStartTime(self):
        return self.__startTime

    # MARK: - Setters
    def setPresetTemp(self, newTemp: int):
        self.__presetTemp = newTemp
        return

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
    def work(self):
        self.__setThread()
        if TEST:
            if self.__ttype == ThreadType.TEMPERATURE:
                self.__testTemp()
            else:
                self.__testPres()
        else:
            if self.__ttype == ThreadType.TEMPERATURE:
                self.__plotT()
            elif self.__ttype==ThreadType.PLASMA or self.__ttype==ThreadType.PRESSURE1 or self.__ttype==ThreadType.PRESSURE2:
                self.__plotPresCur()
            else:
                return

    def __setThread(self):
        threadName = QtCore.QThread.currentThread().objectName()
        threadId = int(QtCore.QThread.currentThreadId())

        self.sigMsg.emit(
            "Running worker #{} from thread '{}' (#{})".format(self.__id, threadName, threadId)
        )

    @QtCore.pyqtSlot()
    def abort(self):
        self.sigMsg.emit("Worker #{} aborting acquisition".format(self.__id))
        self.__abort = True

    # MARK: - Plot
    def __plotPresCur(self):
        """
            plasma current will be controled but now it is not controled.
            because of this, function name is '__plotPresCur'.
        """
        
        aio = adc(0x49, 0x3e) # instance of AIO_32_0RA_IRC from AIO.py
        # Why this addresses?
        
        totalStep = 0
        step = 0
        
        while not (self.__abort):
            time.sleep(TIMESLEEP)
            
            # READ DATA
            CHNLS = [CHP1,CHP2,CHIP]
            kws = {'pga':aio.PGA.PGA_10_0352V}
            arg = [aio.DataRate.DR_860SPS]
            p1_v,p2_v,ip_v = [aio.analog_read_volt(CH,*arg,**kws) for CH in CHNLS]

           # p1_v = aio.analog_read_volt(CHP1, aio.DataRate.DR_860SPS, pga=aio.PGA.PGA_10_0352V)
           # p2_v = aio.analog_read_volt(CHP2, aio.DataRate.DR_860SPS, pga=aio.PGA.PGA_10_0352V)
           # ip_v = aio.analog_read_volt(CHIP, aio.DataRate.DR_860SPS, pga=aio.PGA.PGA_10_0352V)

            deltaSeconds = (datetime.datetime.now() - self.__startTime).total_seconds()
            self.__rawData[step] = [deltaSeconds, p1_v, p2_v, ip_v, self.__IGmode, self.__IGrange, self.__qmsSignal]

            # calculate DATA
            p1_d = ThreadType.getCalcValue(ThreadType.PRESSURE1, p1_v, IGmode=self.__IGmode, IGrange=self.__IGrange)
            p2_d = ThreadType.getCalcValue(ThreadType.PRESSURE2, p2_v)
            ip_d = ip_v # TODO: calc

            self.__calcData[step] = [deltaSeconds, p1_d, p2_d, ip_d]

            if step%(STEP-1) == 0 and step != 0:
                # get average
                ave_p1 = np.mean(self.__calcData[:, 1], dtype=float)
                ave_p2 = np.mean(self.__calcData[:, 2], dtype=float)
                ave_ip = np.mean(self.__calcData[:, 3], dtype=float)
                average = np.array([
                    [ThreadType.PLASMA, ave_ip],
                    [ThreadType.PRESSURE1, ave_p1],
                    [ThreadType.PRESSURE2, ave_p2]
                ])

                self.sigStep.emit(self.__rawData, self.__calcData, average, self.__ttype, self.__startTime)
                self.__rawData = np.zeros(shape=(STEP, 7))
                self.__calcData = np.zeros(shape=(STEP, 4))
                step = 0
            else:
                step += 1
            totalStep += 1                
            self.__app.processEvents()
        else:
            if self.__calcData[step][0] == 0.0:
                step -= 1
            if step > -1:
                # get average
                ave_p1 = np.mean(self.__calcData[:, 1], dtype=float)
                ave_p2 = np.mean(self.__calcData[:, 2], dtype=float)
                ave_ip = np.mean(self.__calcData[:, 3], dtype=float)
                average = np.array([
                    [ThreadType.PLASMA, ave_ip],
                    [ThreadType.PRESSURE1, ave_p1],
                    [ThreadType.PRESSURE2, ave_p2]
                ])
                self.sigStep.emit(self.__rawData[:step+1, :], self.__calcData, average, self.__ttype, self.__startTime)
            self.sigMsg.emit(
                "Worker #{} aborting work at step {}".format(self.__id, totalStep)
            )

        self.sigDone.emit(self.__id, self.__ttype)
        return

    # temperature plot
    @QtCore.pyqtSlot()
    def __plotT(self):
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
            pinNum = ThreadType.getGPIO(ThreadType.TEMPERATURE)
            self.pi.set_mode(pinNum, pigpio.OUTPUT)
            controlStep = -1

        totalStep = 0
        step = 0

        while not (self.__abort):
            time.sleep(0.25)
            temp = -1000

            # READ DATA
            c, d = self.pi.spi_read(sensor, 2) # if c==2: ok else: ng
            if c == 2:
                word = (d[0]<<8) | d[1]
                if (word & 0x8006) == 0: # Bits 15, 2, and 1 should be zero.
                    temp = (word >> 3)/4.0
                else:
                    print("bad reading {:b}".format(word))

            deltaSeconds = (datetime.datetime.now() - self.__startTime).total_seconds()
            self.__rawData[step] = [deltaSeconds, temp, self.__presetTemp]

            if step%(STEP-1) == 0 and step != 0:
                # average 10 points of data
                ave = np.mean(self.__rawData[:, 1], dtype=float)
                average = np.array([
                    [ThreadType.TEMPERATURE, ave],
                ])

                # CONTROL
                if TT:
                    self.__controlTemp(average, eCurrent)
                else:
                    controlStep = self.__controlTemp1(average, controlStep)
                
                self.sigStep.emit(self.__rawData, self.__rawData, average, self.__ttype, self.__startTime)
                self.__rawData = np.zeros(shape=(STEP, 3))
                step = 0
            else:
                step += 1
            totalStep += 1
            if not TT:
                self.pi.write(pinNum, controlStep>0)
                controlStep -= 1           
            self.__app.processEvents()

        else:
            if self.__rawData[step][0] == 0.0:
                step -= 1
            if step > -1:
                ave = np.mean(self.__rawData[:, 1], dtype=float)
                average = np.array([
                    [ThreadType.TEMPERATURE, ave]
                ])
                self.sigStep.emit(self.__rawData[:step+1, :], self.__rawData[:step+1, :], average, self.__ttype, self.__startTime)
            self.sigMsg.emit(
                "Worker #{} aborting work at step {}".format(self.__id, totalStep)
            )
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
        e = self.__presetTemp - aveTemp[0, 1]
        integral = self.__sumE + e * TIMESLEEP
        derivative = (e - self.__exE) / TIMESLEEP

        # TODO: 調整
        Kp = 3.5
        Ki = 0.06
        Kd = 0

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
                return int(d*10)
            else:
                return int(d+1)
        else:
            return steps

    def __controlCur(self, aveCur: float, steps: int):
        pass

    # MARK: - Test
    def __testPres(self):
        totalStep = 0
        step = 0
        while not (self.__abort):
            #print(self.__ttype)
            if self.__ttype == ThreadType.PLASMA:
                pass
            elif self.__ttype == ThreadType.TEMPERATURE:
                val = (np.random.normal()+1)/10000
                time.sleep(0.25)
                STEPtest = 2 
                return

            time.sleep(TIMESLEEP)
            STEPtest = STEP

            p1_v = (np.random.normal()+1)*5
            p2_v = (np.random.normal()+1)*5
            ip_v = np.random.normal()+2.5

            deltaSeconds = (datetime.datetime.now() - self.__startTime).total_seconds()
            self.__rawData[step] = [deltaSeconds, p1_v, p2_v, ip_v, self.__IGmode, self.__IGrange, self.__qmsSignal]

            p1_d = ThreadType.getCalcValue(ThreadType.PRESSURE1, p1_v, IGmode=self.__IGmode, IGrange=self.__IGrange)
            p2_d = ThreadType.getCalcValue(ThreadType.PRESSURE2, p2_v)
            ip_d = ip_v # TODO: calc
            self.__calcData[step] = [deltaSeconds, p1_d, p2_d, ip_d]

            if step%(STEPtest-1) == 0 and step != 0:
                # get average
                ave_p1 = np.mean(self.__calcData[:, 1], dtype=float)
                ave_p2 = np.mean(self.__calcData[:, 2], dtype=float)
                ave_ip = np.mean(self.__calcData[:, 3], dtype=float)
                average = np.array([
                    [ThreadType.PLASMA, ave_ip],
                    [ThreadType.PRESSURE1, ave_p1],
                    [ThreadType.PRESSURE2, ave_p2]
                ])

                self.sigStep.emit(self.__rawData, self.__calcData, average, self.__ttype, self.__startTime)
                self.__rawData = np.zeros(shape=(STEPtest, 7))
                self.__calcData = np.zeros(shape=(STEPtest, 4))
                step = 0
            else:
                step += 1
            totalStep += 1

            self.__app.processEvents()

        else:
            if self.__calcData[step][0] == 0.0:
                step -= 1
            if step > -1:
                # get average
                ave_p1 = np.mean(self.__calcData[:, 1], dtype=float)
                ave_p2 = np.mean(self.__calcData[:, 2], dtype=float)
                ave_ip = np.mean(self.__calcData[:, 3], dtype=float)
                average = np.array([
                    [ThreadType.PLASMA, ave_ip],
                    [ThreadType.PRESSURE1, ave_p1],
                    [ThreadType.PRESSURE2, ave_p2]
                ])

                self.sigStep.emit(self.__rawData[:step+1, :], self.__calcData[:step+1, :], average, self.__ttype, self.__startTime)

            self.sigMsg.emit(
                "Worker #{} aborting work at step {}".format(self.__id, totalStep)
            )
        self.sigDone.emit(self.__id, self.__ttype)
        return

    def __testTemp(self):
        totalStep = 0
        step = 0
        while not (self.__abort):
            time.sleep(0.25)
            STEPtest = STEP
            temperature = (np.random.normal()+1)/10000

            deltaSeconds = (datetime.datetime.now() - self.__startTime).total_seconds()
            self.__rawData[step] = [deltaSeconds, temperature, self.__presetTemp]

            if step%(STEPtest-1) == 0 and step != 0:
                # get average
                ave = np.mean(self.__rawData[:, 1], dtype=float)
                average = np.array([
                    [ThreadType.TEMPERATURE, ave],
                ])

                self.sigStep.emit(self.__rawData, self.__rawData, average, self.__ttype, self.__startTime)
                self.__rawData = np.zeros(shape=(STEPtest, 3), dtype=object)
                step = 0
            else:
                step += 1
            totalStep += 1

            self.__app.processEvents()

        else:
            if self.__rawData[step][0] == 0.0:
                step -= 1
            if step > -1:
                # get average
                ave = np.mean(self.__rawData[:, 1], dtype=float)
                average = np.array([
                    [ThreadType.TEMPERATURE, ave]
                ])

                self.sigStep.emit(self.__rawData[:step+1, :], self.__rawData[:step+1, :], average, self.__ttype, self.__startTime)

            self.sigMsg.emit(
                "Worker #{} aborting work at step {}".format(self.__id, totalStep)
            )
        self.sigDone.emit(self.__id, self.__ttype)
        return

if __name__ == "__main__":
    pass

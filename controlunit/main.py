import sys, datetime, os
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from mainView import UIWindow
from worker import MAX6675, ADC, Worker
from customTypes import Signals
from readsettings import make_datafolders, read_settings
import qmsSignal

testmark = "test-"

try:
    from AIO import AIO_32_0RA_IRC as adc
    import pigpio
except:
    print("no pigpio or AIO")
    TEST = True

    class pigpio:
        def __init__(self) -> None:
            pass

        def pi(self):
            return 0


MAX_SIZE = 10000  # Maximum displayed points in pyqgraph plot

# debug
# def trap_exc_during_debug(*args):
#     print(args)

# sys.excepthook = trap_exc_during_debug


# must inherit QtCore.QObject in order to use 'connect'
class MainWidget(QtCore.QObject, UIWindow):
    DEFAULT_TEMPERATURE = 0
    STEP = 3

    sigAbortWorkers = QtCore.pyqtSignal()

    def __init__(self, app: QtWidgets.QApplication):
        super(self.__class__, self).__init__()
        self.__app = app
        self.connections()
        self.registerDock.setTemp(self.DEFAULT_TEMPERATURE, "---")

        QtCore.QThread.currentThread().setObjectName("main")

        self.__workers_done = 0
        self.__threads = []
        self.__temp = self.DEFAULT_TEMPERATURE

        self.plaData = None
        self.trigData = None
        self.tData = None
        self.p1Data = None
        self.p2Data = None


        # Plot line colors
        self.pens = {
            "Ip": {"color": "#8d3de3", "width": 2},
            "P1": {"color": "#6ac600", "width": 2},
            "P2": {"color": "#c9004d", "width": 2},
            "T": {"color": "#5999ff", "width": 2},
            "trigger": {"color": "#edbc34", "width": 2},
        }
        self.valuePlaPlot = self.graph.plaPl.plot(pen=self.pens["Ip"])
        self.triggerPlot = self.graph.plaPl.plot(pen=self.pens["trigger"])
        self.valueTPlot = self.graph.tempPl.plot(pen=self.pens["T"])
        self.valueP1Plot = self.graph.presPl.plot(pen=self.pens["P1"])
        self.valueP2Plot = self.graph.presPl.plot(pen=self.pens["P2"])
        self.graph.tempPl.setXLink(self.graph.presPl)
        self.graph.plaPl.setXLink(self.graph.presPl)

        self.graph.presPl.setLogMode(y=True)
        self.graph.presPl.setYRange(-8, 3, 0)
        self.graph.tempPl.setYRange(0, 320, 0)

        self.tWorker = None
        self.adcWorker = None

        make_datafolders()
        self.datapth = read_settings()["datafolder"]

        self.sampling = read_settings()["samplingtime"]
        self.__changeScale()

        self.showMain()

    def __changeScale(self):
        """Set data window size for plotting
        STEP = 2 from worker
        """
        index = self.controlDock.scaleBtn.currentIndex()
        txt = self.controlDock.scaleBtn.currentText()
        val = self.controlDock.sampling_windows[txt]
        if val > 0:
            adcind = -int(val / self.sampling / (self.STEP - 1))
            tind = -int(val / 0.25)
        else:
            adcind = 0
            tind = 0
        self.adcind = adcind
        self.tind = tind

        return
        print(f"{txt}\t{adcind}\t{tind}")
        try:
            print(self.p1Data.shape)
        except:
            pass
        # self.__scale = ScaleSize.getEnum(index)

    def connections(self):
        self.controlDock.scaleBtn.currentIndexChanged.connect(self.__changeScale)

        self.registerDock.registerBtn.clicked.connect(self.registerTemp)
        self.controlDock.IGmode.currentIndexChanged.connect(self.updateIGmode)
        self.controlDock.IGrange.valueChanged.connect(self.updateIGrange)

        self.controlDock.FullNormSW.clicked.connect(self.fulltonormal)
        self.controlDock.OnOffSW.clicked.connect(self.__onoff)
        self.controlDock.quitBtn.clicked.connect(self.__quit)
        self.controlDock.qmsSigSw.clicked.connect(self.__qmsSignal)

        # Toggle plots for Current, Temperature, and Pressure
        self.scaleDock.togIp.clicked.connect(self.togglePlots)
        self.scaleDock.togT.clicked.connect(self.togglePlots)
        self.scaleDock.togP.clicked.connect(self.togglePlots)

        self.scaleDock.Pmin.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Pmax.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Imin.valueChanged.connect(self.__updateIScale)
        self.scaleDock.Imax.valueChanged.connect(self.__updateIScale)
        self.scaleDock.Tmax.valueChanged.connect(self.__updateTScale)

        self.scaleDock.autoscale.clicked.connect(self.__auto_or_levels)
        self.SettingsDock.setSamplingBtn.clicked.connect(self.__set_sampling)

    def __quit(self):
        """terminate app"""
        self.__app.quit()

    def __onoff(self):
        """Start and stop worker threads"""
        if self.controlDock.OnOffSW.isChecked():
            self.startThreads()
            self.controlDock.quitBtn.setEnabled(False)
        else:
            quit_msg = "Are you sure you want to stop data acquisition?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow,
                "Message",
                quit_msg,
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.abortThreads()
                self.controlDock.quitBtn.setEnabled(True)
            else:
                self.controlDock.OnOffSW.setChecked(True)

    def __updatePScale(self):
        """Updated plot limits for the Pressure viewgraph"""
        pmin, pmax = [self.scaleDock.Pmin.value(), self.scaleDock.Pmax.value()]

        # self.graph.presPl.setLogMode(y=True)
        self.graph.presPl.setYRange(pmin, pmax, 0)

    def __updateIScale(self):
        """Updated plot limits for the plasma current viewgraph"""
        imin, imax = [self.scaleDock.Imin.value(), self.scaleDock.Imax.value()]
        self.graph.plaPl.setYRange(imin, imax, 0)

    def __updateTScale(self):
        """Updated plot limits for the Temperature viewgraph"""
        tmax = self.scaleDock.Tmax.value()
        self.graph.tempPl.setYRange(0, tmax, 0)

    def __updateScales(self):
        """Update all scales according to spinboxes"""
        self.__updateIScale()
        self.__updateTScale()
        self.__updatePScale()

    def __autoscale(self):
        """Set all plots to autoscale"""
        # enableAutoRange
        plots = [self.graph.plaPl, self.graph.tempPl, self.graph.presPl]

        # [i.autoRange() for i in plots]
        [i.enableAutoRange() for i in plots]

    def __auto_or_levels(self):
        """Change plot scales from full auto to Y axis from settings"""
        if self.scaleDock.autoscale.isChecked():
            self.__autoscale()
        else:
            self.__updateScales()

    def fulltonormal(self):
        """Change from full screen to normal view on click"""
        if self.controlDock.FullNormSW.isChecked():
            self.MainWindow.showFullScreen()
            self.controlDock.setStretch(*(10, 300))  # minimize control dock width
        else:
            self.MainWindow.showNormal()
            self.controlDock.setStretch(*(10, 300))  # minimize control dock width

    def togglePlots(self):
        """Toggle plots
        self.scaleDock.togIp
        self.graph.plaPl
        """

        def toggleplot(i, pl, row=0, col=0):
            if i.isChecked():
                try:
                    self.graph.addItem(pl, row=row, col=col)
                except:
                    pass
            else:
                try:
                    self.graph.removeItem(pl)  # remove plot
                except:
                    pass

        items = {
            "Ip": [self.scaleDock.togIp, self.graph.plaPl, 0, 0],
            "T": [self.scaleDock.togT, self.graph.tempPl, 1, 0],
            "P": [self.scaleDock.togP, self.graph.presPl, 2, 0],
        }

        [toggleplot(*items[jj]) for jj in ["Ip", "T", "P"]]

    def __qmsSignal(self):
        """Experiment indicator, analog output is sent to QMS to sync
        expermint time between recording devices.
        This signal is helpfull to separate experiments (same as shot numbers in fusion)
        """
        if not self.controlDock.OnOffSW.isChecked():
            return

        try:
            pi = pigpio.pi()
        except:
            print("pigpio is not defined")
            return

        if self.controlDock.qmsSigSw.isChecked():
            self.qmsSigThread = qmsSignal.QMSSignal(pi, self.__app, 1)
            self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
            self.qmsSigThread.start()
            self.adcWorker.setQmsSignal(1)
        else:
            quit_msg = "Stop Experiment Marker?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow,
                "Message",
                quit_msg,
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                # old function: QMSSignal.blink_led
                # self.qmsSigThread = qmsSignal.QMSSignal(pi, self.__app, 2)
                self.qmsSigThread = qmsSignal.QMSSignal(pi, self.__app, 0)
                self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
                self.qmsSigThread.start()
                self.adcWorker.setQmsSignal(0)
            else:
                self.controlDock.qmsSigSw.setChecked(True)

    def qmsSignalTerminate(self):
        self.qmsSigThread.quit()
        self.qmsSigThread.wait()

    # MARK: - Threads
    def startThreads(self):
        """Define Workers to run in separate threads.
        2020/03/05: two sensors: ADC and temperatures, hence
        2 threds to read a) temperature, and b) analog signals (P1,P2, Ip)
        """
        sensors = ["MAX6675", "ADC"]
        self.datadict = {i: {} for i in sensors}

        self.logDock.log.append("starting 2 threads")

        self.__workers_done = 0

        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

        now = datetime.datetime.now()
        # make threads from sensor worker classes
        threads = {}

        # MAX6675 thermocouple sensor for Membrane temperature with PID
        sensor = "MAX6675"
        threads[sensor] = QtCore.QThread()
        threads[sensor].setObjectName(f"{sensor}")
        self.tWorker = MAX6675(sensor, self.__app, self.datadict[sensor], now)
        self.tWorker.setTempWorker(self.__temp)

        # Multichannel ADC
        sensor = "ADC"
        threads[sensor] = QtCore.QThread()
        threads[sensor].setObjectName(f"{sensor}")
        self.adcWorker = ADC(sensor, self.__app, self.datadict[sensor], now)
        mode = self.controlDock.IGmode.currentIndex()
        scale = self.controlDock.IGrange.value()
        self.adcWorker.setPresWorker(mode, scale)

        workers = {i: j for i, j in zip(sensors, [self.tWorker, self.adcWorker])}

        print("threads started: {}".format(now))
        self.logDock.progress.append("threads started: {}".format(now))

        # start threads
        [self.setThread(workers[s], threads[s], s) for s in sensors]

    def setThread(self, worker: Worker, thread: QtCore.QThread, name: str):
        """Setup workers [Dataframe creation]
        - Creates instances of worker
        - Creates connections
        - Creates Pandas Dataframes for data logging
        - Saves empty dataframes to local csv. File name based on date and time
        - starts threads
        - sets initial values for all parameters (zeros)
        """

        self.__threads.append((thread, worker))
        worker.moveToThread(thread)

        worker.sigStep.connect(self.onWorkerStep)
        worker.sigDone.connect(self.onWorkerDone)
        worker.sigMsg.connect(self.logDock.log.append)
        self.sigAbortWorkers.connect(worker.abort)

        # temperature
        # [MAX6675 device]
        columns = ["date", "time", "P1", "P2", "Ip", "IGmode", "IGscale", "QMS_signal"]
        if name == "MAX6675":
            df = pd.DataFrame(dtype=float, columns=["time", "T", "PresetT"])
            df.to_csv(
                os.path.join(
                    self.datapth,
                    f"{testmark}out_{worker.getStartTime():%Y%m%d_%H%M%S}_temp.csv",
                ),
                index=False,
            )
        # pressures and current
        # [ADC device]
        elif name == "ADC":
            df = pd.DataFrame(dtype=object, columns=columns)
            df.to_csv(
                os.path.join(
                    self.datapth,
                    f"{testmark}out_{worker.getStartTime():%Y%m%d_%H%M%S}.csv",
                ),
                index=False,
            )
        else:
            return

        # creates file at the start, next data
        # in the loop is placed in another file
        # TODO: why not to save filename here, and reuse it later?

        thread.started.connect(worker.start)
        thread.start()

    currentvals = {
        Signals.PLASMA: 0,
        Signals.TEMPERATURE: 0,
        Signals.PRESSURE1: 0,
        Signals.PRESSURE2: 0,
    }
    print(currentvals)

    # Mark: connecting slots with threads
    @QtCore.pyqtSlot(np.ndarray, np.ndarray, np.ndarray, Signals, datetime.datetime)
    def onWorkerStep(self, rawResult, calcResult, ave, ttype, startTime):
        """collect data on worker step
        - Recives data from worker(s)
        - Updates text indicators in GUI
        - Appends recived data to dataframes (call to self.__setStepData)
        - Updates data in plots (skips points if data is too big)
        """
        # MEMO: ave [[theadtype, average], [], []]
        for l in ave:
            self.currentvals[l[0]] = l[1]
        """ set Bw text """
        temp_now = f"{self.currentvals[Signals.TEMPERATURE]:.0f}"
        self.registerDock.setTempText(self.__temp, temp_now)
        # dd1451b
        txt = f"""
              <table>
                 <tr>
                  <td>
                  <font size=5 color={self.pens['P1']['color']}>
                    Pd = {self.currentvals[Signals.PRESSURE1]:.1e}
                  </font>
                  </td>
                  <td>
                   <font size=5 color={self.pens['P2']['color']}>
                    Pu = {self.currentvals[Signals.PRESSURE2]:.1e}
                   </font>
                  </td>
                 </tr>
                 <tr>
                  <td>
                   <font size=5 color={self.pens['Ip']['color']}>
                    I = {self.currentvals[Signals.PLASMA]:.2f}
                   </font>
                  </td>
                 </tr>
                </table>
        """
        # Update current values
        self.controlDock.valueBw.setText(txt)
        self.controlDock.gaugeT.update_value(self.currentvals[Signals.TEMPERATURE])

        # scale = self.__scale.value
        tind = self.tind  # For MAX6675 Temperature sensor
        scale = self.adcind  # For ADC signals

        if ttype == Signals.TEMPERATURE:
            # get data
            t_data = self.tData
            # set and save data
            self.tData = self.__setStepData(t_data, rawResult, calcResult, ttype, startTime)
            # plot data
            skip = int((self.tData.shape[0] + MAX_SIZE - 1) / MAX_SIZE)
            self.valueTPlot.setData(self.tData[tind::skip, 0], self.tData[tind::skip, 1])
        # elif ttype in self.ADCtypes: # old, relic from Signals
        else:
            # get data
            pl_data = self.plaData
            p1_data = self.p1Data
            p2_data = self.p2Data
            # Append new data and save
            # Each call saves same data. Clean this up.
            # Make one dataframe pere one sensor.
            # plaData, p1Data, and p2Data must be merged.
            self.plaData = self.__setStepData(pl_data, rawResult, calcResult, Signals.PLASMA, startTime)
            self.p1Data = self.__setStepData(p1_data, rawResult, calcResult, Signals.PRESSURE1, startTime)
            self.p2Data = self.__setStepData(p2_data, rawResult, calcResult, Signals.PRESSURE2, startTime)
            # plot data
            skip = int((self.plaData.shape[0] + MAX_SIZE - 1) / MAX_SIZE)
            self.valuePlaPlot.setData(self.plaData[scale::skip, 0], self.plaData[scale::skip, 1])
            # self.triggerPlot.setData()
            self.valueP1Plot.setData(self.p1Data[scale::skip, 0], self.p1Data[scale::skip, 1])
            self.valueP2Plot.setData(self.p2Data[scale::skip, 0], self.p2Data[scale::skip, 1])

    def __setStepData(self, data, rawResult, calcResult, ttype, startTime):
        """
        - Save raw data
        - Append new data from Worker to the main data arrays
        """
        # TODO: save interval
        # Save raw data
        self.__save(rawResult, ttype, startTime)
        if data is None:
            data = np.zeros([self.STEP, 2])
            data[:, 0] = calcResult[:, 0]
            data[:, 1] = calcResult[:, ttype.getIndex()]
        else:
            steps = calcResult.shape[0]
            calcData = np.zeros([steps, 2])
            calcData[:, 0] = calcResult[:, 0]
            calcData[:, 1] = calcResult[:, ttype.getIndex()]
            data = np.concatenate((data, np.array(calcData)))
        return data

    def __save(self, data, ttype, startTime):
        """Save sensor data
        - For [both] sensors dumps dataframe into a *.csv via pandas to_csv
        """
        if ttype == Signals.TEMPERATURE:
            df = pd.DataFrame(data)
            df.to_csv(
                os.path.join(self.datapth, f"{testmark}out_{startTime:%Y%m%d_%H%M%S}_temp.csv"),
                mode="a",
                header=False,
                index=False,
            )
        # TODO: change structure
        # For now to save data only once, a workaround:
        # Save only for one Signal type from ADC signals.
        # elif ttype == self.ADCtypes[0]: # Old version, when using Signals for each ADC channel
        else:
            df = pd.DataFrame(data)
            df.to_csv(
                os.path.join(self.datapth, f"{testmark}out_{startTime:%Y%m%d_%H%M%S}.csv"),
                mode="a",
                header=False,
                index=False,
            )

    @QtCore.pyqtSlot(int, Signals)
    def onWorkerDone(self, workerId, ttype):
        self.logDock.log.append("Worker #{} done".format(workerId))
        self.logDock.progress.append("-- Signal {} STOPPED".format(workerId))
        self.__workers_done += 1
        # reset Data
        if ttype == Signals.TEMPERATURE:
            self.tData = None
        # elif ttype in self.ADCtypes: # old, relic from 
        else:
            self.plaData = None
            self.p1Data = None
            self.p2Data = None

        if self.__workers_done == 2:
            # self.abortThreads()   # not necessary
            self.logDock.log.append("No more plot workers active")

    @QtCore.pyqtSlot()
    def abortThreads(self):
        self.sigAbortWorkers.emit()
        self.logDock.log.append("Asking each worker to abort")
        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()
        self.logDock.log.append("All threads exited")

    # MARK: - Methods
    @QtCore.pyqtSlot()
    def registerTemp(self):
        value = self.registerDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvals[Signals.TEMPERATURE]
        self.registerDock.setTemp(self.__temp, f"{temp_now:.0f}")
        if self.tWorker is not None:
            self.tWorker.setPresetTemp(self.__temp)

    @QtCore.pyqtSlot()
    def updateIGmode(self):
        """Update mode of the IG controller:
        Torr and linear
        or
        Pa and log
        """
        value = self.controlDock.IGmode.currentIndex()
        if self.adcWorker is not None:
            self.adcWorker.setIGmode(value)

    @QtCore.pyqtSlot()
    def __set_sampling(self):
        """Set sampling time for ADC"""
        txt = self.SettingsDock.samplingCb.currentText()
        value = float(txt.split(" ")[0])
        self.sampling = value
        self.__changeScale()
        if self.adcWorker is not None:
            self.adcWorker.setSampling(value)

    @QtCore.pyqtSlot()
    def updateIGrange(self):
        """Update range of the IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        value = self.controlDock.IGrange.value()
        if self.tWorker is not None:
            self.adcWorker.setIGrange(value)


def main():
    """
    for command line script using entrypoint
    """
    app = QtWidgets.QApplication([])
    widget = MainWidget(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    widget = MainWidget(app)

    sys.exit(app.exec_())

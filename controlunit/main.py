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
        self.currentvalues = {"Ip": 0, "P1": 0, "P2": 0, "T": 0}
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
        """
        Start and stop worker threads
        """
        if self.controlDock.OnOffSW.isChecked():
            self.startThreads()
            self.controlDock.quitBtn.setEnabled(False)
        else:
            quit_msg = "Are you sure you want to stop data acquisition?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow, "Message", quit_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No,
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
                self.MainWindow, "Message", quit_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No,
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
        """
        Define Workers to run in separate threads.
        2020/03/05: two sensors: ADC and temperatures, hence
        2 threds to read a) temperature, and b) analog signals (P1,P2, Ip)
        """
        self.logDock.log.append("starting 2 threads")
        self.savepaths = {}

        self.__workers_done = 0

        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

        now = datetime.datetime.now()
        # make threads from sensor worker classes
        threads = {}

        # MAX6675 thermocouple sensor for Membrane temperature with PID
        sensor_name = "MAX6675"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.tWorker = MAX6675(sensor_name, self.__app, now)
        """
        class MAX6675(Worker):
            def __init__(self, id, app, sensor_name, startTime):
        """
        self.tWorker.setTempWorker(self.__temp)

        # Multichannel ADC
        sensor_name = "ADC"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.adcWorker = ADC(sensor_name, self.__app, now)
        """
        class ADC(Worker):
            def __init__(self, id, app, sensor_name, startTime):
        """
        mode = self.controlDock.IGmode.currentIndex()
        scale = self.controlDock.IGrange.value()
        self.adcWorker.init_adc_worker(mode, scale)

        workers = {worker.sensor_name: worker for worker in [self.tWorker, self.adcWorker]}

        print("threads started: {}".format(now))
        self.logDock.progress.append("threads started: {}".format(now))

        self.sensor_names = list(workers)

        # start threads
        [self.setThread(workers[s], threads[s]) for s in self.sensor_names]

    def setThread(
        self, worker: Worker, thread: QtCore.QThread,
    ):
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

        if worker.sensor_name == "MAX6675":
            self.savepaths[worker.sensor_name] = os.path.join(
                self.datapth, f"{testmark}out_{worker.getStartTime():%Y%m%d_%H%M%S}_temp.csv",
            )
        elif worker.sensor_name == "ADC":
            self.savepaths[worker.sensor_name] = (
                os.path.join(self.datapth, f"{testmark}out_{worker.getStartTime():%Y%m%d_%H%M%S}.csv",),
            )
        else:
            return

        thread.started.connect(worker.start)
        thread.start()

    def update_current_vallues(self):
        """
        update current values when new signal comes
        """

        # TODO: updated dislpayed valuves from dataframes

        self.registerDock.setTempText(self.__temp, f"{self.currentvalues['T']:.0f}")
        self.controlDock.gaugeT.update_value(self.currentvalues["T"])
        txt = f"""
              <table>
                 <tr>
                  <td>
                  <font size=5 color={self.pens['P1']['color']}>
                    Pd = {self.currentvalues['P1']:.1e}
                  </font>
                  </td>
                  <td>
                   <font size=5 color={self.pens['P2']['color']}>
                    Pu = {self.currentvalues['P2']:.1e}
                   </font>
                  </td>
                 </tr>
                 <tr>
                  <td>
                   <font size=5 color={self.pens['Ip']['color']}>
                    I = {self.currentvalues['Ip']:.2f}
                   </font>
                  </td>
                 </tr>
                </table>
        """
        # Update current values
        self.controlDock.valueBw.setText(txt)

    # Mark: connecting slots with threads
    @QtCore.pyqtSlot(list)
    def onWorkerStep(self, result):
        """collect data on worker step
        - Recives data from worker(s)
        - Updates text indicators in GUI
        - Appends recived data to dataframes (call to self.__setStepData)
        - Updates data in plots (skips points if data is too big)
        """
        self.update_current_vallues()

        # scale = self.__scale.value
        tind = self.tind  # For MAX6675 Temperature sensor
        scale = self.adcind  # For ADC signals
        sensor_name = result[-2]

        if sensor_name == "MAX6675":
            # [self.data, self.average, self.sensor_name, self.__startTime,]
            averages = result[1]
            print(sensor_name)
            print(averages)
            # plot data
            #
            """
            skip = int((self.tData.shape[0] + MAX_SIZE - 1) / MAX_SIZE)
            self.valueTPlot.setData(self.tData[tind::skip, 0], self.tData[tind::skip, 1])
            """
        elif sensor_name == "ADC":
            #  [self.__adc_data, self.__calcData, self.averages, self.sensor_name, self.__startTime,]
            averages = result[2]
            print(sensor_name)
            print(averages)
            # plot data
            """
            skip = int((self.plaData.shape[0] + MAX_SIZE - 1) / MAX_SIZE)
            self.valuePlaPlot.setData(self.plaData[scale::skip, 0], self.plaData[scale::skip, 1])            
            self.valueP1Plot.setData(self.p1Data[scale::skip, 0], self.p1Data[scale::skip, 1])
            self.valueP2Plot.setData(self.p2Data[scale::skip, 0], self.p2Data[scale::skip, 1])
            """

    def __setStepData(self, data, rawResult, calcResult, sensor_name, startTime):
        """
        - Save raw data
        - Append new data from Worker to the main data arrays
        """
        # TODO: save interval
        # Save raw data
        self.__save(rawResult, sensor_name, startTime)
        if data is None:
            # TODO: create empty dataframe
            pass
        else:
            # TODO: append new data to dataframe
            pass
        return data

    def __save(self, data, sensor_name, startTime):
        """
        Save sensor data        
        """
        savepath = self.savepaths[sensor_name]
        data.to_csv(savepath, mode="a", header=False, index=False)

    @QtCore.pyqtSlot(str)
    def onWorkerDone(self, sensor_name):
        self.logDock.log.append("Worker #{} done".format(sensor_name))
        self.logDock.progress.append("-- Signal {} STOPPED".format(sensor_name))
        self.__workers_done += 1
        self.reset_data()

        if self.__workers_done == 2:
            # self.abortThreads()   # not necessary
            self.logDock.log.append("No more plot workers active")

    def reset_data(self, sensor_name):
        if sensor_name == "MAX6675":
            self.tData = None
        elif sensor_name == "ADC":
            self.plaData = None
            self.p1Data = None
            self.p2Data = None

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

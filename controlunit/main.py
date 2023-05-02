import sys, datetime, os
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from mainView import UIWindow
from worker import MAX6675, ADC, Worker
from readsettings import make_datafolders, read_settings
import qmsSignal
from channels import TCCOLUMNS, ADCCOLUMNS, ADCCONVERTED, ADCSIGNALS

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
        # self.currentvalues = {"Ip": 0, "P1": 0, "P2": 0, "T": 0}
        self.currentvalues = {i: 0 for i in ADCSIGNALS + ["T"]}
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
        """
        Set data window size for plotting
        STEP = 2 from worker
        """
        index = self.controlDock.scaleBtn.currentIndex()
        txt = self.controlDock.scaleBtn.currentText()
        val = self.controlDock.sampling_windows[txt]
        print(f'Scale = {val}')

    def connections(self):
        self.controlDock.scaleBtn.currentIndexChanged.connect(self.__changeScale)

        self.registerDock.registerBtn.clicked.connect(self.registerTemp)
        self.controlDock.IGmode.currentIndexChanged.connect(self.updateIGmode)
        self.controlDock.IGrange.valueChanged.connect(self.updateIGrange)

        self.controlDock.FullNormSW.clicked.connect(self.fulltonormal)
        self.controlDock.OnOffSW.clicked.connect(self.__onoff)
        self.controlDock.quitBtn.clicked.connect(self.__quit)
        self.controlDock.qmsSigSw.clicked.connect(self.sync_signal_switch)

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
            self.prep_threads()
            self.controlDock.quitBtn.setEnabled(False)
        else:
            quit_msg = "Are you sure you want to stop data acquisition?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow, "Message", quit_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.abort_all_threads()
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
        """
        Toggle plots
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

    def sync_signal_switch(self):
        """
        Experiment indicator, analog output is sent to QMS to sync
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
            self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 1)
            self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
            self.qmsSigThread.start()
            self.adcWorker.setQmsSignal(1)
        else:
            quit_msg = "Stop Experiment Marker?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow, "Message", quit_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 0)
                self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
                self.qmsSigThread.start()
                self.adcWorker.setQmsSignal(0)
            else:
                self.controlDock.qmsSigSw.setChecked(True)

    def qmsSignalTerminate(self):
        self.qmsSigThread.quit()
        self.qmsSigThread.wait()

    def prep_threads(self):
        """
        Define Workers to run in separate threads.
        2020/03/05: two sensors: ADC and temperatures, hence
        2 threds to read a) temperature, and b) analog signals (P1,P2, Ip)
        """
        self.logDock.log.append("starting 2 threads")
        self.savepaths = {}
        self.datadict = {
            "MAX6675": pd.DataFrame(columns=TCCOLUMNS),
            "ADC": pd.DataFrame(columns=ADCCOLUMNS + ADCCONVERTED),
        }

        self.__workers_done = 0

        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

        now = datetime.datetime.now()
        threads = {}

        # MAX6675 thermocouple sensor for Membrane temperature with PID
        sensor_name = "MAX6675"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.tWorker = MAX6675(sensor_name, self.__app, now)
        self.tWorker.setTempWorker(self.__temp)

        # Multichannel ADC
        sensor_name = "ADC"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.adcWorker = ADC(sensor_name, self.__app, now)

        mode = self.controlDock.IGmode.currentIndex()
        scale = self.controlDock.IGrange.value()
        self.adcWorker.init_adc_worker(mode, scale)

        workers = {worker.sensor_name: worker for worker in [self.tWorker, self.adcWorker]}
        self.sensor_names = list(workers)

        self.logDock.progress.append("threads started: {}".format(now))
        [self.start_thread(workers[s], threads[s]) for s in self.sensor_names]

    def start_thread(self, worker: Worker, thread: QtCore.QThread):
        """
        Setup workers [Dataframe creation]
        - Creates instances of worker
        - Creates connections
        - Creates Pandas Dataframes for data logging
        - Saves empty dataframes to local csv. File name based on date and time
        - starts threads
        - sets initial values for all parameters (zeros)
        """

        self.__threads.append((thread, worker))
        worker.moveToThread(thread)
        self.connect_worker_signals(worker)

        if worker.sensor_name == "MAX6675":
            self.savepaths[worker.sensor_name] = os.path.join(
                os.path.abspath(self.datapth), f"controlunit_{worker.getStartTime():%Y%m%d_%H%M%S}_temp.csv"
            )
            self.logDock.log.append(f"{worker.sensor_name} savepath: {self.savepaths[worker.sensor_name]}")
        if worker.sensor_name == "ADC":
            self.savepaths[worker.sensor_name] = os.path.join(
                os.path.abspath(self.datapth), f"controlunit_{worker.getStartTime():%Y%m%d_%H%M%S}.csv"
            )
            self.logDock.log.append(f"{worker.sensor_name} savepath: {self.savepaths[worker.sensor_name]}")

        thread.started.connect(worker.start)
        thread.start()

    def connect_worker_signals(self, worker):
        """
        Connects worker signals to the main thread
        """
        worker.send_step_data.connect(self.on_worker_step)
        worker.sigDone.connect(self.on_worker_done)
        worker.send_message.connect(self.logDock.log.append)
        self.sigAbortWorkers.connect(worker.abort)

    def update_current_values(self):
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
    def on_worker_step(self, result):
        """
        Collect data from worker
        - Recives data from worker(s)
        - Updates text indicators in GUI
        - Appends recived data to dataframes (call to self.__setStepData)
        - Updates data in plots (skips points if data is too big)
        """

        sensor_name = result[-1]

        if sensor_name == "MAX6675":
            # [self.data, self.sensor_name]
            self.datadict[sensor_name] = pd.concat([self.datadict[sensor_name], result[0]], ignore_index=True)
            self.save_data(sensor_name)
            self.currentvalues["T"] = self.datadict[sensor_name].iloc[-3:]["T"].mean()
            # plot data
            time = self.datadict[sensor_name]["time"].values.astype(float)
            temperature = self.datadict[sensor_name]["T"].values.astype(float)
            self.valueTPlot.setData(time, temperature)

        if sensor_name == "ADC":
            #  self.send_step_data.emit([newdata, self.sensor_name])
            self.datadict[sensor_name] = pd.concat([self.datadict[sensor_name], result[0]], ignore_index=True)
            self.save_data(sensor_name)
            for plotname, name in zip(ADCSIGNALS, ADCCONVERTED):
                self.currentvalues[plotname] = self.datadict["ADC"].iloc[-3:][name].mean()
            # plot data
            time = self.datadict[sensor_name]["time"].values.astype(float)
            ip = self.datadict[sensor_name]["Ip_c"].values.astype(float)
            p1 = self.datadict[sensor_name]["P1_c"].values.astype(float)
            p2 = self.datadict[sensor_name]["P2_c"].values.astype(float)
            self.valuePlaPlot.setData(time, ip)
            self.valueP1Plot.setData(time, p1)
            self.valueP2Plot.setData(time, p2)

            self.update_current_values()

    def save_data(self, sensor_name):
        """
        Save sensor data        
        """
        savepath = self.savepaths[sensor_name]
        data = self.datadict[sensor_name]
        data.to_csv(savepath, mode="a", header=False, index=False)

    @QtCore.pyqtSlot(str)
    def on_worker_done(self, sensor_name):
        self.logDock.log.append("Worker #{} done".format(sensor_name))
        self.logDock.progress.append("-- Signal {} STOPPED".format(sensor_name))
        self.__workers_done += 1
        self.reset_data(sensor_name)

        if self.__workers_done == 2:
            self.abort_all_threads()
            self.logDock.log.append("No more plot workers active")

    @QtCore.pyqtSlot()
    def abort_all_threads(self):
        self.sigAbortWorkers.emit()
        self.logDock.log.append("Asking each worker to abort")
        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()
        self.logDock.log.append("All threads exited")

    def reset_data(self, sensor_name):
        self.datadict[sensor_name] = self.datadict[sensor_name].iloc[0:0]

    @QtCore.pyqtSlot()
    def registerTemp(self):
        value = self.registerDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvalues["T"]
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

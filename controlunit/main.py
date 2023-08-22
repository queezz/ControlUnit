import sys, datetime, os
import numpy as np
import pandas as pd
from PyQt5 import QtGui, QtCore, QtWidgets

from mainView import UIWindow
from worker import DAC8532, MCP4725, ADC, Worker, Calibrator

# from readsettings import make_datafolders, read_settings
import readsettings
from striphtmltags import strip_tags
import qmsSignal

import time
# from channels import TCCOLUMNS, ADCCOLUMNS, ADCCONVERTED, ADCSIGNALS, CHNLSADC
# from channels import CHHEATER, CHLED


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


# must inherit QtCore.QObject in order to use 'connect'
class MainWidget(QtCore.QObject, UIWindow):
    # DEFAULT_TEMPERATURE = 0
    DEFALT_VOLTAGE = 0
    STEP = 3

    sigAbortWorkers = QtCore.pyqtSignal()

    def __init__(self, app: QtWidgets.QApplication):
        super(self.__class__, self).__init__()
        self.__app = app
        self.connections()
        # self.tempcontrolDock.set_heating_goal(self.DEFAULT_TEMPERATURE, "---")
        self.mfccontrolDock.set_output1_goal(self.DEFALT_VOLTAGE, "---")
        self.mfccontrolDock.set_output2_goal(self.DEFALT_VOLTAGE, "---")




        QtCore.QThread.currentThread().setObjectName("main")

        self.__workers_done = 0
        self.__threads = []
        # self.__temp = self.DEFAULT_TEMPERATURE
        self.__mfc1 = self.DEFALT_VOLTAGE
        self.__mfc2 = self.DEFALT_VOLTAGE

        self.calibration_waiting_time = self.mfccontrolDock.scaleBtn.currentText()

        self.plaData = None
        self.trigData = None
        self.tData = None
        self.p1Data = None
        self.p2Data = None

        self.config = readsettings.init_configuration(verbose=True)
        self.datapath = self.config["Data Folder"]
        self.sampling = self.config["Sampling Time"]

        # Plot line colors
        # self.currentvalues = {"Ip": 0, "P1": 0, "P2": 0, "T": 0}
        # self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"] + ["T"]}
        self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"]}
        self.baratronsignal1 = 0
        self.baratronsignal2 = 0
        self.pens = {
            "Ip": {"color": "#8d3de3", "width": 2},
            "Pu": {"color": "#c9004d", "width": 2},
            "Pd": {"color": "#6ac600", "width": 2},
            "Bu": {"color": "#ffb405", "width": 2},
            "Bd": {"color": "#00a3af", "width": 2},
            # "T": {"color": "#5999ff", "width": 2},
            "trigger": {"color": "#edbc34", "width": 2},
        }
        self.valuePlaPlot = self.graph.plaPl.plot(pen=self.pens["Ip"])
        self.triggerPlot = self.graph.plaPl.plot(pen=self.pens["trigger"])
        # self.valueTPlot = self.graph.tempPl.plot(pen=self.pens["T"])
        self.valueP1Plot = self.graph.presPl.plot(pen=self.pens["Pu"])
        self.valueP2Plot = self.graph.presPl.plot(pen=self.pens["Pd"])
        self.valueB1Plot = self.graph.presPl.plot(pen=self.pens["Bu"])
        self.valueB2Plot = self.graph.presPl.plot(pen=self.pens["Bd"])
        # self.graph.tempPl.setXLink(self.graph.presPl)
        self.graph.plaPl.setXLink(self.graph.presPl)

        self.graph.presPl.setLogMode(y=True)
        self.graph.presPl.setYRange(-8, 3, 0)
        # self.graph.tempPl.setYRange(0, 320, 0)

        self.tWorker = None
        self.adcWorker = None
        self.dacWorker = None
        self.calibrating = False

        self.update_plot_timewindow()

        self.showMain()
        self.log_to_file(f"App started: {os.path.abspath(__file__)}")

    def update_plot_timewindow(self):
        """
        adjust time window for data plots
        """
        # index = self.controlDock.scaleBtn.currentIndex()
        txt = self.controlDock.scaleBtn.currentText()
        val = self.controlDock.sampling_windows[txt]
        self.time_window = val
        # self.log_message(f"Timewindow = {val}")
        try:
            [self.update_plots(sensor_name) for sensor_name in self.sensor_names]
        except AttributeError:
            pass
            # print("can't update plots, no workers yet")

    def update_baratron_gain(self):
        """"""
        txt = self.ADCGainDock.gain_box.currentText()
        val = self.ADCGainDock.gains[txt]
        self.baratrongain = val
        # print(f"ADC gain = {val}")

    def connections(self):
        self.controlDock.scaleBtn.currentIndexChanged.connect(self.update_plot_timewindow)
        self.ADCGainDock.gain_box.currentIndexChanged.connect(self.update_baratron_gain)
        self.ADCGainDock.set_gain_btn.clicked.connect(self.__set_gain)

        # self.tempcontrolDock.registerBtn.clicked.connect(self.set_heater_goal)
        self.mfccontrolDock.registerBtn1.clicked.connect(self.set_mfc1_goal)
        self.mfccontrolDock.registerBtn2.clicked.connect(self.set_mfc2_goal)
        self.mfccontrolDock.resetBtn1.clicked.connect(self.resetSpinBoxes1)
        self.mfccontrolDock.resetBtn2.clicked.connect(self.resetSpinBoxes2)
        self.mfccontrolDock.scaleBtn.currentIndexChanged.connect(self.update_calibration_waiting_time)
        self.mfccontrolDock.calibrationBtn.clicked.connect(self.calibration)
        self.controlDock.IGmode.currentIndexChanged.connect(self.update_ig_mode)
        self.controlDock.IGrange.valueChanged.connect(self.update_ig_range)

        self.controlDock.FullNormSW.clicked.connect(self.fulltonormal)
        self.controlDock.OnOffSW.clicked.connect(self.__onoff)
        self.controlDock.quitBtn.clicked.connect(self.__quit)
        self.controlDock.qmsSigSw.clicked.connect(self.sync_signal_switch)

        self.controlDock.currentsetBtn.clicked.connect(self.set_currentcontrol_voltage)

        # Toggle plots for Current, Temperature, and Pressure
        self.scaleDock.togIp.clicked.connect(self.toggle_plots)
        # self.scaleDock.togT.clicked.connect(self.toggle_plots)
        self.scaleDock.togP.clicked.connect(self.toggle_plots)

        self.scaleDock.Pmin.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Pmax.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Imin.valueChanged.connect(self.__updateIScale)
        self.scaleDock.Imax.valueChanged.connect(self.__updateIScale)
        # self.scaleDock.Tmax.valueChanged.connect(self.__updateTScale)

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
                if self.controlDock.qmsSigSw.isChecked():
                    pi = pigpio.pi()
                    self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 0)
                    self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
                    self.qmsSigThread.start()
                    self.adcWorker.setQmsSignal(0)
                    self.controlDock.qmsSigSw.setChecked(False)
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

    # def __updateTScale(self):
    #     """Updated plot limits for the Temperature viewgraph"""
    #     tmax = self.scaleDock.Tmax.value()
    #     self.graph.tempPl.setYRange(0, tmax, 0)

    def __updateScales(self):
        """Update all scales according to spinboxes"""
        self.__updateIScale()
        # self.__updateTScale()
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

    def toggle_plots(self):
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
            # "T": [self.scaleDock.togT, self.graph.tempPl, 1, 0],
            "P": [self.scaleDock.togP, self.graph.presPl, 1, 0],
        }

        [toggleplot(*items[jj]) for jj in ["Ip",  "P"]]

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

            self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 0)
            self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
            self.qmsSigThread.start()
            self.adcWorker.setQmsSignal(0)


    def qmsSignalTerminate(self):
        self.qmsSigThread.quit()
        self.qmsSigThread.wait()

    def prep_threads(self):
        """
        Define Workers to run in separate threads.
        2020/03/05: two sensors: ADC and temperatures, hence
        2 threds to read a) temperature, and b) analog signals (P1,P2, Ip)
        """
        self.log_message("<font color='#1cad47'>Starting</font> acquisition", htmltag="h2")
        self.savepaths = {}
        self.datadict = {
            # "MAX6675": pd.DataFrame(columns=self.config["Temperature Columns"]),
            "ADC": pd.DataFrame(columns=self.config["ADC Column Names"]),
        }
        self.newdata = {
            # "MAX6675": pd.DataFrame(columns=self.config["Temperature Columns"]),
            "ADC": pd.DataFrame(columns=self.config["ADC Column Names"]),
        }

        self.__workers_done = 0

        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

        now = datetime.datetime.now()
        threads = {}

        # DAC8532 for mfc control
        sensor_name = "DAC8532"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.dacWorker = DAC8532(sensor_name, self.__app, now, self.config)
        self.dacWorker.dac_init()

        sensor_name = "MCP4725"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.mcpWorker = MCP4725(sensor_name, self.__app,now, self.config)
        self.mcpWorker.mcp_init()

        # MAX6675 thermocouple sensor for Membrane temperature with PID
        # sensor_name = "MAX6675"
        # threads[sensor_name] = QtCore.QThread()
        # threads[sensor_name].setObjectName(f"{sensor_name}")
        # self.tWorker = MAX6675(sensor_name, self.__app, now, self.config)
        # self.tWorker.setTempWorker(self.__temp)

        # Multichannel ADC
        sensor_name = "ADC"
        threads[sensor_name] = QtCore.QThread()
        threads[sensor_name].setObjectName(f"{sensor_name}")
        self.adcWorker = ADC(sensor_name, self.__app, now, self.config)

        mode = self.controlDock.IGmode.currentIndex()
        scale = self.controlDock.IGrange.value()
        self.adcWorker.init_adc_worker(mode, scale)

        # workers = {worker.sensor_name: worker for worker in [self.tWorker, self.adcWorker]}
        workers = {worker.sensor_name: worker for worker in [self.dacWorker,self.mcpWorker, self.adcWorker]}
        self.sensor_names = list(workers)

        [self.start_thread(workers[s], threads[s]) for s in self.sensor_names]

    def generate_time_stamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_to_file(self, message):
        filepath = self.config["Log File Path"]
        time_stamp = self.generate_time_stamp()
        new_line = f"{time_stamp}, {message}\n"
        with open(filepath, "a") as f:
            f.write(new_line)

    def log_message(self, message, htmltag="p"):
        """
        Append a message to the log browser with a timestamp.
        """
        time_stamp = self.generate_time_stamp()
        self.log_to_file(strip_tags(message))
        new_line = f"<{htmltag}>{time_stamp}: {message}</{htmltag}>"
        if not self.logDock.log.toPlainText():
            self.logDock.log.setHtml(new_line)
        else:
            current_text = self.logDock.log.toHtml()
            current_text += new_line
            self.logDock.log.setHtml(current_text)

        self.logDock.log.moveCursor(self.logDock.log.textCursor().End)
        # self.logDock.log.append(f"<{htmltag}>{nowstamp}: {message}</{htmltag}>")

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

        # if worker.sensor_name != "DAC8532" or worker.sensor_name != "MCP4725":
        if worker.sensor_name == "ADC":
            self.create_file(worker.sensor_name)
            self.log_message(
                f"<font size=4 color='blue'>{worker.sensor_name}</font> savepath:<br> {self.savepaths[worker.sensor_name]}",
            )

        thread.started.connect(worker.start)
        thread.start()

    def create_file(self, sensor_name):
        """
        Create file for saving sensor data
        """
        # if sensor_name == "MAX6675":
        #     self.savepaths[sensor_name] = os.path.join(
        #         os.path.abspath(self.datapath),
        #         f"cu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_temp.csv",
        #     )
        #     with open(self.savepaths[sensor_name], "w") as f:
        #         f.writelines(self.generate_header_temperature())
        if sensor_name == "ADC":
            self.savepaths[sensor_name] = os.path.join(
                os.path.abspath(self.datapath), f"cu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            with open(self.savepaths[sensor_name], "w") as f:
                f.writelines(self.generate_header_adc())

    def generate_header_adc(self):
        """
        Generage ADC header
        """
        return [
            "# Title , Control Unit ADC signals\n",
            f"# Date , {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"# Columns , {', '.join(self.config['ADC Column Names'])}\n",
            f"# Signals , {', '.join(self.config['ADC Signal Names'])}\n",
            f"# Channels , {', '.join([str(i) for i in self.config['ADC Channel Numbers']])}\n",
            "# For converted signals '_c' is added\n",
            "#\n",
            "# [Data]\n",
        ]

    def generate_header_temperature(self):
        """
        Generage Teperature header
        """
        return [
            "# Control Unit Temperature Control signals\n",
            f"# Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"# Columns: {', '.join(self.config['Temperature Columns'])}\n",
            f"# Heater GPIO: {self.config['Heater GPIO']}\n",
            f"# LED GPIO: {self.config['LED GPIO']}\n",
            "#\n",
            "# [Data]\n",
        ]

    def connect_worker_signals(self, worker):
        """
        Connects worker signals to the main thread
        """
        worker.send_step_data.connect(self.on_worker_step)
        worker.sigDone.connect(self.on_worker_done)
        worker.send_message.connect(self.log_message)
        self.sigAbortWorkers.connect(worker.abort)

    def update_current_values(self):
        """
        update current values when new signal comes
        """

        # TODO: updated dislpayed valuves from dataframes

        # self.tempcontrolDock.update_displayed_temperatures(self.__temp, f"{self.currentvalues['T']:.0f}")
        self.mfccontrolDock.update_displayed_voltage(self.__mfc1,f"{self.currentvalues['MFC1']*1000:.0f}",1)
        self.mfccontrolDock.update_displayed_voltage(self.__mfc2,f"{self.currentvalues['MFC2']*1000:.0f}",2)
        # self.controlDock.gaugeT.update_value(self.currentvalues["T"])
        txt = f"""
              <table>
                 <tr>
                  <td>
                   <font size=4 color={self.pens['Pu']['color']}>
                    Pu = {self.currentvalues['Pu']:.1e}                    
                  </font>
                  </td>
                  <td>
                  <font size=4 color={self.pens['Pd']['color']}>
                    Pd = {self.currentvalues['Pd']:.1e}
                   </font>
                  </td>
                  <td>
                   <font size=4 color={self.pens['Ip']['color']}>
                    I = {self.currentvalues['Ip']:.2f}
                   </font>
                  </td>
                 </tr>
                 <tr>
                  <td>
                   <font size=4 color={self.pens['Bu']['color']}>
                    Bu = {self.currentvalues['Bu']:.1e}
                   </font>
                  </td>
                  <td>
                   <font size=4 color={self.pens['Bd']['color']}>
                    Bd = {self.currentvalues['Bd']:.1e}
                   </font>
                  </td>   
                  <td>
                   <font size=4 color={self.pens['Bd']['color']}>
                    Bd = {self.baratronsignal2:.4f}
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
            self.newdata[sensor_name] = result[0]
            self.append_data(sensor_name)
            self.save_data(sensor_name)
            # here 3 is number of data points recieved from worker.
            # TODO: update to self.newdata[sensor_name]['T'].mean()
            self.currentvalues["T"] = self.datadict[sensor_name].iloc[-3:]["T"].mean()
            self.update_plots(sensor_name)

        if sensor_name == "ADC":
            #  self.send_step_data.emit([newdata, self.sensor_name])
            self.newdata[sensor_name] = result[0]
            self.append_data(sensor_name)
            self.save_data(sensor_name)
            for plotname, name in zip(self.config["ADC Signal Names"], self.config["ADC Converted Names"]):
                self.currentvalues[plotname] = self.datadict["ADC"].iloc[-3:][name].mean()
            # to debug mV signal from Baratron, ouptut it directly.
            self.baratronsignal1 = self.datadict["ADC"].iloc[-3:]["Bu"].mean()
            self.baratronsignal2 = self.datadict["ADC"].iloc[-3:]["Bd"].mean()
            self.update_plots(sensor_name)

        self.update_current_values()

    def calculate_skip_points(self, l, noskip=5000):
        return 1 if l < noskip else l // noskip + 1

    def update_plots(self, sensor_name):
        """"""
        # if sensor_name == "MAX6675":
        #     df = self.select_data_to_plot(sensor_name)
        #     time = df["time"].values.astype(float)
        #     # temperature = df["T"].values.astype(float)
            # skip = self.calculate_skip_points(time.shape[0])
            # self.valueTPlot.setData(time[::skip], temperature[::skip])

        if sensor_name == "ADC":
            df = self.select_data_to_plot(sensor_name)
            time = df["time"].values.astype(float)
            ip = df["Ip_c"].values.astype(float)
            p1 = df["Pu_c"].values.astype(float)
            p2 = df["Pd_c"].values.astype(float)
            b1 = df["Bu_c"].values.astype(float)
            b2 = df["Bd_c"].values.astype(float)
            skip = self.calculate_skip_points(time.shape[0])
            self.valuePlaPlot.setData(time[::skip], ip[::skip])
            self.valueP1Plot.setData(time[::skip], p1[::skip])
            self.valueP2Plot.setData(time[::skip], p2[::skip])
            self.valueB1Plot.setData(time[::skip], b1[::skip])
            self.valueB2Plot.setData(time[::skip], b2[::skip])

    def append_data(self, sensor_name):
        """
        Append new data to dataframe
        """
        self.datadict[sensor_name] = pd.concat(
            [self.datadict[sensor_name], self.newdata[sensor_name]], ignore_index=True
        )

    def select_data_to_plot(self, sensor_name):
        """
        Select data based on self.time_window
        """
        df = self.datadict[sensor_name]
        if self.time_window > 0:
            last_ts = df["date"].iloc[-1]
            timewindow = last_ts - pd.Timedelta(self.time_window, "seconds")
            df = df[df["date"] > timewindow]
        return df

    def save_data(self, sensor_name):
        """
        Save sensor data
        """
        savepath = self.savepaths[sensor_name]
        data = self.newdata[sensor_name]
        data.to_csv(savepath, mode="a", header=False, index=False)

    @QtCore.pyqtSlot(str)
    def on_worker_done(self, sensor_name):
        self.log_message(
            f"Sensor thread <font size=4 color='blue'> {sensor_name}</font> <font size=4 color={'red'}>stopped</font>",
            htmltag="div",
        )
        self.__workers_done += 1
        self.reset_data(sensor_name)

        if self.__workers_done == 2:
            self.abort_all_threads()

    @QtCore.pyqtSlot()
    def abort_all_threads(self):
        self.sigAbortWorkers.emit()
        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

    def reset_data(self, sensor_name):
        self.datadict[sensor_name] = self.datadict[sensor_name].iloc[0:0]
        self.newdata[sensor_name] = self.newdata[sensor_name].iloc[0:0]

    @QtCore.pyqtSlot()
    def set_heater_goal(self):
        value = self.tempcontrolDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvalues["T"]
        self.tempcontrolDock.set_heating_goal(self.__temp, f"{temp_now:.0f}")
        if self.tWorker is not None:
            self.tWorker.setPresetTemp(self.__temp)

    @QtCore.pyqtSlot()
    def set_mfc1_goal(self):
        value=0
        for i, spin_box in enumerate(self.mfccontrolDock.masflowcontrolerSB1):
            voltage = spin_box.value()
            value += (voltage * pow(10, 3-i))
        if value > 5000:
            value = 5000
        self.__mfc1 = value
        voltage_now = self.currentvalues["MFC1"]
        self.mfccontrolDock.set_output1_goal(self.__mfc1,f"{voltage_now*1000:.0f}")
        if self.dacWorker is not None:
            self.dacWorker.output_voltage(1,self.__mfc1)
        if self.adcWorker is not None:
            self.adcWorker.setPresetV_mfc1(self.__mfc1)

    

    @QtCore.pyqtSlot()
    def set_mfc2_goal(self):
        value=0
        for i, spin_box in enumerate(self.mfccontrolDock.masflowcontrolerSB2):
            voltage = spin_box.value()
            value += (voltage * pow(10, 3-i))
        if value > 5000:
            value = 5000
        self.__mfc2 = value
        voltage_now = self.currentvalues["MFC2"]
        self.mfccontrolDock.set_output2_goal(self.__mfc2,f"{voltage_now*1000:.0f}")
        if self.dacWorker is not None:
            self.dacWorker.output_voltage(2, self.__mfc2)
        if self.adcWorker is not None:
            self.adcWorker.setPresetV_mfc2(self.__mfc2)


    @QtCore.pyqtSlot()
    def resetSpinBoxes1(self):
        for spin_box in self.mfccontrolDock.masflowcontrolerSB1:
            spin_box.setValue(0)

    @QtCore.pyqtSlot()
    def resetSpinBoxes2(self):
        for spin_box in self.mfccontrolDock.masflowcontrolerSB2:
            spin_box.setValue(0)

    def update_calibration_waiting_time(self):
        txt = self.mfccontrolDock.scaleBtn.currentText()
        value = self.mfccontrolDock.sampling_windows[txt]
        self.calibration_waiting_time = value

    def calibration(self):
        """
        Start and stop calibration
        """
        if not self.dacWorker.calibrating:
            stating_msg = "Are you sure you want to start calibration?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow, "Message", stating_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                # self.dacWorker.calibration(self.__mfc1,step=10,waiting_time=1)
                try:
                    pi = pigpio.pi()
                except:
                    print("pigpio is not defined")
                    return
                self.calibration_thread = Calibrator(self.__app, self.dacWorker,self.adcWorker,self.__mfc1,10,self.calibration_waiting_time)
                self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 2, self.adcWorker)
                self.calibration_thread.finished.connect(self.calibration_terminated)
                self.calibration_thread.start()
                self.qmsSigThread.start()


            else:
                pass
        else:
            ending_msg = "Are you sure you want to stop calibration?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow, "Message", ending_msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.dacWorker.calibrating = False
                self.calibration_terminated()
            else:
                pass

    def calibration_terminated(self):
        self.qmsSigThread.quit()
        self.qmsSigThread.wait()
        self.calibration_thread.wait()
        self.calibration_thread.quit()
        pi = pigpio.pi()
        self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 0)
        self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
        self.qmsSigThread.start()
        self.adcWorker.setQmsSignal(0)
        self.controlDock.qmsSigSw.setChecked(False)

    @QtCore.pyqtSlot()
    def set_currentcontrol_voltage(self):
        """
        Set voltage for current control
        """
        value = self.controlDock.currentcontrolerSB.value()
        if self.mcpWorker is not None:
            self.mcpWorker.output_voltage(value)
        if self.adcWorker is not None:
            self.adcWorker.setPresetV_cathode(value)
    



    @QtCore.pyqtSlot()
    def update_ig_mode(self):
        """Update mode of the IG controller:
        Torr and linear
        or
        Pa and log
        """
        value = self.controlDock.IGmode.currentIndex()
        if self.adcWorker is not None:
            self.adcWorker.setIGmode(value)

    @QtCore.pyqtSlot()
    def __set_gain(self):
        """
        Set gain for Baratron channel on ADC
        Parameters
        ----------
        value: int
            gain, values [1,2,5,10] (in V)
        """
        txt = self.ADCGainDock.gain_box.currentText()
        gain = self.ADCGainDock.gains[txt]

        if self.adcWorker is not None:
            self.adcWorker.setGain(gain)

    @QtCore.pyqtSlot()
    def __set_sampling(self):
        """Set sampling time for all threads"""
        if not len(self.__threads):
            return
        txt = self.SettingsDock.samplingCb.currentText()
        value = float(txt.split(" ")[0])
        self.sampling = value
        self.update_plot_timewindow()
        if self.adcWorker is not None:
            self.adcWorker.setSampling(value)
            self.log_message(f"ADC sampling set to {value}")

        # For MAX6675 min read time is 0.25s
        # if self.tWorker is not None:
        #     if value < 0.25:
        #         value = 0.25
        #     self.tWorker.setSampling(value)
        #     self.log_message(f"MAX6675 sampling set to {value}")
# 
        # if self.dacWorker is not None:
        #     self.dacWorker.setSampling(value)
        #     self.log_message(f"DAC sampling set to {value}")

    @QtCore.pyqtSlot()
    def update_ig_range(self):
        """Update range of the IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        value = self.controlDock.IGrange.value()
        if self.adcWorker is not None:
            self.adcWorker.setIGrange(value)
            print(f"pressed\ncurrent value = {value}")


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

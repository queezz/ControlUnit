import sys, datetime, os
from datetime import timedelta
import pandas as pd
from PyQt5 import QtCore, QtWidgets

from mainView import UIWindow
from controlunit.devices.adc import ADC
from controlunit.devices.dac8532 import DAC8532
from controlunit.devices.mcp4725 import MCP4725
from calibrator import Calibrator

# from readsettings import make_datafolders, read_settings
import readsettings
from striphtmltags import strip_tags
import qmsSignal

# from channels import TCCOLUMNS, ADCCOLUMNS, ADCCONVERTED, ADCSIGNALS, CHNLSADC
# from channels import CHHEATER, CHLED

RED = "\033[1;31m"
GREEN = "\033[1;32m"
BLUE = "\033[1;34m"
RESET = "\033[0m"
GOOD = "\U00002705"
BAD = "\U0000274C"


try:
    import pigpio
except ImportError as e:
    print(RED + "main.py Error: " + RESET + f"{e}")
    TEST = True
    from devices.dummy import pigpio

    print(
        BLUE
        + "main.py WARNING:"
        + RESET
        + " importing"
        + BLUE
        + " DUMMY"
        + RESET
        + " sensros.dummy.pigpio"
    )


# must inherit QtCore.QObject in order to use 'connect'
class MainWidget(QtCore.QObject, UIWindow):
    # DEFAULT_TEMPERATURE = 0
    DEFAULT_VOLTAGE = 0
    STEP = 3

    sigAbortWorkers = QtCore.pyqtSignal()

    plaData = trigData = tData = p1Data = p2Data = None
    # membrane_temperature_control = adc_signals = mfcs_control = None
    calibrating = False

    # MARK: init
    def __init__(self, app: QtWidgets.QApplication):
        super(self.__class__, self).__init__()
        self.__app = app
        self.connections()
        # self.tempcontrolDock.set_heating_goal(self.DEFAULT_TEMPERATURE, "---")
        self.mfccontrolDock.set_output1_goal(self.DEFAULT_VOLTAGE, "---")
        self.mfccontrolDock.set_output2_goal(self.DEFAULT_VOLTAGE, "---")

        QtCore.QThread.currentThread().setObjectName("main")

        self.__workers_done = 0
        self.__threads = []
        # self.__temp = self.DEFAULT_TEMPERATURE
        self.__mfc1 = self.DEFAULT_VOLTAGE
        self.__mfc2 = self.DEFAULT_VOLTAGE

        self.calibration_waiting_time = self.mfccontrolDock.scaleBtn.currentText()

        self.config = readsettings.init_configuration(verbose=True)
        self.datapath = self.config["Data Folder"]
        self.sampling = self.config["Sampling Time"]

        # MARK: Current Values
        # To display in text browser
        # self.currentvalues = {"Ip": 0, "P1": 0, "P2": 0, "T": 0}
        # self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"] + ["T"]}
        self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"]}
        self.baratronsignal1 = 0
        self.baratronsignal2 = 0

        ## GRAPHS definitions moved to graph.py

        self.controlDock.scaleBtn.setCurrentIndex(2)
        self.update_plot_timewindow()
        self.set_scales_switches()

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
            [self.update_plots(device) for device in self.device_name]
        except AttributeError:
            pass
            # print("can't update plots, no workers yet")

    def update_baratron_gain(self):
        """"""
        txt = self.ADCGainDock.gain_box.currentText()
        val = self.ADCGainDock.gains[txt]
        self.baratrongain = val
        # print(f"ADC gain = {val}")

    # MARK: connections
    def connections(self):
        self.controlDock.scaleBtn.currentIndexChanged.connect(
            self.update_plot_timewindow
        )
        self.ADCGainDock.gain_box.currentIndexChanged.connect(self.update_baratron_gain)
        self.ADCGainDock.set_gain_btn.clicked.connect(self.__set_gain)

        # self.tempcontrolDock.registerBtn.clicked.connect(self.set_heater_goal)
        self.mfccontrolDock.registerBtn1.clicked.connect(self.set_mfc1_goal)
        self.mfccontrolDock.registerBtn2.clicked.connect(self.set_mfc2_goal)
        self.mfccontrolDock.resetBtn1.clicked.connect(self.resetSpinBoxes1)
        self.mfccontrolDock.resetBtn2.clicked.connect(self.resetSpinBoxes2)
        self.mfccontrolDock.scaleBtn.currentIndexChanged.connect(
            self.update_calibration_waiting_time
        )
        self.mfccontrolDock.calibrationBtn.clicked.connect(self.calibration)
        self.mfccontrolDock.stopBtn.clicked.connect(self.stop_mfc)

        self.controlDock.IGmode.currentIndexChanged.connect(self.update_ig_mode)
        self.controlDock.IGrange.valueChanged.connect(self.update_ig_range)

        self.controlDock.FullNormSW.clicked.connect(self.fulltonormal)
        self.controlDock.OnOffSW.clicked.connect(self.__onoff)
        self.controlDock.quitBtn.clicked.connect(self.__quit)
        self.controlDock.qmsSigSw.clicked.connect(self.sync_signal_switch)

        # self.controlDock.currentsetBtn.clicked.connect(self.set_currentcontrol_voltage)

        # Toggle plots for Current, Temperature, and Pressure
        self.scaleDock.togIp.clicked.connect(self.toggle_plots)
        self.scaleDock.togBaratron.clicked.connect(self.toggle_plots_baratron)
        self.scaleDock.togIGs.clicked.connect(self.toggle_plots_igs)
        self.scaleDock.togP.clicked.connect(self.toggle_plots)

        self.scaleDock.Pmin.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Pmax.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Imin.valueChanged.connect(self.__updateIScale)
        self.scaleDock.Imax.valueChanged.connect(self.__updateIScale)
        # self.scaleDock.Tmax.valueChanged.connect(self.__updateTScale)

        self.scaleDock.autoscale.clicked.connect(self.__auto_or_levels)
        self.SettingsDock.setSamplingBtn.clicked.connect(self.__set_sampling)
        self.scaleDock.togYLog.clicked.connect(self.__toggleYLogScale)

    # MARK: GUI setup
    def set_scales_switches(self):
        """Set default checks for swithces in Scales"""
        self.scaleDock.togP.setChecked(True)
        self.scaleDock.togBaratron.setChecked(False)
        self.scaleDock.togIp.setChecked(False)
        self.scaleDock.togYLog.setChecked(True)
        self.scaleDock.togIGs.setChecked(True)
        self.toggle_plots_baratron()
        self.toggle_plots_igs()
        self.toggle_plots()

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
                self.MainWindow,
                "Message",
                quit_msg,
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.abort_all_threads()
                self.controlDock.quitBtn.setEnabled(True)
                if self.controlDock.qmsSigSw.isChecked():
                    pi = pigpio.pi()
                    self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 0)
                    self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
                    self.qmsSigThread.start()
                    self.adc_signals.setQmsSignal(0)
                    self.controlDock.qmsSigSw.setChecked(False)
            else:
                self.controlDock.OnOffSW.setChecked(True)

    def __toggleYLogScale(self):
        """Toggle Y Scale between Log and Lin for Pressure plots"""
        if self.scaleDock.togYLog.isChecked():
            self.graph.pressure_plot.setLogMode(y=True)
        else:
            self.graph.pressure_plot.setLogMode(y=False)

    def __updatePScale(self):
        """Updated plot limits for the Pressure viewgraph"""
        pmin, pmax = [self.scaleDock.Pmin.value(), self.scaleDock.Pmax.value()]

        # self.graph.presPl.setLogMode(y=True)
        self.graph.pressure_plot.setYRange(pmin, pmax, 0)

    def __updateIScale(self):
        """Updated plot limits for the plasma current viewgraph"""
        imin, imax = [self.scaleDock.Imin.value(), self.scaleDock.Imax.value()]
        self.graph.plasma_plot.setYRange(imin, imax, 0)

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
        # plots = [self.graph.plasma_plot, self.graph.temperature_plot, self.graph.pressure_plot]
        plots = [self.graph.plasma_plot, self.graph.pressure_plot]

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
        Toggle plots - pyqtgraph GraphViews
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
            "Ip": [self.scaleDock.togIp, self.graph.plasma_plot, 0, 0],
            # "T": [self.scaleDock.togT, self.graph.tempPl, 1, 0],
            "P": [self.scaleDock.togP, self.graph.pressure_plot, 1, 0],
        }

        [toggleplot(*items[jj]) for jj in ["Ip", "P"]]

    def toggle_plots_baratron(self):
        if self.scaleDock.togBaratron.isChecked():
            self.graph.baratron_up_curve.setVisible(True)
            self.graph.baratron_down_curve.setVisible(True)
        else:
            self.graph.baratron_up_curve.setVisible(False)
            self.graph.baratron_down_curve.setVisible(False)

    def toggle_plots_igs(self):
        """Toggle IG and Pfeiffer lines"""
        if self.scaleDock.togIGs.isChecked():
            self.graph.pressure_up_curve.setVisible(True)
            self.graph.pressure_down_curve.setVisible(True)
        else:
            self.graph.pressure_up_curve.setVisible(False)
            self.graph.pressure_down_curve.setVisible(False)

    # MARK: Trigger
    def sync_signal_switch(self):
        """
        Experiment indicator, analog output is sent to QMS to sync
        expermint time between recording devices.
        This signal is helpfull to separate experiments (same as shot numbers in fusion)
        """
        if not self.controlDock.OnOffSW.isChecked():
            return

        pi = pigpio.pi()

        if self.controlDock.qmsSigSw.isChecked():
            self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 1)
            self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
            self.qmsSigThread.start()
            self.adc_signals.setQmsSignal(1)
        else:

            self.qmsSigThread = qmsSignal.SyncSignal(pi, self.__app, 0)
            self.qmsSigThread.finished.connect(self.qmsSignalTerminate)
            self.qmsSigThread.start()
            self.adc_signals.setQmsSignal(0)

    def qmsSignalTerminate(self):
        self.qmsSigThread.quit()
        self.qmsSigThread.wait()

    def define_devices(self):
        """
        Define devices and data structure
        """
        devices = {
            "MFCs": DAC8532,
            "PlasmaCurrent": MCP4725,
            "ADC": ADC,
        }
        # devices['MembraneTemperature'] = MAX6675

        self.devices = devices

        self.savepaths = {}
        self.datadict = {
            # "MembraneTemperature": pd.DataFrame(columns=self.config["Temperature Columns"]),
            "ADC": pd.DataFrame(columns=self.config["ADC Column Names"]),
        }
        self.newdata = {
            # "MembraneTemperature": pd.DataFrame(columns=self.config["Temperature Columns"]),
            "ADC": pd.DataFrame(columns=self.config["ADC Column Names"]),
        }

        self.create_file("ADC")

    # MARK: Threads
    def prep_threads(self):
        """
        Define Workers for Devices to run in separate threads.
        """
        self.log_message(
            "<font color='#1cad47'>Starting</font> acquisition", htmltag="h2"
        )
        self.__workers_done = 0
        self.terminate_existing_threads()
        self.define_devices()
        now = datetime.datetime.now()

        self.workers = {
            device_name: self.prep_worker(worker_class, device_name, now)
            for device_name, worker_class in self.devices.items()
        }

        self.start_all_threads()

    def prep_worker(self, device_class, device_name, start_time):
        """
        Generalized worker preparation method for different device types.
        """
        thread = QtCore.QThread()
        thread.setObjectName(f"{device_name}")

        worker = device_class(device_name, self.__app, start_time, self.config)

        return worker, thread

    def start_all_threads(self):
        """
        Start all threads by assigning workers to threads and initiating them.
        """
        for device_name, (worker, thread) in self.workers.items():
            self.start_thread(worker, thread)

    def terminate_existing_threads(self):
        """
        Gracefully quits and waits for all currently running threads.
        """
        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

    def start_thread(self, worker, thread):
        """
        Starts Device Worker thread
        """
        self.__threads.append((thread, worker))
        worker.moveToThread(thread)
        self.connect_worker_signals(worker)
        thread.started.connect(worker.start)
        thread.start()

    # MARK: logging
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

    def create_file(self, device_name):
        """
        Create file for saving sensor data
        """
        # if device_name == "MAX6675":
        #     self.savepaths[device_name] = os.path.join(
        #         os.path.abspath(self.datapath),
        #         f"cu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_temp.csv",
        #     )
        #     with open(self.savepaths[device_name], "w") as f:
        #         f.writelines(self.generate_header_temperature())
        if device_name == "ADC":
            self.savepaths[device_name] = os.path.join(
                os.path.abspath(self.datapath),
                f"cu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            with open(self.savepaths[device_name], "w") as f:
                f.writelines(self.generate_header_adc())

        self.log_datafile_name(device_name)

    def log_datafile_name(self, device_name):
        """Log filename of a datafile created"""
        message = (
            f"<font size=4 color='blue'>{device_name}</font>"
            f" savepath:<br> {self.savepaths[device_name]}"
        )
        self.log_message(message)

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

    # MARK: update values
    def update_current_values(self):
        """
        update current values when new signal comes
        """
        # self.tempcontrolDock.update_displayed_temperatures(self.__temp, f"{self.currentvalues['T']:.0f}")
        self.mfccontrolDock.update_display(
            self.__mfc1, f"{self.currentvalues['MFC1']*1000:.0f}", 1
        )
        self.mfccontrolDock.update_display(
            self.__mfc2, f"{self.currentvalues['MFC2']*1000:.0f}", 2
        )
        # self.controlDock.gaugeT.update_value(self.currentvalues["T"])
        font_size = 5
        txt = f"""
              <table>
                 <tr>
                  <td>
                   <font size={font_size} color={self.graph.pens['Pu']['color']}>
                    Pu = {self.currentvalues['Pu']:.2e}                    
                  </font>
                  </td>
                  <td>
                  <font size={font_size} color={self.graph.pens['Pd']['color']}>
                    Pd = {self.currentvalues['Pd']:.2e}
                   </font>
                  </td>
                  <td>
                   <font size={font_size} color={self.graph.pens['Ip']['color']}>
                    I = {self.currentvalues['Ip']:.2f}
                   </font>
                  </td>
                 </tr>
                 <tr>
                  <td>
                   <font size={font_size} color={self.graph.pens['Bu']['color']}>
                    Bu = {self.currentvalues['Bu']:.2e}
                   </font>
                  </td>
                  <td>
                   <font size={font_size} color={self.graph.pens['Bd']['color']}>
                    Bd = {self.currentvalues['Bd']:.2e}
                   </font>
                  </td>   
                 </tr>
                </table>
        """
        # Update current values
        self.controlDock.valueBw.setText(txt)

    # MARK: Worker Step
    @QtCore.pyqtSlot(list)
    def on_worker_step(self, result):
        """
        Collect data from worker
        - Recives data from worker(s)
        - Updates text indicators in GUI
        - Appends recived data to dataframes (call to self.__setStepData)
        - Updates data in plots (skips points if data is too big)
        """

        device_name = result[-1]

        if device_name == "MAX6675":
            # [self.data, self.device_name]
            self.newdata[device_name] = result[0]
            self.append_data(device_name)
            self.save_data(device_name)
            # here 3 is number of data points recieved from worker.
            # TODO: update to self.newdata[device_name]['T'].mean()
            self.currentvalues["T"] = self.datadict[device_name].iloc[-3:]["T"].mean()
            self.update_plots(device_name)

        if device_name == "ADC":
            #  self.send_step_data.emit([newdata, self.device_name])
            self.newdata[device_name] = result[0]
            self.append_data(device_name)
            self.save_data(device_name)
            for plotname, name in zip(
                self.config["ADC Signal Names"], self.config["ADC Converted Names"]
            ):
                self.currentvalues[plotname] = (
                    self.datadict["ADC"].iloc[-3:][name].mean()
                )
            # to debug mV signal from Baratron, ouptut it directly.
            self.baratronsignal1 = self.datadict["ADC"].iloc[-3:]["Bu"].mean()
            self.baratronsignal2 = self.datadict["ADC"].iloc[-3:]["Bd"].mean()
            self.update_plots(device_name)

        self.update_current_values()

    # MARK: Update Plots
    def update_plots(self, device_name):
        """
        Update plots
        """
        if device_name == "MAX6675":
            self.update_plots_max6675()
        if device_name == "ADC":
            self.update_plots_adc()

    def update_plots_max6675(self):
        """
        MAX6675 data: update plots
        """
        df = self.select_data_to_plot("MAX6675")
        time = df["time"].values.astype(float)
        temperature = df["T"].values.astype(float)
        skip = self.calculate_skip_points(time.shape[0])
        self.graph.valueTPlot.setData(time[::skip], temperature[::skip])

    def update_plots_adc(self):
        """
        Update plots for ADC dataframe
        """
        df = self.select_data_to_plot("ADC")
        # time = df["time"].values.astype(float)
        utc_offset = 9
        time = (
            df["date"]
            .apply(lambda x: (x - timedelta(hours=utc_offset)).timestamp())
            .values
        )

        ip = df["Ip_c"].values.astype(float)
        p1 = df["Pu_c"].values.astype(float)
        p2 = df["Pd_c"].values.astype(float)
        b1 = df["Bu_c"].values.astype(float)
        b2 = df["Bd_c"].values.astype(float)
        skip = self.calculate_skip_points(time.shape[0])
        self.graph.baratron_up_curve.setData(time[::skip], b1[::skip])
        self.graph.baratron_down_curve.setData(time[::skip], b2[::skip])
        self.graph.plasma_cruve.setData(time[::skip], ip[::skip])
        self.graph.pressure_up_curve.setData(time[::skip], p1[::skip])
        self.graph.pressure_down_curve.setData(time[::skip], p2[::skip])

    # MARK: append data
    def append_data(self, device_name):
        """
        Append new data to dataframe
        """
        # self.datadict[device_name] = pd.concat([self.datadict[device_name], self.newdata[device_name]], ignore_index=True)
        # Fix FutureWarning
        self.datadict[device_name] = pd.concat(
            [
                self.datadict[device_name],
                self.newdata[device_name].astype(self.datadict[device_name].dtypes),
            ],
            ignore_index=True,
        )
        # self.data = pd.concat([self.adc_values, new_data_row.astype(self.adc_values.dtypes)], ignore_index=True)

    def select_data_to_plot(self, device_name):
        """
        Select data based on self.time_window
        """
        df = self.datadict[device_name]
        if self.time_window > 0:
            last_ts = df["date"].iloc[-1]
            timewindow = last_ts - pd.Timedelta(self.time_window, "seconds")
            df = df[df["date"] > timewindow]
        return self.downsample_data(df)

    def downsample_data(self, df, noskip=3000):
        """downsample data"""
        if df.shape[0] > noskip:
            return df.iloc[:: df.shape[0] // noskip + 1]
        return df

    def calculate_skip_points(self, l, noskip=5000):
        return 1 if l < noskip else l // noskip + 1

    def save_data(self, device_name):
        """
        Save sensor data
        """
        savepath = self.savepaths[device_name]
        data = self.newdata[device_name]
        data.to_csv(savepath, mode="a", header=False, index=False)

    # MARK: worker done
    @QtCore.pyqtSlot(str)
    def on_worker_done(self, device_name):
        self.log_message(
            f"Sensor thread <font size=4 color='blue'> {device_name}</font> <font size=4 color={'red'}>stopped</font>",
            htmltag="div",
        )
        self.__workers_done += 1
        self.reset_data(device_name)

        if self.__workers_done == 2:
            self.abort_all_threads()

    @QtCore.pyqtSlot()
    def abort_all_threads(self):
        self.sigAbortWorkers.emit()
        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []

    def reset_data(self, device_name):
        self.datadict[device_name] = self.datadict[device_name].iloc[0:0]
        self.newdata[device_name] = self.newdata[device_name].iloc[0:0]

    @QtCore.pyqtSlot()
    def set_heater_goal(self):
        value = self.tempcontrolDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvalues["T"]
        self.tempcontrolDock.set_heating_goal(self.__temp, f"{temp_now:.0f}")
        if self.membrane_temperature_control is not None:
            self.membrane_temperature_control.setPresetTemp(self.__temp)

    @QtCore.pyqtSlot()
    def set_mfc1_goal(self):
        value = 0
        for i, spin_box in enumerate(self.mfccontrolDock.masflowcontrolerSB1):
            voltage = spin_box.value()
            value += voltage * pow(10, 3 - i)
        if value > 5000:
            value = 5000
        self.__mfc1 = value
        voltage_now = self.currentvalues["MFC1"]
        self.mfccontrolDock.set_output1_goal(self.__mfc1, f"{voltage_now*1000:.0f}")
        if self.mfcs_control is not None:
            self.mfcs_control.output_voltage(1, self.__mfc1)
        if self.adc_signals is not None:
            self.adc_signals.setPresetV_mfc1(self.__mfc1)

    @QtCore.pyqtSlot()
    def set_mfc2_goal(self):
        value = 0
        for i, spin_box in enumerate(self.mfccontrolDock.masflowcontrolerSB2):
            voltage = spin_box.value()
            value += voltage * pow(10, 3 - i)
        if value > 5000:
            value = 5000
        self.__mfc2 = value
        voltage_now = self.currentvalues["MFC2"]
        self.mfccontrolDock.set_output2_goal(self.__mfc2, f"{voltage_now*1000:.0f}")
        if self.mfcs_control is not None:
            self.mfcs_control.output_voltage(2, self.__mfc2)
        if self.adc_signals is not None:
            self.adc_signals.setPresetV_mfc2(self.__mfc2)

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

    # MARK: QMS Calibration
    def calibration(self):
        """
        Start and stop calibration
        """
        if not self.mfcs_control.calibrating:
            stating_msg = "Are you sure you want to start calibration?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow,
                "Message",
                stating_msg,
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                # self.dacWorker.calibration(self.__mfc1,step=10,waiting_time=1)
                try:
                    pi = pigpio.pi()
                except:
                    print("pigpio is not defined")
                    return
                self.calibration_thread = Calibrator(
                    self.__app,
                    self.mfcs_control,
                    self.adc_signals,
                    self.__mfc1,
                    10,
                    self.calibration_waiting_time,
                )
                self.qmsSigThread = qmsSignal.SyncSignal(
                    pi, self.__app, 2, self.adc_signals
                )
                self.calibration_thread.finished.connect(self.calibration_terminated)
                self.calibration_thread.start()
                self.qmsSigThread.start()

            else:
                pass
        else:
            ending_msg = "Are you sure you want to stop calibration?"
            reply = QtWidgets.QMessageBox.warning(
                self.MainWindow,
                "Message",
                ending_msg,
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.mfcs_control.calibrating = False
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
        self.adc_signals.setQmsSignal(0)
        self.controlDock.qmsSigSw.setChecked(False)

    # MARK: control signals
    @QtCore.pyqtSlot()
    def stop_mfc(self):
        value = 0
        self.__mfc1 = value
        self.__mfc2 = value
        voltage_now1 = self.currentvalues["MFC1"]
        voltage_now2 = self.currentvalues["MFC2"]

        self.mfccontrolDock.set_output1_goal(self.__mfc1, f"{voltage_now1*1000:.0f}")
        self.mfccontrolDock.set_output2_goal(self.__mfc2, f"{voltage_now2*1000:.0f}")
        if self.mfcs_control is not None:
            self.mfcs_control.output_voltage(1, self.__mfc1)
            self.mfcs_control.output_voltage(2, self.__mfc2)
        if self.adc_signals is not None:
            self.adc_signals.setPresetV_mfc1(self.__mfc1)
            self.adc_signals.setPresetV_mfc2(self.__mfc2)

    @QtCore.pyqtSlot()
    def set_currentcontrol_voltage(self):
        """
        Set voltage for current control
        """
        value = self.controlDock.currentcontrolerSB.value()
        if self.plasma_current_control is not None:
            self.plasma_current_control.output_voltage(value)
        if self.adc_signals is not None:
            self.adc_signals.setPresetV_cathode(value)

    @QtCore.pyqtSlot()
    def update_ig_mode(self):
        """
        Update mode of the IG controller:
        Torr and linear
        or
        Pa and log
        """
        value = self.controlDock.IGmode.currentIndex()
        if self.adc_signals is not None:
            self.adc_signals.setIGmode(value)

    @QtCore.pyqtSlot()
    def update_ig_range(self):
        """
        Update range of the IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        value = self.controlDock.IGrange.value()
        self.workers["ADC"][0].setIGrange(value)
        print(f"Ionization Gauge Range = {value}")

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

        if self.adc_signals is not None:
            self.adc_signals.setGain(gain)

    @QtCore.pyqtSlot()
    def __set_sampling(self):
        """Set sampling time for all threads"""
        if not len(self.__threads):
            return
        txt = self.SettingsDock.samplingCb.currentText()
        value = float(txt.split(" ")[0])
        self.sampling = value
        self.update_plot_timewindow()
        if self.adc_signals is not None:
            self.adc_signals.setSampling(value)
            self.log_message(f"ADC sampling set to {value}")


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

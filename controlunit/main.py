import sys, datetime, os
from datetime import timedelta
import pandas as pd
from PyQt5 import QtCore, QtWidgets, QtGui

from mainView import UIWindow
from controlunit.devices.adc import ADC
from controlunit.devices.dac8532 import DAC8532
from controlunit.devices.mcp4725 import MCP4725

import readsettings
from striphtmltags import strip_tags
from controlunit.trigger_signal import IndicatorLED

from controlunit.ui.text_shortcuts import RED, BLUE, RESET

try:
    import pigpio
    from start_gpio import start_pigpiod

    start_pigpiod()
except ImportError as e:
    print(RED + "main.py Error: " + RESET + f"{e}")
    TEST = True
    from devices.dummy import pigpio

    txt = f"{BLUE}main.py WARNING:{RESET} importing {BLUE} DUMMY{RESET} sensors.dummy.pigpio"
    print(txt)


class MainApp(QtCore.QObject, UIWindow):
    # DEFAULT_TEMPERATURE = 0
    DEFAULT_VOLTAGE = 0
    STEP = 3

    sigAbortWorkers = QtCore.pyqtSignal()

    # MARK: init
    def __init__(self, app: QtWidgets.QApplication):
        super(self.__class__, self).__init__()
        self.__app = app
        self.connections()
        # self.tempcontrolDock.set_heating_goal(self.DEFAULT_TEMPERATURE, "---")
        self.gasflow_dock.update_display(self.DEFAULT_VOLTAGE, "NaN", 1)
        self.gasflow_dock.update_display(self.DEFAULT_VOLTAGE, "NaN", 2)

        QtCore.QThread.currentThread().setObjectName("main")

        self.__workers_done = 0
        self.workers = {}
        # Define presets
        # self.__temp = self.DEFAULT_TEMPERATURE
        self._mfc_presets = {1: self.DEFAULT_VOLTAGE, 2: self.DEFAULT_VOLTAGE}

        self.config = readsettings.init_configuration(verbose=True)
        self.datapath = self.config["Data Folder"]
        self.sampling = self.config["Sampling Time"]

        # MARK: Current Values
        # To display in text browser
        self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"]}
        self.baratronsignal1 = 0
        self.baratronsignal2 = 0

        self.update_plot_timewindow()
        self.set_scales_switches()

        self.showMain()
        self.log_to_file(f"App started: {os.path.abspath(__file__)}")

    def update_plot_timewindow(self):
        """
        adjust time window for data plots
        """
        txt = self.control_dock.scaleBtn.currentText()
        val = self.control_dock.sampling_windows[txt]
        self.time_window = val
        try:
            [self.update_plots(device) for device in self.device_name]
        except AttributeError:
            pass

    def update_baratron_gain(self):
        """"""
        txt = self.adcgain_dock.gain_box.currentText()
        val = self.adcgain_dock.gains[txt]
        self.baratrongain = val

    # MARK: connections
    def connections(self):
        self._init_controldock_connections()
        self._init_adcgain_connections()
        self._init_mfc_connections()
        self._init_cocnnections()
        self._init_plot_controls()
        self._init_calibration_connections()
        self._init_plasmacontrol_connections()

        # self.tempcontrolDock.registerBtn.clicked.connect(self.set_heater_goal)

    def _init_plasmacontrol_connections(self):
        self.plasma_control_dock.set_dac_voltage.clicked.connect(
            self.set_currentcontrol_voltage
        )

    def _init_calibration_connections(self):
        self.calibration_dock.calibrationBtn.clicked.connect(self.calibration)
        self.calibration_dock.stopBtn.clicked.connect(self.stop_mfc)

    def _init_mfc_connections(self):
        self.gasflow_dock.registerBtn1.clicked.connect(lambda: self.set_mfc_goal(1))
        self.gasflow_dock.registerBtn2.clicked.connect(lambda: self.set_mfc_goal(2))

    def _init_controldock_connections(self):
        self.control_dock.IGmode.currentIndexChanged.connect(self.update_ig_mode)
        self.control_dock.IGrange.valueChanged.connect(self.update_ig_range)
        self.control_dock.FullNormSW.clicked.connect(self.fulltonormal)
        self.control_dock.OnOffSW.clicked.connect(self.__onoff)
        self.control_dock.quitBtn.clicked.connect(self.__quit)
        self.control_dock.qmsSigSw.clicked.connect(self._toggle_led_status)
        self.control_dock.scaleBtn.currentIndexChanged.connect(
            self.update_plot_timewindow
        )

    def _init_adcgain_connections(self):
        self.adcgain_dock.gain_box.currentIndexChanged.connect(
            self.update_baratron_gain
        )
        self.adcgain_dock.set_gain_btn.clicked.connect(self.__set_gain)

    def _init_cocnnections(self):
        """Toggle plots for Current, Temperature, and Pressure"""
        self.settings_dock.setSamplingBtn.clicked.connect(self.__set_sampling)
        self.scale_dock.subzero_ip.clicked.connect(self._set_zero_ip)

    # MARK: GUI setup

    def __quit(self):
        """terminate app"""
        self.__app.quit()

    def __onoff(self):
        """
        Start and stop worker threads
        """
        if self.control_dock.OnOffSW.isChecked():
            self.prep_threads()
            self.control_dock.quitBtn.setEnabled(False)
            return

        question = "Are you sure you want to stop data acquisition?"
        if self.popup_confirmation_window(question):
            self.abort_all_threads()
            self.control_dock.quitBtn.setEnabled(True)
        else:
            self.control_dock.OnOffSW.setChecked(True)

    def _toggle_led_status(self):
        if not self.control_dock.OnOffSW.isChecked():
            return
        if self.control_dock.qmsSigSw.isChecked():
            self.indicator_led.on()
        else:
            self.indicator_led.off()

    def fulltonormal(self):
        """Change from full screen to normal view on click"""
        if self.control_dock.FullNormSW.isChecked():
            self.MainWindow.showFullScreen()
            self.control_dock.setStretch(*(10, 300))  # minimize control dock width
        else:
            self.MainWindow.showNormal()
            self.control_dock.setStretch(*(10, 300))  # minimize control dock width

    # MARK: Devices
    def define_devices(self):
        """
        Define devices, data structure, and step methods
        """
        devices = {
            "MFCs": DAC8532,
            "PlasmaCurrent": MCP4725,
            "ADC": ADC,
        }
        # devices['MembraneTemperature'] = MAX6675
        self.step_methods = {
            "MembraneTemperature": self._membrane_heater_step,
            "ADC": self._adc_step,
        }

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

        self.plot_methods = {
            "MAX6675": self.update_plots_max6675,
            "ADC": self.update_plots_adc,
        }

        self.zero_adjustment = {"Ip": 0, "Bu": 0}

    # MARK: Prep Threads
    def prep_threads(self):
        """
        Define Workers for Devices to run in separate threads.
        """
        self.log_message(
            "<font color='#1cad47'>Starting</font> acquisition", htmltag="h2"
        )
        self.__workers_done = 0
        self.terminate_existing_threads()
        self.pi = pigpio.pi()
        self.define_devices()
        now = datetime.datetime.now()

        self.workers = {
            device_name: self.prep_worker(worker_class, device_name, now)
            for device_name, worker_class in self.devices.items()
        }

        self.start_all_threads()
        self.start_cross_connections()
        self.indicator_led = IndicatorLED(
            self.__app, self.pi, self.workers["ADC"]["worker"]
        )

    def prep_worker(self, device_class, device_name, start_time):
        """
        Generalized worker preparation method for different device types.
        """
        thread = QtCore.QThread()
        thread.setObjectName(f"{device_name}")

        worker = device_class(device_name, self.__app, start_time, self.config, self.pi)

        return {"worker": worker, "thread": thread}

    def start_all_threads(self):
        """
        Start all threads by assigning workers to threads and initiating them.
        """
        for device_name, worthre in self.workers.items():
            self.start_thread(worthre)

        self.update_ig_range()
        self.update_ig_mode()

    def start_thread(self, worthre):
        """
        Starts Device Worker thread
        """
        worthre["worker"].moveToThread(worthre["thread"])
        self.connect_worker_signals(worthre["worker"])
        worthre["thread"].started.connect(worthre["worker"].start)
        worthre["thread"].start()

    def connect_worker_signals(self, worker):
        """
        Connects worker signals to the main thread
        """
        worker.data_ready.connect(self.on_worker_step)
        worker.sigDone.connect(self.on_worker_done)
        worker.send_message.connect(self.log_message)
        self.sigAbortWorkers.connect(worker.abort)

        if worker.device_name == "ADC":
            worker.send_control_voltage.connect(self._set_cathode_current)
            worker.send_zero_adjustment.connect(self._adjust_zeros)

    def start_cross_connections(self):
        """Connect workers signals directly"""
        mfcs_worker = self.workers["MFCs"]["worker"]
        adc_worker = self.workers["ADC"]["worker"]
        mfcs_worker.send_presets_to_adc.connect(adc_worker.update_mfcs)

    # MARK: Abort
    def terminate_existing_threads(self):
        """
        Gracefully quits and waits for all currently running threads.
        """
        for device_name, worthre in self.workers.items():
            worthre["thread"].quit()
            worthre["thread"].wait()

        self.workers = {}
        self.terminate_indicator_thread()
        if hasattr(self, "pi"):
            self.pi.stop()

    def terminate_indicator_thread(self):
        if hasattr(self, "indicator_led"):
            self.indicator_led.quit()
            self.indicator_led.wait()

    def turn_off_voltages(self):
        """Safely turn off any DAC voltages"""
        if not self.workers:
            return

        self.workers["ADC"]["worker"].set_plasma_current.emit(0)

        self._mfc_presets = {1: 0, 2: 0}
        self.update_current_values()
        self.workers["MFCs"]["worker"].output_voltage(1, 0)
        self.workers["MFCs"]["worker"].output_voltage(2, 0)

    @QtCore.pyqtSlot()
    def abort_all_threads(self):
        """
        Do we need two terminators?
        This one signals to workers to stop.
        """
        self.turn_off_voltages()
        self.sigAbortWorkers.emit()
        self.terminate_existing_threads()

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

    # MARK: Data - handling
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

    # MARK: Data - append
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
        self.step_methods[device_name](result)
        self.update_current_values()

    def _adc_step(self, result):
        device_name = result[-1]
        #  self.data_ready.emit([newdata, self.device_name])
        self.newdata[device_name] = result[0]
        self.append_data(device_name)
        self.save_data(device_name)
        for plotname, name in zip(
            self.config["ADC Signal Names"], self.config["ADC Converted Names"]
        ):
            self.currentvalues[plotname] = self.datadict["ADC"].iloc[-3:][name].mean()
        # to debug mV signal from Baratron, ouptut it directly.
        self.baratronsignal1 = self.datadict["ADC"].iloc[-3:]["Bu"].mean()
        self.baratronsignal2 = self.datadict["ADC"].iloc[-3:]["Bd"].mean()
        self.update_plots(device_name)

    def _membrane_heater_step(self, result):
        device_name = result[-1]
        # [self.data, self.device_name]
        self.newdata[device_name] = result[0]
        self.append_data(device_name)
        self.save_data(device_name)
        # here 3 is number of data points recieved from worker.
        # TODO: update to self.newdata[device_name]['T'].mean()
        self.currentvalues["T"] = self.datadict[device_name].iloc[-3:]["T"].mean()
        self.update_plots(device_name)

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

    def reset_data(self, device_name):
        self.datadict[device_name] = self.datadict[device_name].iloc[0:0]
        self.newdata[device_name] = self.newdata[device_name].iloc[0:0]

    # MARK: update values
    def update_current_values(self):
        """
        update current values when new signal comes
        """
        # self.tempcontrolDock.update_current_values(self.__temp, f"{self.currentvalues['T']:.0f}")
        self.gasflow_dock.update_display(
            self._mfc_presets[1], f"{self.currentvalues['MFC1']*1000:.0f}", 1
        )
        self.gasflow_dock.update_display(
            self._mfc_presets[2], f"{self.currentvalues['MFC2']*1000:.0f}", 2
        )
        # self.control_dock.gaugeT.update_value(self.currentvalues["T"])

        labels = ["Pu", "Pd", "Ip", "Bu", "Bd"]
        values = []
        for label in labels:
            v = self.currentvalues[label]
            if label == "Ip":
                v -= self.zero_adjustment["Ip"]
            values.append([self.graph.pens[label]["color"], label, v])

        self.control_dock.update_current_values(values)

    @QtCore.pyqtSlot(dict)
    def _adjust_zeros(self, zero_adjustment):
        """Set zero adjustment dict"""
        self.zero_adjustment = zero_adjustment

    # MARK: Update Plots
    def update_plots(self, device_name):
        """plot updater abstraction"""
        self.plot_methods[device_name]()

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
        skip = self.calculate_skip_points(time.shape[0])

        what_to_plot = ["Ip", "Pu", "Pd", "Bu", "Bd"]
        for name in what_to_plot:
            if name == "Ip":
                values = (
                    df[name + "_c"].values.astype(float) - self.zero_adjustment["Ip"]
                )
            else:
                values = df[name + "_c"].values.astype(float)

            self.graph.plot_lines[name].setData(time[::skip], values[::skip])

    @QtCore.pyqtSlot()
    def set_heater_goal(self):
        if not self.workers:
            return
        value = self.tempcontrolDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvalues["T"]
        self.tempcontrolDock.set_heating_goal(self.__temp, f"{temp_now:.0f}")
        self.workers["MembraneTemperature"]["worker"].setPresetTemp(self.__temp)

    def get_calibration_time(self):
        txt = self.calibration_dock.scaleBtn.currentText()
        return self.calibration_dock.calibration_durations[txt]

    # MARK: QMS Calibration
    def calibration(self):
        """
        Start and stop calibration
        """
        if not self.workers:
            return
        mfc = self.workers["MFCs"]["worker"]
        if mfc.calibrating:
            question = "STOP calibration?"
            if self.popup_confirmation_window(question):
                mfc.calibrating = False
            return

        question = "START calibration?"
        if self.popup_confirmation_window(question):
            self.indicator_led.qms_calibration_indicator()
            mfc.start_calibration_signal.emit(
                self._mfc_presets[1], 10, self.get_calibration_time()
            )

    # MARK: MFC signal
    def stop_mfc(self):
        """
        Sets 0V output for both Flow Controllers.
        TODO: change to emitting signal
        """
        if not self.workers:
            return
        self._mfc_presets = {1: 0, 2: 0}
        self.update_current_values()
        self.workers["MFCs"]["worker"].stop()

    def set_mfc_goal(self, mfc_num):
        if not self.workers:
            return
        value = self.gasflow_dock.get_massflow_from_gui(mfc_num)
        self._mfc_presets[mfc_num] = value
        voltage_now = self.currentvalues[f"MFC{mfc_num}"]
        self.update_current_values()
        self.workers["MFCs"]["worker"].output_voltage(
            mfc_num, self._mfc_presets[mfc_num]
        )

    # MARK: Plasma Control
    def set_currentcontrol_voltage(self):
        """
        Send control voltage to ADCs plasma current PID
        """
        if not self.workers:
            return
        value = self.plasma_control_dock.voltage_spin_box.value()
        self.workers["ADC"]["worker"].set_plasma_current.emit(value)

    @QtCore.pyqtSlot(float)
    def _set_cathode_current(self, control_voltage):
        """
        Set voltage, recived from ADC worker in PlasmaCurrent worker
        For PID control
        """
        if not self.workers:
            return
        self.workers["PlasmaCurrent"]["worker"].output_voltage(control_voltage)

    # MARK: ADC controls
    def _set_zero_ip(self):
        """set current ip as 0"""
        if not self.workers:
            return
        self.workers["ADC"]["worker"].set_zero_ip()

    @QtCore.pyqtSlot()
    def update_ig_mode(self):
        """
        Update mode of the IG controller:
        Torr and linear
        or
        Pa and log
        """
        if not self.workers:
            return
        value = self.control_dock.IGmode.currentIndex()
        self.workers["ADC"]["worker"].set_ig_mode(value)

    @QtCore.pyqtSlot()
    def update_ig_range(self):
        """
        Update range of the IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        if not self.workers:
            return
        value = self.control_dock.IGrange.value()
        self.workers["ADC"]["worker"].set_ig_range(value)

    @QtCore.pyqtSlot()
    def __set_gain(self):
        """
        Set gain for Baratron channel on ADC
        Parameters
        ----------
        value: int
            gain, values [1,2,5,10] (in V)
        """
        if not self.workers:
            return
        txt = self.adcgain_dock.gain_box.currentText()
        gain = self.adcgain_dock.gains[txt]
        self.workers["ADC"]["worker"].set_adc_gain(gain)

    @QtCore.pyqtSlot()
    def __set_sampling(self):
        """
        Set sampling time for all threads
        """
        if not self.workers:
            return
        txt = self.settings_dock.samplingCb.currentText()
        value = float(txt.split(" ")[0])
        self.sampling = value
        self.update_plot_timewindow()
        self.workers["ADC"]["worker"].set_sampling_time(value)
        self.log_message(f"ADC sampling set to {value}")


# MARK: End
def main():
    """
    for command line script using entrypoint
    """
    app = QtWidgets.QApplication([])
    widget = MainApp(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    from __init__ import _echelle_base

    pth = str(_echelle_base / "icons/controlunit.png")
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(pth))
    widget = MainApp(app)

    sys.exit(app.exec_())

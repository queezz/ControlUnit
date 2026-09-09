import argparse
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

# Plain standard library: a few locked values the optional web view reads,
# and the queue it puts commands on. Nothing here imports Flask, so a machine
# without it starts as it always did.
from controlunit.web.status import RigStatus
from controlunit.web import commands as web_commands

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
    # Baselines exist before the first run does, so nothing has to ask
    # whether the dict is there yet.
    zero_adjustment = {"Ip": 0, "Bu": 0, "Bd": 0}

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

        # What the web view is allowed to know: how many channels, how fast,
        # and whether acquisition is running. It reads a copy, never a worker.
        self.web_status = RigStatus(
            channels=len(self.config["ADC Signal Names"]),
            sampling=self.sampling,
            names=self.config["ADC Signal Names"],
            units=self._web_units(),
        )
        # Where a browser's instruction waits for this thread. The web thread
        # only ever appends to it; every worker call still happens here.
        self.web_commands = web_commands.CommandQueue()
        self.web_status.set_remote(self.control_dock.remoteSW.isChecked())

        # MARK: Current Values
        # To display in text browser
        self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"]}
        self.baratronsignal1 = 0
        self.baratronsignal2 = 0

        self.update_plot_timewindow()
        self.set_scales_switches()

        self.showMain()
        self.log_to_file(f"App started: {os.path.abspath(__file__)}")

    # MARK: Web status
    # Unit per conversion function, for the web view's readouts. A channel
    # whose conversion returns the ADC voltage unchanged stays in volts.
    _WEB_UNITS = {
        "Hall Sensor": "A",
        "Ionization Gauge": "Torr",
        "Pfeiffer Single Gauge": "Torr",
        "Pfeiffer IKR251": "Torr",
        "Baratron": "Torr",
        "cathode volt": "V",
    }

    def _web_units(self):
        """Map each channel name to the unit its converted value carries."""
        props = self.config["Adc Channel Properties"]
        return {
            name: self._WEB_UNITS.get(props[name].conversion_id, "V")
            for name in props
        }

    def _for_web(self, text):
        """
        The same message the Log dock shows, minus this machine's paths:
        a browser is told the data file's name, never where it lives.
        """
        folder = getattr(self, "datapath", "")
        if not folder:
            return text
        for spelling in (os.path.abspath(folder), folder, folder.replace("\\", "/")):
            if spelling:
                text = text.replace(spelling + os.sep, "").replace(spelling + "/", "")
        return text

    def _publish_step(self, newdata):
        """
        Hand the web view the samples this step delivered, in the same
        units and with the same zero adjustment the rig's own screen shows.
        The web view must never stop the acquisition loop, so any failure
        here is printed and swallowed.
        """
        try:
            times = [
                getattr(stamp, "to_pydatetime", lambda: stamp)().timestamp()
                for stamp in newdata["date"]
            ]
            values = {}
            zeros = getattr(self, "zero_adjustment", {})
            for name, column in zip(
                self.config["ADC Signal Names"], self.config["ADC Converted Names"]
            ):
                series = newdata[column].astype(float).tolist()
                zero = zeros.get(name, 0)
                if zero:
                    series = [value - zero for value in series]
                values[name] = series
            self.web_status.record_samples(times, values)
        except Exception as error:
            print(f"{RED}web status:{RESET} {error}")

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
        self.plasma_control_dock.turn_off_pid_btn.clicked.connect(
            self.turn_off_currentcontrol_voltage
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
        self.control_dock.remoteSW.clicked.connect(self._toggle_remote)
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
        self.settings_dock.set_output_voltage_btn.clicked.connect(
            self.__set_plasma_output_voltage
        )
        self.settings_dock.turn_off_output_voltage_btn.clicked.connect(
            self.__turn_off_plasma_output_voltage
        )
        self.scale_dock.subzero_ip.clicked.connect(self._set_zero_ip)
        # The Bu button existed and was never wired; Bd is new beside it.
        self.scale_dock.subzero_baratron.clicked.connect(
            lambda: self._zero_from_dock("Bu")
        )
        self.scale_dock.subzero_baratron_down.clicked.connect(
            lambda: self._zero_from_dock("Bd")
        )

    # MARK: GUI setup

    def __quit(self):
        """terminate app"""
        self.__app.quit()

    def __onoff(self):
        """
        The on/off switch on the rig's own screen. It asks before stopping,
        and then takes the same two paths a browser takes, so a run begins
        and ends the same way whoever asked for it.
        """
        if self.control_dock.OnOffSW.isChecked():
            self.start_acquisition()
            return

        question = "Are you sure you want to stop data acquisition?"
        if self.popup_confirmation_window(question):
            self.stop_acquisition()
        else:
            self.control_dock.OnOffSW.setChecked(True)

    def start_acquisition(self):
        """
        Start the worker threads and say so, whoever asked.

        The switch on the rig's screen calls this, and so does a browser's
        Start through the command queue; the browser's half sets the switch
        to match first, so the rig's own screen agrees with what was done.
        """
        self.prep_threads()
        self.web_status.set_acquiring(True)
        self.control_dock.quitBtn.setEnabled(False)

    def stop_acquisition(self):
        """
        Stop the worker threads and say so, whoever asked.

        The Remote switch is deliberately left exactly as the person at the
        rig set it. It used to be forced off here, so that a laptop could not
        hold a gate over a rig that is not running; a browser that can now
        press Stop would be stranded by a switch that turned itself off
        behind it. The switch is still the only way in, and still only
        turnable on at the rig. The operator lock is let go of instead, in
        `abort_all_threads`, so nobody silently holds an idle rig.
        """
        self.abort_all_threads()
        self.web_status.set_acquiring(False)
        self.control_dock.quitBtn.setEnabled(True)

    # MARK: Remote control
    def _toggle_remote(self):
        """Record the Remote switch, and say so in the log.

        The switch is the whole gate on a browser changing anything: with it
        off the web view reads and nothing more. It cannot be turned on from
        a browser, only here, and it stays exactly where this person put it:
        stopping acquisition no longer takes it down, because a browser may
        now stop a run and would otherwise lock itself out of restarting it.
        """
        on = self.control_dock.remoteSW.isChecked()
        self.web_status.set_remote(on)
        self.log_message("Remote control {}".format("on" if on else "off"))
        if not on:
            web_commands.release(self, "Remote switch off")

    def _drain_web_commands(self):
        """Run what a browser queued, here on the thread that owns the workers."""
        try:
            web_commands.drain(self)
        except Exception as error:
            print(f"{RED}web command:{RESET} {error}")

    def _toggle_led_status(self):
        if not self.control_dock.OnOffSW.isChecked():
            return
        self.web_status.record_setpoints(sync=self.control_dock.qmsSigSw.isChecked())
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

        # Plasma current and both Baratrons can be read from a baseline. A
        # zero changes the display, the plots and the web view; the CSV on
        # disk keeps the converted signal exactly as measured.
        self.zero_adjustment = {"Ip": 0, "Bu": 0, "Bd": 0}
        self.web_status.record_zeros(self.zero_adjustment)

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

        if worker.device_name == "ADC":
            worker.send_control_voltage.connect(self._set_cathode_current)
            worker.send_zero_adjustment.connect(self._adjust_zeros)

    def start_cross_connections(self):
        """Connect workers signals directly"""
        mfcs_worker = self.workers["MFCs"]["worker"]
        adc_worker = self.workers["ADC"]["worker"]
        mfcs_worker.send_presets_to_adc.connect(
            adc_worker.update_mfcs, type=QtCore.Qt.DirectConnection
        )

    # MARK: Abort
    def terminate_existing_threads(self):
        """
        Gracefully quits and waits for all currently running threads.
        """
        for device_name, worthre in self.workers.items():
            worthre["worker"].abort()
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
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=0.0)

        self._mfc_presets = {1: 0, 2: 0}
        self.update_current_values()
        self.workers["MFCs"]["worker"].output_voltage_signal.emit(1, 0)
        self.workers["MFCs"]["worker"].output_voltage_signal.emit(2, 0)

    @QtCore.pyqtSlot()
    def abort_all_threads(self):
        """
        Do we need two terminators?
        This one signals to workers to stop.
        """
        self.turn_off_voltages()
        self.terminate_existing_threads()
        self.web_status.set_acquiring(False)
        # Nobody is left holding control of a rig that is not listening. The
        # Remote switch itself stays as the person at the rig set it: it is
        # theirs, and a browser that has just stopped a run must still be
        # able to start one.
        web_commands.release(self, "acquisition stopped")

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
        self.web_status.log(self._for_web(strip_tags(message)), time_stamp)
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
            # A new file is a new run for the web view: its ring empties and
            # its run facts start again. The name only, never the path.
            self.web_status.start_run(os.path.basename(self.savepaths[device_name]))

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
        self._publish_step(result[0])

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
        self.web_status.record_setpoints(
            mfc1_v=self._mfc_presets[1], mfc2_v=self._mfc_presets[2]
        )
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
            v = self.currentvalues[label] - self.zero_adjustment.get(label, 0)
            values.append([self.graph.pens[label]["color"], label, v])

        self.control_dock.update_current_values(values)

    @QtCore.pyqtSlot(dict)
    def _adjust_zeros(self, zero_adjustment):
        """Set zero adjustment dict"""
        self.zero_adjustment = zero_adjustment
        self.web_status.record_zeros(zero_adjustment)

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
            values = df[name + "_c"].values.astype(float) - self.zero_adjustment.get(
                name, 0
            )
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
        """
        if not self.workers:
            return
        self._mfc_presets = {1: 0, 2: 0}
        self.update_current_values()
        self.workers["MFCs"]["worker"].stop_signal.emit()

    def set_mfc_goal(self, mfc_num):
        if not self.workers:
            return
        value = self.gasflow_dock.get_massflow_from_gui(mfc_num)
        self._mfc_presets[mfc_num] = value
        voltage_now = self.currentvalues[f"MFC{mfc_num}"]
        self.update_current_values()
        self.workers["MFCs"]["worker"].output_voltage_signal.emit(
            mfc_num, self._mfc_presets[mfc_num]
        )

    # MARK: Plasma Control
    def set_currentcontrol_voltage(self):
        """
        Send control voltage to ADCs plasma current PID
        """
        if not self.workers:
            return
        ampere = self.plasma_control_dock.ampere_spin_box.value()
        # value = (ampere / 5 + 2.52) * 1000
        self.workers["ADC"]["worker"].set_plasma_current.emit(ampere)
        self.web_status.record_setpoints(plasma_a=float(ampere))

    @QtCore.pyqtSlot()
    def turn_off_currentcontrol_voltage(self):
        """Stop plasma current PID and force the DAC output to 0 V."""
        if not self.workers:
            return
        self.plasma_control_dock.ampere_spin_box.setValue(0.0)
        self.workers["ADC"]["worker"].set_plasma_current.emit(0)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=0.0)
        self.log_message("Plasma current PID turned off")

    @QtCore.pyqtSlot(float)
    def _set_cathode_current(self, control_voltage):
        """
        Set voltage, recived from ADC worker in PlasmaCurrent worker
        For PID control

        The web record follows the DAC rather than the PID's setpoint: this
        is the only place that knows what the cathode is actually being
        driven with while the loop is closed, and "is anything driven" is
        the question the rig's operating state answers.
        """
        if not self.workers:
            return
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(
            control_voltage
        )
        self.web_status.record_setpoints(cathode_mv=float(control_voltage))

    # MARK: ADC controls
    def _set_zero_ip(self):
        """set current ip as 0"""
        self._zero_from_dock("Ip")

    def _zero_from_dock(self, channel):
        """A Scales dock button: take the baseline, and say so in the log.

        A browser's Zero now takes the same baseline but writes its own log
        line, naming who asked, so a zero is never logged twice.
        """
        if not self.workers:
            return
        if self.set_zero_baseline(channel):
            self.log_message(f"Baseline of {channel} taken")
        else:
            self.log_message(f"Baseline of {channel} not taken: no samples yet")

    #: How much of the run a baseline averages over. Two seconds is twenty
    #: samples at the usual rate: enough to sit above the Hall sensor's noise,
    #: short enough that the reading is still "now".
    BASELINE_SECONDS = 2.0

    def baseline_of(self, channel):
        """
        The mean of the last two seconds of `channel`, as converted and
        never zero-adjusted, or None while there is not a sample yet.
        """
        try:
            column = self.datadict["ADC"][channel + "_c"].astype(float)
        except (KeyError, AttributeError, TypeError, ValueError):
            return None
        try:
            rows = max(1, int(round(self.BASELINE_SECONDS / float(self.sampling))))
        except (TypeError, ValueError, ZeroDivisionError):
            rows = 20
        tail = column.iloc[-rows:]
        if tail.empty:
            return None
        mean = float(tail.mean())
        if mean != mean:
            return None
        return mean

    def set_zero_baseline(self, channel):
        """
        Take what `channel` has read over the last seconds as its zero.
        True when a baseline was taken; False when nothing is running or no
        sample has arrived yet, so a caller can say so instead of claiming
        a zero it did not take.

        One path for all three channels and for both origins: the buttons in
        the Scales dock and a browser's Zero now both arrive here, and the
        worker answers with every zero at once through `send_zero_adjustment`.
        """
        if not self.workers:
            return False
        value = self.baseline_of(channel)
        if value is None:
            return False
        self.workers["ADC"]["worker"].set_zero_signal.emit(channel, value)
        return True

    @QtCore.pyqtSlot()
    def update_ig_mode(self):
        """
        Update mode of the IG controller:
        Torr and linear
        or
        Pa and log
        """
        self.web_status.record_setpoints(ig_mode=self.control_dock.IGmode.currentText())
        if not self.workers:
            return
        value = self.control_dock.IGmode.currentIndex()
        self.workers["ADC"]["worker"].set_ig_mode_signal.emit(value)

    @QtCore.pyqtSlot()
    def update_ig_range(self):
        """
        Update range of the IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        value = self.control_dock.IGrange.value()
        self.web_status.record_setpoints(ig_range=value)
        if not self.workers:
            return
        self.workers["ADC"]["worker"].set_ig_range_signal.emit(value)

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
        self.workers["ADC"]["worker"].set_adc_gain_signal.emit(gain)

    @QtCore.pyqtSlot()
    def __set_sampling(self):
        """
        The Settings dock's Set button: read the combo, then the one path.
        """
        if not self.workers:
            return
        txt = self.settings_dock.samplingCb.currentText()
        self.set_sampling(float(txt.split(" ")[0]))

    def set_sampling(self, seconds):
        """
        Set sampling time for all threads, whoever asked.

        The dock's combo is set to the matching item first, so the rig's own
        screen agrees with what a browser did; the choices a browser may send
        are the combo's own (`web.commands.SAMPLING_CHOICES`, held equal to
        the dock by a test).
        """
        if not self.workers:
            return
        value = float(seconds)
        index = self.settings_dock.samplingCb.findText(f"{value:g} s")
        if index >= 0:
            self.settings_dock.samplingCb.setCurrentIndex(index)
        self.sampling = value
        self.update_plot_timewindow()
        self.workers["ADC"]["worker"].set_sampling_time(value)
        self.web_status.describe_run(len(self.config["ADC Signal Names"]), value)
        self.log_message(f"ADC sampling set to {value}")

    @QtCore.pyqtSlot()
    def __set_plasma_output_voltage(self):
        """Set direct output voltage of plasma current DAC."""
        if not self.workers:
            return
        value = self.settings_dock.output_voltage_spinbox.value() * 1000
        self.workers["ADC"]["worker"].set_plasma_current.emit(0)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(value)
        # The PID is off and the cathode is driven: the exact pair that read
        # as "nothing running" until the record carried the DAC as its own
        # fact, and the pair that kept a plasma on after the reader died on
        # 2026-08-19.
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=float(value))
        self.log_message(f"Plasma DAC output set to {value/1000:.3f} V")

    @QtCore.pyqtSlot()
    def __turn_off_plasma_output_voltage(self):
        """Turn off direct output voltage of plasma current DAC."""
        if not self.workers:
            return
        self.settings_dock.output_voltage_spinbox.setValue(0.0)
        self.workers["ADC"]["worker"].set_plasma_current.emit(0)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=0.0)
        self.log_message("Plasma DAC output turned off")


# MARK: Web view
def parse_arguments(argv=None):
    """
    Read the command line. Without --web nothing about the program changes.
    """
    parser = argparse.ArgumentParser(
        prog="controlunit",
        description="Plasma-lab control and data acquisition.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="also serve the read-only web view in this process",
    )
    parser.add_argument(
        "--host",
        # Answers on the lab network by default (owner decision 2026-09-04,
        # "the whole point is LAN"): the rig is one machine in the lab and the
        # view is read from a laptop or a phone. Pass --host 127.0.0.1 to
        # narrow a run to the Pi itself. The view stays read-only either way.
        default="0.0.0.0",
        help="address the web view listens on (default: the lab network)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4187,
        help="port the web view listens on (default: 4187)",
    )
    return parser.parse_args(argv)


#: How often the main thread looks for what a browser asked for. Fast enough
#: that a press feels answered within one poll of the page, slow enough that
#: it costs the acquisition loop nothing.
WEB_COMMAND_MS = 200


def start_web_view(widget, arguments):
    """
    Start the web view on a daemon thread, if it was asked for.

    The thread reads the status record the main thread writes and appends to
    the command queue the main thread drains; it never calls a worker slot,
    so worker ownership and the hardware-first shutdown order are untouched.
    The timer belongs to the main thread and exists only under --web.
    """
    if not arguments.web:
        return None
    from controlunit.web.server import serve_in_thread

    timer = QtCore.QTimer(widget)
    timer.timeout.connect(widget._drain_web_commands)
    timer.start(WEB_COMMAND_MS)
    widget.web_command_timer = timer

    serve_in_thread(
        widget.web_status,
        commands=widget.web_commands,
        host=arguments.host,
        port=arguments.port,
    )
    print(f" Web view: http://{arguments.host}:{arguments.port}/")
    return True


# MARK: End
def main():
    """
    for command line script using entrypoint
    """
    arguments = parse_arguments()
    app = QtWidgets.QApplication([])
    widget = MainApp(app)
    start_web_view(widget, arguments)
    sys.exit(app.exec_())


if __name__ == "__main__":
    from __init__ import _echelle_base

    arguments = parse_arguments()
    pth = str(_echelle_base / "icons/controlunit.png")
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(pth))
    widget = MainApp(app)
    start_web_view(widget, arguments)

    sys.exit(app.exec_())

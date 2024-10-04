"""
DAC8532 communication

Used for controlling two Mass Flow Controllers: H2 and O2.

High-Precision AD/DA Expansion Module Onboard ADS1256 DAC8532 for Raspberry Pi

https://www.amazon.com/High-Precision-Expansion-Raspberry-Pi-XYGStudy/dp/B017GUVPAK
"""

import time
from PyQt5 import QtCore

from .device import DeviceThread
from controlunit.devices.dac8532_setter import DAC8532Setter

try:
    import RPi.GPIO as GPIO
except ImportError:
    from devices.dummy import GPIO

from controlunit.ui.text_shortcuts import RED, BLUE, RESET


# MARK: DAC8532
class DAC8532(DeviceThread):

    sigAbortHeater = QtCore.pyqtSignal()
    send_presets_to_adc = QtCore.pyqtSignal(list)
    start_calibration_signal = QtCore.pyqtSignal(float, int, float)

    def __init__(self, device_name, app, startTime, config, pi):
        super().__init__(device_name, app, startTime, config, pi)
        self.__app = app
        self.device_name = device_name
        self.__startTime = startTime
        self.config = config
        self.calibrating = False
        self.init()

    def init(self):
        try:
            self.DAC = DAC8532Setter()
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, 0)
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, 0)
            print("High-Precision AD/DA initialised")
        except:
            GPIO.cleanup()

        self.connect_slots()

    def connect_slots(self):
        self.start_calibration_signal.connect(self.do_calibration)

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.device_name)
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True
        self.dac_reset_voltage()

    def init_dac_worker(self, presetVoltage: int):
        pass

    def stop(self):
        self.calibrating = False
        self.dac_reset_voltage()

    def dac_reset_voltage(self):
        """Reset voltage"""
        self.output_voltage(1, 0)
        self.output_voltage(2, 0)

    # MARK: Output Voltage
    def output_voltage(self, channel, voltage):
        """Voltage in mV"""
        if voltage > 5000:
            voltage = 5000

        if channel == 1:
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, voltage / 1000)
            print("DAC8532 MF1 (" + BLUE + "H2" + RESET + f"): {voltage/1000} V")
            self.send_presets_to_adc.emit([channel, voltage])
        elif channel == 2:
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, voltage / 1000)
            print("DAC8532 MF2 (" + RED + "O2" + RESET + f"): {voltage/1000} V")
            self.send_presets_to_adc.emit([channel, voltage])
        else:
            print(f"DAC8532 MFCs: channel {channel} not registered")

    # MARK: Calibration
    @QtCore.pyqtSlot(float, int, float)
    def do_calibration(self, max_voltage, step, waiting_time):
        self.calibrating = True
        if max_voltage == 0:
            max_voltage = 5000

        for i in range(step + 1):
            if self.calibrating == False:
                break
            voltage = (max_voltage) / step * i
            self.output_voltage(1, voltage)
            time.sleep(waiting_time)

        for i in range(step):
            if self.calibrating == False:
                break
            self.output_voltage(1, (max_voltage) / step * (step - i - 1))
            time.sleep(waiting_time)

        self.calibrating = False

        self.output_voltage(1, 0)

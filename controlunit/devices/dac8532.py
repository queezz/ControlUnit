"""
DAC8532 communication

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

TEST = False


# MARK: DAC8532
class DAC8532(DeviceThread):

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, device_descriptor, app, startTime, config):
        super().__init__(device_descriptor, app, startTime, config)
        self.__app = app
        self.device_descriptor = device_descriptor
        self.__startTime = startTime
        self.config = config
        self.__abort = False
        self.calibrating = False

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.device_descriptor)
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True
        self.dac_reset_voltage()

    @QtCore.pyqtSlot()
    def start(self):
        pass

    def init_dac_worker(self, presetVoltage: int):
        pass

    def dac_init(self):
        try:
            self.DAC = DAC8532Setter()
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, 0)
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, 0)
            print("High-Precision AD/DA initialised")
        except:
            GPIO.cleanup()

    def dac_reset_voltage(self):
        """Reset voltage"""
        self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, 0)
        self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, 0)

    def output_voltage(self, channel, voltage):
        if channel == 1:
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, voltage / 1000)
            print(f"voltage output: {voltage/1000} V")
        elif channel == 2:
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, voltage / 1000)
            print(f"voltage output: {voltage/1000} V")
        else:
            print("wrong channel")

    @QtCore.pyqtSlot()
    def calibration(self, max_voltage, step, waiting_time, adc_object):
        self.calibrating = True
        if max_voltage == 0:
            max_voltage = 5000
        while self.calibrating:

            for i in range(step + 1):
                if self.calibrating == False:
                    break
                self.output_voltage(1, (max_voltage) / step * i)
                adc_object.setPresetV_mfc1((max_voltage) / step * i)
                time.sleep(waiting_time)
            for i in range(step):
                if self.calibrating == False:
                    break
                self.output_voltage(1, (max_voltage) / step * (step - i - 1))
                adc_object.setPresetV_mfc1((max_voltage) / step * (step - i - 1))
                time.sleep(waiting_time)
            self.calibrating = False
        self.output_voltage(1, 0)

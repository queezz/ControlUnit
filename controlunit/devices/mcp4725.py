"""
MCP4725 communication
12 bit DAC

Currently unused, planned for plasma current control.

https://www.microchip.com/en-us/product/mcp4725
https://www.sparkfun.com/products/12918
"""

import time
from PyQt5 import QtCore

from .device import DeviceThread
from controlunit.devices.mcp4725_setter import MCP4725Setter


try:
    import pigpio
except ImportError as e:
    from devices.dummy import pigpio


# MARK: MCP4725
class MCP4725(DeviceThread):

    # sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, device_name, app, startTime, config):
        super().__init__(device_name, app, startTime, config)
        self.__app = app
        self.device_name = device_name
        self.__startTime = startTime
        self.config = config
        self.__abort = False
        self.init()

    def init(self):
        try:
            self.pi = pigpio.pi()
            self.mcp = MCP4725Setter(self.pi)
            self.mcp.set_voltage(0)
            print("12 bit DAC MCP4725 initialised")
        except Exception as e:
            print(f"{e}")

    @QtCore.pyqtSlot()
    def abort(self):
        message = f"Device {self.device_name} aborting"
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True
        try:
            self.mcp.set_voltage(0)
        except:
            pass

    def output_voltage(self, voltage):
        """voltage in milli Volts"""
        voltage = voltage / 1000  # convert to volts
        self.mcp.set_voltage(voltage)
        print(f"MCP4725 Ip DAC: {voltage} V")

    def demo(self):
        i = 0
        while i < 50:
            self.output_voltage(i / 10)
            time.sleep(2.0)
            i += 1
        self.mcp.cancel()
        self.pi.stop()

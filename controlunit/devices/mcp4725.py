"""
MCP4725 communication

12 bit DAC

https://www.microchip.com/en-us/product/mcp4725
"""

import time
from PyQt5 import QtCore

from .device import DeviceThread
from mMCP4725 import MCP4725 as mcp

RED = "\033[1;31m"
GREEN = "\033[1;32m"
BLUE = "\033[1;34m"
RESET = "\033[0m"
GOOD = "\U00002705"
BAD = "\U0000274C"

try:
    import pigpio
except ImportError as e:
    from devices.dummy import pigpio

STEP = 3


# MARK: MCP4725
class MCP4725(DeviceThread):

    # sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, device_descriptor, app, startTime, config):
        super().__init__(device_descriptor, app, startTime, config)
        self.__app = app
        self.device_descriptor = device_descriptor
        self.__startTime = startTime
        self.config = config
        self.__abort = False

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.sensor_name)
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True
        self.mcp_init()

    @QtCore.pyqtSlot()
    def start(self):
        pass

    def init_mpc_worker(self, presetVoltage: int):
        pass

    def mcp_init(self):
        try:
            print("mcp started correctry\r\n")
            self.pi = pigpio.pi()
            self.mcp = mcp(self.pi)
            self.mcp.set_voltage(0)

        except:
            print("error starting mcp")
            self.pi = pigpio.pi()
            self.mcp = mcp(self.pi)
            self.mcp.set_voltage(0)
            # exit()

    def output_voltage(self, voltage):
        self.mcp.set_voltage(voltage / 1000)
        print(f"voltage output: {voltage/1000} V")
        # self.pi.stop()

    def demo(self):
        i = 0
        while i < 50:
            self.output_voltage(i / 10)
            time.sleep(2.0)
            i += 1
        self.mcp.cancel()
        self.pi.stop()

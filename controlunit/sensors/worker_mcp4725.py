"""
MCP4725 worker
"""
import time
from PyQt5 import QtCore

from .worker import Worker
from mMCP4725 import MCP4725 as mcp

TEST = False
try: 
    import pigpio
except ImportError:
    TEST = True
    import pigpioplug as pigpio


STEP = 3

# MARK: MCP4725
class MCP4725(Worker):

    # sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, sensor_name, app, startTime, config):
        super().__init__(sensor_name, app, startTime, config)
        self.__app = app
        self.sensor_name = sensor_name
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
        

        except :
            print("error starting mcp")
            self.pi = pigpio.pi()
            self.mcp = mcp(self.pi)
            self.mcp.set_voltage(0)
            # exit()

    def output_voltage(self, voltage):
        self.mcp.set_voltage(voltage/1000)
        print(f"voltage output: {voltage/1000} V")
        # self.pi.stop()

    def demo(self):
        i=0
        while i < 50:
            self.output_voltage(i/10)
            time.sleep(2.0)
            i += 1
        self.mcp.cancel()
        self.pi.stop()


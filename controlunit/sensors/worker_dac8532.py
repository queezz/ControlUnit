"""
DAC8532 worker
"""
import time
from PyQt5 import QtCore

from .worker import Worker
from DAC import DAC8532 as dac
import RPi.GPIO as GPIO

TEST = False
STEP = 3

# MARK: DAC8532
class DAC8532(Worker):

    sigAbortHeater = QtCore.pyqtSignal()

    def __init__(self, sensor_name, app, startTime, config):
        super().__init__(sensor_name, app, startTime, config)
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.config = config
        self.__abort = False
        self.calibrating = False

    @QtCore.pyqtSlot()
    def abort(self):
        message = "Worker thread {} aborting acquisition".format(self.sensor_name)
        # self.send_message.emit(message)
        # print(message)
        self.__abort = True
        self.dac_init()

    @QtCore.pyqtSlot()
    def start(self):
        pass

    def init_dac_worker(self, presetVoltage: int):
        pass

    def dac_init(self):
        try:
            print("DAC started correctry\r\n")
            
            self.DAC = dac()
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, 0)
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, 0)
        

        except :
            self.DAC = dac()
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, 0)
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, 0)
            GPIO.cleanup()
            print ("\r\nProgram end     ")
            exit()

    def output_voltage(self, channel, voltage):
        if channel == 1:
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_A, voltage/1000)
            print(f"voltage output: {voltage/1000} V")
        elif channel == 2:
            self.DAC.DAC8532_Out_Voltage(self.DAC.channel_B, voltage/1000)
            print(f"voltage output: {voltage/1000} V")
        else:
            print("wrong channel")

    @QtCore.pyqtSlot()
    def calibration(self,max_voltage,step,waiting_time,adc_object):
        self.calibrating = True
        if max_voltage == 0:
            max_voltage = 5000
        while self.calibrating:

            for i in range(step+1):
                if self.calibrating == False:
                    break
                self.output_voltage(1,(max_voltage)/step*i)
                adc_object.setPresetV_mfc1((max_voltage)/step*i)
                time.sleep(waiting_time)
            for i in range(step):
                if self.calibrating == False:
                    break
                self.output_voltage(1,(max_voltage)/step*(step-i - 1))
                adc_object.setPresetV_mfc1((max_voltage)/step*(step-i - 1))
                time.sleep(waiting_time)
            self.calibrating = False
        self.output_voltage(1,0)



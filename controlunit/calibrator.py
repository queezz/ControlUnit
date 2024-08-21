"""
QMS Calibration thread
"""
from PyQt5 import QtCore

# MARK: Calibrator
class Calibrator(QtCore.QThread):
    def __init__(self, app, dac_object, adc_object, voltage, step, waiting_time):
        super().__init__()
        self.app = app
        self.dac_object = dac_object
        self.adc_object = adc_object
        self.voltage = voltage
        self.step = step
        self.waiting_time = waiting_time
    
    def run(self):
        self.dac_object.calibrating = True
        self.dac_object.calibration(self.voltage,self.step,self.waiting_time,self.adc_object)
        self.dac_object.calibrating = False
        self.app.processEvents()
        self.finished.emit()
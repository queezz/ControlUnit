import time

try:
    import pigpio
except:
    print("no pigpio module, continue for a test")

from pyqtgraph.Qt import QtCore
from readsettings import select_settings

config = select_settings(verbose=False)
CHLED = config["LED GPIO"]

# must inherit QtCore.QObject in order to use 'connect'
class SyncSignal(QtCore.QThread):
    """
    Emit signal for syncronization. Also connected to LED indicator.
    TODO: hardware: use GPIO as a switching signal, don't keep this on
    When this is kept on for too long, the APP crashes.
    TODO: when turn on and off LED so many times (10 or more), the signal is not stable. 
    """

    def __init__(self, pi, app, mode,worker=None):
        super().__init__()
        self.pi = pi  # pigpio.pi() - access local GPIO
        self.app = app
        # GPIO output count
        self.mode = mode
        self.pinNum = CHLED
        self.worker = worker

    # MARK: - Methods
    def run(self):
        self.pi.set_mode(self.pinNum, pigpio.OUTPUT)
        self.led_on_off(self.mode)
        self.app.processEvents()
        self.finished.emit()

    def led_on_off(self, mode):
        """switch led:
        ON:  self.mode == 1
        OFF: self.mode == 0
        calibration light : self.mode == 2
        """
        if mode == 1:
            self.pi.write(self.pinNum, 1)
            self.pi.stop()
        elif mode == 0:
            self.pi.write(self.pinNum, 0)
            self.pi.stop()
        elif (mode == 2) & (self.worker is not None):
            self.calibration_light()

    def calibration_light(self):
        """turn on and off LED for calibration"""
        i = 0
        while i < 3:
            self.pi.write(self.pinNum, 1)
            self.worker.setQmsSignal(1)
            time.sleep(0.1)
            self.pi.write(self.pinNum, 0)
            self.worker.setQmsSignal(0)
            time.sleep(0.3)
            i += 1
        self.pi.write(self.pinNum, 1)
        self.worker.setQmsSignal(2)
        self.pi.stop()

    def abort_calibration(self):
        self.pi.write(self.pinNum, 0)
        self.pi.stop()
        self.worker.setQmsSignal(0)


    def blink_led(self):
        """turn led on and off, "onoff" times"""
        for _ in range(self.onoff):
            self.pi.write(self.pinNum, 1)
            time.sleep(6)
            self.pi.write(self.pinNum, 0)
            time.sleep(3)


if __name__ == "__main__":
    pass

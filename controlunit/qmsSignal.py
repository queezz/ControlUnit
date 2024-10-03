import time

try:
    import pigpio
except ImportError as e:
    from devices.dummy import pigpio

from pyqtgraph.Qt import QtCore
from readsettings import select_settings

config = select_settings(verbose=False)
CHLED = config["LED GPIO"]


# must inherit QtCore.QObject in order to use 'connect'
class IndicatorLED(QtCore.QThread):
    """
    Emit signal for syncronization. Also connected to LED indicator.
    TODO: hardware: use GPIO as a switching signal, don't keep this on
    When this is kept on for too long, the APP crashes.
    TODO: when turn on and off LED so many times (10 or more), the signal is not stable.
    """

    def __init__(self, app, adc_worker):
        super().__init__()
        self.pi = pigpio.pi()  # pigpio.pi() - access local GPIO
        self.app = app
        self.pinNum = CHLED
        # to save the status
        # Maybe it's better to create a separate file.
        # That'll help save a bit of storage space.
        # And this worker will not be necessary.
        self.worker = adc_worker

    # MARK: - Methods
    def run(self):
        pass

    def on(self):
        self.pi.set_mode(self.pinNum, pigpio.OUTPUT)
        self.pi.write(self.pinNum, 1)
        #self.pi.stop()
        self.worker.setQmsSignal(1)
        self.app.processEvents()

    def off(self):
        self.pi.set_mode(self.pinNum, pigpio.OUTPUT)
        self.pi.write(self.pinNum, 0)
        #self.pi.stop()
        self.worker.setQmsSignal(0)
        self.app.processEvents()

    def qms_calibration_indicator(self):
        """turn on and off LED for calibration"""
        self.pi.set_mode(self.pinNum, pigpio.OUTPUT)
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
        self.worker.setQmsSignal(0)

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

    def __del__(self):
        """Cleanup when the object is destroyed"""
        self.pi.stop()


if __name__ == "__main__":
    pass

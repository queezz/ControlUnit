import time
from channels import CHLED

try:
    import pigpio
except:
    print("no pigpio module, continue for a test")

from pyqtgraph.Qt import QtCore

# must inherit QtCore.QObject in order to use 'connect'
class SyncSignal(QtCore.QThread):
    """
    Emit signal for syncronization. Also connected to LED indicator.
    TODO: hardware: use GPIO as a switching signal, don't keep this on
    When this is kept on for too long, the APP crashes.
    """

    def __init__(self, pi, app, onoff):
        super().__init__()
        self.pi = pi  # pigpio.pi() - access local GPIO
        self.app = app
        # GPIO output count
        self.onoff = onoff
        self.pinNum = CHLED

    # MARK: - Methods
    def run(self):
        self.pi.set_mode(self.pinNum, pigpio.OUTPUT)
        self.led_on_off()
        self.app.processEvents()
        self.finished.emit()

    def led_on_off(self):
        """switch led:
        ON:  self.onoff > 0
        OFF: self.onoff == 0
        """
        if self.onoff:
            self.pi.write(self.pinNum, 1)
        else:
            self.pi.write(self.pinNum, 0)

    def blink_led(self):
        """turn led on and off, "onoff" times"""
        for _ in range(self.onoff):
            self.pi.write(self.pinNum, 1)
            time.sleep(6)
            self.pi.write(self.pinNum, 0)
            time.sleep(3)


if __name__ == "__main__":
    pass

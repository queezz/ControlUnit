import time

try:
    import pigpio
except:
    print("no pigpio module, continue for a test")

from pyqtgraph.Qt import QtCore

# must inherit QtCore.QObject in order to use 'connect'
class QMSSignal(QtCore.QThread):
    def __init__(self, pi, app, count):
        super().__init__()
        self.pi = pi  # pigpio.pi() - access local GPIO
        self.app = app
        # GPIO output count
        self.count = count

    # MARK: - Methods
    def run(self):
        pinNum = 27
        self.pi.set_mode(pinNum, pigpio.OUTPUT)
        # self.blink_led(pinNum)
        self.led_on_off(pinNum)
        self.app.processEvents()
        self.finished.emit()

    def led_on_off(self, pinNum):
        """ switch led:
        ON:  self.count > 0
        OFF: self.count == 0
        """
        if self.count:
            self.pi.write(pinNum, 1)
        else:
            self.pi.write(pinNum, 0)

    def blink_led(self, pinNum):
        """ turn led on and off, "count" times
        """
        for _ in range(self.count):
            self.pi.write(pinNum, 1)
            time.sleep(6)
            self.pi.write(pinNum, 0)
            time.sleep(3)


if __name__ == "__main__":
    pass

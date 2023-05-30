import time

try:
    import pigpio
except:
    print("no pigpio module, continue for a test")
    import pigpioplug as pigpio


from pyqtgraph.Qt import QtCore
from readsettings import select_settings

config = select_settings(verbose=True)
CHHEATER = config["Heater GPIO"]


# must inherit QtCore.QObject in order to use 'connect'
class HeaterContol(QtCore.QObject):
    def __init__(self, pi, app):
        super().__init__()
        self.pi = pi
        self.app = app
        # range 0~0.01
        self.set_heater_on_duration = 0
        self.abort = False

    # MARK: setter
    def setOnLight(self, value: float):
        self.set_heater_on_duration = value

    # MARK: - Methods
    @QtCore.pyqtSlot()
    def work(self):
        self.__setThread()
        self.pi.set_mode(CHHEATER, pigpio.OUTPUT)
        while not self.abort:
            if self.set_heater_on_duration == 0:
                time.sleep(0.01)
            else:
                self.pi.write(CHHEATER, 1)
                time.sleep(min(self.set_heater_on_duration, 0.01))
                self.pi.write(CHHEATER, 0)
                time.sleep(max(0.01 - self.set_heater_on_duration, 0))
            self.app.processEvents()

    def __setThread(self):
        self.threadName = QtCore.QThread.currentThread().objectName()
        self.threadId = int(QtCore.QThread.currentThreadId())

    @QtCore.pyqtSlot()
    def setAbort(self):
        self.abort = True


if __name__ == "__main__":
    pass

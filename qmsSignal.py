import time
try:
	import pigpio
except:
	print('no pigpio module, continue for a test')

from pyqtgraph.Qt import QtCore

# must inherit QtCore.QObject in order to use 'connect'
class QMSSignal(QtCore.QThread):
    def __init__(self, pi, app, count):
        super().__init__()
        self.pi = pi
        self.app = app
        # GPIO output count
        self.count = count

    # MARK: - Methods
    def run(self):
        pinNum = 27
        self.pi.set_mode(pinNum, pigpio.OUTPUT)
        for _ in range(self.count):
            self.pi.write(pinNum, 1)
            time.sleep(6)
            self.pi.write(pinNum, 0)
            time.sleep(3)
            self.app.processEvents()
        self.finished.emit()

if __name__ == "__main__":
    pass

"""
Worker super class
"""
from PyQt5 import QtCore

TEST = False
PRINTTHREADINFO = False

# MARK: Worker
class Sensor(QtCore.QObject):
    """
    send_message usage:
    self.send_message.emit(f"Your Message Here to pass to main.py")
    """
    STEP = 3
    send_step_data = QtCore.pyqtSignal(list)
    sigDone = QtCore.pyqtSignal(str)
    send_message = QtCore.pyqtSignal(str)

    def __init__(self, sensor_name, app, startTime, config):
        super().__init__()

        self.__id = id
        self.__app = app
        self.sensor_name = sensor_name
        self.__startTime = startTime
        self.config = config

    def print_checks(self):
        attrs = vars(self)

        if PRINTTHREADINFO:
            print("Thread Checks:")
            print(", ".join(f"{i}" for i in attrs.items()))
            print("ID:", self.__id)
            print("End Thread Checks")

    def set_thread_name(self):
        """Set Thread name and ID, signal them to the log browser"""
        threadName = QtCore.QThread.currentThread().objectName()
        print(threadName)
        return

    def getStartTime(self):
        return self.__startTime

    def setSampling(self, sampling):
        """Set sampling time"""
        self.sampling = sampling

if __name__ == "__main__":
    pass

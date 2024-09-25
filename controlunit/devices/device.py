"""
Worker super class
"""

from PyQt5 import QtCore

TEST = False
PRINTTHREADINFO = False


# MARK: Worker
class DeviceThread(QtCore.QObject):
    """
    send_message usage:
    self.send_message.emit(f"Your Message Here to pass to main.py")
    """

    STEP = 3
    send_step_data = QtCore.pyqtSignal(list)
    sigDone = QtCore.pyqtSignal(str)
    send_message = QtCore.pyqtSignal(str)

    def __init__(self, device_descriptor, app, startTime, config):
        super().__init__()

        self.__id = id
        self.__app = app
        self.device_descriptor = device_descriptor
        self.__startTime = startTime
        self.config = config

    def print_checks(self):
        attrs = vars(self)

        if PRINTTHREADINFO:
            print("Thread Checks:")
            print(", ".join(f"{i}" for i in attrs.items()))
            print("ID:", self.__id)
            print("End Thread Checks")

    def getStartTime(self):
        return self.__startTime

    def setSampling(self, sampling):
        """Set sampling time"""
        self.sampling = sampling


if __name__ == "__main__":
    pass

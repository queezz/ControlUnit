"""
Worker super class
"""

import time
from PyQt5 import QtCore

TEST = False
PRINTTHREADINFO = False

#: How often a sleeping worker looks at its abort flag. A stop is answered
#: within this, whatever the sampling time.
ABORT_CHECK_SECONDS = 0.1


def sleep_unless_aborted(seconds, aborted, slice_seconds=ABORT_CHECK_SECONDS):
    """Sleep `seconds`, looking at `aborted()` every `slice_seconds`.

    A worker that sleeps a whole sampling period and only then looks at its
    abort flag holds the main thread's `thread.wait()` for that whole period:
    at the rig's ten-second sampling the quit button took ten seconds to come
    back (owner report 2026-09-07). Returns True if the sleep ran its course
    and False if it was cut short by an abort.
    """
    end = time.monotonic() + max(0.0, float(seconds))
    while True:
        if aborted():
            return False
        left = end - time.monotonic()
        if left <= 0:
            return True
        time.sleep(min(slice_seconds, left))


# MARK: Worker
class DeviceThread(QtCore.QObject):
    """
    send_message usage:
    self.send_message.emit(f"Your Message Here to pass to main.py")
    """

    STEP = 3
    data_ready = QtCore.pyqtSignal(list)
    sigDone = QtCore.pyqtSignal(str)
    send_message = QtCore.pyqtSignal(str)

    def __init__(self, device_name, app, startTime, config, pi):
        super().__init__()

        self.__id = id
        self.__app = app
        self.device_name = device_name
        self.__startTime = startTime
        self.config = config
        self._abort = False
        self.pi = pi

    def print_checks(self):
        attrs = vars(self)

        if PRINTTHREADINFO:
            print("Thread Checks:")
            print(", ".join(f"{i}" for i in attrs.items()))
            print("ID:", self.__id)
            print("End Thread Checks")

    def getStartTime(self):
        return self.__startTime

    def set_sampling_time(self, sampling_time):
        """Set sampling time"""
        self.sampling_time = sampling_time
        if sampling_time >= 0.9:
            self.STEP = 1
        if sampling_time < 0.9:
            self.STEP = 3
        if sampling_time < 0.1:
            self.STEP = 5

    def start(self):
        """
        This start does nothing,
        it's for unifing thread creation syntax in
        main.py MainWidget.start_thread()
        """
        pass

    def pause(self, seconds):
        """Sleep between steps, but wake at once when told to abort."""
        return sleep_unless_aborted(seconds, lambda: self._abort)

    def abort(self):
        message = f"<font color='blue'>{self.device_name}</font> aborting acquisition"
        # self.send_message.emit(message)
        self._abort = True


if __name__ == "__main__":
    pass

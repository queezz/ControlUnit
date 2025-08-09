import os
import sys
from PyQt5 import QtCore

# Ensure the package is importable when running tests from the tests directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from controlunit.core_logic import CoreLogic


class Receiver(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.called = False

    @QtCore.pyqtSlot(object)
    def slot(self, value):
        self.called = True


def test_plot_update_signal_emits():
    logic = CoreLogic()
    receiver = Receiver()
    logic.plot_update_signal.connect(receiver.slot)
    logic.plot_update_signal.emit("data")
    assert receiver.called

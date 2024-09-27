import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets, QtGui
from pyqtgraph.dockarea import Dock


class CalibrationDock(Dock):
    def __init__(self):
        super().__init__("Calibrate")
        self._set_layout()

    def _set_layout(self):
        self.widget = pg.LayoutWidget()
        self.addWidget(self.widget)

        self._init_calibration_ui()
        self._add_caclibration_ui()

        self._add_vertical_spacer()

    def _add_vertical_spacer(self):
        # Spacer to adjust layout
        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.addItem(self.verticalSpacer)

    # MARK: Calibration UI
    def _init_calibration_ui(self):
        self.calibrationBtn = self._create_button("calib", size=(60, 50))
        self.stopBtn = self._create_button("stop both", size=(120, 50))

        items = ["1 s", "5 s", "10 s", "30 s", "1 min"]
        durations = [1, 5, 10, 30, 60]
        self.calibration_durations = {i: j for i, j in zip(items, durations)}
        combo_box = QtWidgets.QComboBox()
        combo_box.setFont(QtGui.QFont("serif", 18))
        [combo_box.addItem(i) for i in items]

        self.scaleBtn = combo_box

    def _add_caclibration_ui(self, row=0):
        self.widget.addWidget(self.scaleBtn, row, 0)
        self.widget.addWidget(self.calibrationBtn, row, 1)
        self.widget.addWidget(self.stopBtn, row, 2, 1, 2)

    def _create_button(self, label, size=(80, 50)):
        button = QtWidgets.QPushButton(label)
        button.setMinimumSize(QtCore.QSize(*size))
        button.setStyleSheet("font: 20pt")
        return button


if __name__ == "__main__":
    pass

import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import Dock


class PlasmaCurrentDock(Dock):
    """The cathode, two ways.

    The first row is the plasma current PID: a current in amperes the loop
    holds by moving the cathode DAC. The second is the manual drive (owner
    direction 2026-09-09, "just give me a set current, I want my knob"): a
    voltage in millivolts held on the DAC with the PID off, so the filament
    sits where a person put it whatever the plasma does. Setting either
    turns the other off, in `main.py`; the dock only offers the two boxes.
    The manual row used to live in the Settings dock as "Output voltage",
    where nobody running a plasma looked for it.
    """

    #: The manual drive's bounds in millivolts, the DAC's own unit. The
    #: browser's bound (`web.commands.CATHODE_MAX_MV`) is held equal by a
    #: test.
    CATHODE_MAX_MV = 5000

    def __init__(self):
        super().__init__("Cathode")

        self._setLayout()

    def _setLayout(self):
        self.widget = pg.LayoutWidget()
        self.addWidget(self.widget)

        self._init_ui()
        self._add_ui()
        self._add_vertical_spacer()

    def _init_ui(self):
        self.pid_label = QtWidgets.QLabel("PID")
        self.ampere_spin_box = QtWidgets.QDoubleSpinBox()
        self.set_dac_voltage = QtWidgets.QPushButton("set")
        self.turn_off_pid_btn = QtWidgets.QPushButton("off")
        self.ampere_spin_box.setSuffix(" A")
        self.ampere_spin_box.setMaximum(3.0)
        self.ampere_spin_box.setMinimum(0.0)
        self.ampere_spin_box.setSingleStep(0.1)

        self.manual_label = QtWidgets.QLabel("Manual")
        self.cathode_spin_box = QtWidgets.QSpinBox()
        self.cathode_set_btn = QtWidgets.QPushButton("set")
        self.cathode_off_btn = QtWidgets.QPushButton("off")
        self.cathode_spin_box.setSuffix(" mV")
        self.cathode_spin_box.setRange(0, self.CATHODE_MAX_MV)
        self.cathode_spin_box.setSingleStep(100)
        self.cathode_spin_box.setToolTip(
            "Cathode DAC voltage held with the plasma current PID off"
        )

        for button in (
            self.set_dac_voltage,
            self.turn_off_pid_btn,
            self.cathode_set_btn,
            self.cathode_off_btn,
        ):
            button.setStyleSheet("font: 20pt")
        for label in (self.pid_label, self.manual_label):
            label.setStyleSheet("font: 14pt")
        for box in (self.ampere_spin_box, self.cathode_spin_box):
            box.setStyleSheet(
                "QAbstractSpinBox::up-button   { width: 30px; }\n"
                "QAbstractSpinBox::down-button { width: 30px;}\n"
                "QAbstractSpinBox {font: 20pt;}"
            )

    def _add_ui(self):
        self.widget.addWidget(self.pid_label, 0, 0)
        self.widget.addWidget(self.ampere_spin_box, 0, 1)
        self.widget.addWidget(self.set_dac_voltage, 0, 2)
        self.widget.addWidget(self.turn_off_pid_btn, 0, 3)
        self.widget.addWidget(self.manual_label, 1, 0)
        self.widget.addWidget(self.cathode_spin_box, 1, 1)
        self.widget.addWidget(self.cathode_set_btn, 1, 2)
        self.widget.addWidget(self.cathode_off_btn, 1, 3)

    def _add_vertical_spacer(self):
        """Add vertical spacer"""
        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(3)
        self.widget.layout.addItem(self.verticalSpacer, 2, 0, 1, 4)


if __name__ == "__main__":
    pass

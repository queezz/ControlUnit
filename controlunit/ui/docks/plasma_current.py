import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import Dock


class PlasmaCurrentDock(Dock):
    def __init__(self):
        super().__init__("Ip PID")

        self._setLayout()

    def _setLayout(self):
        self.widget = pg.LayoutWidget()
        self.addWidget(self.widget)

        self._init_ui()
        self._add_ui()
        self._add_vertical_spacer()

    def _init_ui(self):
        self.voltage_spin_box = QtWidgets.QDoubleSpinBox()
        self.set_dac_voltage = QtWidgets.QPushButton("set")
        self.voltage_spin_box.setSuffix(f" mV")

        self.voltage_spin_box.setMaximum(5000)
        self.voltage_spin_box.setMinimum(0.0)
        self.voltage_spin_box.setSingleStep(100)

        self.set_dac_voltage.setStyleSheet("font: 20pt")
        self.voltage_spin_box.setStyleSheet(
            "QDoubleSpinBox::up-button   { width: 30px; }\n"
            "QDoubleSpinBox::down-button { width: 30px;}\n"
            "QDoubleSpinBox {font: 20pt;}"
        )

    def _add_ui(self):
        self.widget.addWidget(self.voltage_spin_box, 0, 0)
        self.widget.addWidget(self.set_dac_voltage, 0, 1)

    def _add_vertical_spacer(self):
        """Add vertical spacer"""
        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(3)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import Dock


class SettingsDock(Dock):
    def __init__(self):
        super().__init__("Settings")
        self.widget = pg.LayoutWidget()

        self.output_voltage_label = QtWidgets.QLabel("Output voltage")
        self.output_voltage_spinbox = QtWidgets.QDoubleSpinBox()
        self.output_voltage_spinbox.setSuffix(" V")
        self.output_voltage_spinbox.setRange(0.0, 5.0)
        self.output_voltage_spinbox.setSingleStep(0.1)
        self.output_voltage_spinbox.setDecimals(3)
        self.output_voltage_spinbox.setMaximumWidth(120)
        self.output_voltage_spinbox.setToolTip("Direct MCP4725 output voltage")
        self.set_output_voltage_btn = QtWidgets.QPushButton("set")
        self.turn_off_output_voltage_btn = QtWidgets.QPushButton("off")

        self.samplingCb = QtWidgets.QComboBox()
        items = [f"{i} s" for i in [10, 1, 0.1, 0.01]]
        [self.samplingCb.addItem(i) for i in items]
        self.samplingCb.setCurrentIndex(2)
        self.samplingCb.setMaximumWidth(120)
        self.samplingCb.setToolTip("sampling time")
        self.setSamplingBtn = QtWidgets.QPushButton("set")

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.output_voltage_label, 0, 0)
        self.widget.addWidget(self.output_voltage_spinbox, 0, 1)
        self.widget.addWidget(self.set_output_voltage_btn, 0, 2)
        self.widget.addWidget(self.turn_off_output_voltage_btn, 0, 3)

        self.widget.addWidget(self.samplingCb, 1, 0)
        self.widget.addWidget(self.setSamplingBtn, 1, 1)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

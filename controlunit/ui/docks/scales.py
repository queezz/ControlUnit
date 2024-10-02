import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, QtWidgets
from pyqtgraph.dockarea import Dock
from ..buttons.toggles import *


class PlotScaleDock(Dock):
    def __init__(self):
        super().__init__("Scales")
        self.widget = pg.LayoutWidget()

        self._setLayout()

    def _setLayout(self):
        self.addWidget(self.widget)

        self._init_switches()
        self._init_spinboxes()

        self._add_swithces_and_spinners()

        self._init_buttons()
        self._add_buttons()

        # self._init_tmax_spinbox()
        # self.widget.addWidget(self.Tmax, 1, 0)
        self._add_vspacer()

    def _init_switches(self):
        self.autoscale = changeScale()
        self.togIp = ToggleCurrentPlot()
        # self.togT = ToggleTemperaturePlot()
        self.togP = TogglePressurePlot()
        self.togBaratron = ToggleBaratronPlot()
        self.togIGs = ToggleIGPlots()
        self.togYLog = ToggleYLogScale()

    def _init_buttons(self):
        self.subzero_ip = QtWidgets.QPushButton("O Ip")
        self.subzero_baratron = QtWidgets.QPushButton("O Bu")
        [
            btn.setStyleSheet("font: 20pt")
            for btn in [self.subzero_ip, self.subzero_baratron]
        ]

    def _add_buttons(self):
        self.widget.addWidget(self.subzero_ip, 2, 2)
        self.widget.addWidget(self.subzero_baratron, 2, 3)

    def _init_spinboxes(self):
        self.Pmax = QtWidgets.QSpinBox()
        self.Pmin = QtWidgets.QSpinBox()
        self.Pmax.setToolTip("Pmax")
        self.Pmin.setToolTip("Pmin")
        self.Pmax.setMinimum(-8)
        self.Pmax.setMaximum(2)
        self.Pmin.setMinimum(-9)
        self.Pmin.setMaximum(1)
        self.Pmax.setValue(1)
        self.Pmin.setValue(-8)

        self.Imax = QtWidgets.QSpinBox()
        self.Imin = QtWidgets.QSpinBox()
        self.Imax.setToolTip("Imax")
        self.Imin.setToolTip("Imin")
        self.Imax.setMinimum(-29)
        self.Imax.setMaximum(30)
        self.Imin.setMinimum(-30)
        self.Imin.setMaximum(29)
        self.Imax.setValue(6)
        self.Imin.setValue(-1)

        [
            self._set_spinbox_style(i)
            for i in [self.Pmax, self.Pmin, self.Imax, self.Imin]
        ]

    @staticmethod
    def _set_spinbox_style(spinbox):
        spinbox.setStyleSheet(
            "QSpinBox::up-button   { width: 30px; }\n"
            "QSpinBox::down-button { width: 30px;}\n"
            "QSpinBox {font: 16pt;}"
        )

    def _add_swithces_and_spinners(self):
        self.widget.addWidget(self.Pmax, 0, 0)
        self.widget.addWidget(self.Pmin, 0, 1)
        self.widget.addWidget(self.Imin, 0, 2)
        self.widget.addWidget(self.Imax, 0, 3)
        self.widget.addWidget(self.togIp, 1, 0)
        self.widget.addWidget(self.togP, 1, 1)
        self.widget.addWidget(self.togBaratron, 1, 2)
        self.widget.addWidget(self.togIGs, 1, 3)
        self.widget.addWidget(self.autoscale, 2, 1)
        self.widget.addWidget(self.togYLog, 2, 0)

    def _init_tmax_spinbox(self):
        self.Tmax = QtWidgets.QSpinBox()
        self.Tmax.setMinimum(50)
        self.Tmax.setMaximum(1000)
        self.Tmax.setMinimumSize(QtCore.QSize(60, 60))
        self.Tmax.setSingleStep(50)

    def _add_vspacer(self):
        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

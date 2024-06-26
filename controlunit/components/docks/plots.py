import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, QtWidgets
from pyqtgraph.dockarea import Dock
from ..buttons.toggles import *


class PlotScaleDock(Dock):
    def __init__(self):
        super().__init__("Scales")
        self.widget = pg.LayoutWidget()

        self.autoscale = changeScale()
        self.togIp = ToggleCurrentPlot()
        # self.togT = ToggleTemperaturePlot()
        self.togP = TogglePressurePlot()
        self.togBaratron = ToggleBaratronPlot()
        self.togIGs = ToggleIGPlots()
        self.togYLog = ToggleYLogScale()
        # [i.setChecked(True) for i in [self.togIp, self.togT, self.togP]]
        # self.Tmax = QtWidgets.QSpinBox()
        # self.Tmax.setMinimum(50)
        # self.Tmax.setMaximum(1000)
        # self.Tmax.setMinimumSize(QtCore.QSize(60, 60))
        # self.Tmax.setSingleStep(50)

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
            i.setStyleSheet(
                "QSpinBox::up-button   { width: 30px; }\n"
                "QSpinBox::down-button { width: 30px;}\n"
                "QSpinBox {font: 16pt;}"
            )
            for i in [self.Pmax, self.Pmin, self.Imax, self.Imin]
        ]

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.Pmax, 0, 0)
        self.widget.addWidget(self.Pmin, 0, 1)
        self.widget.addWidget(self.Imin, 0, 2)
        self.widget.addWidget(self.Imax, 0, 3)
        self.widget.addWidget(self.togIp, 1, 0)
        self.widget.addWidget(self.togP, 1, 1)
        self.widget.addWidget(self.togBaratron, 1, 2)
        self.widget.addWidget(self.togIGs, 1, 3)
        self.widget.addWidget(self.autoscale, 2, 1)
        self.widget.addWidget(self.togYLog,2,0)
        # self.widget.addWidget(self.Tmax, 1, 0)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

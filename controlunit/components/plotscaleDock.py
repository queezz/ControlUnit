import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, QtWidgets
from pyqtgraph.dockarea import Dock
from components.onoffswitch import *


class PlotScaleDock(Dock):
    def __init__(self):
        super().__init__("Scales")
        self.widget = pg.LayoutWidget()

        self.autoscale = changeScale()
        self.togIp = ToggleCurrentPlot()
        self.togT = ToggleTemperaturePlot()
        self.togP = TogglePressurePlot()
        [i.setChecked(True) for i in [self.togIp, self.togT, self.togP]]
        self.Tmax = QtWidgets.QSpinBox()
        self.Tmax.setMinimum(50)
        self.Tmax.setMaximum(1000)
        self.Tmax.setMinimumSize(QtCore.QSize(60, 60))
        self.Tmax.setSingleStep(50)

        self.Pmax = QtWidgets.QSpinBox()
        self.Pmin = QtWidgets.QSpinBox()
        self.Pmax.setMinimum(-7)
        self.Pmax.setMaximum(2)
        self.Pmin.setMinimum(-8)
        self.Pmin.setMaximum(1)
        self.Pmax.setValue(1)
        self.Pmin.setValue(-8)

        self.Imax = QtWidgets.QSpinBox()
        self.Imin = QtWidgets.QSpinBox()
        self.Imax.setMinimum(-29)
        self.Imax.setMaximum(30)
        self.Imin.setMinimum(-30)
        self.Imin.setMaximum(29)
        self.Imax.setValue(6)
        self.Imin.setValue(-1)

        [
            i.setStyleSheet(
                "QSpinBox::up-button   { width: 50px; }\n"
                "QSpinBox::down-button { width: 50px;}\n"
                "QSpinBox {font: 26pt;}"
            )
            for i in [self.Tmax, self.Pmax, self.Pmin, self.Imax, self.Imin]
        ]

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.Imax, 0, 1)
        self.widget.addWidget(self.Imin, 0, 0)
        self.widget.addWidget(self.Tmax, 1, 0)
        self.widget.addWidget(self.Pmax, 2, 1)
        self.widget.addWidget(self.Pmin, 2, 0)
        self.widget.addWidget(self.togIp, 3, 0)
        self.widget.addWidget(self.togT, 3, 1)
        self.widget.addWidget(self.togP, 4, 0)
        self.widget.addWidget(self.autoscale, 5, 1)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

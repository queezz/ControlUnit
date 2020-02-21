import sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from pyqtgraph import QtCore
from pyqtgraph.dockarea import Dock

class PlotScaleDock(Dock):

    def __init__(self):
        super().__init__("Scales")
        self.widget = pg.LayoutWidget()

        self.autoscale = QtGui.QPushButton("auto")
        self.Tmax = QtGui.QSpinBox()
        self.Tmax.setMinimum(50)
        self.Tmax.setMaximum(1000)
        self.Tmax.setMinimumSize(QtCore.QSize(60, 60))
        self.Tmax.setSingleStep(50)

        self.Pmax = QtGui.QSpinBox()
        self.Pmin = QtGui.QSpinBox()
        self.Pmax.setMinimum(-7)
        self.Pmax.setMaximum(2)
        self.Pmin.setMinimum(-8)
        self.Pmin.setMaximum(1)
        self.Pmax.setValue(1)
        self.Pmin.setValue(-8)

        [i.setStyleSheet(
                "QSpinBox::up-button   { width: 50px; }\n"
                "QSpinBox::down-button { width: 50px;}\n"
                "QSpinBox {font: 26pt;}"
        ) for i in [self.Tmax,self.Pmax,self.Pmin]]

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.autoscale, 0, 0)
        self.widget.addWidget(self.Tmax, 1, 0)
        self.widget.addWidget(self.Pmax, 2, 1)
        self.widget.addWidget(self.Pmin, 2, 0)

        self.verticalSpacer = QtGui.QSpacerItem(
            0, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)

if __name__ == "__main__":
    pass

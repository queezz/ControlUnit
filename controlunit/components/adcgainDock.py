import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, QtWidgets
from pyqtgraph.dockarea import Dock
from components.onoffswitch import *


class ADCGainDock(Dock):
    def __init__(self):
        super().__init__("Gain")
        self.widget = pg.LayoutWidget()

        self.gain_box = QtWidgets.QComboBox()
        self.gain_box.setFont(QtGui.QFont("serif", 18))
        items = ["10 V", "5 V", "2 V", "1 V"]
        gains = [10, 5, 2, 1]
        [self.gain_box.addItem(i) for i in items]
        self.gains = {i: j for i, j in zip(items, gains)}

        self.set_gain_btn = QtWidgets.QPushButton("set")
        self.set_gain_btn.setFont(QtGui.QFont("serif", 18))



        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.gain_box, 0, 1)
        self.widget.addWidget(self.set_gain_btn, 0, 0)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

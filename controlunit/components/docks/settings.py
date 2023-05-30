import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import Dock


class SettingsDock(Dock):
    def __init__(self):
        super().__init__("Settings")
        self.widget = pg.LayoutWidget()
        self.samplingCb = QtWidgets.QComboBox()
        items = [f"{i} s" for i in [1, 0.1, 0.01]]
        [self.samplingCb.addItem(i) for i in items]
        self.samplingCb.setCurrentIndex(1)
        self.samplingCb.setMaximumWidth(120)
        self.samplingCb.setToolTip("sampling time")
        self.setSamplingBtn = QtWidgets.QPushButton("set")

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.samplingCb, 0, 0)
        self.widget.addWidget(self.setSamplingBtn, 0, 1)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

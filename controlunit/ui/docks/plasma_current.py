import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import Dock


class CurrentControlDock(Dock):
    def __init__(self):
        super().__init__("Ip PID")
        self.widget = pg.LayoutWidget()
        self.__uiDefinitions()
        self.__setStyles()
        self.__setLayout()

    def __uiDefinitions(self):
        self.voltage_spin_box = QtWidgets.QDoubleSpinBox()
        self.setSamplingBtn = QtWidgets.QPushButton("set")

    def __setStyles(self):
        self.setSamplingBtn.setStyleSheet("font: 20pt")
        self.voltage_spin_box.setStyleSheet(
            "QDoubleSpinBox::up-button   { width: 30px; }\n"
            "QDoubleSpinBox::down-button { width: 30px;}\n"
            "QDoubleSpinBox {font: 20pt;}"
        )

    def __setLayout(self):
        self.addWidget(self.widget)
        self.widget.addWidget(self.voltage_spin_box, 0, 0)
        self.widget.addWidget(self.setSamplingBtn, 0, 1)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

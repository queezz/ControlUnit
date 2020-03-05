import sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from pyqtgraph import QtCore
from pyqtgraph.dockarea import Dock
from components.onoffswitch import MySwitch, OnOffSwitch, QmsSwitch
from components.analoggaugewidget import AnalogGaugeWidget

class SettingsDock(Dock):

    def __init__(self):
        super().__init__("Settings")
        self.widget = pg.LayoutWidget()
        self.samplingRateCB = QtGui.QComboBox()
        items = [f'{i} s' for i in [1,0.1,0.01,]]
        [self.samplingRateCB.addItem(i) for i in items]
        self.samplingRateCB.setCurrentIndex(1)
        self.samplingRateCB.setMaximumWidth(120)
        self.samplingRateCB.setToolTip('sampling time')
        self.setSamplingTimeBTN = QtGui.QPushButton('set')
        
        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.samplingRateCB, 0, 0)
        self.widget.addWidget(self.setSamplingTimeBTN, 0, 1)
        
        self.verticalSpacer = QtGui.QSpacerItem(
            0, 0,
            QtGui.QSizePolicy.Minimum,
            QtGui.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)

if __name__ == "__main__":
    pass

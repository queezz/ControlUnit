import sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from pyqtgraph import QtCore
from pyqtgraph.dockarea import Dock
from customTypes import ThreadType
from components.scaleButtons import ScaleButtons
from components.onoffswitch import MySwitch, OnOffSwitch, QmsSwitch
from components.analoggaugewidget import AnalogGaugeWidget

class ControlDock(Dock):

    def __init__(self):
        super().__init__("Control")
        self.widget = pg.LayoutWidget()

        self.quitBtn = QtGui.QPushButton("quit")
        self.quitBtn.setStyleSheet(
            "QPushButton {color:#f9ffd9; background:#ed2a0c;}"
            "QPushButton:disabled {color:#8f8f8f; background:#bfbfbf;}"
        )
        self.quitBtn.setFont(QtGui.QFont('serif',16))

        self.valueBw = QtGui.QTextBrowser()
        self.valueBw.setMaximumHeight(80)
        self.valueBw.setCurrentFont(QtGui.QFont("Courier New")) 

        self.scaleBtn = ScaleButtons()
        self.IGmode = QtGui.QComboBox()
        items = ["Torr","Pa"]
        [self.IGmode.addItem(i) for i in items]
        self.IGmode.setFont(QtGui.QFont('serif',18))

        self.IGrange = QtGui.QSpinBox()
        self.IGrange.setMinimum(-8)
        self.IGrange.setMaximum(-3)
        self.IGrange.setMinimumSize(QtCore.QSize(60, 60))
        self.IGrange.setSingleStep(1)
        self.IGrange.setStyleSheet(
                "QSpinBox::up-button   { width: 50px; }\n"
                "QSpinBox::down-button { width: 50px;}\n"
                "QSpinBox {font: 26pt;}"
        )

        self.qmsSigSw = QmsSwitch()
        self.FullNormSW = MySwitch()
        self.OnOffSW = OnOffSwitch()
        self.OnOffSW.setFont(QtGui.QFont('serif',16))
        
        # Analog Gauge to show Temperature
        self.gaugeT = AnalogGaugeWidget()
        self.gaugeT.set_MinValue(0)
        self.gaugeT.set_MaxValue(400)
        self.gaugeT.set_total_scale_angle_size(180)
        self.gaugeT.set_start_scale_angle(180)
        self.gaugeT.set_enable_value_text(False)

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.OnOffSW, 0, 0)
        self.widget.addWidget(self.quitBtn, 0, 1)

        self.widget.addWidget(self.valueBw, 1, 0,1,2)
        self.widget.addWidget(self.scaleBtn, 2, 1)
        self.widget.addWidget(self.FullNormSW,2,0)
        self.widget.addWidget(self.IGmode,3, 0)
        self.widget.addWidget(self.IGrange,3, 1)

        # Temperature analouge gauge
        self.widget.addWidget(self.gaugeT, 5, 0, 10, 1)

        self.widget.addWidget(self.qmsSigSw, 10, 1, 1, 1)
        
        self.verticalSpacer = QtGui.QSpacerItem(
            0, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(5)
        self.widget.layout.addItem(self.verticalSpacer)

if __name__ == "__main__":
    pass

import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, QtWidgets
from pyqtgraph.dockarea import Dock

# from components.scaleButtons import ScaleButtons
from ..buttons.toggles import MySwitch, OnOffSwitch, QmsSwitch
from ..widgets.analoggauge import AnalogGaugeWidget
from readsettings import select_settings

# Seems that QLed was removed, and it's not used.
# TODO: Delete
# from QLed import QLed

config = select_settings(verbose=False)
MAXTEMP = config["Max Voltage"]

class ControlDock(Dock):
    def __init__(self):
        super().__init__("Control")
        self.widget = pg.LayoutWidget()

        self.quitBtn = QtWidgets.QPushButton("quit")
        self.quitBtn.setStyleSheet(
            "QPushButton {color:#f9ffd9; background:#ed2a0c;}"
            "QPushButton:disabled {color:#8f8f8f; background:#bfbfbf;}"
        )
        self.quitBtn.setFont(QtGui.QFont("serif", 16))

        self.valueBw = QtWidgets.QTextBrowser()
        self.valueBw.setMaximumHeight(100)
        self.valueBw.setMinimumWidth(400)
        self.valueBw.setCurrentFont(QtGui.QFont("Courier New"))

        # self.scaleBtn = ScaleButtons()

        self.scaleBtn = QtWidgets.QComboBox()
        self.scaleBtn.setFont(QtGui.QFont("serif", 18))
        items = ["20 s", "60 sec", "5 min", "15 min", "30 min", "1 hr","1.5 hr", "2 hr", "Full"]
        sizes = [20, 60, 5 * 60, 15 * 60, 30 * 60, 60 * 60, 90*60, 120*60, -1]
        [self.scaleBtn.addItem(i) for i in items]
        self.sampling_windows = {i: j for i, j in zip(items, sizes)}

        self.IGmode = QtWidgets.QComboBox()
        items = ["Torr", "Pa"]
        [self.IGmode.addItem(i) for i in items]
        self.IGmode.setFont(QtGui.QFont("serif", 18))

        self.IGrange = QtWidgets.QSpinBox()
        self.IGrange.setMinimum(-8)
        self.IGrange.setMaximum(-3)
        self.IGrange.setMinimumSize(QtCore.QSize(60, 60))
        self.IGrange.setSingleStep(1)
        self.IGrange.setStyleSheet(
            "QSpinBox::up-button   { width: 40px; }\n"
            "QSpinBox::down-button { width: 40px;}\n"
            "QSpinBox {font: 26pt;}"
        )

        self.qmsSigSw = QmsSwitch()
        self.FullNormSW = MySwitch()
        self.OnOffSW = OnOffSwitch()
        self.OnOffSW.setFont(QtGui.QFont("serif", 16))
    
        self.__setLayout()

    def current_controls(self):        
        """
        Current Power supply is changed
        Current control is not needed, the Kikusui PWR401L is doing that
        This method is just to preserve the controls for now,
        if we need them back.
        """
        self.currentBw = QtWidgets.QTextBrowser()
        self.currentBw.setMinimumSize(QtCore.QSize(60, 50))
        self.currentBw.setMaximumHeight(60)

        self.currentcontrolerSB = QtWidgets.QSpinBox()
        self.currentcontrolerSB.setSuffix(f"mV")
        self.currentcontrolerSB.setMinimum(0)
        self.currentcontrolerSB.setMaximum(500)
        self.currentcontrolerSB.setMinimumSize(QtCore.QSize(60, 50))
        self.currentcontrolerSB.setSingleStep(10)
        self.currentcontrolerSB.setStyleSheet(
            "QSpinBox::up-button   { width: 40px; }\n"
            "QSpinBox::down-button { width: 40px;}\n"
            "QSpinBox {font: 26pt;}"
        )
    
        self.currentsetBtn = QtWidgets.QPushButton("set")
        self.currentsetBtn.setMinimumSize(QtCore.QSize(60, 50))
        self.currentsetBtn.setStyleSheet("font: 20pt")

    def analog_gauge(self):
        """
        Analog Gauge to show Temperature
        Removed from GUI for now
        """
        self.gaugeT = AnalogGaugeWidget()
        self.gaugeT.set_MinValue(0)
        self.gaugeT.set_MaxValue(MAXTEMP)
        self.gaugeT.set_total_scale_angle_size(180)
        self.gaugeT.set_start_scale_angle(180)
        self.gaugeT.set_enable_value_text(False)        

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.OnOffSW, 0, 0, 1, 2)
        self.widget.addWidget(self.qmsSigSw, 0, 2, 1, 2)
        self.widget.addWidget(self.quitBtn, 0, 4, 1, 2)

        self.widget.addWidget(self.valueBw, 1, 0, 1, 6)

        self.widget.addWidget(self.FullNormSW, 2, 0, 1, 2)
        self.widget.addWidget(self.scaleBtn, 2, 2)
        
        self.widget.addWidget(self.IGmode, 2, 3, 1, 2)
        self.widget.addWidget(self.IGrange, 2, 5)

        # self.widget.addWidget(self.currentBw, 3, 0, 1, 4)
        # self.widget.addWidget(self.currentcontrolerSB, 3, 0,1,3)
        # self.widget.addWidget(self.currentsetBtn, 3, 3, 1, 2)

        # Temperature analouge gauge
        # self.widget.addWidget(self.gaugeT, 5, 0, 10, 1)
        # self.widget.addWidget(self.qmsSigSw, 5, 1, 1, 1)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(3)
        self.widget.layout.addItem(self.verticalSpacer)


if __name__ == "__main__":
    pass

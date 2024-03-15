import pyqtgraph as pg
from PyQt5 import QtGui, QtWidgets
from pyqtgraph.dockarea import DockArea, Dock

from components.docks.log import LogDock
from components.docks.plots import PlotScaleDock
from components.docks.control import ControlDock
from components.docks.adcgain import ADCGain
from components.docks.settings import SettingsDock
# from components.docks.tempcontrol import HeaterControl
from components.docks.mfccontrol import MassFlowControllerControl as MFCControl
from components.widgets.graph import Graph


class UIWindow(object):
    def __init__(self):
        super().__init__()
        pg.setConfigOptions(imageAxisOrder="row-major")

        self.MainWindow = QtWidgets.QMainWindow()
        self.tabwidg = QtWidgets.QTabWidget()
        self.area = DockArea()
        self.plotDock = Dock("Plots", size=(300, 400))
        self.controlDock = ControlDock()
        self.logDock = LogDock()
        # self.tempcontrolDock = HeaterControl()
        self.mfccontrolDock = MFCControl()
        [i.setStretch(*(10, 20)) for i in [self.controlDock, self.logDock, self.mfccontrolDock]]
        self.controlDock.setStretch(*(10, 300))
        self.graph = Graph()
        self.scaleDock = PlotScaleDock()

        self.settings_area = DockArea()
        self.SettingsDock = SettingsDock()
        self.logDock.setStretch(*(200, 100))
        self.SettingsDock.setStretch(*(80, 100))

        self.ADCGainDock = ADCGain()

        self.MainWindow.setGeometry(20, 50, 800, 400)
        sizeObject = QtWidgets.QDesktopWidget().screenGeometry(-1)
        # print(" Screen size : " + str(sizeObject.height()) + "x" + str(sizeObject.width()))
        if sizeObject.height() < 1000:
            self.MainWindow.showMaximized()

        # self.MainWindow.showFullScreen()
        self.MainWindow.setObjectName("Monitor")
        self.MainWindow.setWindowTitle("Data Logger")
        # self.MainWindow.statusBar().showMessage("")
        self.MainWindow.setAcceptDrops(True)

        self.__setLayout()

    def __setLayout(self):
        self.MainWindow.setCentralWidget(self.tabwidg)
        self.tabwidg.addTab(self.area, "Data")
        
        self.area.addDock(self.controlDock)
        self.area.addDock(self.plotDock)
        self.area.addDock(self.mfccontrolDock,'right')
        self.area.addDock(self.scaleDock,'bottom',self.mfccontrolDock)
    

        self.plotDock.addWidget(self.graph)

        self.tabwidg.addTab(self.settings_area, "Settings")
        self.settings_area.addDock(self.SettingsDock)
        self.area.addDock(self.ADCGainDock, "bottom", self.SettingsDock)
        self.settings_area.addDock(self.logDock, "right")

    def showMain(self):
        self.MainWindow.show()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    ui = UIWindow()
    ui.showMain()
    sys.exit(app.exec_())

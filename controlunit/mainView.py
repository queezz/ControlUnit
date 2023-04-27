import pyqtgraph as pg
from PyQt5 import QtGui, QtWidgets
from pyqtgraph.dockarea import DockArea, Dock

from components.controlDock import ControlDock
from components.logDock import LogDock
from components.registerDock import RegisterDock
from components.graph import Graph
from components.plotscaleDock import PlotScaleDock
from components.settingsDock import SettingsDock


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
        self.registerDock = RegisterDock()
        [i.setStretch(*(10, 20)) for i in [self.controlDock, self.logDock, self.registerDock]]
        self.controlDock.setStretch(*(10, 300))
        self.graph = Graph()
        self.scaleDock = PlotScaleDock()

        self.settings_area = DockArea()
        self.SettingsDock = SettingsDock()
        self.logDock.setStretch(*(200, 100))
        self.SettingsDock.setStretch(*(80, 100))

        self.MainWindow.setGeometry(20, 50, 1000, 600)
        sizeObject = QtWidgets.QDesktopWidget().screenGeometry(-1)
        # print(" Screen size : " + str(sizeObject.height()) + "x" + str(sizeObject.width()))
        if sizeObject.hight() < 1000:
            self.MainWindow.showMaximized()

        # self.MainWindow.showFullScreen()
        self.MainWindow.setObjectName("Monitor")
        self.MainWindow.setWindowTitle("Data Logger")
        self.MainWindow.statusBar().showMessage("")
        self.MainWindow.setAcceptDrops(True)

        self.__setLayout()

    def __setLayout(self):
        self.MainWindow.setCentralWidget(self.tabwidg)
        self.tabwidg.addTab(self.area, "Data")

        self.area.addDock(self.plotDock, "top")
        self.area.addDock(self.scaleDock, "left")
        self.area.addDock(self.controlDock, "above", self.scaleDock)
        self.area.addDock(self.registerDock, "bottom", self.controlDock)

        self.plotDock.addWidget(self.graph)

        self.tabwidg.addTab(self.settings_area, "Settings")
        self.settings_area.addDock(self.SettingsDock)
        self.settings_area.addDock(self.logDock, "right")

    def showMain(self):
        self.MainWindow.show()


if __name__ == "__main__":
    import sys

    app = QtGui.QApplication(sys.argv)
    ui = UIWindow()
    ui.showMain()
    sys.exit(app.exec_())

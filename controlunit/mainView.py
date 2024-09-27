import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import DockArea, Dock

from ui.docks.log import LogDock
from ui.docks.plots import PlotScaleDock
from ui.docks.control import ControlDock
from ui.docks.adcgain import ADCGain
from ui.docks.settings import SettingsDock
from ui.docks.calibration import CalibrationDock
from controlunit.ui.docks.plasma_current import PlasmaCurrentDock

# from components.docks.tempcontrol import HeaterControl
from controlunit.ui.docks.gas_flow import GasFlowDock
from ui.widgets.graph import Graph


class UIWindow(object):
    def __init__(self):
        super().__init__()
        pg.setConfigOptions(imageAxisOrder="row-major")

        self._init_main_window()
        self._initialize_layout()

    def _init_main_window(self):
        """Initializes the main window settings."""
        self.MainWindow = QtWidgets.QMainWindow()
        self.tabwidg = QtWidgets.QTabWidget()
        self.MainWindow.setCentralWidget(self.tabwidg)
        self.MainWindow.setGeometry(20, 50, 800, 400)

        sizeObject = QtWidgets.QDesktopWidget().screenGeometry(-1)
        if sizeObject.height() < 1000:
            self.MainWindow.showMaximized()

        self.MainWindow.setObjectName("Monitor")
        self.MainWindow.setWindowTitle("Data Logger")
        self.MainWindow.setAcceptDrops(True)

    def _initialize_layout(self):
        """Sets up the layout by creating tabs and docks."""
        self._setup_main_tab()
        self._setup_settings_tab()
        self._setup_test_tab()  # Un-comment if needed

    def _setup_main_tab(self):
        """Sets up the main tab with control, plot, and log docks."""
        self.area = DockArea()
        self.plot_dock = Dock("Plots", size=(300, 400))
        self.control_dock = ControlDock()
        self.gasflow_dock = GasFlowDock()
        self.calibration_dock = CalibrationDock()
        self.plasma_control_dock = PlasmaCurrentDock()
        self.scale_dock = PlotScaleDock()

        # Set stretching for docks
        self._set_dock_stretch([self.control_dock, self.gasflow_dock], 10, 20)
        self.control_dock.setStretch(10, 300)

        # Arrange the elements in the dock area
        self.tabwidg.addTab(self.area, "Data")
        self.area.addDock(self.control_dock)
        self.area.addDock(self.plot_dock)
        self.area.addDock(self.gasflow_dock, "right")
        self.area.addDock(self.calibration_dock, "bottom", self.gasflow_dock)
        self.area.addDock(self.plasma_control_dock, "below", self.calibration_dock)
        self.area.addDock(self.scale_dock, "bottom", self.calibration_dock)

        self.graph = Graph()
        self.plot_dock.addWidget(self.graph)

    def _setup_test_tab(self):
        """Extra tab for UI and other tests"""
        self.test_area = DockArea()
        # self.plasma_control_dock = PlasmaCurrentDock()
        # self.tabwidg.addTab(self.test_area, "Tests")
        # self.test_area.addDock(self.plasma_control_dock)

    def _setup_settings_tab(self):
        """Configures the settings tab with its components."""
        self.settings_area = DockArea()
        self.settings_dock = SettingsDock()
        self.settings_dock.setStretch(80, 100)
        self.adcgain_dock = ADCGain()
        self.logDock = LogDock()

        self.tabwidg.addTab(self.settings_area, "Settings")
        self.settings_area.addDock(self.settings_dock)
        self.settings_area.addDock(self.adcgain_dock, "bottom", self.settings_dock)
        self.settings_area.addDock(self.logDock, "right")
        self.logDock.setStretch(300, 20)

    @staticmethod
    def _set_dock_stretch(docks, stretch_x, stretch_y):
        """Sets stretch values for multiple docks."""
        for dock in docks:
            dock.setStretch(stretch_x, stretch_y)

    def showMain(self):
        self.MainWindow.show()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    ui = UIWindow()
    ui.showMain()
    sys.exit(app.exec_())

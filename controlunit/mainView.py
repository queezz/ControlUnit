import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import DockArea, Dock

from ui.docks.log import LogDock
from controlunit.ui.docks.scales import PlotScaleDock
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

    # MARK: Layout
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
        # self._setup_test_tab()  # Un-comment if needed

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
        self.tabwidg.addTab(self.test_area, "Tests")

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

    # MARK: Logic
    def _init_plot_controls(self):
        """Toggle plots for Current, Temperature, and Pressure"""
        self.scale_dock.togIp.clicked.connect(self.toggle_plots)
        self.scale_dock.togBaratron.clicked.connect(self.toggle_plots_baratron)
        self.scale_dock.togIGs.clicked.connect(self.toggle_plots_igs)
        self.scale_dock.togP.clicked.connect(self.toggle_plots)

        self.scale_dock.Pmin.valueChanged.connect(self.__updatePScale)
        self.scale_dock.Pmax.valueChanged.connect(self.__updatePScale)
        self.scale_dock.Imin.valueChanged.connect(self.__updateIScale)
        self.scale_dock.Imax.valueChanged.connect(self.__updateIScale)
        # self.scale_dock.Tmax.valueChanged.connect(self.__updateTScale)

        self.scale_dock.autoscale.clicked.connect(self.__auto_or_levels)
        self.scale_dock.togYLog.clicked.connect(self.__toggleYLogScale)

        self.set_scales_switches()

    def toggle_plots(self):
        """
        Toggle plots - pyqtgraph GraphViews
        self.scale_dock.togIp
        self.graph.plaPl
        """

        def toggleplot(i, pl, row=0, col=0):
            if i.isChecked():
                try:
                    self.graph.addItem(pl, row=row, col=col)
                except:
                    pass
            else:
                try:
                    self.graph.removeItem(pl)  # remove plot
                except:
                    pass

        items = {
            "Ip": [self.scale_dock.togIp, self.graph.plasma_plot, 0, 0],
            # "T": [self.scale_dock.togT, self.graph.tempPl, 1, 0],
            "P": [self.scale_dock.togP, self.graph.pressure_plot, 1, 0],
        }

        [toggleplot(*items[jj]) for jj in ["Ip", "P"]]

    def toggle_plots_baratron(self):
        if self.scale_dock.togBaratron.isChecked():
            [self.graph.plot_lines[name].setVisible(True) for name in ["Bu", "Bd"]]
        else:
            [self.graph.plot_lines[name].setVisible(False) for name in ["Bu", "Bd"]]

    def toggle_plots_igs(self):
        """Toggle IG and Pfeiffer lines"""
        if self.scale_dock.togIGs.isChecked():
            [self.graph.plot_lines[name].setVisible(True) for name in ["Pu", "Pd"]]
        else:
            [self.graph.plot_lines[name].setVisible(False) for name in ["Pu", "Pd"]]

    def __toggleYLogScale(self):
        """Toggle Y Scale between Log and Lin for Pressure plots"""
        if self.scale_dock.togYLog.isChecked():
            self.graph.pressure_plot.setLogMode(y=True)
        else:
            self.graph.pressure_plot.setLogMode(y=False)

    def __updatePScale(self):
        """Updated plot limits for the Pressure viewgraph"""
        pmin, pmax = [self.scale_dock.Pmin.value(), self.scale_dock.Pmax.value()]

        # self.graph.presPl.setLogMode(y=True)
        self.graph.pressure_plot.setYRange(pmin, pmax, 0)

    def __updateIScale(self):
        """Updated plot limits for the plasma current viewgraph"""
        imin, imax = [self.scale_dock.Imin.value(), self.scale_dock.Imax.value()]
        self.graph.plasma_plot.setYRange(imin, imax, 0)

    # def __updateTScale(self):
    #     """Updated plot limits for the Temperature viewgraph"""
    #     tmax = self.scale_dock.Tmax.value()
    #     self.graph.tempPl.setYRange(0, tmax, 0)

    def __updateScales(self):
        """Update all scales according to spinboxes"""
        self.__updateIScale()
        # self.__updateTScale()
        self.__updatePScale()

    def __autoscale(self):
        """Set all plots to autoscale"""
        # enableAutoRange
        # plots = [self.graph.plasma_plot, self.graph.temperature_plot, self.graph.pressure_plot]
        plots = [self.graph.plasma_plot, self.graph.pressure_plot]

        # [i.autoRange() for i in plots]
        [i.enableAutoRange() for i in plots]

    def __auto_or_levels(self):
        """Change plot scales from full auto to Y axis from settings"""
        if self.scale_dock.autoscale.isChecked():
            self.__autoscale()
        else:
            self.__updateScales()

    def fulltonormal(self):
        """Change from full screen to normal view on click"""
        if self.control_dock.FullNormSW.isChecked():
            self.MainWindow.showFullScreen()
            self.control_dock.setStretch(*(10, 300))  # minimize control dock width
        else:
            self.MainWindow.showNormal()
            self.control_dock.setStretch(*(10, 300))  # minimize control dock width

    def set_scales_switches(self):
        """Set default checks for swithces in Scales"""
        self.scale_dock.togP.setChecked(True)
        self.scale_dock.togBaratron.setChecked(False)
        self.scale_dock.togIp.setChecked(False)
        self.scale_dock.togYLog.setChecked(True)
        self.scale_dock.togIGs.setChecked(True)
        self.toggle_plots_baratron()
        self.toggle_plots_igs()
        self.toggle_plots()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    ui = UIWindow()
    ui.showMain()
    sys.exit(app.exec_())

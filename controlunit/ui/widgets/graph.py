import pyqtgraph as pg
from PyQt5 import QtGui

from controlunit.ui.text_shortcuts import DEGREE_SMB


class Graph(pg.GraphicsLayoutWidget):
    pens = {
        "Ip": {"color": "#8d3de3", "width": 1},
        "Pu": {"color": "#c9004d", "width": 1},
        "Pu2": {"color": "#3b82f6", "width": 1},
        "Pd": {"color": "#6ac600", "width": 1},
        "Bu": {"color": "#ffb405", "width": 1},
        "Bd": {"color": "#00a3af", "width": 1},
        "T": {"color": "#5999ff", "width": 1},
        "trigger": {"color": "#edbc34", "width": 1},
    }

    #: The pressure curves in the order the rig's screen lists them: the ion
    #: gauges (the Pfeiffer Pu and the two ionization gauges, Pu2 upstream
    #: since 2026-09-15 and Pd downstream), then the two Baratrons. Every
    #: list of what is plotted, toggled or read out is built from these, so
    #: a gauge is added in one place.
    ION_CURVES = ("Pu", "Pu2", "Pd")
    BARATRON_CURVES = ("Bu", "Bd")
    PRESSURE_CURVES = ION_CURVES + BARATRON_CURVES

    #: What the rig's own small screen spells out in its value browser: the
    #: five it has always fitted, three to a row. Not every signal (owner
    #: decision 2026-09-15, seeing six wrap and scroll: "Maybe we don't
    #: have to put ALL the signals in that tiny display on GUI. When I face
    #: the controlunit, I can see the IG block and read the value. But WebUI
    #: gets it all."). Pu2 is read off its own controller at the rig, and
    #: still drawn on the plot and recorded in the file.
    SCREEN_READOUTS = ("Ip", "Bu", "Bd", "Pu", "Pd")
    #: Of those, the ones with no display anywhere but this screen: the Hall
    #: sensor's current and the two Baratrons. They lead the row and are
    #: written large; the two gauges, which have controllers of their own in
    #: the rack, follow small (owner direction 2026-09-15: "make the in-the-
    #: rack displayed values smaller, and show hall sensor current and two
    #: baratrons more prominent. They have no displays but the ControlUnit").
    SCREEN_PROMINENT = ("Ip", "Bu", "Bd")

    def __init__(self):
        super().__init__()
        self.labelStyle = {"color": "#FFF", "font-size": "14pt"}
        self.font = QtGui.QFont("serif", 14)
        self.plot_lines = {}

        self.init()

    def init(self):
        self.setObjectName("graph")
        pg.setConfigOptions(useOpenGL=True)
        self.setBackground(background="#25272b")

        self._init_plasma_plot(row=0)
        self._init_pressure_plot(row=1)
        self._init_plasma_curves()
        self._init_pressure_curves()

    def __init_plotitem_curves(self, plot_item, names):
        """Add curves to a given plot, and add them to the plot_lines dict"""
        for name in names:
            self.plot_lines[name] = plot_item.plot(pen=self.pens[name])

    def _init_plasma_curves(self):
        self.__init_plotitem_curves(self.plasma_plot, ["Ip", "trigger"])
        self.plasma_plot.setXLink(self.pressure_plot)

    def _init_pressure_curves(self):
        """Add curves to pressure plot"""
        self.__init_plotitem_curves(self.pressure_plot, list(self.PRESSURE_CURVES))

        self.pressure_plot.setLogMode(y=True)
        self.pressure_plot.setYRange(-8, 3, 0)

    def _init_temperature_curves(self):
        self.__init_plotitem_curves(self.temperature_plot, ["T"])

        self.temperature_plot.setXLink(self.presPl)
        self.temperature_plot.setYRange(0, 320, 0)

    def _init_plasma_plot(self, row=0):
        """Plasma parameters plot: Plasma current"""
        self.plasma_plot = self.addPlot(row=row, col=0)
        self.plasma_plot.setLabel("left", "Ip", units="A", **self.labelStyle)
        left_axis = self.plasma_plot.getAxis("left")
        left_axis.setWidth(70)
        left_axis.tickFont = self.font
        left_axis.setTextPen("#ff7878")
        axis = pg.DateAxisItem()
        self.plasma_plot.setAxisItems({"bottom": axis})

    def _init_pressure_plot(self, row=1):
        """Init pressure plot"""
        self.pressure_plot = self.addPlot(row=row, col=0)
        self.pressure_plot.setLabel("left", "P", units="Torr", **self.labelStyle)
        self.pressure_plot.setLabel("bottom", "time", units="sec", **self.labelStyle)
        left_axis = self.pressure_plot.getAxis("left")
        left_axis.setWidth(70)
        left_axis.setTextPen("#ff7878")
        axis = pg.DateAxisItem()
        self.pressure_plot.setAxisItems({"bottom": axis})
        bottom_axis = self.pressure_plot.getAxis("bottom")
        bottom_axis.tickFont = self.font
        bottom_axis.setStyle(tickTextOffset=10)
        bottom_axis.setTextPen("#ff7878")

    def _init_temperature_plot(self, row=2):
        """
        Prep MAX6675 plots
        Currently moved thermocouples to National Instruments on Windows.
        """
        self.temperature_plot = self.addPlot(row=row, col=0)
        self.temperature_plot.setLabel(
            "left", "T", units=DEGREE_SMB + "C", **self.labelStyle
        )
        self.temperature_plot.getAxis("left").setWidth(100)
        self.temperature_plot.getAxis("left").setPen("#fcfcc7")
        self.temperature_plot.getAxis("left").tickFont = self.font


if __name__ == "__main__":
    pass

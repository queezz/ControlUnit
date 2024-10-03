import pyqtgraph as pg
from PyQt5 import QtGui

from controlunit.ui.text_shortcuts import DEGREE_SMB


class Graph(pg.GraphicsLayoutWidget):
    pens = {
        "Ip": {"color": "#8d3de3", "width": 1},
        "Pu": {"color": "#c9004d", "width": 1},
        "Pd": {"color": "#6ac600", "width": 1},
        "Bu": {"color": "#ffb405", "width": 1},
        "Bd": {"color": "#00a3af", "width": 1},
        "T": {"color": "#5999ff", "width": 1},
        "trigger": {"color": "#edbc34", "width": 1},
    }

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
        self.__init_plotitem_curves(self.pressure_plot, ["Pu", "Pd", "Bu", "Bd"])

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

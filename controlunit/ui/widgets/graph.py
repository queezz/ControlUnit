import pyqtgraph as pg
from PyQt5 import QtGui,QtWidgets

DEGREE_SMB = u'\N{DEGREE SIGN}'

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
        self.setObjectName("graph")
        pg.setConfigOptions(useOpenGL=True)
        self.setBackground(background='#25272b')

        self.labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        self.font = QtGui.QFont('serif',14)

        self.prep_adc_plots()
        self.prep_pressure_curves()
        self.prep_plasma_curves()
        #self.prep_temperature_curves()

    def prep_plasma_curves(self):
        self.plasma_cruve = self.plasma_plot.plot(pen=self.pens["Ip"])
        self.trigger_curve = self.plasma_plot.plot(pen=self.pens["trigger"])
        self.plasma_plot.setXLink(self.pressure_plot)

    def prep_pressure_curves(self):
        self.baratron_up_curve = self.pressure_plot.plot(pen=self.pens["Bu"])
        self.baratron_down_curve = self.pressure_plot.plot(pen=self.pens["Bd"])
        self.pressure_up_curve = self.pressure_plot.plot(pen=self.pens["Pu"])
        self.pressure_down_curve = self.pressure_plot.plot(pen=self.pens["Pd"])

        self.pressure_plot.setLogMode(y=True)
        self.pressure_plot.setYRange(-8, 3, 0)

    def prep_temperature_curves(self):
        self.valueTPlot = self.tempPl.plot(pen=self.pens["T"])
        self.tempPl.setXLink(self.presPl)
        self.tempPl.setYRange(0, 320, 0)              
        

    def prep_adc_plots(self,row=0):
        """Prep ADC plots"""
        self.plasma_plot = self.addPlot(row=0, col=0)
        self.plasma_plot.setLabel('left', "Ip", units='A',**self.labelStyle)
        left_axis = self.plasma_plot.getAxis('left') 
        left_axis.setWidth(70)
        left_axis.tickFont = self.font
        left_axis.setTextPen("#ff7878")
        axis = pg.DateAxisItem()
        self.plasma_plot.setAxisItems({"bottom": axis})

        self.pressure_plot = self.addPlot(row=1, col=0)
        self.pressure_plot.setLabel('left', "P", units='Torr',**self.labelStyle)
        self.pressure_plot.setLabel('bottom', "time", units='sec',**self.labelStyle)
        left_axis = self.pressure_plot.getAxis('left')
        left_axis.setWidth(70)
        left_axis.setTextPen("#ff7878")
        axis = pg.DateAxisItem()
        self.pressure_plot.setAxisItems({"bottom": axis})
        bottom_axis = self.pressure_plot.getAxis('bottom')
        bottom_axis.tickFont = self.font
        bottom_axis.setStyle(tickTextOffset = 10)
        bottom_axis.setTextPen("#ff7878")

    def prep_max6675_plots(self,row=2):
        """
        Prep MAX6675 plots
        Currently moved thermocouples to National Instruments on Windows.
        """
        self.temperature_plot = self.addPlot(row=row, col=0)
        self.temperature_plot.setLabel('left', "T", units=DEGREE_SMB+'C',**self.labelStyle)
        self.temperature_plot.getAxis('left').setWidth(100)
        self.temperature_plot.getAxis('left').setPen('#fcfcc7')
        self.temperature_plot.getAxis('left').tickFont = self.font

if __name__ == '__main__':
    pass

import pyqtgraph as pg
from PyQt5 import QtGui,QtWidgets

DEGREE_SMB = u'\N{DEGREE SIGN}'

class Graph(pg.GraphicsLayoutWidget):

    def __init__(self):
        super().__init__()
        self.setObjectName("graph")
        self.setBackground(background='#25272b')

        self.labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        self.font = QtGui.QFont('serif',14)

        self.prep_adc_plots()


    def prep_adc_plots(self):
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

    def prep_max6675_plots(self):
        """
        Prep MAX6675 plots
        Currently moved thermocouples to National Instruments on Windows.
        """
        self.temperature_plot = self.addPlot(row=1, col=0)
        self.temperature_plot.setLabel('left', "T", units=DEGREE_SMB+'C',**self.labelStyle)
        # Adjust the label offset
        self.temperature_plot.getAxis('left').setWidth(100)
        self.temperature_plot.getAxis('left').setPen('#fcfcc7')
        self.temperature_plot.getAxis('left').tickFont = self.font

if __name__ == '__main__':
    pass

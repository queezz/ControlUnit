import pyqtgraph as pg
from PyQt5 import QtGui,QtWidgets

DEGREE_SMB = u'\N{DEGREE SIGN}'

class Graph(pg.GraphicsLayoutWidget):

    def __init__(self):
        super().__init__()
        self.setObjectName("graph")
        self.setBackground(background='#25272b')

        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        font = QtGui.QFont('serif',14)

        self.plasma_plot = self.addPlot(row=0, col=0)    
        self.plasma_plot.setLabel('left', "Ip", units='A',**labelStyle)
        self.plasma_plot.getAxis('left').setWidth(70)
        self.plasma_plot.getAxis('left').tickFont = font

        # self.tempPl = self.addPlot(row=1, col=0)
        # self.tempPl.setLabel('left', "T", units=DEGREE_SMB+'C',**labelStyle)
        # # Adjust the label offset
        # self.tempPl.getAxis('left').setWidth(100)
        # self.tempPl.getAxis('left').setPen('#fcfcc7')
        # self.tempPl.getAxis('left').tickFont = font

        self.pressure_plot = self.addPlot(row=1, col=0)
        self.pressure_plot.setLabel('left', "P", units='Torr',**labelStyle)
        self.pressure_plot.getAxis('left').setWidth(70)
        self.pressure_plot.setLabel('bottom', "time", units='sec',**labelStyle)

        axis = pg.DateAxisItem()
        self.pressure_plot.setAxisItems({"bottom": axis})

        self.pressure_plot.getAxis('bottom').tickFont = font
        self.pressure_plot.getAxis('bottom').setStyle(tickTextOffset = 10)

if __name__ == '__main__':
    pass

import pyqtgraph as pg
from PyQt5 import QtGui,QtWidgets

DEGREE_SMB = u'\N{DEGREE SIGN}'

class Graph(pg.GraphicsLayoutWidget):

    def __init__(self):
        super().__init__()
        self.setObjectName("graph")

        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        font = QtGui.QFont('serif',14)

        self.plaPl = self.addPlot(row=0, col=0)
        # TODO: 単位
        self.plaPl.setLabel('left', "Ip", units='A',**labelStyle)
        self.plaPl.getAxis('left').setWidth(50)
        self.plaPl.getAxis('left').tickFont = font

        # self.tempPl = self.addPlot(row=1, col=0)
        # self.tempPl.setLabel('left', "T", units=DEGREE_SMB+'C',**labelStyle)
        # # Adjust the label offset
        # self.tempPl.getAxis('left').setWidth(100)

        self.presPl = self.addPlot(row=1, col=0)
        self.presPl.setLabel('left', "P", units='Torr',**labelStyle)
        self.presPl.getAxis('left').setWidth(50)
        self.presPl.setLabel('bottom', "time", units='sec',**labelStyle)
        
        self.setBackground(background='#25272b')
               
        # self.tempPl.getAxis('left').setPen('#fcfcc7')
        # self.tempPl.getAxis('left').tickFont = font
        self.presPl.getAxis('bottom').tickFont = font
        self.presPl.getAxis('bottom').setStyle(tickTextOffset = 10)

if __name__ == '__main__':
    pass

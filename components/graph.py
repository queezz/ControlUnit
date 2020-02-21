import pyqtgraph as pg
from pyqtgraph.Qt import QtGui

DEGREE_SMB = u'\N{DEGREE SIGN}'

class Graph(pg.GraphicsLayoutWidget):

    def __init__(self):
        super().__init__()
        self.setObjectName("graph")

        self.plaPl = self.addPlot(row=0, col=0)
        # TODO: 単位
        self.plaPl.setLabel('left', "Ip", units='mA')

        self.tempPl = self.addPlot(row=1, col=0)
        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        self.tempPl.setLabel('left', "T", units=DEGREE_SMB+'C',**labelStyle)
        # Adjust the label offset
        self.tempPl.getAxis('left').setWidth(100)

        self.presPl = self.addPlot(row=2, col=0)
        self.presPl.setLabel('left', "P", units='Torr',**labelStyle)
        self.presPl.getAxis('left').setWidth(100)
        self.presPl.setLabel('bottom', "time", units='sec',**labelStyle)
        
        self.setBackground(background='#25272b')
               
        self.tempPl.getAxis('left').setPen('#fcfcc7')
        font = QtGui.QFont('serif',15)
        self.tempPl.getAxis('left').tickFont = font
        self.presPl.getAxis('left').tickFont = font
        self.presPl.getAxis('bottom').tickFont = font
        self.presPl.getAxis('bottom').setStyle(tickTextOffset = 10)

if __name__ == '__main__':
    pass

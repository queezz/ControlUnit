from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRect
import sys

class MySwitch(QtWidgets.QPushButton):
    radius = 10
    width = 38
    # 0 - On, 1 - Off
    labels = ['FULL','NORM']
    #colors = [Qt.green, Qt.red]
    colors = [QtGui.QColor('#e9fac5'), QtGui.QColor('#8f94c2')]
    
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumWidth(66)
        self.setMinimumHeight(22)

    def paintEvent(self, event):
        radius = self.radius
        width = self.width
        
        label = self.labels[0] if self.isChecked() else self.labels[1]
        bg_color = self.colors[0] if self.isChecked() else self.colors[1]

        center = self.rect().center()

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.translate(center)
        painter.setBrush(QtGui.QColor(0,0,0))

        pen = QtGui.QPen(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)

        painter.drawRoundedRect(QRect(-width, -radius, 2*width, 2*radius), radius, radius)
        painter.setBrush(QtGui.QBrush(bg_color))
        sw_rect = QRect(-radius, -radius, width + radius, 2*radius)
        
        if not self.isChecked():
            sw_rect.moveLeft(-width)
            
        painter.drawRoundedRect(sw_rect, radius, radius)
        painter.drawText(sw_rect, Qt.AlignCenter, label)

class OnOffSwitch(MySwitch):    
    radius = 15
    width = 40
    # 0 - On, 1 - Off
    labels = ['ON','OFF']
    colors = [QtGui.QColor('#8df01d'), QtGui.QColor('#b89c76')]

class QmsSwitch(MySwitch):
    radius = 14
    width = 40

    labels = ['qRun', 'qStop']
    colors = [QtGui.QColor('#33CCFF'), QtGui.QColor('#b89c76')]

if __name__ == "__main__":
    pass

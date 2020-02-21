import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from pyqtgraph import QtCore
from pyqtgraph.dockarea import Dock

DEGREE_SMB = u'\N{DEGREE SIGN}'

class RegisterDock(Dock):

    def __init__(self):
        super().__init__("Membreane Heater")
        self.widget = pg.LayoutWidget()        
        self.tempBw = QtGui.QTextBrowser()        
        self.tempBw.setMinimumSize(QtCore.QSize(80,60))
        self.tempBw.setMaximumHeight(60)
        self.temperatureSB = QtGui.QSpinBox()
        self.temperatureSB.setMinimum(0)
        self.temperatureSB.setMaximum(600)
        self.temperatureSB.setSuffix(f'{DEGREE_SMB} C')
        self.temperatureSB.setMinimumSize(QtCore.QSize(180, 80))
        self.temperatureSB.setSingleStep(10)
        self.temperatureSB.setStyleSheet(
                "QSpinBox::up-button   { width: 60px; }\n"
                "QSpinBox::down-button { width: 60px;}\n"
                "QSpinBox {font: 26pt;}"
        )
        self.registerBtn = QtGui.QPushButton("set")
        self.registerBtn.setMinimumSize(QtCore.QSize(80, 80))
        self.registerBtn.setStyleSheet("font: 26pt")
        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.tempBw, 0, 0,1,2)        
        self.widget.addWidget(self.temperatureSB, 1, 0)
        self.widget.addWidget(self.registerBtn, 1, 1)
        
        self.verticalSpacer = QtGui.QSpacerItem(
            0, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding
        )
        #self.widget.layout.setVerticalSpacing(0)
        self.widget.layout.addItem(self.verticalSpacer)        

    def __setLabelFont(self, text: str, color: str):
        txt = "<font color={}><h4>{}</h4></font>".format(color, text)
        return txt

    def setTempText(self,temperature, temp_now):
        """ set values into browser"""
        htmltag = '<font size=6 color="#d1451b">'
        htag1 = '<font size=6 color = "#4275f5">'
        cf = '</font>'
        self.tempBw.setText(
            f'{htmltag}{temperature} {DEGREE_SMB}C{cf}'
            f'&nbsp;&nbsp;&nbsp;{htag1}{temp_now} {DEGREE_SMB}C{cf}')
        
    def setTemp(self, temperature: int,temp_now):
        self.setTempText(temperature,temp_now)
        self.temperatureSB.setValue(temperature)

if __name__ == "__main__":
    pass

import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import Dock
from customTypes import ScaleSize

class ScaleButtons(pg.LayoutWidget):

    def __init__(self):
        super().__init__()
        self.scaleLabel = QtGui.QLabel(self.__setLabelFont("Scale:", "#000001"))
        self.selectBtn = QtGui.QComboBox()
        self.selectBtn.setFont(QtGui.QFont('serif',18))
        self.__setSelect()
        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.selectBtn, 1, 0, 1, 1)

    def __setSelect(self):
        items = ["Small","Medium","Large","Full"]
        [self.selectBtn.addItem(i) for i in items]

    def __setLabelFont(self, text: str, color: str):
        txt = f"<font color={color}><h5>{text}</h5></font>"
        return txt

if __name__ == "__main__":
    pass

import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from pyqtgraph.dockarea import Dock

class LogDock(Dock):

    def __init__(self):
        super().__init__("Log")
        self.widget = pg.LayoutWidget()

        self.log = QtGui.QTextEdit()
        self.progress = QtGui.QTextEdit()

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.log, 0, 0, 1, 2)
        self.widget.addWidget(self.progress, 0, 2, 1, 2)

if __name__ == "__main__":
    pass
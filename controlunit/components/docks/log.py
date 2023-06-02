import pyqtgraph as pg
from PyQt5 import QtWidgets
from pyqtgraph.dockarea import Dock


class LogDock(Dock):
    def __init__(self):
        super().__init__("Log")
        self.widget = pg.LayoutWidget()

        self.log = QtWidgets.QTextBrowser()
        self.log.document().setDefaultStyleSheet('p{font-size:16px; margin-top:0px; margin-bottom:0px;}')

        self.__setLayout()

    def __setLayout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.log, 0, 0, 1, 1)


if __name__ == "__main__":
    pass

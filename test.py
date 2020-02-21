import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore

from electricCurrent import ElectricCurrent
from customTypes import ThreadType, ScaleSize
from worker import Worker

class UIWindow(object):
    DEFAULT_TEMPERATURE = 
    sigAbortWorkers = QtCore.pyqtSignal()

    def __init__(self, app):
        super().__init__()
        self.__setLayout()
        self.app = app
        self.worker = Worker()
        self.worker.setWorker(1, ThreadType.TEMPERATURE, self.app)

        thread = QtCore.QThread()
        thread.setObjectName("test")
        self.worker.moveToThread(thread)
        self.sigAbortWorkers.connect(worker.abort)

    def __setLayout(self):
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.MainWindow = QtGui.QMainWindow()
        self.widget = pg.LayoutWidget()

        self.valueBw1 = QtGui.QTextBrowser()
        self.valueBw1.setMaximumHeight(110)

        self.valueBw2 = QtGui.QTextBrowser()
        self.valueBw2.setMaximumHeight(110)
        self.MainWindow.setCentralWidget(self.widget)
        self.widget.addWidget(self.valueBw1, 0, 0)
        self.widget.addWidget(self.valueBw2, 0, 1)

    def showMain(self):
        self.MainWindow.show()

if __name__ == '__main__':
    import sys 
    app = QtGui.QApplication(sys.argv)
    ui = UIWindow(app)
    sys.exit(app.exec_())

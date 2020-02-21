import sys, datetime, os
import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtGui

from mainView import UIWindow
from worker import Worker
from customTypes import ThreadType, ScaleSize
from readsettings import make_datafolders, get_datafolderpth
import qmsSignal

try:
    from AIO import AIO_32_0RA_IRC as adc
    import pigpio
except:
    print("no pigpio or AIO")
    TEST = True

# debug 
# def trap_exc_during_debug(*args):
#     print(args)

# sys.excepthook = trap_exc_during_debug

# must inherit QtCore.QObject in order to use 'connect'
class MainWidget(QtCore.QObject, UIWindow):
    DEFAULT_TEMPERATURE = 0

    sigAbortWorkers = QtCore.pyqtSignal()

    def __init__(self, app: QtGui.QApplication):
        super(self.__class__, self).__init__()
        self.__app = app
        self.__setConnects()
        self.registerDock.setTemp(self.DEFAULT_TEMPERATURE,'---')

        QtCore.QThread.currentThread().setObjectName("main")

        self.__workers_done = 0
        self.__threads = []
        self.__temp = self.DEFAULT_TEMPERATURE

        self.__scale = ScaleSize.SMALL

        self.plaData = None
        self.tData = None
        self.p1Data = None
        self.p2Data = None

        self.graph.removeItem(self.graph.plaPl) # remove Plasma current plot
        
        # Plot line colors
        self.valuePlaPlot = self.graph.plaPl.plot(pen='#6ac600')
        self.valueTPlot = self.graph.tempPl.plot(pen='#5999ff')
        self.valueP1Plot = self.graph.presPl.plot(pen='#6ac600')
        self.valueP2Plot = self.graph.presPl.plot(pen='#c9004d')
        self.graph.tempPl.setXLink(self.graph.presPl)
        
        self.graph.presPl.setLogMode(y=True)
        self.graph.presPl.setYRange(-8,3,0)
        self.graph.tempPl.setYRange(0,320,0)

        self.tWorker = None
        self.presCurWorker = None

        make_datafolders()
        self.datapth = get_datafolderpth()[0]
       
        self.showMain()

    def __changeScale(self):
        """ select how much data to display """
        index = self.controlDock.scaleBtn.selectBtn.currentIndex()
        self.__scale = ScaleSize.getEnum(index)

    def __setConnects(self):
        self.controlDock.scaleBtn.selectBtn.currentIndexChanged.connect(self.__changeScale)
        
        self.registerDock.registerBtn.clicked.connect(self.registerTemp)
        self.controlDock.IGmode.currentIndexChanged.connect(self.updateIGmode)
        self.controlDock.IGrange.valueChanged.connect(self.updateIGrange)
        
        self.controlDock.FullNormSW.clicked.connect(self.fulltonormal)
        self.controlDock.OnOffSW.clicked.connect(self.__onoff)
        self.controlDock.quitBtn.clicked.connect(self.__quit)
        self.controlDock.qmsSigSw.clicked.connect(self.__qmsSignal)

        self.scaleDock.Pmin.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Pmax.valueChanged.connect(self.__updatePScale)
        self.scaleDock.Tmax.valueChanged.connect(self.__updateTScale)
        self.scaleDock.autoscale.clicked.connect(self.__autoscale)
        
    def __quit(self):
        """ terminate app """
        self.__app.quit()   
        
    def __onoff(self):
        """ prototype method to start and stop worker threads """
        if self.controlDock.OnOffSW.isChecked():
            self.startThreads()
            self.controlDock.quitBtn.setEnabled(False)
        else:
            quit_msg = "Are you sure you want to stop data acquisition?"
            reply = QtGui.QMessageBox.warning(
                self.MainWindow,
                'Message',
                quit_msg,
                QtGui.QMessageBox.Yes,
                QtGui.QMessageBox.No
            )
            if reply == QtGui.QMessageBox.Yes:                
                self.abortThreads()
                self.controlDock.quitBtn.setEnabled(True)
            else:
                self.controlDock.OnOffSW.setChecked(True)                

    def __updatePScale(self):
        """ Updated plot limits for the Pressure viewgraph """
        pmin,pmax = [self.scaleDock.Pmin.value(),self.scaleDock.Pmax.value()]

        #self.graph.presPl.setLogMode(y=True)
        if pmin < pmax:
            self.graph.presPl.setYRange(pmin,pmax,0)

    def __updateTScale(self):
        """ Updated plot limits for the Temperature viewgraph """
        tmax = self.scaleDock.Tmax.value()
        self.graph.tempPl.setYRange(0,tmax,0)

    def __autoscale(self):
        """ Set all plots to autoscale """
        self.graph.tempPl.enableAutoRange()
        self.graph.presPl.enableAutoRange()

    def fulltonormal(self):
       """ Change from full screen to normal view on click"""
       if self.controlDock.FullNormSW.isChecked():
           self.MainWindow.showFullScreen()
           self.controlDock.setStretch(*(10,300)) # minimize control dock width
       else:
           self.MainWindow.showNormal()
           self.controlDock.setStretch(*(10,300)) # minimize control dock width

    def __qmsSignal(self):
        """ qms signal """
        try:
            pi = pigpio.pi()
        except:
            print('pigpio is not defined')
            return

        if self.controlDock.qmsSigSw.isChecked():
            self.qmsSigThread = qmsSignal.QMSSignal(pi, self.__app, 1)
            self.qmsSigThread.finished.connect(self.qmsSigThFin)
            self.qmsSigThread.start()
            self.presCurWorker.setQmsSignal(1)
        else:
            quit_msg = "Are you sure you want to stop QMS?"
            reply = QtGui.QMessageBox.warning(
                self.MainWindow,
                'Message',
                quit_msg,
                QtGui.QMessageBox.Yes,
                QtGui.QMessageBox.No
            )
            if reply == QtGui.QMessageBox.Yes:
                self.qmsSigThread = qmsSignal.QMSSignal(pi, self.__app, 2)
                self.qmsSigThread.finished.connect(self.qmsSigThFin)
                self.qmsSigThread.start()
                self.presCurWorker.setQmsSignal(0)
            else:
                self.controlDock.qmsSigSw.setChecked(True)

    def qmsSigThFin(self):
        self.qmsSigThread.quit()
        self.qmsSigThread.wait()
    
    # MARK: - Threads
    def startThreads(self):
        self.logDock.log.append("starting 2 threads")

        self.__workers_done = 0

        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()

        self.__threads = []
        self.tWorker = Worker()
        self.presCurWorker = Worker()

        now = datetime.datetime.now()

        print("start threads: {}".format(now))
        self.logDock.progress.append("start threads: {}".format(now))

        for index, worker in enumerate([self.tWorker, self.presCurWorker]):
            thread = QtCore.QThread()
            thread.setObjectName("thread_{}".format(index))

            if index == 0:
                worker.setWorker(index, self.__app, ThreadType.TEMPERATURE, now)
                worker.setTempWorker(self.__temp)
            elif index == 1:
                worker.setWorker(index, self.__app, ThreadType.PRESSURE1, now)

                mode = self.controlDock.IGmode.currentIndex()
                scale = self.controlDock.IGrange.value()
                worker.setPresWorker(mode, scale)

            self.setThread(worker, thread, index)

    def setThread(self, worker: Worker, thread: QtCore.QThread, index: int):
        self.__threads.append((thread, worker))
        worker.moveToThread(thread)

        worker.sigStep.connect(self.onWorkerStep)
        worker.sigDone.connect(self.onWorkerDone)
        worker.sigMsg.connect(self.logDock.log.append)
        self.sigAbortWorkers.connect(worker.abort)

        # temperature
        if index == 0:
            df = pd.DataFrame(dtype=float, columns=["time", "T", "PresetT"])
            df.to_csv(
                os.path.join(
                    self.datapth,
                    f"out_{worker.getStartTime():%Y%m%d_%H%M%S}_temp.csv"
                ),
                index=False,
            )
        # pressures and current
        elif index == 1:
            df = pd.DataFrame(dtype=object, columns=["time", "P1", 'P2', 'Ip', 'IGmode', 'IGscale', 'QMS_signal'])
            df.to_csv(
                os.path.join(
                    self.datapth,
                    f"out_{worker.getStartTime():%Y%m%d_%H%M%S}.csv"
                ),
                index=False
            )
        else:
            return

        # creates file at the start, next data
        # in the loop is placed in another file
        # TODO: why not to save filename here, and reuse it later?

        thread.started.connect(worker.work)
        thread.start()

    currentvals = {ThreadType.PLASMA:0,ThreadType.TEMPERATURE:0,ThreadType.PRESSURE1:0,ThreadType.PRESSURE2:0}
    @QtCore.pyqtSlot(np.ndarray, np.ndarray, np.ndarray, ThreadType, datetime.datetime)
    def onWorkerStep(self, rawResult: np.ndarray, calcResult: np.ndarray,
                    ave: np.ndarray, ttype: ThreadType, startTime: datetime.datetime):
        """ collect data on worker step """
        # MEMO: ave [[theadtype, average], [], []]
        for l in ave:
            self.currentvals[l[0]] = l[1]
        """ set Bw text """
        temp_now = f"{self.currentvals[ThreadType.TEMPERATURE]:.0f}"
        self.registerDock.setTempText(self.__temp,temp_now)
#dd1451b
        txt = f"""
              <table>
                 <tr>
                  <td>
                  <font size=5 color="#6ac600">
                    Pd = {self.currentvals[ThreadType.PRESSURE1]:.1e}
                  </font>
                  </td>
                  <td>
                   <font size=5 color="#c9004d"> 
                    Pu = {self.currentvals[ThreadType.PRESSURE2]:.1e}
                   </font>
                  </td>
                 </tr>
                 <tr>
                  <td>
                   <font size=5 color="#6b32a8"> 
                    I = {self.currentvals[ThreadType.PLASMA]:.2f}
                   </font>
                  </td>
                 </tr>
                </table>
        """
        self.controlDock.valueBw.setText(txt) 
        self.controlDock.gaugeT.update_value(
            self.currentvals[ThreadType.TEMPERATURE]
        )

        scale = self.__scale.value
        MAX_SIZE = 20000
        if ttype == ThreadType.TEMPERATURE:
            # get data
            t_data = self.tData
            # set and save data
            self.tData = self.__setStepData(t_data, rawResult, calcResult, ttype, startTime)
            # plot data
            skip = int((self.tData.shape[0]+MAX_SIZE-1)/MAX_SIZE)
            self.valueTPlot.setData(self.tData[scale::skip, 0], self.tData[scale::skip, 1])
        elif ttype == ThreadType.PLASMA or ttype==ThreadType.PRESSURE1 or ttype==ThreadType.PRESSURE2:
            # get data
            pl_data = self.plaData
            p1_data = self.p1Data
            p2_data = self.p2Data
            # set and save data
            self.plaData = self.__setStepData(pl_data, rawResult, calcResult, ThreadType.PLASMA, startTime)
            self.p1Data = self.__setStepData(p1_data, rawResult, calcResult, ThreadType.PRESSURE1, startTime)
            self.p2Data = self.__setStepData(p2_data, rawResult, calcResult, ThreadType.PRESSURE2, startTime)
            # plot data
            skip = int((self.plaData.shape[0]+MAX_SIZE-1)/MAX_SIZE)
            self.valuePlaPlot.setData(self.plaData[scale::skip, 0], self.plaData[scale::skip, 1])
            self.valueP1Plot.setData(self.p1Data[scale::skip, 0], self.p1Data[scale::skip, 1])
            self.valueP2Plot.setData(self.p2Data[scale::skip, 0], self.p2Data[scale::skip, 1])
        else:
            return

    def __setStepData(self, data: np.ndarray, rawResult: np.ndarray,
                      calcResult: np.ndarray, ttype: ThreadType,
                      startTime: datetime.datetime):
        """ Append new data from Worker to main data arrays """
        # TODO: save interval
        self.__save(rawResult, ttype, startTime)
        if data is None:
            data = np.zeros([5, 2])
            data[:, 0] = calcResult[:, 0]
            data[:, 1] = calcResult[:, ttype.getIndex()]
        else:
            steps = calcResult.shape[0]
            calcData = np.zeros([steps, 2])
            calcData[:, 0] = calcResult[:, 0]
            calcData[:, 1] = calcResult[:, ttype.getIndex()]
            data = np.concatenate((data, np.array(calcData)))
        return data

    """ write csv """
    def __save(self, data: np.ndarray, ttype: ThreadType, startTime: datetime.datetime):
        if ttype == ThreadType.TEMPERATURE:
            df = pd.DataFrame(data)
            df.to_csv(
                os.path.join(
                    self.datapth,
                    f"out_{startTime:%Y%m%d_%H%M%S}_temp.csv"
                ),
                mode="a",
                header=False,
                index=False
            )
        elif ttype==ThreadType.PLASMA or ttype==ThreadType.PRESSURE1 or ttype==ThreadType.PRESSURE2:
            df = pd.DataFrame(data)
            df.to_csv(
                os.path.join(
                    self.datapth,
                    f"out_{startTime:%Y%m%d_%H%M%S}.csv"
                ),
                mode="a",
                header=False,
                index=False
            )

    @QtCore.pyqtSlot(int, ThreadType)
    def onWorkerDone(self, workerId: int, ttype: ThreadType):
        self.logDock.log.append("Worker #{} done".format(workerId))
        self.logDock.progress.append("-- Signal {} STOPPED".format(workerId))
        self.__workers_done += 1
        # reset Data
        if ttype == ThreadType.TEMPERATURE:
            self.tData = None
        elif ttype==ThreadType.PLASMA or ttype==ThreadType.PRESSURE1 or ttype==ThreadType.PRESSURE2:
            self.plaData = None
            self.p1Data = None
            self.p2Data = None

        if self.__workers_done == 2:
            # self.abortThreads()   # not necessary
            self.logDock.log.append("No more plot workers active")

    @QtCore.pyqtSlot()
    def abortThreads(self):
        self.sigAbortWorkers.emit()
        self.logDock.log.append("Asking each worker to abort")
        for thread, worker in self.__threads:
            thread.quit()
            thread.wait()
        self.logDock.log.append("All threads exited")

    # MARK: - Methods
    @QtCore.pyqtSlot()
    def registerTemp(self):
        value = self.registerDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvals[ThreadType.TEMPERATURE]
        self.registerDock.setTemp(self.__temp,f'{temp_now:.0f}')
        if self.tWorker is not None:
            self.tWorker.setPresetTemp(self.__temp)

    @QtCore.pyqtSlot()
    def updateIGmode(self):
        """ Update mode of the IG controller:
        Torr and linear
        or
        Pa and log
        """
        value = self.controlDock.IGmode.currentIndex()
        if self.tWorker is not None:
            self.presCurWorker.setIGmode(value)

    @QtCore.pyqtSlot()
    def updateIGrange(self):
        """ Update range of the IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        value = self.controlDock.IGrange.value()
        if self.tWorker is not None:
            self.presCurWorker.setIGrange(value)

if __name__ == "__main__":
    app = QtGui.QApplication([])
    widget = MainWidget(app)

    sys.exit(app.exec_())

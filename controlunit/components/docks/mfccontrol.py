import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets, QtGui
from pyqtgraph.dockarea import Dock

from readsettings import select_settings

config = select_settings(verbose=False)
MAXVOLTAGE = config["Max Voltage"]

class MassFlowControllerControl(Dock):
    def __init__(self):
        super().__init__("MFC control")
        self.widget = pg.LayoutWidget()
        self.mfcBw1 = QtWidgets.QTextBrowser()
        self.mfcBw1.setMinimumSize(QtCore.QSize(60, 50))
        self.mfcBw1.setMaximumHeight(60)

        self.mfcBw2 = QtWidgets.QTextBrowser()
        self.mfcBw2.setMinimumSize(QtCore.QSize(60, 50))
        self.mfcBw2.setMaximumHeight(60)

        
        self.masflowcontrolerSB1 = []
        for i in range(4):
            spin_box = QtWidgets.QSpinBox()
            spin_box.setMinimum(0)
            if i == 0:
                spin_box.setMaximum(MAXVOLTAGE)
            else:
                spin_box.setMaximum(9)
            spin_box.setSuffix(f"e{3-i}")
            spin_box.setMinimumSize(QtCore.QSize(80, 40))
            spin_box.setSingleStep(1)
            spin_box.setStyleSheet(
                "QSpinBox::up-button   { width: 35px; }\n"
                "QSpinBox::down-button { width: 35px;}\n"
                "QSpinBox {font: 16pt;}"
                )
            spin_box.setWrapping(True)
            self.masflowcontrolerSB1.append(spin_box)

        self.masflowcontrolerSB2 = []
        for i in range(4):
            spin_box = QtWidgets.QSpinBox()
            spin_box.setMinimum(0)
            if i == 0:
                spin_box.setMaximum(MAXVOLTAGE)
            else:
                spin_box.setMaximum(9)
            spin_box.setSuffix(f"e{3-i}")
            spin_box.setMinimumSize(QtCore.QSize(80, 40))
            spin_box.setSingleStep(1)
            spin_box.setStyleSheet(
                "QSpinBox::up-button   { width: 35px; }\n"
                "QSpinBox::down-button { width: 35px;}\n"
                "QSpinBox {font: 16pt;}"
                )
            spin_box.setWrapping(True)
            self.masflowcontrolerSB2.append(spin_box)


        self.registerBtn1 = QtWidgets.QPushButton("set")
        self.registerBtn1.setMinimumSize(QtCore.QSize(80, 50))
        self.registerBtn1.setStyleSheet("font: 20pt")

        self.registerBtn2 = QtWidgets.QPushButton("set")
        self.registerBtn2.setMinimumSize(QtCore.QSize(80, 50))
        self.registerBtn2.setStyleSheet("font: 20pt")

        self.resetBtn1 = QtWidgets.QPushButton("reset")
        self.resetBtn1.setMinimumSize(QtCore.QSize(80, 50))
        self.resetBtn1.setStyleSheet("font: 20pt")


        self.resetBtn2 = QtWidgets.QPushButton("reset")
        self.resetBtn2.setMinimumSize(QtCore.QSize(80, 50))
        self.resetBtn2.setStyleSheet("font: 20pt")

        self.scaleBtn = QtWidgets.QComboBox()
        self.scaleBtn.setFont(QtGui.QFont("serif", 18))
        items = ["1 s", "5 s", "10 s", "30 s", "1 min"]
        sizes = [1, 5, 10, 30, 60]
        [self.scaleBtn.addItem(i) for i in items]
        self.sampling_windows = {i: j for i, j in zip(items, sizes)}

        # self.calibrationBtn = QtWidgets.QPushButton("c\na\nl\ni\nb\nr\na\nt\ni\no\nn")
        self.calibrationBtn = QtWidgets.QPushButton("calib")
        # self.calibrationBtn.setMinimumSize(QtCore.QSize(30, 200))
        self.calibrationBtn.setMinimumSize(QtCore.QSize(60,50))
        self.calibrationBtn.setStyleSheet("font: 20pt")

        self.set_layout()

    def set_layout(self):
        self.addWidget(self.widget)

        self.widget.addWidget(self.mfcBw1, 0, 0, 1, 2)
        for i, spin_box in enumerate(self.masflowcontrolerSB1):
            self.widget.addWidget(spin_box, 1, i)

        self.widget.addWidget(self.registerBtn1, 0, 2, 1)

        self.widget.addWidget(self.resetBtn1, 0, 3, 1)

        self.widget.addWidget(self.mfcBw2, 2, 0, 1, 2)
        for i, spin_box in enumerate(self.masflowcontrolerSB2):
            self.widget.addWidget(spin_box, 3, i)

        self.widget.addWidget(self.registerBtn2, 2, 2)

        self.widget.addWidget(self.resetBtn2, 2, 3)

        self.widget.addWidget(self.scaleBtn, 4, 0,)

        self.widget.addWidget(self.calibrationBtn, 4, 1,)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        # self.widget.layout.setVerticalSpacing(0)
        self.widget.layout.addItem(self.verticalSpacer)

    def set_label_font(self, text: str, color: str):
        txt = "<font color={}><h4>{}</h4></font>".format(color, text)
        return txt

    def update_displayed_temperatures(self, temperature, temp_now):
        """ set values into browser"""
        htmltag = '<font size=6 color="#d1451b">'
        htag1 = '<font size=6 color = "#4275f5">'
        cf = "</font>"
        self.mfcBw1.setText(
            f"{htmltag}{temperature} mV{cf}"
            # f"&nbsp;&nbsp;&nbsp;{htag1}{temp_now} mV{cf}"
        )
        self.mfcBw2.setText(
            f"{htmltag}{temperature} mV{cf}"
            # f"&nbsp;&nbsp;&nbsp;{htag1}{temp_now} mV{cf}"
        )

    def update_displayed_voltage(self, voltage, mfc_num):
        """ set values into browser"""
        htmltag = '<font size=6 color="#d1451b">'
        htag1 = '<font size=6 color = "#4275f5">'
        cf = "</font>"
        if mfc_num == 1:
            self.mfcBw1.setText(
                f"{htmltag}{voltage} mV{cf}"
                # f"&nbsp;&nbsp;&nbsp;{htag1}{temp_now} mV{cf}"
            )
        elif mfc_num == 2:
            self.mfcBw2.setText(
                f"{htmltag}{voltage} mV{cf}"
                # f"&nbsp;&nbsp;&nbsp;{htag1}{temp_now} mV{cf}"
            )
        else:
            pass

    def update_displayed_voltage(self, voltage, voltage_now, mfc_num):
        """ set values into browser"""
        htmltag = '<font size=4 color="#d1451b">'
        htag1 = '<font size=4 color = "#4275f5">'
        cf = "</font>"
        if mfc_num == 1:
            self.mfcBw1.setText(
                f"{htmltag}{voltage} mV{cf}"
                f"&nbsp;&nbsp;&nbsp;{htag1}{voltage_now} mV{cf}"
            )
        elif mfc_num == 2:
            self.mfcBw2.setText(
                f"{htmltag}{voltage} mV{cf}"
                f"&nbsp;&nbsp;&nbsp;{htag1}{voltage_now} mV{cf}"
            )
        else:
            pass

    # def set_heating_goal(self, temperature: float, temp_now):
    #     self.update_displayed_temperatures(temperature, temp_now)
    #     self.masflowcontrolerSB1.setValue(temperature)
    #     self.masflowcontrolerSB2.setValue(temperature)

    def set_output1_goal(self, voltage,voltage_now):
        self.update_displayed_voltage(voltage, voltage_now,1)
    
    def set_output2_goal(self, voltage,voltage_now):
        self.update_displayed_voltage(voltage, voltage_now,2)



if __name__ == "__main__":
    pass
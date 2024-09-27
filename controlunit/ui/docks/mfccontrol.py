import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets, QtGui
from pyqtgraph.dockarea import Dock

from readsettings import select_settings

config = select_settings(verbose=False)
MAXVOLTAGE = int(config["Max Voltage"])


class MassFlowControllerControl(Dock):
    def __init__(self):
        super().__init__("Mass Flow Control")
        self.widget = pg.LayoutWidget()

        # Browser Widgets
        self.mfcBw1 = self._init_text_browser()
        self.mfcBw2 = self._init_text_browser()

        # Spin Boxes for Mass Flow Controller 1 and 2
        self.masflowcontrolerSB1 = self._init_spin_boxes(MAXVOLTAGE)
        self.masflowcontrolerSB2 = self._init_spin_boxes(MAXVOLTAGE)

        # Control Buttons
        self.registerBtn1 = self._init_button("set")
        self.registerBtn2 = self._init_button("set")
        self.resetBtn1 = self._init_button("reset")
        self.resetBtn2 = self._init_button("reset")
        self.calibrationBtn = self._init_button("calib", size=(60, 50))
        self.stopBtn = self._init_button("stop both", size=(120, 50))

        # Scale Selection
        self.scaleBtn = self._init_combo_box(
            ["1 s", "5 s", "10 s", "30 s", "1 min"], [1, 5, 10, 30, 60]
        )

        # Set layout
        self.set_layout()

    def _init_text_browser(self):
        browser = QtWidgets.QTextBrowser()
        browser.setMinimumSize(QtCore.QSize(60, 50))
        browser.setMaximumHeight(60)
        return browser

    def _init_spin_boxes(self, max_voltage):
        spin_boxes = []
        for i in range(4):
            spin_box = QtWidgets.QSpinBox()
            spin_box.setMinimum(0)
            spin_box.setMaximum(max_voltage if i == 0 else 9)
            spin_box.setSuffix(f"e{3-i}")
            spin_box.setMinimumSize(QtCore.QSize(80, 40))
            spin_box.setSingleStep(1)
            spin_box.setStyleSheet(
                "QSpinBox::up-button { width: 35px; }"
                "QSpinBox::down-button { width: 35px; }"
                "QSpinBox { font: 16pt; }"
            )
            spin_box.setWrapping(True)
            spin_boxes.append(spin_box)
        return spin_boxes

    def _init_button(self, label, size=(80, 50)):
        button = QtWidgets.QPushButton(label)
        button.setMinimumSize(QtCore.QSize(*size))
        button.setStyleSheet("font: 20pt")
        return button

    def _init_combo_box(self, items, sizes):
        combo_box = QtWidgets.QComboBox()
        combo_box.setFont(QtGui.QFont("serif", 18))
        [combo_box.addItem(i) for i in items]
        self.sampling_windows = {i: j for i, j in zip(items, sizes)}
        return combo_box

    def set_layout(self):
        self.addWidget(self.widget)

        # Layout for the first set of controls
        self.widget.addWidget(self.mfcBw1, 0, 0, 1, 2)
        for i, spin_box in enumerate(self.masflowcontrolerSB1):
            self.widget.addWidget(spin_box, 1, i)
        self.widget.addWidget(self.registerBtn1, 0, 2)
        self.widget.addWidget(self.resetBtn1, 0, 3)

        # Layout for the second set of controls
        self.widget.addWidget(self.mfcBw2, 2, 0, 1, 2)
        for i, spin_box in enumerate(self.masflowcontrolerSB2):
            self.widget.addWidget(spin_box, 3, i)
        self.widget.addWidget(self.registerBtn2, 2, 2)
        self.widget.addWidget(self.resetBtn2, 2, 3)

        # Bottom row of controls
        self.widget.addWidget(self.scaleBtn, 4, 0)
        self.widget.addWidget(self.calibrationBtn, 4, 1)
        self.widget.addWidget(self.stopBtn, 4, 2, 1, 2)

        # Spacer to adjust layout
        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.addItem(self.verticalSpacer)

    def update_current_values(self, set_voltage, signal_voltage, mfc_num):
        """
        Set Mass Flow Controllers signal values in the browsers.
        """
        htag0 = '<font size=4 color="#d1451b">'
        htag1 = '<font size=4 color = "#4275f5">'
        cf = "</font>"
        text = f"{htag0}{set_voltage} mV{cf}&nbsp;&nbsp;&nbsp;{htag1}{signal_voltage} mV{cf}"
        if mfc_num == 1:
            self.mfcBw1.setText(f"{text}&nbsp;H")
        elif mfc_num == 2:
            self.mfcBw2.setText(f"{text}&nbsp;O")

    def set_output1_goal(self, voltage, voltage_now):
        self.update_current_values(voltage, voltage_now, 1)

    def set_output2_goal(self, voltage, voltage_now):
        self.update_current_values(voltage, voltage_now, 2)


if __name__ == "__main__":
    pass

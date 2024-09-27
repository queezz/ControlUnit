import pyqtgraph as pg
from PyQt5 import QtGui, QtCore, QtWidgets
from pyqtgraph.dockarea import Dock
from ..buttons.toggles import MySwitch, OnOffSwitch, QmsSwitch
from ..widgets.analoggauge import AnalogGaugeWidget
from readsettings import select_settings

config = select_settings(verbose=False)
MAXTEMP = config["Max Voltage"]


class ControlDock(Dock):
    def __init__(self):
        super().__init__("Control")
        self.widget = pg.LayoutWidget()

        self.__setLayout()

    def __setLayout(self):
        """Set the layout of the ControlDock."""
        self.addWidget(self.widget)

        self._init_buttons()
        self._init_text_browsers()
        self._init_comboboxes()
        self._init_spinboxes()
        self._init_switches()

        self._add_main_widgets()
        self._add_vertical_spacer()

    def _add_vertical_spacer(self):
        """Add vertical spacer"""
        self.verticalSpacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.widget.layout.setVerticalSpacing(3)
        self.widget.layout.addItem(self.verticalSpacer)

    def _init_buttons(self):
        """Initialize buttons."""
        self.quitBtn = QtWidgets.QPushButton("quit")
        self.quitBtn.setStyleSheet(
            "QPushButton {color:#f9ffd9; background:#ed2a0c;}"
            "QPushButton:disabled {color:#8f8f8f; background:#bfbfbf;}"
        )
        self.quitBtn.setFont(QtGui.QFont("serif", 16))

    # MARK: browser
    def _init_text_browsers(self):
        """Initialize text browsers."""
        self.valueBw = QtWidgets.QTextBrowser()
        self.valueBw.setMaximumHeight(100)
        self.valueBw.setMinimumWidth(400)
        self.valueBw.setCurrentFont(QtGui.QFont("Courier New"))

    def _init_comboboxes(self):
        """Initialize comboboxes."""
        # Scale buttons
        self.scaleBtn = QtWidgets.QComboBox()
        self.scaleBtn.setFont(QtGui.QFont("serif", 18))
        items = [
            "20 s",
            "60 sec",
            "5 min",
            "15 min",
            "30 min",
            "1 hr",
            "1.5 hr",
            "2 hr",
            "Full",
        ]
        sizes = [20, 60, 5 * 60, 15 * 60, 30 * 60, 60 * 60, 90 * 60, 120 * 60, -1]
        [self.scaleBtn.addItem(i) for i in items]
        self.sampling_windows = {i: j for i, j in zip(items, sizes)}

        # IG mode
        self.IGmode = QtWidgets.QComboBox()
        items = ["Torr", "Pa"]
        [self.IGmode.addItem(i) for i in items]
        self.IGmode.setFont(QtGui.QFont("serif", 18))

    def _init_spinboxes(self):
        """Initialize spinboxes."""
        self.IGrange = QtWidgets.QSpinBox()
        self.IGrange.setMinimum(-8)
        self.IGrange.setMaximum(-3)
        self.IGrange.setMinimumSize(QtCore.QSize(60, 60))
        self.IGrange.setSingleStep(1)
        self.IGrange.setStyleSheet(
            "QSpinBox::up-button   { width: 40px; }\n"
            "QSpinBox::down-button { width: 40px;}\n"
            "QSpinBox {font: 26pt;}"
        )

    def _init_switches(self):
        """Initialize switches."""
        self.qmsSigSw = QmsSwitch()
        self.FullNormSW = MySwitch()
        self.OnOffSW = OnOffSwitch()
        self.OnOffSW.setFont(QtGui.QFont("serif", 16))

    def _add_main_widgets(self):
        """Add widgets to the layout"""
        self.widget.addWidget(self.OnOffSW, 0, 0, 1, 2)
        self.widget.addWidget(self.qmsSigSw, 0, 2, 1, 2)
        self.widget.addWidget(self.quitBtn, 0, 4, 1, 2)
        self.widget.addWidget(self.valueBw, 1, 0, 1, 6)
        self.widget.addWidget(self.FullNormSW, 2, 0, 1, 2)
        self.widget.addWidget(self.scaleBtn, 2, 2)
        self.widget.addWidget(self.IGmode, 2, 3, 1, 2)
        self.widget.addWidget(self.IGrange, 2, 5)

    def __init_analog_gauge(self):
        """Initialize the analog gauge (removed from GUI)."""
        self.gaugeT = AnalogGaugeWidget()
        self.gaugeT.set_MinValue(0)
        self.gaugeT.set_MaxValue(MAXTEMP)
        self.gaugeT.set_total_scale_angle_size(180)
        self.gaugeT.set_start_scale_angle(180)
        self.gaugeT.set_enable_value_text(False)

    # MARK: suppimentary
    def __add_analouge_gauge(self):
        """Temperature analouge gauge"""
        self.widget.addWidget(self.gaugeT, 5, 0, 10, 1)

    def __init_current_control(self):
        """Initialize the current control section."""
        self.currentBw = QtWidgets.QTextBrowser()
        self.currentBw.setMinimumSize(QtCore.QSize(60, 50))
        self.currentBw.setMaximumHeight(60)

        self.currentcontrolerSB = QtWidgets.QSpinBox()
        self.currentcontrolerSB.setSuffix(f"mV")
        self.currentcontrolerSB.setMinimum(0)
        self.currentcontrolerSB.setMaximum(500)
        self.currentcontrolerSB.setMinimumSize(QtCore.QSize(60, 50))
        self.currentcontrolerSB.setSingleStep(10)
        self.currentcontrolerSB.setStyleSheet(
            "QSpinBox::up-button   { width: 40px; }\n"
            "QSpinBox::down-button { width: 40px;}\n"
            "QSpinBox {font: 26pt;}"
        )

        self.currentsetBtn = QtWidgets.QPushButton("set")
        self.currentsetBtn.setMinimumSize(QtCore.QSize(60, 50))
        self.currentsetBtn.setStyleSheet("font: 20pt")

    def __add_current_cotrols(self):
        self.widget.addWidget(self.currentBw, 3, 0, 1, 4)
        self.widget.addWidget(self.currentcontrolerSB, 3, 0, 1, 3)
        self.widget.addWidget(self.currentsetBtn, 3, 3, 1, 2)

    # MARK: Update Values
    def update_current_values(self, values: list[tuple[str, float]]):
        """Update current values displayed in the browser with passed values.

        Args:
            values: List of tuples containing pen color (str) and value (float).
                    Example: [("red", 1.23), ("green", 2.34), ("blue", 3.45)]
        """
        font_size = 5
        padding = "1px"  # Set your desired padding here
        cell_width = "10px"  # Set your desired cell width here

        # Generate table cells with padding and fixed width
        table_cells = [
            f'<td style="padding:{padding};width:{cell_width};">'
            f'<font size="{font_size}" color="{pen}">{label} = {val:.2e}</font></td>'
            for pen, label, val in values
        ]

        # Split cells into rows of 3 columns each
        table_rows = [
            f"""
            <tr>
                {''.join(table_cells[i:i+3])}
            </tr>
            """
            for i in range(0, len(table_cells), 3)
        ]

        # Concatenate the rows into a table structure
        txt = f"""
            <table>
                {"".join(table_rows)}
            </table>
        """

        self.valueBw.setText(txt)


if __name__ == "__main__":
    pass

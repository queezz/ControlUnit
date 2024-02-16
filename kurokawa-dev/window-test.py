import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget

class GraphWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout()
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)

        self.toggle_button = QPushButton('Toggle Plot')
        self.toggle_button.clicked.connect(self.toggle_plot)
        layout.addWidget(self.toggle_button)

        self.central_widget.setLayout(layout)

        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_curve = self.plot_item.plot()

        self.plot_visible = True

    def toggle_plot(self):
        if self.plot_visible:
            self.plot_item.removeItem(self.plot_curve)
        else:
            self.plot_item.addItem(self.plot_curve)

        self.plot_visible = not self.plot_visible

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = GraphWindow()
    window.show()
    sys.exit(app.exec_())

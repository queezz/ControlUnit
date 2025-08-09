"""
Class for core logic in main.py
TODO: move signal connection from main.py here
Currently, this is an example.
"""

from PyQt5 import QtCore


class CoreLogic(QtCore.QObject):
    plot_update_signal = QtCore.pyqtSignal(object)  # To send data to the plot

    def __init__(self):
        super().__init__()

    def connect_signals(self, adc_worker, graph):
        # Connect ADC data_ready signal to CoreLogic's plot_update_signal
        adc_worker.data_ready.connect(self.plot_update_signal)

        # Connect CoreLogic's plot_update_signal to the Graph's update method
        self.plot_update_signal.connect(graph.update_plot)

    def start_device(self, device):
        # Example of starting a device
        device.start_operation()

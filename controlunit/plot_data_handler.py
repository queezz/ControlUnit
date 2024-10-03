"""
This class will handle plotting.
TODO: move plotting logic from main.py here
"""

import pandas as pd
from PyQt5 import QtCore


class PlotDataHandler(QtCore.QObject):
    def __init__(self, adc_instance, graph_instance):
        self.adc = adc_instance
        self.graph = graph_instance
        self.data_buffer = pd.DataFrame()  # In-memory buffer

        # Connect ADC signals to update the plot
        self.adc.data_ready.connect(self.on_data_ready)

    def on_data_ready(self, new_data):
        # Append new data to the buffer
        self.data_buffer = pd.concat([self.data_buffer, new_data], ignore_index=True)
        self.update_graph()

    def update_graph(self):
        # Optionally filter or process the data before plotting
        if not self.data_buffer.empty:
            self.graph.update_plot(self.data_buffer)

    def request_data(self, start_time, end_time):
        # Fetch and filter data based on time range
        filtered_data = self.data_buffer[
            (self.data_buffer["Time"] >= start_time)
            & (self.data_buffer["Time"] <= end_time)
        ]
        self.graph.update_plot(filtered_data)

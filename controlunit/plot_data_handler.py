"""
This class will handle plotting.
TODO: move plotting logic from main.py here
"""

from datetime import timedelta
import pandas as pd
from PyQt5 import QtCore


class PlotDataHandler(QtCore.QObject):
    def __init__(self, adc_instance, graph_instance):
        self.adc = adc_instance
        self.graph = graph_instance
        self.data_buffer = pd.DataFrame()  # In-memory buffer

        # Connect ADC signals to update the plot
        self.adc.data_ready.connect(self.on_data_ready)

    def update_plots(self, device_name):
        """plot updater abstraction"""
        self.plot_methods[device_name]()

    def update_plots_max6675(self):
        """
        MAX6675 data: update plots
        """
        df = self.select_data_to_plot("MAX6675")
        time = df["time"].values.astype(float)
        temperature = df["T"].values.astype(float)
        skip = self.calculate_skip_points(time.shape[0])
        self.graph.valueTPlot.setData(time[::skip], temperature[::skip])

    def update_plots_adc(self):
        """
        Update plots for ADC dataframe
        """
        df = self.select_data_to_plot("ADC")
        # time = df["time"].values.astype(float)
        utc_offset = 9
        time = (
            df["date"]
            .apply(lambda x: (x - timedelta(hours=utc_offset)).timestamp())
            .values
        )
        skip = self.calculate_skip_points(time.shape[0])

        what_to_plot = ["Ip", "Pu", "Pd", "Bu", "Bd"]
        for name in what_to_plot:
            if name == "Ip":
                values = (
                    df[name + "_c"].values.astype(float) - self.zero_adjustment["Ip"]
                )
            else:
                values = df[name + "_c"].values.astype(float)

            self.graph.plot_lines[name].setData(time[::skip], values[::skip])

    def select_data_to_plot(self, device_name):
        """
        Select data based on self.time_window
        """
        df = self.datadict[device_name]
        if self.time_window > 0:
            last_ts = df["date"].iloc[-1]
            timewindow = last_ts - pd.Timedelta(self.time_window, "seconds")
            df = df[df["date"] > timewindow]
        return self.downsample_data(df)

    def downsample_data(self, df, noskip=3000):
        """downsample data"""
        if df.shape[0] > noskip:
            return df.iloc[:: df.shape[0] // noskip + 1]
        return df

    def calculate_skip_points(self, l, noskip=5000):
        return 1 if l < noskip else l // noskip + 1

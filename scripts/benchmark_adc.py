"""Off-device ADC software benchmark; excludes I2C, CSV I/O and Qt rendering.

Run with the shared hardware-dev Python. Optional --output writes JSON.
Hardware-capable environments are refused before device modules are imported.
"""

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace


def measure(function, repeats):
    durations = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        durations.append((time.perf_counter() - started) * 1000)
    return {"median_ms": statistics.median(durations),
            "p95_ms": sorted(durations)[int(.95 * (repeats - 1))]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for library in ("smbus", "pigpio", "spidev", "RPi"):
        if importlib.util.find_spec(library) is not None:
            parser.error(f"Off-device only: {library} is installed")
    with tempfile.TemporaryDirectory(prefix="controlunit-adc-benchmark-") as home:
        for name in ("HOME", "USERPROFILE", "CONTROLUNIT_SETTINGS_HOME"):
            os.environ[name] = home
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from PyQt5.QtWidgets import QApplication
        from controlunit.devices.adc import ADC
        from controlunit.main import MainApp
        from controlunit.web.status import dummy_hardware_loaded
        import pandas as pd
        import readsettings

        assert dummy_hardware_loaded(), "Off-device benchmark only"
        app = QApplication([])
        worker = ADC("ADC", app, datetime.datetime.now(),
                     readsettings.init_configuration(), None)
        worker.hold_voltages({name: .5 for name in worker.adc_signals_columns})
        latest = []
        worker.data_ready.connect(lambda result: latest.__setitem__(slice(None), [result[0]]))

        def rows():
            for _ in range(3):
                worker.put_new_data_in_dataframe()
                worker.update_processed_signals_dataframe()
            worker.send_processed_data_to_main_thread()

        results = {"environment": {"python": platform.python_version(),
                                   "platform": platform.platform(), "pandas": pd.__version__},
                   "workload": "Three-row batches; 10 Hz synthetic history; 300 s plot window; no I2C, disk or rendering",
                   "row_batch_3": measure(rows, 200)}
        batch = latest[0]
        for size in (1000, 20000, 100000):
            history = pd.concat([batch] * (size // 3 + 1), ignore_index=True).iloc[:size].copy()
            history["date"] = pd.date_range("2026-09-10 18:00", periods=size, freq="100ms")
            fresh = batch.copy()
            fresh["date"] = pd.date_range(history["date"].iloc[-1] + pd.Timedelta("100ms"), periods=3, freq="100ms")
            host = SimpleNamespace(
                datadict={"ADC": history}, newdata={"ADC": fresh},
                time_window=300, zero_adjustment={},
                graph=SimpleNamespace(plot_lines={name: SimpleNamespace(setData=lambda *args: None)
                                                 for name in ("Ip", "Pu", "Pd", "Bu", "Bd")}),
            )
            for name in ("downsample_data", "select_data_to_plot", "calculate_skip_points"):
                setattr(host, name, getattr(MainApp, name).__get__(host))

            def append():
                host.datadict["ADC"] = history
                MainApp.append_data(host, "ADC")

            results[str(size)] = {"append": measure(append, 50),
                                  "plot": measure(lambda: MainApp.update_plots_adc(host), 50)}
        output = json.dumps(results, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()

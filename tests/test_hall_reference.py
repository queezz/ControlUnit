"""Supply correction removes common supply drift without hiding raw readings."""
import math

import pytest

from controlunit.devices.adc_channels import AdcChannelProps
from test_adc_average import qt_app, home, worker


@pytest.mark.parametrize("supply", [4.5, 4.9, 5.0, 5.3])
@pytest.mark.parametrize("current", [-1.0, 0.0, 0.8, 2.0])
def test_current_is_independent_of_supply(worker, supply, current):
    values = dict.fromkeys(worker.adc_signals_columns, 0.1)
    values.update(Ip=supply * (0.5 + current / 25), Vhall=supply)
    worker.hold_voltages(values)
    worker.put_new_data_in_dataframe()
    # A later scan must not change the conversion of the already captured row.
    worker.adc_voltages = dict(values, Vhall=5.8)
    worker.update_processed_signals_dataframe()
    assert worker.plasma_current_converted == pytest.approx(current)
    assert worker.converted_values.iloc[-1]["Ip_c"] == pytest.approx(current)
    assert worker.adc_values.iloc[-1]["Ip"] == values["Ip"]
    assert worker.adc_values.iloc[-1]["Vhall"] == supply


@pytest.mark.parametrize("supply", [0, -1, 0.01, 3.9, 6.1, float("nan"), float("inf")])
def test_invalid_reference_is_recorded_and_never_sent_to_pid(worker, supply):
    messages = []
    commands = []
    worker.send_message.connect(messages.append)
    worker.send_control_voltage.connect(commands.append)
    values = dict.fromkeys(worker.adc_signals_columns, 0.1)
    values.update(Ip=2.5, Vhall=supply)
    worker.hold_voltages(values)
    worker.put_new_data_in_dataframe()
    worker.update_processed_signals_dataframe()
    worker.plasma_current_control()  # no PID instance: must not call it
    assert math.isnan(worker.converted_values.iloc[-1]["Ip_c"])
    assert commands == []
    worker.hold_voltages(values)
    assert len(messages) == 1
    worker.hold_voltages(dict(values, Vhall=5.0))
    assert worker.plasma_current_converted == pytest.approx(0)
    assert "recovered" in messages[-1]


def test_legacy_settings_keep_the_original_conversion():
    channel = AdcChannelProps("Ip", Channel=0, Gain=5, Description="Current",
                              **{"Conversion Function": "Hall Sensor"})
    assert channel.convert_hall({"Ip": 2.52}) == pytest.approx(0)
    assert channel.convert_hall({"Ip": 2.72}) == pytest.approx(1)


def test_missing_reference_does_not_reuse_previous_sample(worker):
    worker.hold_voltages({"Ip": 2.5, "Vhall": 5.0})
    worker.hold_voltages({"Ip": 2.5})
    assert math.isnan(worker.plasma_current_converted)

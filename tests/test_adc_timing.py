"""Acquisition deadlines, data integrity, and diagnostics without hardware."""

import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from controlunit.devices import adc as adc_module
from controlunit.devices import adc_setter
from controlunit.devices.timing import SampleClock, TimingDiagnostics
from test_adc_average import qt_app, home, worker  # shared isolated real worker


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run_clocked(worker, monkeypatch, read_times, period=0.1, process=0.02):
    clock = Clock()
    monkeypatch.setattr(adc_module, 'time', clock)
    worker.set_sampling_time(period)
    worker.pause = lambda seconds: (clock.sleep(seconds) or not worker._abort)
    stamps, sent = [], []
    worker.data_ready.connect(lambda result: sent.append(result[0]))
    original = worker.put_new_data_in_dataframe

    def collect():
        clock.sleep(read_times[len(stamps)])
        worker.hold_voltages({name: 0.5 for name in worker.adc_signals_columns})
        return True

    def put():
        stamps.append(clock.monotonic())
        original()
        clock.sleep(process)
        if len(stamps) == len(read_times):
            worker._abort = True

    worker.collect_data = collect
    worker.put_new_data_in_dataframe = put
    worker.acquisition_loop()
    return stamps, sent


def test_work_time_comes_out_of_the_next_wait(worker, monkeypatch):
    stamps, batches = run_clocked(worker, monkeypatch, [0.02] * 7)
    assert stamps == pytest.approx([0.12 + i * 0.1 for i in range(7)])
    assert [len(batch) for batch in batches] == [3, 3, 1]
    assert sum(map(len, batches)) == 7  # final completed row survives Stop


def test_a_slow_read_does_not_trigger_a_catch_up_burst(worker, monkeypatch):
    stamps, batches = run_clocked(worker, monkeypatch, [0.02, 0.45, 0.02, 0.02])
    assert stamps == pytest.approx([0.12, 0.65, 0.79, 0.89])
    assert sum(map(len, batches)) == 4  # no fabricated rows for missed slots


def test_retiming_resets_the_deadline(worker, monkeypatch):
    original = worker.set_sampling_time
    # Change after the first emitted batch: neither duplicate rows nor a
    # stale old deadline should stretch the next period.
    worker.data_ready.connect(lambda _: original(0.2))
    stamps, _ = run_clocked(worker, monkeypatch, [0.02] * 4)
    assert stamps == pytest.approx([0.12, 0.22, 0.32, 0.56])


def test_elapsed_time_bounds_a_stuck_converter_even_with_slow_bus_calls(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(adc_setter, 'time', clock)

    class SlowBus:
        calls = 0

        def write_word_data(self, *args):
            pass

        def read_byte_data(self, *args):
            self.calls += 1
            clock.sleep(0.02)
            return 0

    chip = adc_setter.ADS1115(0x49)
    chip.i2c = SlowBus()
    with pytest.raises(TimeoutError):
        chip.analog_read(4, 7, 2)
    assert chip.i2c.calls == 3
    assert 0.05 <= clock.now < 0.08


@pytest.mark.parametrize('rate', [0, 7])
def test_busy_then_ready_reads_one_signed_result_without_changing_wire_format(monkeypatch, rate):
    clock = Clock()
    monkeypatch.setattr(adc_setter, 'time', clock)
    writes = []

    class Bus:
        def write_word_data(self, *args):
            writes.append(args)

        def read_byte_data(self, *args):
            return 0x80 if clock.now >= 1 / adc_setter.ADS1115.RATES[rate] else 0

        def write_byte_data(self, *args):
            writes.append(args)

        def read_word_data(self, *args):
            return 0x0080  # SMBus little-endian word, ADC signed -32768

    chip = adc_setter.ADS1115(0x49)
    chip.i2c = Bus()
    assert chip.analog_read(4, rate, 2) == -32768
    assert writes[0] == (0x49, 1, rate << 13 | 3 << 8 | 1 << 7 | 4 << 4 | 2 << 1 | 1)
    assert writes[1] == (0x49, 0, 1)


def test_batch_is_typed_detached_and_uses_captured_gauge_metadata(worker):
    from controlunit.devices.conversions import ionization_gauge
    worker.adc_channels['Pu'].conversion = ionization_gauge
    captured = []
    worker.data_ready.connect(lambda result: captured.append(result[0]))
    worker.hold_voltages({name: 0.5 for name in worker.adc_signals_columns})
    worker.set_ig_mode(0)
    worker.set_ig_range(-3)
    worker.put_new_data_in_dataframe()
    worker.set_ig_range(-7)  # arrives between row capture and conversion
    worker.update_processed_signals_dataframe()
    expected = worker.adc_channels['Pu'].conversion(0.5, 0, -3)
    worker.send_processed_data_to_main_thread()
    row = captured[0]
    assert row['Pu_c'].iloc[0] == pytest.approx(expected)
    assert row['IGscale'].iloc[0] == -3
    assert list(row.columns) == worker.config['ADC Column Names']
    assert pd.api.types.is_datetime64_any_dtype(row['date'])
    assert all(pd.api.types.is_numeric_dtype(row[c]) for c in row.columns if c != 'date')
    worker.clear_datasets()
    assert len(row) == 1
    assert row.attrs['adc_emitted_at'] > 0


def test_empty_history_preserves_typed_batches_and_plot_time_values():
    from controlunit.main import MainApp
    dates = pd.date_range('2026-09-10 19:00:00.123456', periods=3, freq='100ms')
    batch = pd.DataFrame({'date': dates, 'Ip_c': [1., 2., 3.]})
    for name in ('Pu', 'Pd', 'Bu', 'Bd'):
        batch[name + '_c'] = batch['Ip_c']
    plotted = {}
    host = SimpleNamespace(
        datadict={'ADC': pd.DataFrame(columns=batch.columns)}, newdata={'ADC': batch},
        zero_adjustment={'Ip': 0.25},
        graph=SimpleNamespace(plot_lines={name: SimpleNamespace(
            setData=lambda x, y, name=name: plotted.update({name: (x, y)})
        ) for name in ('Ip', 'Pu', 'Pd', 'Bu', 'Bd')}),
    )
    MainApp.append_data(host, 'ADC')
    MainApp.append_data(host, 'ADC')
    assert pd.api.types.is_float_dtype(host.datadict['ADC']['Ip_c'])
    host.select_data_to_plot = lambda _: batch
    host.calculate_skip_points = lambda _: 1
    MainApp.update_plots_adc(host)
    expected = [(stamp - datetime.timedelta(hours=9)).timestamp() for stamp in dates]
    assert plotted['Ip'][0] == pytest.approx(expected, abs=1e-6, rel=0)
    assert plotted['Ip'][1] == pytest.approx([0.75, 1.75, 2.75])


def test_timing_reports_slow_successes_without_flooding_the_log():
    clock, messages = Clock(), []
    report = TimingDiagnostics('ADC timing', messages.append, clock.monotonic)
    for _ in range(100):
        clock.sleep(0.1)
        report.observe({'read': 0.08}, slow=True, missed=1, channel=('Ip', 0.07))
    assert len(messages) == 1
    assert 'overrun' in messages[0] and 'slowest channel Ip' in messages[0]
    clock.sleep(30)
    report.observe({'read': 0.01})
    assert len(messages) == 2
    assert 'missed slots 99' in messages[-1]
    report.report()
    assert len(messages) == 2  # empty windows do not log


def test_sample_clock_counts_missed_slots_and_keeps_a_future_deadline():
    clock = SampleClock(0.1, 0.0)
    assert clock.advance(0.65) == 5
    assert clock.due == pytest.approx(0.75)


def test_averaged_windows_include_processing_cost(worker, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(adc_module, 'time', clock)
    worker.set_sampling_time(1.0)
    worker.pause = lambda seconds: (clock.sleep(seconds) or not worker._abort)
    stamps, batches = [], []
    original = worker.put_new_data_in_dataframe

    def collect():
        clock.sleep(0.02)
        worker.hold_voltages({name: 0.5 for name in worker.adc_signals_columns})
        return True

    def put():
        stamps.append(clock.now)
        original()
        clock.sleep(0.08)
        if len(stamps) == 3:
            worker._abort = True

    worker.collect_data = collect
    worker.put_new_data_in_dataframe = put
    worker.data_ready.connect(lambda result: batches.append(result[0]))
    worker.acquisition_loop()
    assert stamps == pytest.approx([1.0, 2.0, 3.0])
    assert [len(batch) for batch in batches] == [1, 1, 1]


def test_abort_between_channels_discards_partial_scan(worker):
    calls = []

    def read(*args, **kwargs):
        calls.append(args)
        worker.abort()
        return 0.5

    worker.aio.analog_read_volt = read
    worker.set_adc_datarate()
    assert worker.collect_data() is False
    assert len(calls) == 1
    assert not worker._raw_rows

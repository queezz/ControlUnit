"""Slow sampling records the mean of a period, not one instant of it.

At the rig's ten-second overnight setting the reader used to take a single
~1 ms conversion per period, so the file recorded whatever noise sat on the
line at that instant. From one second upwards it now converts every
`INNER_SECONDS` through the period and records their mean (owner decision
2026-09-07: "we don't care about transients in 0.1 Hz, just an
overnight/overweekend log. So averages are cheap and good").

Below one second nothing changed, and these tests hold that too. The loop is
driven here in the test's own thread with a stubbed `collect_data`, so no
hardware and no Qt thread is involved. Nothing here touches the rig.
"""

import datetime
import os
import time

import pytest

# Before PyQt is imported by anything: these tests draw no window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit.devices import adc as adc_module  # noqa: E402
from controlunit.devices.adc import mean_of_readings  # noqa: E402


# MARK: the pure helper


def test_the_mean_is_taken_per_channel():
    readings = [
        {"Ip": 1.0, "Pu": 10.0},
        {"Ip": 2.0, "Pu": 20.0},
        {"Ip": 3.0, "Pu": 30.0},
    ]
    assert mean_of_readings(readings) == {"Ip": 2.0, "Pu": 20.0}


def test_one_reading_averages_to_itself():
    only = {"Ip": 0.125, "Pu": -3.5}
    assert mean_of_readings([only]) == only


def test_the_mean_keeps_the_channel_order_the_row_is_built_from():
    """`put_new_data_in_dataframe` writes `adc_voltages.values()` positionally."""
    readings = [{"c": 1.0, "a": 2.0, "b": 3.0}, {"c": 3.0, "a": 4.0, "b": 5.0}]
    assert list(mean_of_readings(readings)) == ["c", "a", "b"]


def test_an_empty_period_has_no_sample_to_offer():
    """The chosen answer for an empty list is None, not an exception."""
    assert mean_of_readings([]) is None


# MARK: a worker to drive


@pytest.fixture(scope="module")
def qt_app():
    """One QApplication for the module; Qt allows exactly one per process."""
    QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
    existing = QtWidgets.QApplication.instance()
    if existing is not None:
        return existing
    try:
        return QtWidgets.QApplication([])
    except Exception as error:  # a machine with no usable Qt platform
        pytest.skip("no Qt platform available: {}".format(error))


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home of this test's own: no data folder lands in the owner's."""
    place = tmp_path / "home"
    place.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(place))
    monkeypatch.setenv("HOMEDRIVE", "")
    monkeypatch.setenv("HOMEPATH", "")
    assert os.path.expanduser("~") == str(place)
    return place


@pytest.fixture
def worker(qt_app, home):
    """A real ADC worker on the dummy board, with nothing connected to it."""
    import readsettings

    config = readsettings.init_configuration()
    return adc_module.ADC("ADC", qt_app, datetime.datetime.now(), config, None)


class Driver:
    """A stub ADC in front of a real worker's loop.

    `collect_data` is replaced by a counter that hands out a fresh, distinct
    set of voltages each time, so the mean of a period is a number no single
    reading in it equals. Every recorded row is captured with the count of
    inner readings that stood behind it, and the loop stops itself after
    `periods` rows.
    """

    def __init__(self, worker, periods):
        self.worker = worker
        self.periods = periods
        self.readings = []
        self.rows = []
        self.sent = []
        self.channels = list(worker.adc_channels)
        self._put = worker.put_new_data_in_dataframe
        self._send = worker.send_processed_data_to_main_thread
        worker.collect_data = self.collect
        worker.put_new_data_in_dataframe = self.put
        worker.send_processed_data_to_main_thread = self.send
        self.on_reading = None

    def collect(self):
        step = len(self.readings) + 1
        voltages = {
            name: 0.1 * step + 0.001 * index
            for index, name in enumerate(self.channels)
        }
        self.worker.hold_voltages(voltages)
        self.readings.append(dict(voltages))
        if self.on_reading is not None:
            self.on_reading(self)
        # The real `collect_data` answers True for a reading and False for an
        # abort while waiting on a board that does not answer.
        return True

    def put(self):
        self.rows.append((dict(self.worker.adc_voltages), len(self.readings)))
        self._put()
        if len(self.rows) >= self.periods:
            self.worker._abort = True

    def send(self):
        # Snapshot before the worker clears its buffers on the way out.
        self.sent.append(self.worker.converted_values.copy())
        self._send()

    def inner_readings_of(self, row_index):
        """The readings that went into row `row_index`."""
        start = 0 if row_index == 0 else self.rows[row_index - 1][1]
        return self.readings[start : self.rows[row_index][1]]


# MARK: the slow path


def test_a_slow_period_records_the_mean_of_its_readings(worker, monkeypatch):
    monkeypatch.setattr(adc_module, "INNER_SECONDS", 0.05)
    worker.set_sampling_time(1.0)
    driver = Driver(worker, periods=2)

    worker.acquisition_loop()

    # One row per period, and no more.
    assert len(driver.rows) == 2
    for index in range(2):
        inner = driver.inner_readings_of(index)
        # The period really was filled with conversions, not read once.
        assert len(inner) > 5
        recorded = driver.rows[index][0]
        for name in driver.channels:
            expected = sum(one[name] for one in inner) / len(inner)
            assert recorded[name] == pytest.approx(expected)
        # And the mean is nobody's single reading.
        assert all(one["Ip"] != recorded["Ip"] for one in inner)


def test_the_recorded_row_converts_the_mean_it_recorded(worker, monkeypatch):
    """Converting the raw column of the CSV reproduces the converted one."""
    monkeypatch.setattr(adc_module, "INNER_SECONDS", 0.05)
    worker.set_sampling_time(1.0)
    driver = Driver(worker, periods=1)

    worker.acquisition_loop()

    raw = driver.rows[0][0]
    row = driver.sent[0].iloc[0]
    for name in driver.channels:
        conversion = worker.adc_channels[name].conversion
        if conversion.__name__ == "ionization_gauge":
            continue  # takes the gauge's mode and range as well
        assert row[name + "_c"] == pytest.approx(conversion(raw[name]))


def test_a_slow_period_takes_about_the_sampling_time(worker, monkeypatch):
    """N inner reads plus their overhead sum to the period, not to more."""
    monkeypatch.setattr(adc_module, "INNER_SECONDS", 0.05)
    worker.set_sampling_time(1.0)
    driver = Driver(worker, periods=1)

    started = time.monotonic()
    worker.acquisition_loop()
    took = time.monotonic() - started

    assert len(driver.readings) > 5
    assert 0.95 <= took <= 1.6


# MARK: the fast path


def test_fast_sampling_still_takes_one_reading_per_row(worker):
    """Below the threshold the current path is untouched: one conversion."""
    worker.set_sampling_time(0.1)
    assert worker.sampling_time < adc_module.AVERAGE_FROM_SECONDS
    driver = Driver(worker, periods=3)

    worker.acquisition_loop()

    assert len(driver.rows) == 3
    assert len(driver.readings) == 3
    for index in range(3):
        assert len(driver.inner_readings_of(index)) == 1


# MARK: aborting


def test_an_abort_mid_period_records_no_partial_mean(worker, monkeypatch):
    monkeypatch.setattr(adc_module, "INNER_SECONDS", 0.05)
    worker.set_sampling_time(1.0)
    driver = Driver(worker, periods=99)  # never reached; the abort ends it

    def abort_partway(driver):
        """Three readings into the second period, tell the worker to stop."""
        if driver.rows and len(driver.readings) == driver.rows[0][1] + 3:
            driver.worker._abort = True

    driver.on_reading = abort_partway

    worker.acquisition_loop()

    # The first period's row stands; the half-measured second one is dropped.
    assert len(driver.rows) == 1
    assert len(worker.adc_values) == 0  # the row was sent, none was added after
    assert len(driver.sent) == 1  # and no second, partial send on the way out
    assert len(driver.readings) == driver.rows[0][1] + 3

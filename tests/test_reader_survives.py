"""The reader survives a board that stops answering, and says so.

Three times this month the ADC worker died between two samples with the
outputs held and nothing on the screen saying the file had stopped
(Mizuno-kun's "logging interrupted" of 2026-08-19 and 2026-08-20, queezz's
"logging dead" of 2026-09-09, every one while the plasma was arcing). Its
I²C reads had no error handling: one exception ended the thread, and the
PID that lived in that thread ended with it, which is why "PID on" then
moved nothing.

Now a read that raises is retried until the board answers or the run is
aborted, a row that cannot be recorded is dropped rather than ending the
loop, a conversion that never finishes raises instead of spinning, and the
main thread says "reader lost" when samples stop arriving anyway. Every
test here drives the real worker's methods in the test's own thread against
a stub board; nothing touches the rig.
"""

import datetime
import os
import time

import pytest

# Before PyQt is imported by anything: these tests draw no window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit.devices import adc as adc_module  # noqa: E402
from controlunit.devices import adc_setter  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
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
def worker(qt_app, home, monkeypatch):
    """A real ADC worker on the dummy board, retrying fast, messages kept."""
    import readsettings

    monkeypatch.setattr(adc_module, "RETRY_SECONDS", 0.01)
    config = readsettings.init_configuration()
    made = adc_module.ADC("ADC", qt_app, datetime.datetime.now(), config, None)
    made.messages = []
    made.send_message.connect(made.messages.append)
    return made


class FlakyBoard:
    """Reads that raise `failures` times, then answer."""

    def __init__(self, worker, failures):
        self.worker = worker
        self.failures = failures
        self.calls = 0
        self.channels = list(worker.adc_channels)

    def read(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise OSError(121, "Remote I/O error")
        return {name: 0.5 for name in self.channels}


# MARK: a read that fails


def test_a_failed_read_is_retried_until_the_board_answers(worker):
    board = FlakyBoard(worker, failures=3)
    worker.read_all_channels = board.read

    assert worker.collect_data() is True

    assert board.calls == 4
    assert worker.adc_voltages == {name: 0.5 for name in board.channels}
    # Said once when it failed, once when it came back, and never per retry.
    assert len(worker.messages) == 2
    assert "ADC read failed" in worker.messages[0]
    assert "Remote I/O error" in worker.messages[0]
    assert "answering again" in worker.messages[1]
    assert "3 failed reads" in worker.messages[1]
    # The counters are back at rest for the next fault.
    assert worker._read_failures == 0
    assert worker._failing_since is None


def test_a_board_that_never_answers_only_ends_the_read_on_abort(worker):
    board = FlakyBoard(worker, failures=10**9)
    worker.read_all_channels = board.read

    def abort_after_a_few(*args, **kwargs):
        if board.calls >= 5:
            worker._abort = True
        return original_pause(*args, **kwargs)

    original_pause = worker.pause
    worker.pause = abort_after_a_few

    assert worker.collect_data() is False
    assert board.calls >= 5
    assert len(worker.messages) == 1  # the one complaint; no "again"


def test_a_long_fault_is_repeated_in_the_log_but_not_every_read(worker, monkeypatch):
    monkeypatch.setattr(adc_module, "COMPLAIN_EVERY_SECONDS", 0.05)
    board = FlakyBoard(worker, failures=10**9)
    worker.read_all_channels = board.read
    started = time.monotonic()

    def abort_after(*args, **kwargs):
        if time.monotonic() - started > 0.2:
            worker._abort = True
        return original_pause(*args, **kwargs)

    original_pause = worker.pause
    worker.pause = abort_after

    worker.collect_data()

    assert board.calls > 5
    assert 2 <= len(worker.messages) < board.calls
    assert "still not answering" in worker.messages[1]


def test_a_failed_read_inside_a_slow_period_does_not_end_the_run(worker, monkeypatch):
    """The averaged path retries too; the period's mean is of what answered."""
    monkeypatch.setattr(adc_module, "INNER_SECONDS", 0.02)
    board = FlakyBoard(worker, failures=2)
    worker.read_all_channels = board.read

    assert worker.collect_period_average(0.1) is True
    assert worker.adc_voltages == {name: 0.5 for name in board.channels}


# MARK: a row that cannot be recorded


def test_a_row_that_fails_to_record_is_dropped_and_the_loop_goes_on(worker):
    worker.set_sampling_time(0.01)
    channels = list(worker.adc_channels)
    worker.read_all_channels = lambda: {name: 0.25 for name in channels}
    rows = []
    original_put = worker.put_new_data_in_dataframe

    def put_or_fail():
        rows.append(1)
        if len(rows) == 2:
            raise ValueError("a row the pandas side could not take")
        original_put()
        if len(rows) >= 5:
            worker._abort = True

    worker.put_new_data_in_dataframe = put_or_fail
    worker.send_processed_data_to_main_thread = lambda: None

    worker.acquisition_loop()

    assert len(rows) == 5
    assert any("ADC step failed" in message for message in worker.messages)


# MARK: a conversion that never finishes


class StuckBus:
    """An ADS1115 whose conversion-ready bit never sets."""

    def __init__(self):
        self.reads = 0

    def write_word_data(self, address, register, value):
        pass

    def read_byte_data(self, address, register):
        self.reads += 1
        return 0


def test_a_conversion_that_never_finishes_raises_instead_of_spinning():
    chip = adc_setter.ADS1115(0x49)
    chip.i2c = StuckBus()
    with pytest.raises(TimeoutError):
        chip.analog_read(0, adc_setter.ADS1115.DataRate.DR_860SPS, 0)
    assert chip.i2c.reads == adc_setter.ADS1115.MAX_POLLS + 1


# MARK: the main thread's watchdog


def test_reader_lost_is_twice_the_stale_line_and_never_under_five_seconds():
    from controlunit.main import reader_lost_after
    from controlunit.web.status import stale_after

    assert reader_lost_after(10.0) == 2 * stale_after(10.0) == 100.0
    assert reader_lost_after(0.1) == 5.0
    assert reader_lost_after(None) == 5.0


def test_the_main_thread_says_reader_lost_once_and_reader_back_once(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.workers = {"ADC": object()}  # a run, as far as the watchdog knows
        widget._last_sample_at = time.monotonic() - 1000.0
        widget._reader_lost_since = None
        before = len(widget.web_status.log_since(0)["lines"])

        widget._check_reader()
        widget._check_reader()  # a second look is silent

        lines = [entry["text"] for entry in widget.web_status.log_since(0)["lines"][before:]]
        assert len(lines) == 1
        assert "Reader lost" in lines[0]
        assert "Stop and Start" in lines[0]

        widget._note_sample_arrived()
        widget._check_reader()  # a fresh sample; nothing to say

        lines = [entry["text"] for entry in widget.web_status.log_since(0)["lines"][before:]]
        assert len(lines) == 2
        assert "Reader back" in lines[1]
        assert widget._reader_lost_since is None
    finally:
        widget.workers = {}
        widget.reader_watchdog.stop()

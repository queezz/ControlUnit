"""The Raspberry Pi's own health: read, judged, and carried to the Log.

No test here runs `vcgencmd` or reads a thermal zone: every reader is handed
what it would have read, so the suite says the same on Windows, macOS and
the Pi. The Qt half builds a window offscreen with a home of its own.
"""

import os
import subprocess
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit import pi_health  # noqa: E402
from controlunit.pi_health import PiHealthJudge, Reading, Report  # noqa: E402
from controlunit.web.status import RigStatus, health_body  # noqa: E402


def reading(throttled=0x0, temperature=52.1, free=41e9, at=1000.0):
    return Reading(throttled=throttled, temperature_c=temperature, free_bytes=free, at=at)


# -- the readers ---------------------------------------------------------------


def test_the_throttled_word_is_read_from_vcgencmd_s_answer():
    assert pi_health.parse_throttled("throttled=0x50000\n") == 0x50000
    assert pi_health.parse_throttled("throttled=0x0") == 0
    assert pi_health.parse_throttled("error=1 error_msg=\"no\"") is None
    assert pi_health.parse_throttled(None) is None


def test_off_a_pi_vcgencmd_is_never_started():
    def no_process(*args, **kwargs):
        pytest.fail("a machine without vcgencmd started a process")

    assert pi_health.read_throttled(run=no_process, which=lambda name: None) is None


def test_on_a_pi_vcgencmd_is_asked_and_its_failures_read_as_none():
    asked = []

    class Done:
        stdout = "throttled=0x50005\n"

    def run(command, **kwargs):
        asked.append((command, kwargs["timeout"]))
        return Done()

    found = lambda name: "/usr/bin/vcgencmd"  # noqa: E731
    assert pi_health.read_throttled(run=run, which=found) == 0x50005
    assert asked == [(["vcgencmd", "get_throttled"], pi_health.VCGENCMD_TIMEOUT_SECONDS)]

    def times_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    def cannot_run(command, **kwargs):
        raise OSError("gone")

    assert pi_health.read_throttled(run=times_out, which=found) is None
    assert pi_health.read_throttled(run=cannot_run, which=found) is None


def test_the_temperature_is_millidegrees_and_absent_off_a_pi(tmp_path):
    zone = tmp_path / "temp"
    zone.write_text("52123\n")
    assert pi_health.read_temperature(str(zone)) == pytest.approx(52.123)
    assert pi_health.read_temperature(str(tmp_path / "nothing")) is None
    zone.write_text("not a number")
    assert pi_health.read_temperature(str(zone)) is None


def test_the_free_disk_is_the_data_folder_s_filesystem(tmp_path):
    assert pi_health.read_free_bytes(str(tmp_path)) > 0
    assert pi_health.read_free_bytes(str(tmp_path / "not" / "there")) is None


def test_a_reader_that_raises_reads_as_not_available():
    def broken(*args):
        raise RuntimeError("no")

    got = pi_health.read_pi(
        "folder", throttled=broken, temperature=broken, free=broken, clock=lambda: 5.0
    )
    assert got == Reading(None, None, None, 5.0)


# -- what the Log says ---------------------------------------------------------


def test_the_start_line_on_a_pi_and_off_one():
    assert PiHealthJudge().see(reading()) == [
        ("Pi health: 52.1 C, power fine, 41 GB free", False)
    ]
    assert PiHealthJudge().see(reading(throttled=None, temperature=None, free=120.4e9)) == [
        ("Pi health: temperature not available, power flags not available, 120 GB free", False)
    ]
    assert PiHealthJudge().see(reading(throttled=0x50000)) == [
        ("Pi health: 52.1 C, power fine now (under-voltage, throttled since boot),"
         " 41 GB free", False)
    ]
    # Something wrong at the start is red at the start.
    assert PiHealthJudge().see(reading(throttled=0x50001, free=1.5e9)) == [
        ("Pi health: 52.1 C, under-voltage now, 1.5 GB free", True)
    ]


def test_an_unchanged_pi_says_nothing_after_the_start():
    judge = PiHealthJudge()
    judge.see(reading())
    for _ in range(5):
        assert judge.see(reading(temperature=55.0, free=40e9)) == []


def test_a_flag_that_sets_is_red_and_one_that_clears_is_plain():
    judge = PiHealthJudge()
    judge.see(reading(throttled=0x0))
    assert judge.see(reading(throttled=0x50005)) == [
        ("Pi: under-voltage, throttled now (get_throttled 0x50005)", True)
    ]
    assert judge.see(reading(throttled=0x50005)) == []
    assert judge.see(reading(throttled=0x50000)) == [
        ("Pi: under-voltage, throttled over (get_throttled 0x50000)", False)
    ]


def test_a_sag_between_two_readings_is_said_from_the_since_boot_bits():
    """The sag during a discharge that five minutes between asks would miss."""
    judge = PiHealthJudge()
    judge.see(reading(throttled=0x0))
    assert judge.see(reading(throttled=0x10000)) == [
        ("Pi: under-voltage came and went since the last check (get_throttled 0x10000)", True)
    ]
    assert judge.see(reading(throttled=0x10000)) == []


def test_not_available_for_a_moment_says_nothing():
    judge = PiHealthJudge()
    judge.see(reading(throttled=0x0))
    assert judge.see(reading(throttled=None, temperature=None, free=None)) == []
    assert judge.see(reading(throttled=0x0)) == []


def test_the_temperature_crosses_70_and_comes_back_under_65():
    judge = PiHealthJudge()
    judge.see(reading(temperature=60.0))
    assert judge.see(reading(temperature=69.9)) == []
    assert judge.see(reading(temperature=70.0)) == [("Pi at 70.0 C, above 70 C", True)]
    assert judge.see(reading(temperature=72.0)) == []
    assert judge.see(reading(temperature=66.0)) == []
    assert judge.see(reading(temperature=64.9)) == [("Pi back to 64.9 C, under 65 C", False)]


def test_the_disk_falling_under_2_gb_is_said_once():
    judge = PiHealthJudge()
    judge.see(reading(free=2.5e9))
    assert judge.see(reading(free=1.8e9)) == [
        ("Pi: 1.8 GB free under the data folder, less than 2.0 GB", True)
    ]
    assert judge.see(reading(free=1.5e9)) == []
    assert judge.see(reading(free=3.0e9)) == [("Pi: 3.0 GB free under the data folder again", False)]


def test_a_disk_sitting_at_the_line_is_said_once_until_it_has_room_again():
    """The review of 2026-11-13: 1.99, 2.01, 1.99, 2.01 GB was a line at
    every reading. Under 2 GB sets it; only back over 2.5 GB clears it."""
    judge = PiHealthJudge()
    judge.see(reading(free=2.1e9))
    assert judge.see(reading(free=1.99e9)) == [
        ("Pi: 2.0 GB free under the data folder, less than 2.0 GB", True)
    ]
    for free in (2.01e9, 1.99e9, 2.4e9, 1.99e9, 2.49e9):
        assert judge.see(reading(free=free)) == []
    assert judge.see(reading(free=2.5e9)) == [
        ("Pi: 2.5 GB free under the data folder again", False)
    ]


def test_a_start_with_no_power_word_holds_the_first_one_against_nothing_set():
    """The review of 2026-11-13: `vcgencmd` failing at the start made the
    next readable word, under-voltage and all, the baseline in silence."""
    judge = PiHealthJudge()
    judge.see(reading(throttled=None))
    assert judge.see(reading(throttled=0x50005)) == [
        ("Pi: under-voltage, throttled now (get_throttled 0x50005)", True)
    ]
    assert judge.see(reading(throttled=0x50005)) == []
    # A since-boot bit on that first word is said as since boot, not as
    # something that came and went since a check that never read it.
    judge = PiHealthJudge()
    judge.see(reading(throttled=None))
    assert judge.see(reading(throttled=0x10000)) == [
        ("Pi: under-voltage occurred since boot (get_throttled 0x10000)", True)
    ]
    # A clean first word says nothing.
    judge = PiHealthJudge()
    judge.see(reading(throttled=None))
    assert judge.see(reading(throttled=0x0)) == []


def test_a_reading_in_the_health_report_s_shape():
    body = pi_health.as_json(reading(throttled=0x50001, temperature=52.14, free=41.26e9, at=7.5))
    assert body == {
        "temperature_c": 52.1,
        "throttled": "0x50001",
        "now": ["under-voltage"],
        "since_boot": ["under-voltage", "throttled"],
        "free_gb": 41.3,
        "checked_at": 7.5,
    }
    assert pi_health.as_json(None) == pi_health.UNREAD
    assert set(body) == set(pi_health.UNREAD)


def test_api_health_carries_the_newest_reading_without_touching_the_rest(monkeypatch):
    from controlunit._version import __version__
    from controlunit.web import status as status_module
    from controlunit.web.server import create_app

    monkeypatch.setattr(status_module, "dummy_hardware_loaded", lambda: False)
    rig = RigStatus(channels=9, sampling=0.1)
    before = health_body(rig, __version__)
    rig.record_pi(pi_health.as_json(reading(at=9.0)))
    body = create_app(status=rig).test_client().get("/api/health").get_json()
    assert body["pi"] == {
        "temperature_c": 52.1,
        "throttled": "0x0",
        "now": [],
        "since_boot": [],
        "free_gb": 41.0,
        "checked_at": 9.0,
    }
    for key in ("service", "version", "status", "detail"):
        assert body[key] == before[key]
    assert body["detail"] == "idle, not recording"


# -- the thread ----------------------------------------------------------------


def test_one_check_reads_judges_and_reports():
    reports = []
    monitor = pi_health.PiHealthMonitor("folder", reports.append, read=lambda: reading())
    report = monitor.check_once()
    assert reports == [report]
    assert report.lines == [("Pi health: 52.1 C, power fine, 41 GB free", False)]
    assert monitor.check_once().lines == []


def test_a_reading_or_a_receiver_that_fails_never_ends_the_thread():
    def broken():
        raise RuntimeError("no Pi")

    def gone(report):
        raise RuntimeError("wrapped C/C++ object has been deleted")

    assert pi_health.PiHealthMonitor("f", lambda r: None, read=broken).check_once() is None
    assert pi_health.PiHealthMonitor("f", gone, read=lambda: reading()).check_once() is not None


def test_the_thread_reads_off_the_main_thread_and_stops_at_once():
    seen = []
    readers = []

    def read():
        readers.append(threading.current_thread())
        return reading()

    monitor = pi_health.PiHealthMonitor("f", seen.append, interval=60.0, read=read)
    monitor.start()
    deadline = time.monotonic() + 5
    while not seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen and readers
    assert threading.main_thread() not in readers
    assert monitor.thread.name == "pi-health" and monitor.thread.daemon
    started = time.monotonic()
    assert monitor.stop() is True  # not after the 60 s wait
    assert time.monotonic() - started < 1.0


# -- through the window --------------------------------------------------------


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
    place = tmp_path / "home"
    place.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(place))
    monkeypatch.setenv("HOMEDRIVE", "")
    monkeypatch.setenv("HOMEPATH", "")
    monkeypatch.delenv("CONTROLUNIT_SETTINGS_HOME", raising=False)
    return place


def _log(widget):
    return [line["text"] for line in widget.web_status.log_since(0)["lines"]]


def test_a_window_starts_no_monitor_of_its_own(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        assert widget._pi_health is None
        assert widget._stop_pi_health() is True
    finally:
        widget.abort_all_threads()


def test_a_report_reaches_the_log_and_the_health_record(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        lines = [("Pi: under-voltage now (get_throttled 0x50001)", True)]
        widget._pi_health_reported(Report(reading(throttled=0x50001, at=3.0), lines))
        assert _log(widget)[-1] == "Pi: under-voltage now (get_throttled 0x50001)"
        panel = widget.logDock.log.toHtml()
        assert "Pi: under-voltage now" in panel
        pi = health_body(widget.web_status, "x")["pi"]
        assert pi["now"] == ["under-voltage"] and pi["checked_at"] == 3.0
    finally:
        widget.abort_all_threads()


def test_the_monitor_s_reports_cross_to_the_main_thread_and_it_stops(qt_app, home):
    from controlunit.main import MainApp

    readers = []

    def read():
        readers.append(threading.current_thread())
        return reading(throttled=None, temperature=None, free=41e9)

    widget = MainApp(qt_app)
    try:
        widget.start_pi_health(read=read, interval=60.0)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(
            line.startswith("Pi health:") for line in _log(widget)
        ):
            qt_app.processEvents()
            time.sleep(0.01)
        assert (
            "Pi health: temperature not available, power flags not available, 41 GB free"
            in _log(widget)
        )
        assert threading.main_thread() not in readers
        assert health_body(widget.web_status, "x")["pi"]["free_gb"] == 41.0
    finally:
        stopped = widget._stop_pi_health()
        widget.abort_all_threads()
    assert stopped
    assert not widget._pi_health.thread.is_alive()


def test_every_line_is_ascii():
    """The rig's locale is Latin-1: a degree sign reached controlunit.log as
    a byte no UTF-8 reader accepts (2026-11-16)."""
    judge = PiHealthJudge()
    lines = judge.see(reading(temperature=52.1)) + judge.see(reading(temperature=70.0))
    lines += judge.see(reading(temperature=64.9))
    assert lines and all(text.isascii() for text, _ in lines)

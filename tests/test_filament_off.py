"""Ip read with the filament off: warned once, cleared once, never by drift.

queezz, 2026-11-13: "if we see the current with the filament power off, it's
a SUS. So we should warn, really. Sometimes the current sensor gets a wrong
zero". The shapes below are the files' own: the one stretch of 2026-10-22 to
11-13 with the drive at 0 and Ip above 0.1 A for more than three seconds
(15:25 on 11-13, 27 s at a flat 2.38 A), the ordinary drift at -0.012 A,
a discharge dying within its drive, and a lit filament.

Nothing here touches the rig; the Qt half builds a window offscreen with the
dummy hardware and a home of the test's own.
"""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit import filament_off  # noqa: E402
from controlunit.filament_off import FilamentOffCurrent  # noqa: E402

LIT_ABOVE = 0.1
SUPPLY_LIT = {"status": "ok", "current_a": 18.0, "output_on": 1, "voltage_v": 7.9}


def run(rows, supply=None, lit_above=LIT_ABOVE):
    """Feed `(t, drive_mv, ip)` rows to a fresh watch; the lines it said."""
    watch = FilamentOffCurrent(lit_above)
    said = []
    for at, drive, ip in rows:
        off, why = filament_off.filament_off(drive, supply)
        line = watch.observe(at, ip, off, why)
        if line is not None:
            said.append(line)
    return watch, said


def stretch(start, seconds, drive, ip, step=0.1):
    """Rows every `step` seconds from `start` for `seconds`; `ip` a number
    or a function of the time since `start`."""
    count = int(round(seconds / step))
    return [
        (start + i * step, drive, ip(i * step) if callable(ip) else ip)
        for i in range(count)
    ]


def test_the_15_25_shape_warns_once_and_clears_once():
    """A discharge at 1900 mV, the drive to 0, Ip held at 2.38 A for 27 s,
    then the sensor's -0.02 A: the 2026-11-13 file, at 0.1 s sampling."""
    rows = (
        stretch(0.0, 10.0, 1900.0, 2.38)          # lit, driven: not this warning
        + stretch(10.0, 27.0, 0.0, 2.38)          # drive 0, Ip flat
        + stretch(37.0, 10.0, 0.0, -0.02)         # gone
    )
    watch, said = run(rows)
    assert len(said) == 2
    head, rest, alarm = said[0]
    assert alarm
    assert head == "Ip reads 2.38 A with the filament off (cathode drive 0 mV)"
    assert rest == (
        ": not plasma current. If the preanode supply's panel shows no current,"
        " the sensor's zero is off (Zero Ip with everything off); if it shows"
        " current, something conducts with the filament off."
    )
    head, rest, alarm = said[1]
    assert not alarm
    assert head + rest == (
        "Ip no longer reads current with the filament off, after 27 s at up to 2.38 A"
    )
    assert not watch.warning


def test_the_warning_waits_three_seconds_on_the_rows_own_clock():
    _, said = run(stretch(0.0, 2.9, 0.0, 2.38))  # the last row at 2.8 s
    assert said == []
    _, said = run(stretch(0.0, 2.9, 0.0, 2.38) + stretch(2.9, 0.3, 0.0, 2.38))
    assert len(said) == 1
    # And at the rig's 10 s sampling, two rows in a row are three seconds.
    _, said = run([(0.0, 0.0, 2.38), (10.0, 0.0, 2.38)])
    assert len(said) == 1
    _, said = run([(0.0, 0.0, 2.38), (10.0, 0.0, -0.01)])
    assert said == []


def test_the_ordinary_drift_never_warns():
    """-0.005 to -0.016 A for ten minutes with the drive at 0."""
    rows = stretch(0.0, 600.0, 0.0, lambda t: -0.012 + 0.004 * math.sin(t / 30.0))
    _, said = run(rows)
    assert said == []


def test_a_discharge_dying_within_three_seconds_of_its_drive_does_not_warn():
    """The drive to 0 at t = 10 s and the current down from 1.5 A to nothing
    over 2.5 s: plasma current, going."""
    rows = stretch(0.0, 10.0, 2000.0, 1.5) + stretch(
        10.0, 10.0, 0.0, lambda t: max(-0.01, 1.5 * (1.0 - t / 2.5))
    )
    _, said = run(rows)
    assert said == []


def test_a_lit_filament_never_warns():
    """Drive 2200 mV and the supply measuring 18 A: Ip is plasma current."""
    rows = stretch(0.0, 120.0, 2200.0, 1.5)
    _, said = run(rows, supply=SUPPLY_LIT)
    assert said == []


def test_the_filament_on_the_supply_s_own_knob_never_warns():
    """CF10 off: the program's drive at 0 mV and the supply measuring 18 A
    from its front panel (docs/hardware/cathode-control.md). The supply's
    own measurement is the filament's power, and it is on."""
    _, said = run(stretch(0.0, 120.0, 0.0, 1.5), supply=SUPPLY_LIT)
    assert said == []
    # Fresh, but with no current in it: the link is there and says nothing
    # of the filament, so neither does the drive.
    supply = {"status": "ok", "output_on": 1}
    assert filament_off.filament_off(0.0, supply) == (False, "")


def test_the_supply_can_say_the_filament_is_off_when_the_drive_does_not():
    """Drive held at 2000 mV with the supply's output switched off, or the
    supply measuring under 1 A: off either way, and the line says which."""
    _, said = run(stretch(0.0, 5.0, 2000.0, 2.0), supply={"status": "ok", "output_on": 0})
    assert [head for head, _, _ in said] == [
        "Ip reads 2.00 A with the filament off (the supply's output off)"
    ]
    supply = {"status": "dummy", "output_on": 1, "current_a": 0.4}
    _, said = run(stretch(0.0, 5.0, 2000.0, 2.0), supply=supply)
    assert [head for head, _, _ in said] == [
        "Ip reads 2.00 A with the filament off (the supply at 0.40 A)"
    ]


def test_a_stale_or_lost_supply_never_says_off():
    for status in ("stale", "lost", "idle", "error", "disabled"):
        supply = {"status": status, "output_on": 0, "current_a": 0.0}
        assert filament_off.filament_off(2000.0, supply) == (False, "")
    assert filament_off.filament_off(float("nan"), None) == (False, "")


@pytest.mark.parametrize(
    "status", ["stale", "unavailable", "connecting", "stopped", "idle", "error"])
def test_a_link_that_is_configured_but_not_fresh_leaves_the_filament_unknown(status):
    """The review of 2026-11-13: with the supply's LAN down, the drive at
    0 mV was taken as the filament off, and a discharge run on the supply's
    own knob would have been warned about. Unknown is never off."""
    supply = {"status": status}
    assert filament_off.filament_off(0.0, supply) == (False, "")
    _, said = run(stretch(0.0, 30.0, 0.0, 2.38), supply=supply)
    assert said == []


def test_with_no_link_configured_the_drive_is_the_filament():
    assert filament_off.filament_off(0.0, {"status": "disabled"}) == (
        True, "cathode drive 0 mV")
    assert filament_off.filament_off(0.0, None) == (True, "cathode drive 0 mV")
    assert filament_off.filament_off(1800.0, {"status": "disabled"}) == (False, "")


def test_a_nan_never_counts_as_current():
    _, said = run(stretch(0.0, 10.0, 0.0, float("nan")))
    assert said == []


def test_a_nan_row_is_passed_over_not_taken_as_the_end():
    """The review of 2026-11-13: a NaN row (the Hall supply out of range for
    one sample) ended a standing warning, and the next row began it again,
    a red line and a plain one for nothing. It says nothing either way."""
    gap = [(5.0, 0.0, float("nan"))]
    _, said = run(stretch(0.0, 5.0, 0.0, 2.38) + gap + stretch(5.1, 10.0, 0.0, 2.38))
    assert [alarm for _, _, alarm in said] == [True]
    # Nor does it break a stretch still counting its three seconds.
    _, said = run(stretch(0.0, 2.0, 0.0, 2.38) + [(2.0, 0.0, float("nan"))]
                  + stretch(2.1, 1.5, 0.0, 2.38))
    assert [alarm for _, _, alarm in said] == [True]


def test_a_stop_during_a_warning_says_the_run_ended_it():
    watch, said = run(stretch(0.0, 5.0, 0.0, 2.38))
    assert len(said) == 1
    head, rest, alarm = watch.close(6.0)
    assert not alarm
    assert head + rest == (
        "Acquisition stopped while Ip still read current with the filament off,"
        " after 6 s at up to 2.38 A"
    )
    assert watch.close(7.0) is None
    quiet = FilamentOffCurrent(LIT_ABOVE)
    assert quiet.close(1.0) is None


# -- through the window, as a delivered batch ----------------------------------


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


def _batch(start, seconds, drive, ip_c, step=1.0):
    import datetime

    import pandas as pd

    stamps = [start + datetime.timedelta(seconds=i * step) for i in range(int(seconds / step))]
    return pd.DataFrame(
        {
            "date": stamps,
            "PresetV_cathode": [float(drive)] * len(stamps),
            "Ip_c": [float(ip_c)] * len(stamps),
        }
    )


def _log(widget):
    return [line["text"] for line in widget.web_status.log_since(0)["lines"]]


def test_the_window_reads_the_batch_after_the_ip_zero(qt_app, home):
    """Ip as the PID sees it: 2.40 A read, 0.02 A zero, 2.38 A said; the
    threshold is the reader's own `Lit Above A`, read from settings.yml."""
    import datetime

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        assert widget._lit_above() == pytest.approx(0.1)
        widget._filament_watch = FilamentOffCurrent(widget._lit_above())
        widget.zero_adjustment = {"Ip": 0.02, "Bu": 0, "Bd": 0}
        start = datetime.datetime(2026, 11, 13, 15, 25, 25)
        widget._watch_filament_off_current(_batch(start, 10, 1900, 2.40))
        assert not any("filament off" in line for line in _log(widget))
        for second in range(10, 37, 3):  # three-row batches, as at 1 s
            widget._watch_filament_off_current(
                _batch(start + datetime.timedelta(seconds=second), 3, 0, 2.40)
            )
        widget._watch_filament_off_current(
            _batch(start + datetime.timedelta(seconds=37), 3, 0, 0.0)
        )
        said = [line for line in _log(widget) if "filament off" in line]
        assert said == [
            "Ip reads 2.38 A with the filament off (cathode drive 0 mV): not plasma"
            " current. If the preanode supply's panel shows no current, the"
            " sensor's zero is off (Zero Ip with everything off); if it shows"
            " current, something conducts with the filament off.",
            "Ip no longer reads current with the filament off, after 27 s at up to 2.38 A",
        ]
        # A fresh supply at 18 A and the drive up: nothing more is said.
        widget._kikusui_snapshot = dict(SUPPLY_LIT)
        widget._watch_filament_off_current(
            _batch(start + datetime.timedelta(seconds=40), 30, 2200, 1.5)
        )
        assert len([line for line in _log(widget) if "filament off" in line]) == 2
    finally:
        widget.abort_all_threads()


def test_a_stop_says_how_long_the_warning_stood_on_the_rows_own_clock(qt_app, home):
    """The review of 2026-11-13: the end line after Stop said "after 0 s".
    The rows' naive local stamps were read as UTC (pandas'
    `Timestamp.timestamp()`), nine hours ahead of `time.time()` on a JST
    clock; they are now read as local time, as the web view's are."""
    import datetime
    import re

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        # No kikusui.yml in this home: no link, so the drive is the word.
        assert widget._kikusui_snapshot["status"] == "disabled"
        now = datetime.datetime.now()
        widget._watch_filament_off_current(
            _batch(now - datetime.timedelta(seconds=20), 21, 0, 2.38))
        assert any(line.startswith("Ip reads 2.38 A") for line in _log(widget))
        widget.abort_all_threads()
        ended = [line for line in _log(widget)
                 if line.startswith("Acquisition stopped while Ip")]
        assert len(ended) == 1
        seconds = int(re.search(r"after (\d+) s", ended[0]).group(1))
        assert 18 <= seconds <= 30
    finally:
        widget.abort_all_threads()


def test_a_warning_s_end_line_that_fails_never_leaves_the_run_behind(qt_app, home):
    """The end line is the last thing a stop does, and a failure in it is
    swallowed: before, it raised out of `abort_all_threads` before the
    switch checks, the acquiring flag and the browser's control were let go."""
    import datetime

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        widget.web_commands.control.take_over("Owner", "10.0.0.5")
        widget._watch_filament_off_current(
            _batch(datetime.datetime.now() - datetime.timedelta(seconds=10), 10, 0, 2.38))
        widget._switch_checks["Pd"] = object()

        def broken(said):
            raise OSError(28, "No space left on device")

        widget._say_filament = broken
        widget.abort_all_threads()
        assert not widget.workers
        assert widget._switch_checks == {}
        assert widget.web_status.read()["acquiring"] is False
        assert widget.web_commands.control.read()["holder"] == ""
        assert widget._filament_watch is None
    finally:
        widget.abort_all_threads()

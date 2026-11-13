"""Why the program stopped: the last Log line, and Stop's path on a signal.

2026-11-11 16:47 the program restarted with no reason anywhere. Each way it
ends now says which as its last line. A signal ends it the way Stop then
Quit would, hardware first. An uncaught error no longer ends it: the Log
says what broke, the outputs are held, and the program carries on.

No real signal is sent and no real hook is left installed: the handler and
the hook are called the way Python would call them, and the event loop's
end is stood in for (`_exit_program`, `_closing`). The window is built
offscreen with the dummy hardware and a home of the test's own.
"""

import os
import signal
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit.web import commands  # noqa: E402


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
    # Ending wraps the streams and a hook replaces sys.excepthook; both are
    # put back after each test, so nothing outlives it.
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    return place


def _log(widget):
    return [line["text"] for line in widget.web_status.log_since(0)["lines"]]


class Recorder:
    """What a DAC worker was told to write, in the order it was told."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


def _running_with_outputs(widget):
    """A run with the cathode held at 1500 mV and gas line 1 at 1000 mV,
    each DAC worker's own write recorded from here on."""
    widget.start_acquisition()
    widget.plasma_control_dock.cathode_spin_box.setValue(1500)
    widget.set_cathode_drive()
    commands._apply_mfc(widget, {"n": 1, "mv": 1000})
    assert widget.web_status.read()["setpoints"]["cathode_mv"] == 1500
    cathode, gas = Recorder(), Recorder()
    widget.workers["PlasmaCurrent"]["worker"].output_voltage = cathode
    widget.workers["MFCs"]["worker"].output_voltage = gas
    return cathode, gas


def test_each_stop_signal_is_named_in_words():
    from controlunit.main import STOP_SIGNALS, signal_reason

    assert signal_reason(signal.SIGTERM) == (
        "SIGTERM, asked to stop by another program (kill, a service manager or a shutdown)"
    )
    assert signal_reason(signal.SIGINT) == "SIGINT, Ctrl+C in the terminal it ran from"
    if hasattr(signal, "SIGHUP"):
        assert signal_reason(signal.SIGHUP) == (
            "SIGHUP, the terminal it ran from was closed, or its session ended"
        )
    assert [name for name, _ in STOP_SIGNALS] == ["SIGTERM", "SIGHUP", "SIGINT"]


def test_a_signal_stops_the_run_hardware_first_then_ends_with_its_status(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    exits = []
    widget._exit_program = exits.append
    try:
        cathode, gas = _running_with_outputs(widget)

        # The handler only notes: nothing stops inside it.
        widget._signal_received(signal.SIGTERM, None)
        assert widget.workers and not exits

        widget._take_pending_stop()  # the signal timer's slot
        assert not widget.workers
        assert not widget.control_dock.OnOffSW.isChecked()
        # Every DAC worker wrote zero before the threads were let go.
        assert (0,) in cathode.calls
        assert (1, 0) in gas.calls and (2, 0) in gas.calls
        setpoints = widget.web_status.read()["setpoints"]
        assert setpoints["cathode_mv"] == 0 and setpoints["mfc1_v"] == 0
        assert exits == [128 + signal.SIGTERM]

        # A second signal while ending changes nothing.
        widget._signal_received(signal.SIGINT, None)
        widget._take_pending_stop()
        assert exits == [128 + signal.SIGTERM]

        widget._closing()  # aboutToQuit
        assert _log(widget)[-1] == (
            "Program closing: SIGTERM, asked to stop by another program (kill, a"
            " service manager or a shutdown); the run was stopped first, outputs to zero"
        )
    finally:
        widget.abort_all_threads()


def test_a_shutdown_survives_a_terminal_that_is_gone(qt_app, home):
    """After SIGHUP every print to the closed terminal raises; the DAC8532
    worker prints after each write, and gas line 2 must still be zeroed."""
    from controlunit.main import MainApp

    class Gone:
        def write(self, text):
            raise OSError(5, "Input/output error")

        def flush(self):
            raise OSError(5, "Input/output error")

    widget = MainApp(qt_app)
    exits = []
    widget._exit_program = exits.append
    try:
        widget.start_acquisition()
        dac = widget.workers["MFCs"]["worker"]
        written = []
        dac.DAC.DAC8532_Out_Voltage = lambda channel, volts: written.append(volts)
        sys.stdout = Gone()
        widget._signal_received(getattr(signal, "SIGHUP", signal.SIGTERM), None)
        widget._take_pending_stop()
        assert not widget.workers
        assert written.count(0) >= 2  # both channels, through abort's own writes
        print("a line the terminal no longer takes")  # lost, never raised
        widget._closing()
        assert _log(widget)[-1].startswith("Program closing: SIG")
    finally:
        widget.abort_all_threads()


def _raised(function):
    try:
        function()
    except Exception:  # noqa: BLE001 -- the error is the point
        return sys.exc_info()
    raise AssertionError("it did not raise")


def test_an_uncaught_error_is_logged_then_printed_and_the_program_carries_on(qt_app, home):
    """queezz's ruling for a dead reader, "Hold and alarm!" (2026-09-07),
    for any error no code caught: a red line, the outputs where they were,
    and no stop. 4.30.0 ended the program through Stop instead, which
    zeroes a discharge somebody is running."""
    from controlunit.main import MainApp, install_stop_handlers

    printed = []
    sys.excepthook = lambda *args: printed.append((args, _log(widget)[-1]))
    handlers = {}
    widget = MainApp(qt_app)
    exits = []
    widget._exit_program = exits.append
    try:
        install_stop_handlers(widget, set_handler=lambda n, h: handlers.__setitem__(n, h))
        assert handlers[signal.SIGTERM] == widget._signal_received
        assert handlers[signal.SIGINT] == widget._signal_received
        if hasattr(signal, "SIGHUP"):  # Windows has none, and is passed over
            assert handlers[signal.SIGHUP] == widget._signal_received
        assert len(handlers) == 2 + hasattr(signal, "SIGHUP")
        assert widget.stop_signal_timer.isActive()
        assert widget.stop_signal_timer.interval() == 250
        cathode, gas = _running_with_outputs(widget)

        def _breaks():
            return 1 / 0

        sys.excepthook(*_raised(_breaks))

        line = _log(widget)[-1]
        assert line.startswith(
            "Uncaught error: ZeroDivisionError: division by zero (in _breaks,"
            " test_program_end.py line "
        )
        assert line.endswith("; outputs held, the program carries on")
        # The hook that was there before still prints the traceback, after
        # the Log has the line.
        assert len(printed) == 1 and printed[0][0][0] is ZeroDivisionError
        assert printed[0][1] == line

        # Nothing is stopped, zeroed or ended.
        widget._take_pending_stop()
        assert exits == [] and widget._stop_pending is None
        assert widget.workers
        assert cathode.calls == [] and gas.calls == []
        assert widget.web_status.read()["setpoints"]["cathode_mv"] == 1500
    finally:
        widget.stop_signal_timer.stop()
        widget.abort_all_threads()


def test_the_same_uncaught_error_is_said_once_a_minute(qt_app, home):
    """A slot on a timer that raises every tick is one line and one
    traceback a minute, the next line counting the rest."""
    from controlunit import main
    from controlunit.main import MainApp, install_stop_handlers

    printed = []
    sys.excepthook = lambda *args: printed.append(args)
    clock = [1000.0]
    widget = MainApp(qt_app)
    widget._uncaught_repeats = main._Repeats(60.0, clock=lambda: clock[0])
    try:
        install_stop_handlers(widget, set_handler=lambda n, h: None)

        def _breaks():
            return 1 / 0

        for _ in range(5):
            sys.excepthook(*_raised(_breaks))
            clock[0] += 1.0
        assert sum("Uncaught error" in line for line in _log(widget)) == 1
        assert len(printed) == 1
        # Another error is its own line.
        sys.excepthook(*_raised(lambda: {}["missing"]))
        assert sum("Uncaught error" in line for line in _log(widget)) == 2
        clock[0] += 60.0
        sys.excepthook(*_raised(_breaks))
        last = _log(widget)[-1]
        assert "; outputs held, the program carries on; 4 more like it since " in last
        assert sum("Uncaught error" in line for line in _log(widget)) == 3
        assert len(printed) == 3
    finally:
        widget.stop_signal_timer.stop()
        widget.abort_all_threads()


def test_an_error_on_a_worker_thread_reaches_the_log_and_stops_nothing(qt_app, home):
    """A hardware worker's slot runs on its own `QThread`, and PyQt calls the
    hook there. Before, the line went to stderr alone; now it crosses to the
    main thread, which writes the Log."""
    import threading
    import time

    from PyQt5 import QtCore

    from controlunit.main import MainApp, install_stop_handlers

    printed = []
    sys.excepthook = lambda *args: printed.append(args)
    widget = MainApp(qt_app)
    exits = []
    widget._exit_program = exits.append

    class Breaking(QtCore.QObject):
        @QtCore.pyqtSlot()
        def run(self):
            self.thread_seen = threading.current_thread()
            raise RuntimeError("the board said no")

    thread = QtCore.QThread()
    thread.setObjectName("ADC")
    breaking = Breaking()
    breaking.moveToThread(thread)
    thread.started.connect(breaking.run)
    try:
        install_stop_handlers(widget, set_handler=lambda n, h: None)
        thread.start()
        deadline = time.monotonic() + 5
        while not printed and time.monotonic() < deadline:
            time.sleep(0.01)
        assert printed and printed[0][0] is RuntimeError
        qt_app.processEvents()
        line = _log(widget)[-1]
        assert line.startswith(
            "Uncaught error on ADC: RuntimeError: the board said no (in run,"
            " test_program_end.py line ")
        assert line.endswith("; outputs held")
        assert breaking.thread_seen is not threading.main_thread()
        widget._take_pending_stop()
        assert exits == [] and widget._stop_pending is None
    finally:
        thread.quit()
        thread.wait(5000)
        widget.stop_signal_timer.stop()
        widget.abort_all_threads()


def test_once_ending_has_begun_sigterm_and_sigint_end_it_at_once(qt_app, home):
    """A shutdown that hangs runs no event loop, so a noted signal would be
    the last thing that happened: SIGTERM and SIGINT get their default back.
    SIGHUP keeps its handler, for a terminal that closes twice."""
    from controlunit.main import MainApp, install_stop_handlers

    handlers = {}
    widget = MainApp(qt_app)
    exits = []
    widget._exit_program = exits.append
    try:
        install_stop_handlers(widget, set_handler=lambda n, h: handlers.__setitem__(n, h))
        widget.start_acquisition()
        assert handlers[signal.SIGTERM] == widget._signal_received
        widget._signal_received(signal.SIGTERM, None)
        widget._take_pending_stop()
        assert exits == [128 + signal.SIGTERM]
        assert handlers[signal.SIGTERM] == signal.SIG_DFL
        assert handlers[signal.SIGINT] == signal.SIG_DFL
        if hasattr(signal, "SIGHUP"):
            assert handlers[signal.SIGHUP] == widget._signal_received
    finally:
        widget.stop_signal_timer.stop()
        widget.abort_all_threads()


def test_the_window_closed_on_a_run_stops_it_first(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        cathode, gas = _running_with_outputs(widget)
        widget._window_closed()  # lastWindowClosed
        widget._closing()  # aboutToQuit
        assert not widget.workers
        assert (0,) in cathode.calls and (2, 0) in gas.calls
        assert _log(widget)[-1] == (
            "Program closing: the window was closed; the run was stopped first,"
            " outputs to zero"
        )
    finally:
        widget.abort_all_threads()


def test_the_quit_button_and_an_unknown_end_say_so(qt_app, home):
    from controlunit.main import MainApp

    class App:
        quits = 0

        def quit(self):
            App.quits += 1

    widget = MainApp(qt_app)
    real_app = widget._MainApp__app
    try:
        widget._MainApp__app = App()
        widget.control_dock.quitBtn.click()
        assert App.quits == 1
        widget._closing()
        assert _log(widget)[-1] == "Program closing: the Quit button was pressed"
    finally:
        widget._MainApp__app = real_app
        widget.abort_all_threads()

    other = MainApp(qt_app)
    try:
        other._closing()
        assert _log(other)[-1] == (
            "Program closing: no reason recorded; the event loop was ended from elsewhere"
        )
    finally:
        other.abort_all_threads()


def test_closing_ends_the_program_s_helpers_before_the_last_line(qt_app, home):
    from controlunit import pi_health
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_pi_health(
            read=lambda: pi_health.Reading(None, None, None, 0.0), interval=60.0
        )
        widget._closing()
        assert not widget._pi_health.thread.is_alive()
        assert _log(widget)[-1].startswith("Program closing: ")
    finally:
        widget.abort_all_threads()


def test_closing_writes_its_line_whatever_a_helper_s_stop_raises(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        def broken():
            raise RuntimeError("the helper would not stop")

        widget._stop_diagram_follower = broken
        widget._stop_pi_health = broken
        widget._window_closed()
        widget._closing()
        assert _log(widget)[-1] == "Program closing: the window was closed"
    finally:
        widget.abort_all_threads()

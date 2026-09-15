"""The Qt half of starting, stopping and sampling from a browser.

Two things nothing else can check. First, that the sampling times a browser
may ask for are the very items the Settings dock's combo offers: two lists in
two files that must never drift, so the dock is built offscreen and compared.

Second, the whole path in one piece — a command queued the way the Flask
thread queues one, drained the way the main thread's timer drains one, and a
real `MainApp` with the dummy hardware at the far end. It is the only test
here that starts worker threads, so it stops them again whatever happens.

The home directory is redirected before the app is built, so the data file
and the log this makes land in the test's own folder and never in the
owner's. Nothing in this file touches the rig.
"""

import os

import pytest

# Before PyQt is imported by anything: these tests draw no window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit.web import commands  # noqa: E402


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
    """A home of this test's own: no data file lands in the owner's."""
    place = tmp_path / "home"
    place.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(place))
    monkeypatch.setenv("HOMEDRIVE", "")
    monkeypatch.setenv("HOMEPATH", "")
    assert os.path.expanduser("~") == str(place)
    return place


def test_the_browser_offers_exactly_the_sampling_times_the_dock_does(qt_app):
    """One list of choices, in two files, held equal here and nowhere else."""
    from controlunit.ui.docks.settings import SettingsDock

    dock = SettingsDock()
    items = [
        dock.samplingCb.itemText(index)
        for index in range(dock.samplingCb.count())
    ]
    assert items == [commands.sampling_label(s) for s in commands.SAMPLING_CHOICES]
    # And the label a browser's value is matched against is one of them, so
    # `set_sampling` can always find the item to select.
    for seconds in commands.SAMPLING_CHOICES:
        assert dock.samplingCb.findText(commands.sampling_label(seconds)) >= 0


def test_the_browser_s_cathode_bound_is_the_dock_s(qt_app):
    """One bound for the manual cathode drive, in two files, held equal."""
    from controlunit.ui.docks.plasma_current import PlasmaCurrentDock

    dock = PlasmaCurrentDock()
    assert dock.cathode_spin_box.maximum() == commands.CATHODE_MAX_MV
    assert dock.CATHODE_MAX_MV == commands.CATHODE_MAX_MV
    assert dock.ampere_spin_box.maximum() == commands.PLASMA_MAX_A


def test_a_browser_starts_stops_and_retimes_a_real_run(qt_app, home):
    """The whole path: queue, drain, workers, and the record a browser reads.

    Stopping leaves the Remote switch exactly as the person at the rig set
    it — the one invariant this slice deliberately changed.
    """
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.control_dock.remoteSW.setChecked(True)
        widget._toggle_remote()
        assert widget.web_status.read()["remote"] is True

        widget.web_commands.submit("start", {}, actor="tester", origin="10.0.0.9")
        assert commands.drain(widget) == 1
        assert widget.web_status.read()["acquiring"] is True
        # The rig's own screen agrees with what the browser did.
        assert widget.control_dock.OnOffSW.isChecked() is True
        assert widget.web_status.read()["last_command"]["outcome"] == commands.APPLIED

        # Starting again is refused rather than laying a second set of
        # workers over the first.
        widget.web_commands.submit("start", {}, actor="tester", origin="10.0.0.9")
        commands.drain(widget)
        again = widget.web_status.read()["last_command"]
        assert again["outcome"] == commands.REFUSED
        assert again["reason"] == commands.ALREADY_ACQUIRING
        assert widget.web_status.read()["acquiring"] is True

        widget.web_commands.submit(
            "sampling", {"seconds": 1.0}, actor="tester", origin="10.0.0.9"
        )
        commands.drain(widget)
        assert widget.sampling == 1.0
        assert widget.settings_dock.samplingCb.currentText() == "1 s"
        assert widget.web_status.read()["sampling"] == 1.0

        widget.web_commands.submit("stop", {}, actor="tester", origin="10.0.0.9")
        commands.drain(widget)
        assert widget.web_status.read()["acquiring"] is False
        assert widget.control_dock.OnOffSW.isChecked() is False
        # The switch is the rig's own, and stopping no longer takes it down.
        assert widget.web_status.read()["remote"] is True
        assert widget.control_dock.remoteSW.isChecked() is True
        # The lock is let go of, so the next browser is not shut out.
        assert widget.web_commands.control.read()["holder"] == ""

        # And a browser may start again straight away.
        widget.web_commands.submit("start", {}, actor="tester", origin="10.0.0.9")
        commands.drain(widget)
        assert widget.web_status.read()["acquiring"] is True
    finally:
        widget.abort_all_threads()


def test_a_real_run_at_one_second_sampling_delivers_averaged_samples(qt_app, home):
    """The averaging path, end to end, in a real worker thread.

    At one second and slower the ADC worker fills each period with
    conversions and records their mean. Here the point is only that the
    rows still arrive, one per period, through the same Qt signal as
    before; what the mean is made of is checked in `test_adc_average.py`.
    """
    import time

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        widget.set_sampling(1.0)
        assert widget.workers["ADC"]["worker"].sampling_time == 1.0

        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline and len(widget.datadict["ADC"]) < 2:
            qt_app.processEvents()
            time.sleep(0.02)

        assert len(widget.datadict["ADC"]) >= 2
    finally:
        widget.abort_all_threads()


def test_dummy_kikusui_records_with_the_run_and_stops_after_hardware(qt_app, home, monkeypatch):
    import time

    from controlunit.devices.kikusui import ReadOnlyClient
    from controlunit.main import MainApp

    config = home / ".controlunit"
    config.mkdir()
    (config / "kikusui.yml").write_text("dummy: true\ninterval_s: 0.1\n")
    # Even an accidental construction of a network client fails this off-rig check.
    monkeypatch.setattr(ReadOnlyClient, "__init__", lambda *args: pytest.fail("real PSU access"))
    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        logger = widget._kikusui_logger
        assert logger is not None
        widget.web_status.record_setpoints(cathode_mv=1500)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if logger.path.exists() and ",1500," in logger.path.read_text():
                break
            time.sleep(0.02)
        assert ",1500," in logger.path.read_text()
        assert ",dummy," in logger.path.read_text()
        widget._refresh_kikusui_display()
        shown = widget.control_dock.valueBw.toPlainText()
        assert "Uc·SIM = 0.000" in shown and "Ic·SIM = 0.000" in shown
        assert widget.web_status.read()["kikusui"]["status"] == "dummy"
        original_stop = logger.stop

        def stop_after_hardware():
            assert widget.workers == {}
            assert widget.web_status.read()["setpoints"]["cathode_mv"] == 0
            return original_stop()

        monkeypatch.setattr(logger, "stop", stop_after_hardware)
        widget.stop_acquisition()
        assert widget._kikusui_logger is None
        assert not logger.thread.is_alive()
        assert "Uc = —" in widget.control_dock.valueBw.toPlainText()
        assert widget.web_status.read()["kikusui"]["status"] == "idle"
        assert "Uc·SIM" not in widget.control_dock.valueBw.toPlainText()
    finally:
        widget.abort_all_threads()


def test_a_slow_kikusui_stop_does_not_block_the_next_run(qt_app, home, monkeypatch):
    """A stop that outlives its wait keeps the reference; once that thread has
    actually ended, the next Start records again instead of refusing forever."""
    from controlunit.devices.kikusui import ReadOnlyClient
    from controlunit.main import MainApp

    config = home / ".controlunit"
    config.mkdir()
    (config / "kikusui.yml").write_text("dummy: true\ninterval_s: 0.1\n")
    monkeypatch.setattr(ReadOnlyClient, "__init__", lambda *args: pytest.fail("real PSU access"))
    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        first = widget._kikusui_logger
        assert first is not None

        def slow_stop():
            first.stopping.set()
            first.client.close()
            return False  # The wait ran out before the thread ended.

        monkeypatch.setattr(first, "stop", slow_stop)
        widget.stop_acquisition()
        assert widget._kikusui_logger is first

        # While the old thread is genuinely alive a new recorder is refused.
        # Its own patch context: undoing the test's monkeypatch would also
        # undo the redirected home and read the owner's own configuration.
        with pytest.MonkeyPatch.context() as alive:
            alive.setattr(first.thread, "is_alive", lambda: True)
            widget.start_acquisition()
            assert widget._kikusui_logger is first
            widget.stop_acquisition()
        first.thread.join(2)
        assert not first.thread.is_alive()

        widget.start_acquisition()
        second = widget._kikusui_logger
        assert second is not None and second is not first
        assert second.thread.is_alive()
        widget.stop_acquisition()
        assert widget._kikusui_logger is None
    finally:
        widget.abort_all_threads()


def test_every_gauge_selector_reaches_a_freshly_started_worker(qt_app, home):
    """What the selectors show before Start is what the new worker runs
    with, for every gauge, not only the first one."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        pd_mode, pd_range = widget.control_dock.gauges["Pd"]
        pu2_mode, pu2_range = widget.control_dock.gauges["Pu2"]
        pd_range.setValue(-8)
        pu2_range.setValue(-6)
        pu2_mode.setCurrentIndex(1)  # Pa
        widget.start_acquisition()
        worker = widget.workers["ADC"]["worker"]
        assert worker._gauge_settings["Pd"] == {"mode": 0, "scale": -8}
        assert worker._gauge_settings["Pu2"] == {"mode": 1, "scale": -6}
        gauges = widget.web_status.read()["setpoints"]["gauges"]
        assert gauges["Pd"] == {"mode": "Torr", "range": -8}
        assert gauges["Pu2"] == {"mode": "Pa", "range": -6}
        widget.stop_acquisition()
    finally:
        widget.abort_all_threads()


def test_dummy_hardware_refuses_a_real_kikusui_config(qt_app, home, monkeypatch):
    from controlunit.devices.kikusui import ReadOnlyClient
    from controlunit.main import MainApp

    config = home / ".controlunit"
    config.mkdir()
    (config / "kikusui.yml").write_text("host: 127.0.0.1\n")
    monkeypatch.setattr(ReadOnlyClient, "__init__", lambda *args: pytest.fail("real PSU access"))
    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        assert widget._kikusui_logger is None
        assert widget.workers
    finally:
        widget.abort_all_threads()


def test_kikusui_display_clears_numbers_on_loss(qt_app, home):
    """The supply's numbers stand in the value browser while the telemetry
    is fresh and read as dashes the moment it is not; simulated data is
    marked so it is never taken for a measurement."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget._publish_kikusui({"status": "ok", "voltage_v": 2.4, "current_a": 12, "output_on": 1})
        shown = widget.control_dock.valueBw.toPlainText()
        assert "Uc = 2.400" in shown and "Ic = 12.000" in shown
        widget._publish_kikusui({"status": "unavailable"})
        shown = widget.control_dock.valueBw.toPlainText()
        assert "12.000" not in shown and "Uc = —" in shown and "Ic = —" in shown
        widget._publish_kikusui({"status": "dummy", "voltage_v": 0.0, "current_a": 0.0, "output_on": 0})
        assert "Uc·SIM = 0.000" in widget.control_dock.valueBw.toPlainText()
    finally:
        widget.abort_all_threads()
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
    # The settings folder, where the screen is remembered, follows the home.
    monkeypatch.delenv("CONTROLUNIT_SETTINGS_HOME", raising=False)
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


def test_the_cathode_dock_carries_the_supply_s_own_output_switch(qt_app):
    """Two buttons for the wire the drive does not reach (owner decision
    2026-09-15): the supply's output, off and on, beside the drive rows."""
    from controlunit.ui.docks.plasma_current import PlasmaCurrentDock

    dock = PlasmaCurrentDock()
    assert dock.output_off_btn.text() == "output off"
    assert dock.output_on_btn.text() == "output on"
    # And they are not a third way to drive the filament: nothing about them
    # is a value.
    assert not hasattr(dock, "output_spin_box")


def test_remote_starts_enabled_and_local_still_revokes_it(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        assert widget.control_dock.remoteSW.isChecked()
        assert widget.web_status.read()["remote"] is True
        assert not widget.workers  # enabling Remote does not start acquisition
        widget.control_dock.remoteSW.click()
        assert not widget.control_dock.remoteSW.isChecked()
        assert widget.web_status.read()["remote"] is False
    finally:
        widget.abort_all_threads()


def test_the_refusal_is_worded_once_for_the_rig_and_the_browser(qt_app):
    from controlunit.main import MainApp

    assert MainApp.NO_SUPPLY_ANSWER == commands.NO_SUPPLY_ANSWER
    assert MainApp.NO_SUPPLY_LINK == commands.NO_SUPPLY_LINK


def test_the_supply_s_output_is_switched_on_dummy_hardware(qt_app, home, monkeypatch):
    """The whole press on the main thread, with dummy hardware at the far end.

    The dock's own button and the browser's command reach one method; the
    recorder's thread carries the write; the dummy's flag moves; and every
    sentence says SIMULATED, so a simulated press is never read as a real one.
    """
    import time

    from controlunit.devices.kikusui import ReadOnlyClient
    from controlunit.main import MainApp

    config = home / ".controlunit"
    config.mkdir()
    (config / "kikusui.yml").write_text("dummy: true\ninterval_s: 0.1\n")
    monkeypatch.setattr(ReadOnlyClient, "__init__", lambda *args: pytest.fail("real PSU access"))
    widget = MainApp(qt_app)
    try:
        widget.control_dock.remoteSW.setChecked(True)
        widget._toggle_remote()
        widget.start_acquisition()
        logger = widget._kikusui_logger
        assert logger is not None

        def wait_for(predicate, seconds=3):
            end = time.monotonic() + seconds
            while time.monotonic() < end and not predicate():
                qt_app.processEvents()
                time.sleep(0.02)
            assert predicate()

        wait_for(lambda: widget.web_status.read()["kikusui"].get("output_on") == 0)

        # On, from the browser's own path: queued, drained, and carried by
        # the recorder's thread rather than this one.
        widget.web_commands.submit(
            "cathode_output", {"on": True}, actor="tester", origin="10.0.0.9"
        )
        assert commands.drain(widget) == 1
        assert widget.web_status.read()["last_command"]["outcome"] == commands.APPLIED
        wait_for(lambda: logger.client.output_on == 1)
        wait_for(lambda: any("output ON SIMULATED" in m for m in _log_of(widget)))

        # Off, from the rig's own dock button, which is the same method.
        widget.plasma_control_dock.output_off_btn.click()
        wait_for(lambda: logger.client.output_on == 0)
        wait_for(lambda: any("output OFF SIMULATED" in m for m in _log_of(widget)))
        assert ",output_on," in logger.path.read_text()
        assert ",output_off," in logger.path.read_text()
    finally:
        widget.abort_all_threads()


def test_the_supply_is_not_switched_on_while_nothing_can_see_it(qt_app, home):
    """No recorder, no fresh reading, no closing an output onto a filament."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        sent, reason = widget.turn_on_cathode_output()
        assert sent is False
        assert reason == commands.NO_SUPPLY_ANSWER
        # Off asks none of that; here there is simply no link configured, and
        # the rig says so rather than pretending a write went out.
        widget._publish_kikusui({"status": "unavailable"})
        sent, reason = widget.turn_off_cathode_output()
        assert sent is False
        assert reason == commands.NO_SUPPLY_LINK
        assert any("output OFF not sent" in m for m in _log_of(widget))
    finally:
        widget.abort_all_threads()


def test_a_failed_supply_press_reaches_the_log_and_the_browser_s_answer(qt_app, home):
    """The link's failure sentence goes to the Log as every link line does,
    and marks the browser's press failed with it (queezz, 2026-10-07)."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        press = commands.Command(3, "cathode_output", {"on": False}, actor="queezz")
        widget.web_status.record_command(press.as_record(commands.APPLIED))
        why = ("Kikusui output OFF FAILED: the supply's LAN did not answer. Press "
               "OUTPUT on the supply, or power-cycle it to bring its LAN back; the "
               "DAC drive is unchanged.")
        widget._kikusui_said(why)
        assert why in _log_of(widget)
        last = widget.web_status.read()["last_command"]
        assert (last["outcome"], last["reason"]) == ("failed", why)
        # Any other line from the link is only a Log line.
        widget._kikusui_said("Kikusui telemetry BACK: recording fresh measurements")
        assert widget.web_status.read()["last_command"]["reason"] == why
    finally:
        widget.abort_all_threads()


def _log_of(widget):
    """The message log as the Log tab reads it."""
    return [line["text"] for line in widget.web_status.log_since(0)["lines"]]


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


def test_a_gauge_declared_off_on_the_dock_reaches_the_worker_and_the_record(qt_app, home):
    """queezz, 2026-10-07: "I need a toggle in ControlUnit for IGs to be off."
    The dock's box has a third item, Off; choosing it tells the worker mode 2
    through the existing signal, the record says Off, and the dock's own
    readout writes the word rather than a NaN."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        pu2_mode, _ = widget.control_dock.gauges["Pu2"]
        assert [pu2_mode.itemText(i) for i in range(pu2_mode.count())] == list(
            commands.GAUGE_MODES)
        pu2_mode.setCurrentIndex(2)
        widget.start_acquisition()
        worker = widget.workers["ADC"]["worker"]
        assert worker._gauge_settings["Pu2"]["mode"] == 2
        assert widget.web_status.read()["setpoints"]["gauges"]["Pu2"]["mode"] == "Off"
        seen = []
        widget.control_dock.update_current_values = seen.append
        widget._render_value_browser()
        pu2 = [entry for entry in seen[-1] if entry[1] == "Pu2"]
        assert pu2 and pu2[0][2] == "off"
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

def test_the_cathode_curve_is_recorded_only_from_a_fresh_sidecar_row(qt_app, home):
    """The `Ic` curve the Live page draws is fed here, on the main thread,
    from the recorder's own snapshot (owner ask 2026-09-15, "we need to add
    cathode current to the current plot").

    Three rules, all because this is a LAN reading and not an ADC sample:
    only `ok` and `dummy` carry measurements, so nothing else is recorded; a
    point is stamped with the sidecar row's own time rather than this
    moment; and a snapshot republished unchanged — which the 500 ms display
    timer does whenever the 2 Hz recorder has not written a new row — never
    lays the same point down twice.
    """
    import datetime

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        first = datetime.datetime(2026, 9, 15, 21, 40, 3, tzinfo=datetime.timezone.utc)
        second = first + datetime.timedelta(seconds=0.5)
        fresh = {"status": "ok", "voltage_v": 2.4, "current_a": 12.0,
                 "output_on": 1, "date": first.isoformat()}
        widget._publish_kikusui(dict(fresh))
        widget._publish_kikusui(dict(fresh))          # the same row, looked at again
        widget._publish_kikusui({"status": "unavailable", "date": second.isoformat()})
        widget._publish_kikusui({"status": "stale"})
        widget._publish_kikusui(dict(fresh, current_a=12.5, date=second.isoformat()))
        # A fresh row with no timestamp at all is not guessed a time for.
        widget._publish_kikusui({"status": "ok", "voltage_v": 2.4, "current_a": 99.0,
                                 "output_on": 1})

        body = widget.web_status.series(window_seconds=0)
        assert body["channels"]["Ic"] == [
            [first.timestamp(), 12.0], [second.timestamp(), 12.5]
        ]
        assert body["channels"]["Uc"] == [
            [first.timestamp(), 2.4], [second.timestamp(), 2.4]
        ]
        # And none of it is an ADC sample.
        assert body["count"] == 0
        assert widget.web_status.read()["samples"] == 0
    finally:
        widget.abort_all_threads()


def _panel_lines(widget):
    """The Log panel's lines, as the rig's screen shows them."""
    return widget.logDock.log.toPlainText().split("\n")


def _file_lines(widget):
    with open(widget.config["Log File Path"]) as log:
        return log.read().splitlines()


def test_the_log_panel_is_capped_and_shows_the_newest_line_last(qt_app, home):
    """The rig's logs of 2026-10-21: every line used to rebuild the whole
    panel, so a line cost as much as the panel was long and held the reader
    still while it did. A line is added at the end now, and the panel keeps
    the newest `LOG_PANEL_LINES`; the file and the web view keep the rest."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        cap = MainApp.LOG_PANEL_LINES
        widget.log_message("<font color='#1cad47'>Starting</font> acquisition", htmltag="h2")
        widget.log_message("the line after a heading")
        blocks = widget.logDock.log.document()
        heading = blocks.begin()
        while heading.isValid() and "Starting" not in heading.text():
            heading = heading.next()
        # A heading keeps its shape and does not lend it to the next line.
        assert heading.blockFormat().headingLevel() == 2
        assert heading.next().blockFormat().headingLevel() == 0
        assert "the line after a heading" in heading.next().text()

        total = cap + 500
        for number in range(total):
            widget.log_message(f"line {number}", htmltag="div" if number % 2 else "p")
        assert blocks.blockCount() == cap
        lines = _panel_lines(widget)
        assert len(lines) == cap
        assert lines[-1].endswith(f": line {total - 1}")
        assert lines[0].endswith(f": line {total - cap}")
        # The file is the record and keeps every line.
        assert _file_lines(widget)[-1].endswith(f", line {total - 1}")
    finally:
        widget.abort_all_threads()


def test_routine_timing_reports_stay_off_the_panel_and_overruns_do_not(qt_app, home):
    """The thirty-second timing summaries, ~5800 lines a day, are kept in the
    file and the web view's Log exactly as before and left off the panel; an
    overrun still goes to the panel. Through the real worker wiring, and the
    main thread's own delivery summary as `_adc_step` builds it."""
    from controlunit.devices.timing import TimingDiagnostics
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        reader = widget.workers["ADC"]["worker"]
        routine = ("ADC timing: 300 observations in 30.0 s; read mean/max 1.0/2.0 ms;"
                   " missed slots 0")
        overrun = ("ADC timing overrun: 4 observations in 0.5 s; read mean/max"
                   " 1.0/450.0 ms; missed slots 1")
        reader.send_routine.emit(routine)
        reader.send_message.emit(overrun)
        qt_app.processEvents()

        clock = [0.0]
        delivery = TimingDiagnostics(
            "ADC delivery", widget.log_message, clock=lambda: clock[0],
            routine=widget.log_routine,
        )
        clock[0] = 31.0
        delivery.observe({"total": 0.01})
        delivery.observe({"total": 0.9}, slow=True)

        panel = "\n".join(_panel_lines(widget))
        web = _log_of(widget)
        files = _file_lines(widget)
        assert routine in web and any(line.endswith(", " + routine) for line in files)
        assert routine not in panel
        assert overrun in web and overrun in panel
        said = [line for line in web if line.startswith("ADC delivery: ")]
        overran = [line for line in web if line.startswith("ADC delivery overrun: ")]
        assert said and overran
        assert said[0] not in panel
        assert overran[0] in panel
        assert any(line.endswith(", " + said[0]) for line in files)
    finally:
        widget.abort_all_threads()


def test_a_restart_runs_with_the_sampling_the_screen_shows(qt_app, home):
    """2026-10-19: 10 s was chosen from a browser, then Stop and Start; the
    new reader took settings.yml's 0.1 s while the dock and the web view
    still said 10 s, and two days were recorded at 0.1 s unseen. queezz:
    "it should remember settings, not run with whatever is default and
    invisible"."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        assert widget.config["Sampling Time"] != 10.0  # the default is not the choice
        widget.start_acquisition()
        widget.set_sampling(10)
        widget.stop_acquisition()
        widget.start_acquisition()
        reader = widget.workers["ADC"]["worker"]
        assert reader.sampling_time == 10.0
        assert reader.STEP == 1
        assert widget.sampling == 10.0
        assert widget.settings_dock.samplingCb.currentText() == "10 s"
        assert widget.web_status.read()["sampling"] == 10.0
        assert "Started with sampling 10 s" in _log_of(widget)

        # The same from a browser's Stop and Start, through the queue.
        widget.control_dock.remoteSW.setChecked(True)
        widget._toggle_remote()
        for kind, body in (("sampling", {"seconds": 1.0}), ("stop", {}), ("start", {})):
            widget.web_commands.submit(kind, body, actor="tester", origin="10.0.0.9")
            assert commands.drain(widget) == 1
        assert widget.web_status.read()["acquiring"] is True
        assert widget.workers["ADC"]["worker"].sampling_time == 1.0
        assert widget.web_status.read()["sampling"] == 1.0
    finally:
        widget.abort_all_threads()


def test_the_sampling_shown_before_the_first_start_is_the_one_it_runs_with(qt_app, home):
    """The combo starts at settings.yml's value, so the screen, the watchdog
    and the web view agree from the start; and what it shows when Start is
    pressed is what the first run takes."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        configured = float(widget.config["Sampling Time"])
        assert widget.settings_dock.samplingCb.currentText() == f"{configured:g} s"
        assert widget.sampling == configured
        assert widget.web_status.read()["sampling"] == configured

        widget.settings_dock.samplingCb.setCurrentIndex(
            widget.settings_dock.samplingCb.findText("1 s")
        )
        widget.start_acquisition()
        assert widget.workers["ADC"]["worker"].sampling_time == 1.0
        assert widget.web_status.read()["sampling"] == 1.0
    finally:
        widget.abort_all_threads()


def test_a_restart_drives_nothing(qt_app, home):
    """Settings are remembered across Stop and Start; outputs are not. Gas,
    the cathode drive and the PID start at zero and off after a restart."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        widget.plasma_control_dock.cathode_spin_box.setValue(1500)
        widget.set_cathode_drive()
        widget._mfc_presets = {1: 1200, 2: 300}
        widget.stop_acquisition()
        widget.start_acquisition()
        reader = widget.workers["ADC"]["worker"]
        assert reader.plasma_current_setpopint == 0
        assert reader.control_voltage == 0
        assert reader._mfc_presets == {1: 0.0, 2: 0.0}
        setpoints = widget.web_status.read()["setpoints"]
        assert setpoints["cathode_mv"] == 0
        assert setpoints["plasma_a"] == 0
        assert setpoints["mfc1_v"] == 0 and setpoints["mfc2_v"] == 0
    finally:
        widget.abort_all_threads()


def test_hold_hands_the_cathode_to_the_hand_at_the_loop_s_drive(qt_app, home):
    """2026-11-13: "PID off" zeroed the drive and put out two discharges the
    loop had just brought to 1.5 A. Hold turns the PID off and keeps the
    drive the loop was giving, as Manual."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        reader = widget.workers["ADC"]["worker"]
        sent = []
        widget.workers["PlasmaCurrent"]["worker"].output_voltage_signal.connect(sent.append)
        reader.control_voltage = 2211.4          # the loop's last command
        reader.plasma_current_setpopint = 1.5
        widget.hold_currentcontrol_voltage()
        qt_app.processEvents()
        assert sent and sent[-1] == 2211
        assert 0 not in sent
        assert widget.plasma_control_dock.cathode_spin_box.value() == 2211
        assert widget.plasma_control_dock.ampere_spin_box.value() == 0.0
        setpoints = widget.web_status.read()["setpoints"]
        assert setpoints["cathode_mv"] == 2211 and setpoints["plasma_a"] == 0
        assert reader.plasma_current_setpopint == 0
        assert "Cathode drive set to 2211 mV, PID off" in widget.web_status.log_since(0)["lines"][-1]["text"]
    finally:
        widget.abort_all_threads()


# -- the gauges follow the PIHTI Diagram (queezz, 2026-11-13) ----------------
#
# "Gauge left off, maybe we sync from the journal? Why should we turn that
# off twice??" These drive `_follow_diagram` with answers already fetched,
# as the follower's timer slot does; the asking itself, on its own thread,
# is in test_diagram_follower.py, and one test below runs it end to end
# against a stand-in Diagram on this machine's loopback.

DIAGRAM_PD = "downstream-ionization-gauge"
DIAGRAM_PU2 = "bypass-ionization-gauge"


def _diagram(pd="active", pu2="active"):
    return {DIAGRAM_PD: pd, DIAGRAM_PU2: pu2, "turbo-pump": "active"}


def _count(widget, text):
    return sum(1 for line in _log_of(widget) if text in line)


def test_a_gauge_follows_the_diagram_off_and_back_to_the_mode_it_had(qt_app, home):
    from controlunit import screen_memory
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        pu2_mode, _ = widget.control_dock.gauges["Pu2"]
        pd_mode, _ = widget.control_dock.gauges["Pd"]
        pu2_mode.setCurrentIndex(1)  # Pa, by hand on the dock
        lines = len(_log_of(widget))

        # The first answer: both on, both already reading; nothing to do.
        widget._follow_diagram(_diagram())
        assert len(_log_of(widget)) == lines

        widget._follow_diagram(_diagram(pu2="inactive"))
        assert pu2_mode.currentText() == "Off"
        assert pd_mode.currentText() == "Torr"
        off = "Pu2 declared off: the Diagram shows the upstream ion gauge off"
        assert _log_of(widget)[-1] == off
        # One line, the Diagram's: not also the dock-press line.
        assert _count(widget, "Pu2 declared off") == 1
        assert widget.web_status.read()["setpoints"]["gauges"]["Pu2"]["mode"] == "Off"
        assert screen_memory.read_screen()[0]["gauges"]["Pu2"]["mode"] == "Off"

        # Polls that say the same say nothing.
        for _ in range(3):
            widget._follow_diagram(_diagram(pu2="inactive"))
        assert _count(widget, "Pu2 declared off") == 1

        widget._follow_diagram(_diagram())
        assert pu2_mode.currentText() == "Pa"
        assert _log_of(widget)[-1] == (
            "Pu2 in Pa: the Diagram shows the upstream ion gauge on")
        assert widget.web_status.read()["setpoints"]["gauges"]["Pu2"]["mode"] == "Pa"
        assert screen_memory.read_screen()[0]["gauges"]["Pu2"]["mode"] == "Pa"

        # A gauge never seen reading in anything else comes back in Torr.
        widget._follow_diagram(_diagram(pd="inactive"))
        widget._follow_diagram(_diagram())
        assert pd_mode.currentText() == "Torr"
        assert _log_of(widget)[-1] == (
            "Pd in Torr: the Diagram shows the downstream ion gauge on")
    finally:
        widget.abort_all_threads()


def test_the_first_answer_after_launch_takes_the_diagram_s_word(qt_app, home):
    """A gauge switched off while the program was down comes back declared
    off, whatever the remembered screen said."""
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget._follow_diagram(_diagram(pd="inactive"))
        assert widget.control_dock.gauges["Pd"][0].currentText() == "Off"
        assert widget.control_dock.gauges["Pu2"][0].currentText() == "Torr"
        # Start carries the Diagram's word into the worker.
        widget.start_acquisition()
        assert widget.workers["ADC"]["worker"]._gauge_settings["Pd"]["mode"] == 2
    finally:
        widget.abort_all_threads()


def test_a_press_after_the_diagram_s_change_holds_until_it_changes_again(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        pd_mode, _ = widget.control_dock.gauges["Pd"]
        widget._follow_diagram(_diagram(pd="inactive"))
        assert pd_mode.currentText() == "Off"

        pd_mode.setCurrentIndex(0)  # a hand on the dock: Torr
        assert _log_of(widget)[-1] == "Pd in Torr"
        for _ in range(3):
            widget._follow_diagram(_diagram(pd="inactive"))
        assert pd_mode.currentText() == "Torr"

        # The Diagram turns it on: it already reads, so nothing moves.
        lines = len(_log_of(widget))
        widget._follow_diagram(_diagram())
        assert pd_mode.currentText() == "Torr"
        assert len(_log_of(widget)) == lines

        # And off again is a change again.
        widget._follow_diagram(_diagram(pd="inactive"))
        assert pd_mode.currentText() == "Off"
    finally:
        widget.abort_all_threads()


def test_an_unreachable_or_unreadable_diagram_changes_nothing_and_says_so_once(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        pd_mode, _ = widget.control_dock.gauges["Pd"]
        widget._follow_diagram(_diagram())
        for _ in range(4):
            widget._follow_diagram(None, "no answer within two seconds")
        assert pd_mode.currentText() == "Torr"
        assert _count(widget, "Gauges not following the Diagram") == 1
        assert _log_of(widget)[-1] == (
            "Gauges not following the Diagram: no answer within two seconds;"
            " gauge modes left as they are")

        widget._follow_diagram(_diagram(pd="inactive"))
        assert _count(widget, "Gauges following the Diagram again") == 1
        assert pd_mode.currentText() == "Off"

        # Malformed: not the states at all. Nothing moves; one line.
        widget._follow_diagram(["downstream-ionization-gauge"])
        widget._follow_diagram("<html>")
        assert pd_mode.currentText() == "Off"
        assert _count(widget, "Gauges not following the Diagram") == 2
    finally:
        widget.abort_all_threads()


def test_an_unmapped_gauge_is_not_followed(qt_app, home):
    from controlunit import diagram_follower
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        # As a rig whose settings give Pu2 no Diagram Element.
        widget._gauge_following = diagram_follower.GaugeFollowing({"Pd": DIAGRAM_PD})
        widget._follow_diagram(_diagram(pd="inactive", pu2="inactive"))
        assert widget.control_dock.gauges["Pd"][0].currentText() == "Off"
        assert widget.control_dock.gauges["Pu2"][0].currentText() == "Torr"
    finally:
        widget.abort_all_threads()


def test_no_address_means_no_follower_and_one_line(qt_app, home):
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        assert widget._diagram_follower is None
        assert _count(widget, "Gauges do not follow the Diagram: this machine has"
                              " no address for pihti-diagram") == 1
        assert widget._stop_diagram_follower() is True
    finally:
        widget.abort_all_threads()


def test_dummy_hardware_never_asks_the_rig_s_diagram(qt_app, home):
    from controlunit.main import MainApp

    folder = home / ".controlunit"
    folder.mkdir()
    (folder / "neighbours.yml").write_text(
        "pihti-diagram:\n  url: http://pihti:5000\n", encoding="utf-8")
    widget = MainApp(qt_app)
    try:
        assert widget._diagram_follower is None
        assert _count(widget, "dummy hardware never asks a Diagram on another"
                              " machine (http://pihti:5000)") == 1
    finally:
        widget.abort_all_threads()


def test_the_follower_runs_end_to_end_off_the_main_thread_and_stops(qt_app, home, monkeypatch):
    """neighbours.yml -> the follower's thread -> a stand-in Diagram on
    loopback -> the main thread's timer -> the dock's selector."""
    import http.server
    import json
    import threading
    import time

    from controlunit import diagram_follower
    from controlunit.main import MainApp

    body = {"answer": json.dumps(_diagram(pd="inactive")).encode()}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 -- http.server's own name
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body["answer"])

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    ).start()
    url = "http://127.0.0.1:{}".format(server.server_address[1])
    folder = home / ".controlunit"
    folder.mkdir()
    (folder / "neighbours.yml").write_text(
        "pihti-diagram:\n  url: {}\n".format(url), encoding="utf-8")

    asked_from = []
    real_fetch = diagram_follower.fetch_elements_state

    def recording_fetch(address, timeout=diagram_follower.TIMEOUT_SECONDS):
        asked_from.append(threading.current_thread())
        return real_fetch(address, timeout)

    monkeypatch.setattr(diagram_follower, "fetch_elements_state", recording_fetch)
    monkeypatch.setattr(diagram_follower, "POLL_SECONDS", 0.05)
    monkeypatch.setattr("controlunit.main.DIAGRAM_CHECK_MS", 20)

    def settle(predicate, seconds=5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            qt_app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        return False

    widget = MainApp(qt_app)
    pd_mode, _ = widget.control_dock.gauges["Pd"]
    try:
        follower = widget._diagram_follower
        assert follower is not None and follower.thread.is_alive()
        assert _count(widget, "Gauges follow the Diagram's on and off at " + url) == 1
        assert settle(lambda: pd_mode.currentText() == "Off")
        body["answer"] = json.dumps(_diagram()).encode()
        assert settle(lambda: pd_mode.currentText() == "Torr")
        assert _count(widget, "Pd declared off: the Diagram shows") == 1
        assert _count(widget, "Pd in Torr: the Diagram shows") == 1
    finally:
        stopped = widget._stop_diagram_follower()
        widget.abort_all_threads()
        server.shutdown()
        server.server_close()
    assert stopped
    assert not widget._diagram_follower.thread.is_alive()
    assert not widget.diagram_timer.isActive()
    assert asked_from
    assert threading.main_thread() not in asked_from


# -- a recorded switch held against the gauge's own volts ---------------------


def _history_around(edge, pd_volts, seconds=(-60, 120)):
    """A run history of one row a second around `edge`, as the window keeps
    it, with Pd's raw volts from `pd_volts(t)` and a live Pu2."""
    import datetime

    import pandas as pd

    from controlunit.history import RunHistory

    offsets = range(seconds[0], seconds[1] + 1)
    history = RunHistory()
    history.append(pd.DataFrame({
        "date": pd.to_datetime([edge + datetime.timedelta(seconds=t) for t in offsets]),
        "Pd": [pd_volts(t) for t in offsets],
        "Pu2": [2.0 for _ in offsets],
    }))
    return history


def test_a_recorded_off_the_signal_does_not_show_leaves_one_red_line(qt_app, home):
    """queezz, 2026-11-13: "When the diagram says the gauge is off, but the
    signal doesn't change, we should warn." The Diagram's edge is the
    trigger, the raw column the check, and the gauge keeps the Diagram's
    word either way."""
    import datetime

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        # An hour ago, so the dummy's own rows could not fall in the window
        # even if one were delivered (none is: no events are processed).
        edge = datetime.datetime.now() - datetime.timedelta(hours=1)
        widget.datadict["ADC"] = _history_around(edge, lambda t: 1.53)
        widget._follow_diagram(_diagram(pd="inactive"), at=edge)
        assert widget.control_dock.gauges["Pd"][0].currentText() == "Off"
        assert set(widget._switch_checks) == {"Pd", "Pu2"}

        widget._check_gauge_switches(now=edge + datetime.timedelta(seconds=30))
        # Pu2's first "on" is confirmed by its live 2 V and dropped in
        # silence; Pd's "off" waits for the end of its window.
        assert set(widget._switch_checks) == {"Pd"}
        widget._check_gauge_switches(now=edge + datetime.timedelta(seconds=91))
        warning = (
            "Pd: the Diagram shows the downstream ion gauge off, but Pd still"
            " reads 1.53 V, a live gauge's signal; is its controller still on,"
            " or was another gauge recorded?")
        assert _log_of(widget)[-1] == warning
        widget._check_gauge_switches(now=edge + datetime.timedelta(seconds=200))
        assert _count(widget, warning) == 1
        assert widget._switch_checks == {}
        assert widget.control_dock.gauges["Pd"][0].currentText() == "Off"
    finally:
        widget.abort_all_threads()


def test_a_recorded_off_the_signal_shows_says_nothing(qt_app, home):
    import datetime

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget._follow_diagram(_diagram())
        widget.start_acquisition()
        edge = datetime.datetime.now() - datetime.timedelta(hours=1)
        # Switched off at the controller 50 s before it was recorded.
        widget.datadict["ADC"] = _history_around(edge, lambda t: 1.5 if t < -50 else 0.002)
        widget._follow_diagram(_diagram(pd="inactive"), at=edge)
        lines = len(_log_of(widget))
        widget._check_gauge_switches(now=edge + datetime.timedelta(seconds=5))
        assert widget._switch_checks == {}
        widget._check_gauge_switches(now=edge + datetime.timedelta(seconds=91))
        assert len(_log_of(widget)) == lines
    finally:
        widget.abort_all_threads()


def test_a_switch_is_checked_only_while_a_run_records_and_ends_with_it(qt_app, home):
    import datetime

    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        # Not recording: nothing to check, and nothing is held.
        widget._follow_diagram(_diagram(pd="inactive"))
        assert widget._switch_checks == {}

        widget.start_acquisition()
        edge = datetime.datetime.now() - datetime.timedelta(hours=1)
        widget.datadict["ADC"] = _history_around(edge, lambda t: 0.002)
        widget._follow_diagram(_diagram(), at=edge)
        assert set(widget._switch_checks) == {"Pd"}
        # Stop drops it: the run that would have answered it is over.
        widget.stop_acquisition()
        assert widget._switch_checks == {}
        widget.start_acquisition()
        widget._check_gauge_switches(now=edge + datetime.timedelta(seconds=91))
        assert _count(widget, "the Diagram shows the downstream ion gauge on, but") == 0
    finally:
        widget.abort_all_threads()


def _window_stamp(moment):
    from controlunit import diagram_follower
    return diagram_follower._stamp(moment)


def test_a_recorded_switch_counts_from_the_diagram_s_own_time(qt_app, home):
    """The check's window and the Log line take the time the operator
    recorded the switch, from the Diagram's history, not the poll's."""
    import datetime as dt
    from controlunit.main import MainApp

    widget = MainApp(qt_app)
    try:
        widget.start_acquisition()
        widget._follow_diagram(_diagram())
        noticed = dt.datetime.now()
        pressed = noticed - dt.timedelta(seconds=40)
        recorded = {DIAGRAM_PD: {"inactive": (pressed, "KAA")}}
        widget._follow_diagram(_diagram(pd="inactive"), at=noticed, recorded=recorded)
        assert _log_of(widget)[-1] == (
            "Pd declared off: the Diagram shows the downstream ion gauge off"
            " (recorded {} by KAA)".format(pressed.strftime("%H:%M:%S")))
        check = widget._switch_checks["Pd"]
        assert check.start == _window_stamp(pressed - dt.timedelta(seconds=60))
        # A recorded time after the notice is not believed.
        later = {DIAGRAM_PD: {"active": (noticed + dt.timedelta(seconds=30), "KAA")}}
        widget._follow_diagram(_diagram(), at=noticed, recorded=later)
        assert "recorded" not in _log_of(widget)[-1]
        check = widget._switch_checks["Pd"]
        assert check.start == _window_stamp(noticed - dt.timedelta(seconds=60))
    finally:
        widget.abort_all_threads()

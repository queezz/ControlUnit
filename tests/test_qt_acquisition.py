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

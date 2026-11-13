"""The screen's gauges and sampling time, remembered across a restart.

A program restart on 2026-11-11 at 16:47:15 brought both ion gauges back at
settings.yml's Torr and 1e-3 and forgot that Pu2 was declared off, so Pd_c
read 1.5e-3 Torr for 18 s when the vessel was at about 1.5e-7; and a fresh
program started at settings.yml's 0.1 s sampling whatever the run before
had used. The same audit found the dock's own gauge presses left no line in
the Log, only in the file's IGmode and IGscale columns.

The file half is checked on its own; the rest through a real `MainApp`
with the dummy hardware. The home directory, and the settings folder under
it, are redirected before anything is built, so nothing here writes the
owner's `~/.controlunit`, and nothing here touches the rig.
"""

import json
import os

import pytest

# Before PyQt is imported by anything: these tests draw no window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit import screen_memory  # noqa: E402
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
    """A home of this test's own, and the settings folder inside it."""
    place = tmp_path / "home"
    place.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(place))
    monkeypatch.setenv("HOMEDRIVE", "")
    monkeypatch.setenv("HOMEPATH", "")
    monkeypatch.delenv("CONTROLUNIT_SETTINGS_HOME", raising=False)
    assert os.path.expanduser("~") == str(place)
    assert screen_memory.screen_path() == place / ".controlunit" / "screen.json"
    return place


def _log_of(widget):
    """The message log as the Log tab reads it."""
    return [line["text"] for line in widget.web_status.log_since(0)["lines"]]


def _gauge_lines(lines):
    """The lines that say a gauge was set, from the dock or a browser."""
    words = (" range ", " in Torr", " in Pa", " declared off")
    return [line for line in lines if any(word in line for word in words)]


def _remembered(home):
    return json.loads((home / ".controlunit" / "screen.json").read_text(encoding="utf-8"))


# MARK: the file


STATE = {
    "gauges": {"Pd": {"mode": "Torr", "range": -7}, "Pu2": {"mode": "Off", "range": -3}},
    "sampling_s": 10.0,
}


def test_the_file_holds_what_was_written_and_says_its_schema(tmp_path):
    assert screen_memory.write_screen(STATE, home=tmp_path)
    body = json.loads((tmp_path / "screen.json").read_text(encoding="utf-8"))
    assert body["schema"] == screen_memory.SCHEMA
    assert screen_memory.read_screen(home=tmp_path) == (STATE, [])
    # Nothing but the file itself is left in the folder: the temporary
    # copy it was written through has been moved over it.
    assert [p.name for p in tmp_path.iterdir()] == ["screen.json"]
    assert screen_memory.describe(STATE) == "Pd Torr 1e-7, Pu2 off, sampling 10 s"


@pytest.mark.parametrize(
    "text, reason",
    [
        (None, "no file yet"),
        ("{ half a file", "not JSON"),
        ("[1, 2, 3]", "not a controlunit-screen/v1 file"),
        ('{"gauges": {}, "sampling_s": 10}', "not a controlunit-screen/v1 file"),
    ],
)
def test_a_file_that_cannot_be_used_is_nothing_remembered(tmp_path, text, reason):
    if text is not None:
        (tmp_path / "screen.json").write_text(text, encoding="utf-8")
    assert screen_memory.read_screen(home=tmp_path) == (None, [reason])


def test_a_folder_in_the_file_s_place_is_unreadable_and_unwritable(tmp_path):
    (tmp_path / "screen.json").mkdir()
    state, notes = screen_memory.read_screen(home=tmp_path)
    assert state is None and notes[0].startswith("unreadable")
    assert screen_memory.write_screen(STATE, home=tmp_path) is False


def test_a_value_the_dock_does_not_offer_is_passed_over_alone(tmp_path):
    body = {
        "schema": screen_memory.SCHEMA,
        "gauges": {
            "Pd": {"mode": "Pa", "range": -6},
            "Pu2": {"mode": "Torr", "range": -2},   # above 1e-3
            "Pu3": {"mode": "mbar", "range": -5},   # not a mode
            "Pu4": {"mode": "Torr", "range": True},  # a flag, not a decade
        },
        "sampling_s": 0.5,  # not one of the dock's four
    }
    (tmp_path / "screen.json").write_text(json.dumps(body), encoding="utf-8")
    state, notes = screen_memory.read_screen(home=tmp_path)
    assert state == {"gauges": {"Pd": {"mode": "Pa", "range": -6}}}
    assert notes == ["Pu2", "Pu3", "Pu4", "sampling"]


def test_a_gauge_keeps_its_reading_mode_and_the_diagram_s_word(tmp_path):
    """Since the review of 2026-11-13, beside mode and range: the mode a
    gauge declared off read in before, and the Diagram's word last applied.
    Both optional; a file from before them reads as it always did, and an
    unusable one is passed over alone, the gauge kept."""
    from controlunit import diagram_follower

    assert screen_memory.DIAGRAM_WORDS == (diagram_follower.ACTIVE, diagram_follower.INACTIVE)
    body = {
        "schema": screen_memory.SCHEMA,
        "gauges": {
            "Pd": {"mode": "Off", "range": -7, "reading": "Pa", "diagram": "inactive"},
            "Pu2": {"mode": "Torr", "range": -3, "diagram": "active"},
            "Pu3": {"mode": "Off", "range": -3, "reading": "Off", "diagram": "on"},
            "Pu4": {"mode": "Off", "range": -3, "reading": 1, "diagram": None},
        },
    }
    (tmp_path / "screen.json").write_text(json.dumps(body), encoding="utf-8")
    state, notes = screen_memory.read_screen(home=tmp_path)
    assert state == {"gauges": {
        "Pd": {"mode": "Off", "range": -7, "reading": "Pa", "diagram": "inactive"},
        "Pu2": {"mode": "Torr", "range": -3, "diagram": "active"},
        "Pu3": {"mode": "Off", "range": -3},
        "Pu4": {"mode": "Off", "range": -3},
    }}
    assert notes == []
    assert screen_memory.describe(state) == "Pd off, Pu2 Torr 1e-3, Pu3 off, Pu4 off"
    # Written back as read.
    assert screen_memory.write_screen(state, home=tmp_path)
    assert screen_memory.read_screen(home=tmp_path) == (state, [])


# MARK: the program


def test_the_screen_is_remembered_and_put_back_at_the_next_launch(qt_app, home):
    """Set on one program, from the dock and from a browser; restored, said
    once in the Log, and carried into the next program's first Start."""
    from controlunit.main import MainApp

    first = MainApp(qt_app)
    try:
        configured = float(first.config["Sampling Time"])
        assert configured != 10.0  # the default is not the choice
        pd_mode, pd_range = first.control_dock.gauges["Pd"]
        pu2_mode, _ = first.control_dock.gauges["Pu2"]
        pd_range.setValue(-7)                 # the dock, while idle
        assert _remembered(home)["gauges"]["Pd"] == {"mode": "Torr", "range": -7}
        first.start_acquisition()
        first.set_sampling(10)
        assert _remembered(home)["sampling_s"] == 10.0
        # A browser's command is remembered as well as a hand's.
        first.web_commands.submit(
            "gauge", {"gauge": "Pu2", "mode": "Off"}, actor="tester", origin="10.0.0.9"
        )
        first._drain_web_commands()
        assert pu2_mode.currentText() == "Off"
        first.stop_acquisition()
    finally:
        first.abort_all_threads()
    assert _remembered(home) == dict(STATE, schema=screen_memory.SCHEMA)

    second = MainApp(qt_app)
    try:
        pd_mode, pd_range = second.control_dock.gauges["Pd"]
        pu2_mode, _ = second.control_dock.gauges["Pu2"]
        assert (pd_mode.currentText(), pd_range.value()) == ("Torr", -7)
        assert pu2_mode.currentText() == "Off"
        assert second.settings_dock.samplingCb.currentText() == "10 s"
        assert second.sampling == 10.0
        assert second.web_status.read()["sampling"] == 10.0
        said = [line for line in _log_of(second) if line.startswith("Restored")]
        assert said == ["Restored from the last run: Pd Torr 1e-7, Pu2 off, sampling 10 s"]

        second.start_acquisition()
        reader = second.workers["ADC"]["worker"]
        assert reader._gauge_settings["Pd"] == {"mode": 0, "scale": -7}
        assert reader._gauge_settings["Pu2"]["mode"] == 2
        assert reader.sampling_time == 10.0 and reader.STEP == 1
        assert "Started with sampling 10 s" in _log_of(second)
        gauges = second.web_status.read()["setpoints"]["gauges"]
        assert gauges["Pd"] == {"mode": "Torr", "range": -7}
        assert gauges["Pu2"]["mode"] == "Off"
    finally:
        second.abort_all_threads()


def test_a_corrupt_file_starts_with_settings_yml_and_is_written_afresh(qt_app, home):
    from controlunit.main import MainApp

    folder = home / ".controlunit"
    folder.mkdir()
    (folder / "screen.json").write_text("{ the rig lost power mid-write", encoding="utf-8")
    widget = MainApp(qt_app)
    try:
        configured = float(widget.config["Sampling Time"])
        assert widget.sampling == configured
        assert widget.settings_dock.samplingCb.currentText() == f"{configured:g} s"
        for mode_box, range_box in widget.control_dock.gauges.values():
            assert (mode_box.currentText(), range_box.value()) == ("Torr", -3)
        said = [line for line in _log_of(widget) if "settings.yml" in line]
        assert said == [
            "Gauges and sampling from settings.yml: nothing remembered from a"
            " last run (not JSON)"
        ]
        assert not any(line.startswith("Restored") for line in _log_of(widget))
        # Launching wrote nothing; the first setting replaces the bad file.
        assert "mid-write" in (folder / "screen.json").read_text(encoding="utf-8")
        widget.control_dock.gauges["Pd"][1].setValue(-6)
        assert _remembered(home)["gauges"]["Pd"] == {"mode": "Torr", "range": -6}
    finally:
        widget.abort_all_threads()


def test_a_settings_folder_that_cannot_be_written_never_stops_the_program(qt_app, home):
    """A folder where the file should be: unreadable at launch, unwritable at
    every press. The window opens, runs and says it once."""
    from controlunit.main import MainApp

    (home / ".controlunit" / "screen.json").mkdir(parents=True)
    widget = MainApp(qt_app)
    try:
        assert any(
            line.startswith("Gauges and sampling from settings.yml: nothing remembered")
            for line in _log_of(widget)
        )
        _, pd_range = widget.control_dock.gauges["Pd"]
        pd_range.setValue(-6)
        pd_range.setValue(-5)
        widget.start_acquisition()
        assert widget.workers["ADC"]["worker"]._gauge_settings["Pd"]["scale"] == -5
        failed = [line for line in _log_of(widget) if "not saved" in line]
        assert len(failed) == 1
    finally:
        widget.abort_all_threads()


def test_a_press_on_the_dock_is_logged_once_and_the_program_s_own_moves_never(
    qt_app, home
):
    """2026-11-02 and 2026-11-11: gauge presses on the rig's own screen left
    no Log line. Each one now leaves one, in the browser's words; putting the
    last run back, Start's push into the workers and a browser's command
    (which logs its own "Remote:" line) leave no dock line."""
    from controlunit.main import MainApp

    screen_memory.write_screen({
        "gauges": {"Pd": {"mode": "Pa", "range": -6}, "Pu2": {"mode": "Off", "range": -4}},
        "sampling_s": 1.0,
    })
    widget = MainApp(qt_app)
    try:
        pd_mode, pd_range = widget.control_dock.gauges["Pd"]
        assert (pd_mode.currentText(), pd_range.value()) == ("Pa", -6)
        widget.start_acquisition()
        assert _gauge_lines(_log_of(widget)) == []  # launch and Start: none

        before = len(_log_of(widget))
        pd_range.setValue(-5)
        pd_mode.setCurrentIndex(pd_mode.findText("Torr"))
        pd_mode.setCurrentIndex(pd_mode.findText("Off"))
        assert _gauge_lines(_log_of(widget)[before:]) == [
            "Pd range -5", "Pd in Torr", "Pd declared off",
        ]
        assert widget.workers["ADC"]["worker"]._gauge_settings["Pd"] == {
            "mode": 2, "scale": -5}

        before = len(_log_of(widget))
        widget.web_commands.submit(
            "gauge", {"gauge": "Pu2", "mode": "Torr", "range": -7},
            actor="tester", origin="10.0.0.9",
        )
        widget._drain_web_commands()
        assert _gauge_lines(_log_of(widget)[before:]) == [
            "Remote: tester from 10.0.0.9: Pu2 in Torr, Pu2 range -7"
        ]
        assert widget.workers["ADC"]["worker"]._gauge_settings["Pu2"] == {
            "mode": 0, "scale": -7}

        # A restart of the run pushes the same settings again, silently.
        before = len(_log_of(widget))
        widget.stop_acquisition()
        widget.start_acquisition()
        assert _gauge_lines(_log_of(widget)[before:]) == []
    finally:
        widget.abort_all_threads()


def test_the_dock_line_uses_the_browser_s_words():
    """One phrase for one setting, whichever hand set it."""
    assert commands.summarise("gauge", {"gauge": "Pd", "range": -7}) == "Pd range -7"
    assert commands.summarise("gauge", {"gauge": "Pu2", "mode": "Off"}) == "Pu2 declared off"

"""Browser control: what a body may say, who may press what, and what the
main thread does with a command once it is queued.

Nothing here starts Qt. The main thread's half is exercised against a stand-in
that records the calls a real `MainApp` would make, which is the point of the
split: `controlunit.web.commands` knows method names, never widgets.
"""

import pytest

from controlunit._version import __version__
from controlunit.web import commands
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.server import create_app
from controlunit.web.status import RigStatus

NAMES = ["Ip", "Pu", "Pd", "Bu", "Bd", "MFC1", "MFC2", "Cv"]


# -- what a body may say ------------------------------------------------------


def test_a_flow_setpoint_is_whole_millivolts_in_range():
    assert commands.validate_mfc(1, {"mv": 1234}) == {"n": 1, "mv": 1234}
    assert commands.validate_mfc(2, {"mv": 0}) == {"n": 2, "mv": 0}
    assert commands.validate_mfc(1, {"mv": 5000})["mv"] == 5000


@pytest.mark.parametrize(
    "number, body",
    [
        (1, {}),
        (1, {"mv": -1}),
        (1, {"mv": 5001}),
        (1, {"mv": 12.5}),
        (1, {"mv": "lots"}),
        (1, {"mv": None}),
        (3, {"mv": 100}),
        (0, {"mv": 100}),
    ],
)
def test_a_bad_flow_setpoint_is_refused(number, body):
    with pytest.raises(commands.Invalid):
        commands.validate_mfc(number, body)


def test_a_plasma_setpoint_is_amperes_or_the_word_off():
    assert commands.validate_plasma({"a": 1.2}) == {"a": 1.2}
    assert commands.validate_plasma({"a": 0}) == {"a": 0.0}
    assert commands.validate_plasma({"a": 3.0}) == {"a": 3.0}
    assert commands.validate_plasma({"off": True}) == {"off": True}


@pytest.mark.parametrize("body", [{}, {"a": -0.1}, {"a": 3.1}, {"a": "hot"}, {"a": None}])
def test_a_bad_plasma_setpoint_is_refused(body):
    with pytest.raises(commands.Invalid):
        commands.validate_plasma(body)


def test_the_gauge_takes_a_mode_a_range_or_both():
    assert commands.validate_gauge({"mode": "Pa"}) == {"mode": "Pa"}
    assert commands.validate_gauge({"range": -5}) == {"range": -5}
    assert commands.validate_gauge({"mode": "Torr", "range": -8}) == {
        "mode": "Torr",
        "range": -8,
    }


@pytest.mark.parametrize(
    "body", [{}, {"mode": "bar"}, {"range": -2}, {"range": -9}, {"range": -4.5}]
)
def test_a_bad_gauge_body_is_refused(body):
    with pytest.raises(commands.Invalid):
        commands.validate_gauge(body)


def test_the_sync_line_is_a_boolean_and_nothing_else():
    assert commands.validate_sync({"on": True}) == {"on": True}
    assert commands.validate_sync({"on": False}) == {"on": False}
    for body in ({}, {"on": "yes"}, {"on": 1}, {"on": None}):
        with pytest.raises(commands.Invalid):
            commands.validate_sync(body)


def test_a_baseline_is_taken_for_one_of_three_channels():
    for channel in ("Ip", "Bu", "Bd"):
        assert commands.validate_zero({"channel": channel}) == {"channel": channel}
    for body in ({}, {"channel": "Pu"}, {"channel": ""}, {"channel": 7}):
        with pytest.raises(commands.Invalid):
            commands.validate_zero(body)


def test_stop_all_says_nothing_and_needs_nothing():
    assert commands.validate_stop_all(None) == {}
    assert commands.validate_stop_all({"anything": 1}) == {}


def test_an_unknown_kind_is_refused():
    with pytest.raises(commands.Invalid):
        commands.validate("launch", {})


def test_a_name_is_reduced_to_something_safe_to_print():
    assert commands.clean_actor("  Arseniy ") == "Arseniy"
    assert commands.clean_actor("<b>hack</b>") == "bhackb"
    assert commands.clean_actor("x" * 100) == "x" * commands.ACTOR_MAX
    assert commands.clean_actor(None) == ""


# -- who may press what -------------------------------------------------------


@pytest.mark.parametrize("kind", ["mfc", "plasma", "gauge", "sync", "zero"])
def test_setting_needs_the_switch_and_a_name(kind):
    assert commands.refusal(kind, False, "queezz") == commands.NO_REMOTE
    assert commands.refusal(kind, True, "") == commands.NO_ACTOR
    assert commands.refusal(kind, True, "queezz") == ""


def test_stopping_is_allowed_with_neither():
    assert commands.refusal("stop_all", False, "") == ""


def test_only_stopping_works_without_the_workers():
    assert commands.needs_acquisition("stop_all") is False
    for kind in ("mfc", "plasma", "gauge", "sync", "zero"):
        assert commands.needs_acquisition(kind) is True


# -- the queue ----------------------------------------------------------------


def test_a_queue_hands_back_what_was_put_on_it_oldest_first():
    desk = commands.CommandQueue()
    desk.submit("zero", {"channel": "Ip"}, actor="a", origin="10.0.0.1")
    desk.submit("sync", {"on": True}, actor="b", origin="10.0.0.2")
    taken = desk.take_all()
    assert [c.kind for c in taken] == ["zero", "sync"]
    assert [c.id for c in taken] == [1, 2]
    assert taken[0].actor == "a" and taken[0].origin == "10.0.0.1"
    assert desk.take_all() == []


def test_a_full_queue_refuses_rather_than_growing():
    desk = commands.CommandQueue(maxsize=2)
    desk.submit("sync", {"on": True})
    desk.submit("sync", {"on": False})
    with pytest.raises(commands.Invalid):
        desk.submit("sync", {"on": True})


# -- the main thread's half ---------------------------------------------------


class SpinBox(object):
    def __init__(self, value=0):
        self._value = value

    def setValue(self, value):
        self._value = value

    def value(self):
        return self._value


class ComboBox(object):
    def __init__(self, items):
        self.items = items
        self.index = 0

    def setCurrentIndex(self, index):
        self.index = index

    def currentText(self):
        return self.items[self.index]


class Switch(object):
    def __init__(self):
        self.checked = False

    def setChecked(self, on):
        self.checked = bool(on)

    def isChecked(self):
        return self.checked


class GasFlowDock(object):
    def __init__(self):
        self.mfc_spinboxes = {1: [SpinBox() for _ in range(4)], 2: [SpinBox() for _ in range(4)]}

    def resetSpinBoxes(self, number):
        for box in self.mfc_spinboxes[number]:
            box.setValue(0)

    def millivolts(self, number):
        return sum(
            box.value() * pow(10, 3 - i)
            for i, box in enumerate(self.mfc_spinboxes[number])
        )


class PlasmaDock(object):
    def __init__(self):
        self.ampere_spin_box = SpinBox(0.0)


class ControlDock(object):
    def __init__(self):
        self.IGmode = ComboBox(["Torr", "Pa"])
        self.IGrange = SpinBox(-3)
        self.qmsSigSw = Switch()


class FakeApp(object):
    """Everything `commands.drain` is allowed to touch, and nothing else."""

    def __init__(self, running=True):
        self.workers = {"ADC": object()} if running else {}
        self.gasflow_dock = GasFlowDock()
        self.plasma_control_dock = PlasmaDock()
        self.control_dock = ControlDock()
        self.web_status = RigStatus(names=NAMES)
        self.web_commands = commands.CommandQueue()
        self.calls = []
        self.messages = []

    def turn_off_voltages(self):
        self.calls.append(("turn_off_voltages",))

    def set_mfc_goal(self, number):
        self.calls.append(("set_mfc_goal", number, self.gasflow_dock.millivolts(number)))

    def set_currentcontrol_voltage(self):
        self.calls.append(
            ("set_currentcontrol_voltage", self.plasma_control_dock.ampere_spin_box.value())
        )

    def turn_off_currentcontrol_voltage(self):
        self.calls.append(("turn_off_currentcontrol_voltage",))

    def update_ig_mode(self):
        self.calls.append(("update_ig_mode", self.control_dock.IGmode.currentText()))

    def update_ig_range(self):
        self.calls.append(("update_ig_range", self.control_dock.IGrange.value()))

    def _toggle_led_status(self):
        self.calls.append(("_toggle_led_status", self.control_dock.qmsSigSw.isChecked()))

    #: Whether the main thread had samples to average; the real one answers
    #: False before the first step lands.
    has_samples = True

    def set_zero_baseline(self, channel):
        self.calls.append(("set_zero_baseline", channel))
        return self.has_samples

    def log_message(self, message, htmltag="p"):
        self.messages.append(message)


def test_a_flow_command_moves_the_spinboxes_then_calls_the_same_slot():
    app = FakeApp()
    app.web_commands.submit("mfc", {"n": 1, "mv": 1234}, actor="queezz")
    assert commands.drain(app) == 1
    assert app.gasflow_dock.millivolts(1) == 1234
    assert app.calls == [("set_mfc_goal", 1, 1234)]


def test_the_zero_button_is_a_flow_command_of_zero():
    app = FakeApp()
    app.gasflow_dock.mfc_spinboxes[2][0].setValue(3)
    app.web_commands.submit("mfc", {"n": 2, "mv": 0}, actor="queezz")
    commands.drain(app)
    assert app.gasflow_dock.millivolts(2) == 0


def test_a_plasma_command_sets_the_spinbox_then_the_setpoint():
    app = FakeApp()
    app.web_commands.submit("plasma", {"a": 1.2}, actor="queezz")
    commands.drain(app)
    assert app.plasma_control_dock.ampere_spin_box.value() == 1.2
    assert app.calls == [("set_currentcontrol_voltage", 1.2)]


def test_plasma_off_takes_the_same_path_the_off_button_takes():
    app = FakeApp()
    app.web_commands.submit("plasma", {"off": True}, actor="queezz")
    commands.drain(app)
    assert app.calls == [("turn_off_currentcontrol_voltage",)]


def test_a_gauge_command_sets_the_widgets_and_the_worker():
    app = FakeApp()
    app.web_commands.submit("gauge", {"mode": "Pa", "range": -6}, actor="queezz")
    commands.drain(app)
    assert app.control_dock.IGmode.currentText() == "Pa"
    assert app.control_dock.IGrange.value() == -6
    assert app.calls == [("update_ig_mode", "Pa"), ("update_ig_range", -6)]


def test_a_sync_command_checks_the_switch_then_toggles_the_led():
    app = FakeApp()
    app.web_commands.submit("sync", {"on": True}, actor="queezz")
    commands.drain(app)
    assert app.control_dock.qmsSigSw.isChecked() is True
    assert app.calls == [("_toggle_led_status", True)]


def test_a_zero_command_reaches_the_one_baseline_method():
    app = FakeApp()
    app.web_commands.submit("zero", {"channel": "Bd"}, actor="queezz")
    commands.drain(app)
    assert app.calls == [("set_zero_baseline", "Bd")]
    assert app.web_status.read()["last_command"]["outcome"] == commands.APPLIED
    assert app.messages[-1] == "Remote: queezz: baseline of Bd taken"


def test_a_zero_with_nothing_to_average_is_refused_not_claimed():
    """A baseline that was not taken is never reported as one that was."""
    app = FakeApp()
    app.has_samples = False
    app.web_commands.submit("zero", {"channel": "Bu"}, actor="queezz", origin="10.0.0.5")
    commands.drain(app)
    record = app.web_status.read()["last_command"]
    assert record["outcome"] == commands.REFUSED
    assert record["reason"] == commands.NO_SAMPLES
    assert app.messages[-1] == (
        "Remote: queezz from 10.0.0.5: baseline of Bu taken - refused, "
        + commands.NO_SAMPLES
    )


def test_the_log_line_reads_as_a_sentence_for_every_kind():
    app = FakeApp()
    app.web_commands.submit("mfc", {"n": 1, "mv": 1234}, actor="queezz")
    app.web_commands.submit("stop_all", {}, actor="queezz")
    commands.drain(app)
    assert app.messages[-2] == "Remote: queezz: H2 flow 1234 mV"
    assert app.messages[-1] == "Remote: queezz: all outputs to zero"


def test_stop_all_turns_the_outputs_off_and_zeroes_the_screen():
    app = FakeApp()
    app.plasma_control_dock.ampere_spin_box.setValue(2.0)
    app.gasflow_dock.mfc_spinboxes[1][0].setValue(4)
    app.web_commands.submit("stop_all", {})
    commands.drain(app)
    assert app.calls == [("turn_off_voltages",)]
    assert app.plasma_control_dock.ampere_spin_box.value() == 0.0
    assert app.gasflow_dock.millivolts(1) == 0


def test_commands_run_in_the_order_they_were_queued():
    app = FakeApp()
    app.web_commands.submit("zero", {"channel": "Ip"}, actor="queezz")
    app.web_commands.submit("sync", {"on": True}, actor="queezz")
    app.web_commands.submit("plasma", {"off": True}, actor="queezz")
    assert commands.drain(app) == 3
    assert [call[0] for call in app.calls] == [
        "set_zero_baseline",
        "_toggle_led_status",
        "turn_off_currentcontrol_voltage",
    ]


def test_a_setter_drained_without_workers_is_refused_not_run():
    app = FakeApp(running=False)
    app.web_commands.submit("plasma", {"a": 1.0}, actor="queezz")
    commands.drain(app)
    assert app.calls == []
    record = app.web_status.read()["last_command"]
    assert record["outcome"] == "refused"
    assert record["reason"] == commands.NO_ACQUISITION


def test_stopping_without_workers_still_runs_and_says_so():
    app = FakeApp(running=False)
    app.web_commands.submit("stop_all", {})
    commands.drain(app)
    assert app.calls == [("turn_off_voltages",)]
    assert app.web_status.read()["last_command"]["outcome"] == "applied"


def test_one_failing_command_does_not_stop_the_next():
    app = FakeApp()

    def explode(number):
        raise RuntimeError("the bus is busy")

    app.set_mfc_goal = explode
    app.web_commands.submit("mfc", {"n": 1, "mv": 10}, actor="queezz")
    app.web_commands.submit("sync", {"on": True}, actor="queezz")
    assert commands.drain(app) == 2
    assert app.calls == [("_toggle_led_status", True)]


def test_every_command_lands_in_the_message_log_with_who_and_from_where():
    app = FakeApp()
    app.web_commands.submit(
        "mfc", {"n": 1, "mv": 1234}, actor="queezz", origin="10.249.254.17"
    )
    commands.drain(app)
    line = app.messages[0]
    assert "queezz" in line
    assert "10.249.254.17" in line
    assert "1234 mV" in line
    # The log is appended to a text file with the platform's own encoding.
    line.encode("ascii")


def test_a_refusal_is_logged_as_a_refusal_with_its_reason():
    app = FakeApp(running=False)
    app.web_commands.submit("sync", {"on": True}, actor="queezz")
    commands.drain(app)
    assert "refused" in app.messages[0]
    assert commands.NO_ACQUISITION in app.messages[0]


def test_draining_an_app_with_no_queue_does_nothing():
    class Bare(object):
        pass

    assert commands.drain(Bare()) == 0


# -- the module's own boundary ------------------------------------------------


def test_the_command_module_imports_no_pyqt():
    import ast
    import pathlib

    source = pathlib.Path(commands.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "PyQt5" not in imported
    assert not any(name.lower().startswith("pyqt") for name in imported)


# -- the routes ---------------------------------------------------------------


def rig(remote=False, acquiring=True):
    status = RigStatus(channels=8, sampling=0.1, names=NAMES)
    status.set_acquiring(acquiring)
    status.set_remote(remote)
    return status


def app_for(status, tmp_path, desk=None):
    return create_app(
        status=status,
        board=NeighbourBoard(home=tmp_path / "nowhere"),
        commands=desk if desk is not None else commands.CommandQueue(),
    )


SETTERS = [
    ("/api/mfc/1", {"mv": 1000}),
    ("/api/plasma-current", {"a": 1.0}),
    ("/api/gauge", {"mode": "Pa"}),
    ("/api/sync", {"on": True}),
    ("/api/zero", {"channel": "Ip"}),
]


@pytest.mark.parametrize("path, body", SETTERS)
def test_with_the_switch_off_every_setter_is_refused(path, body, tmp_path):
    client = app_for(rig(remote=False), tmp_path).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post(path, json=body)
    assert response.status_code == 403
    assert response.get_json()["reason"] == commands.NO_REMOTE


@pytest.mark.parametrize("path, body", SETTERS)
def test_with_the_switch_on_but_no_name_every_setter_is_refused(path, body, tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    response = client.post(path, json=body)
    assert response.status_code == 403
    assert response.get_json()["reason"] == commands.NO_ACTOR


@pytest.mark.parametrize("path, body", SETTERS)
def test_with_the_switch_on_and_a_name_a_setter_is_queued(path, body, tmp_path):
    desk = commands.CommandQueue()
    client = app_for(rig(remote=True), tmp_path, desk).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post(path, json=body, environ_base={"REMOTE_ADDR": "10.0.0.9"})
    assert response.status_code == 202
    assert response.get_json()["id"] == 1
    queued = desk.take_all()
    assert len(queued) == 1
    assert queued[0].actor == "queezz"
    assert queued[0].origin == "10.0.0.9"


@pytest.mark.parametrize("path, body", SETTERS)
def test_a_setter_with_no_acquisition_is_a_conflict(path, body, tmp_path):
    client = app_for(rig(remote=True, acquiring=False), tmp_path).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post(path, json=body)
    assert response.status_code == 409
    assert response.get_json()["reason"] == commands.NO_ACQUISITION


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/mfc/1", {"mv": 9999}),
        ("/api/mfc/9", {"mv": 10}),
        ("/api/plasma-current", {"a": 9}),
        ("/api/gauge", {}),
        ("/api/sync", {"on": "yes"}),
        ("/api/zero", {"channel": "Pu"}),
    ],
)
def test_a_bad_body_is_a_four_hundred_with_a_readable_reason(path, body, tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post(path, json=body)
    assert response.status_code in (400, 404)
    if response.status_code == 400:
        reason = response.get_json()["reason"]
        assert reason and reason[0].islower()


@pytest.mark.parametrize("remote", [False, True])
def test_stopping_is_queued_with_no_name_and_no_switch(remote, tmp_path):
    desk = commands.CommandQueue()
    status = rig(remote=remote, acquiring=False)
    client = app_for(status, tmp_path, desk).test_client()
    response = client.post("/api/stop-all", json={})
    assert response.status_code == 202
    assert [c.kind for c in desk.take_all()] == ["stop_all"]


def test_identify_sets_the_name_this_browser_carries(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    response = client.post("/api/identify", json={"name": " Arseniy "})
    assert response.status_code == 200
    assert response.get_json()["actor"] == "Arseniy"
    assert "actor=Arseniy" in response.headers["Set-Cookie"]


def test_identify_refuses_an_empty_name(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    assert client.post("/api/identify", json={"name": "   "}).status_code == 400


def test_state_carries_the_switch_the_zeros_and_the_last_command(tmp_path):
    status = rig(remote=True)
    status.record_zeros({"Ip": 0.25, "Bu": -0.001, "Bd": 0.0})
    status.record_command(
        commands.Command(4, "zero", {"channel": "Ip"}, actor="queezz").as_record(
            commands.APPLIED
        )
    )
    client = app_for(status, tmp_path).test_client()
    body = client.get("/api/state").get_json()
    assert body["remote"] is True
    assert body["zeros"]["Ip"] == 0.25
    assert body["zeros"]["Bd"] == 0.0
    assert body["last_command"]["kind"] == "zero"
    assert body["last_command"]["actor"] == "queezz"
    assert body["last_command"]["outcome"] == "applied"
    assert body["last_command"]["value"] == "baseline of Ip taken"


def test_an_untouched_rig_reports_no_last_command(tmp_path):
    body = app_for(rig(), tmp_path).test_client().get("/api/state").get_json()
    assert body["last_command"] is None
    assert body["remote"] is False
    assert body["zeros"] == {"Ip": 0.0, "Bu": 0.0, "Bd": 0.0}


def test_a_queued_command_lands_on_the_queue_the_main_thread_drains(tmp_path):
    """The route and the drain meet on one queue, and nowhere else."""
    app = FakeApp()
    client = app_for(rig(remote=True), tmp_path, app.web_commands).test_client()
    client.set_cookie("actor", "queezz")
    assert client.post("/api/mfc/2", json={"mv": 2500}).status_code == 202
    commands.drain(app)
    assert app.gasflow_dock.millivolts(2) == 2500


def test_the_outcome_of_a_drained_command_appears_in_state(tmp_path):
    app = FakeApp(running=False)
    client = app_for(app.web_status, tmp_path, app.web_commands).test_client()
    app.web_status.set_remote(True)
    app.web_status.set_acquiring(True)
    client.set_cookie("actor", "queezz")
    posted = client.post("/api/sync", json={"on": True}).get_json()
    commands.drain(app)
    last = client.get("/api/state").get_json()["last_command"]
    assert last["id"] == posted["id"]
    assert last["outcome"] == "refused"
    assert last["reason"] == commands.NO_ACQUISITION


@pytest.mark.parametrize("path", ["/api/stop-all", "/api/gauge", "/api/identify"])
def test_a_command_route_answers_nothing_to_a_get(path, tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    assert client.get(path).status_code == 405


def test_no_answer_from_a_command_route_is_ever_stored(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    response = client.post("/api/stop-all", json={})
    assert response.headers["Cache-Control"] == "no-store"


def test_the_version_the_pages_key_their_assets_to_moved(tmp_path):
    assert __version__ >= "0.7.0"

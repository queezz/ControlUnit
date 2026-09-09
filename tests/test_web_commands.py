"""Browser control: what a body may say, who may press what, and what the
main thread does with a command once it is queued.

Nothing here starts Qt. The main thread's half is exercised against a stand-in
that records the calls a real `MainApp` would make, which is the point of the
split: `controlunit.web.commands` knows method names, never widgets.
"""

import os
import time

import pytest

from controlunit._version import __version__
from controlunit.web import commands
from controlunit.web.fence import Fence
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.roster import Roster
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


def test_a_cathode_drive_is_whole_millivolts_or_the_word_off():
    assert commands.validate_cathode({"mv": 1900}) == {"mv": 1900}
    assert commands.validate_cathode({"mv": "250"}) == {"mv": 250}
    assert commands.validate_cathode({"mv": 0}) == {"mv": 0}
    assert commands.validate_cathode({"mv": 5000}) == {"mv": 5000}
    assert commands.validate_cathode({"off": True}) == {"off": True}


@pytest.mark.parametrize(
    "body", [{}, {"mv": -1}, {"mv": 5001}, {"mv": 1.5}, {"mv": "hot"}, {"mv": None}]
)
def test_a_bad_cathode_drive_is_refused(body):
    with pytest.raises(commands.Invalid):
        commands.validate_cathode(body)


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


def test_starting_and_stopping_a_run_say_nothing_either():
    assert commands.validate_start(None) == {}
    assert commands.validate_start({"anything": 1}) == {}
    assert commands.validate_stop(None) == {}
    assert commands.validate_stop({"anything": 1}) == {}


def test_a_sampling_time_is_one_of_the_four_the_rig_offers():
    for seconds in commands.SAMPLING_CHOICES:
        assert commands.validate_sampling({"seconds": seconds}) == {"seconds": seconds}
    # A browser sends JSON; a number that arrived as text is still a number.
    assert commands.validate_sampling({"seconds": "0.1"}) == {"seconds": 0.1}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"seconds": 0},
        {"seconds": 5},
        {"seconds": -1},
        {"seconds": 0.5},
        {"seconds": "fast"},
        {"seconds": None},
    ],
)
def test_a_sampling_time_the_rig_does_not_offer_is_refused(body):
    with pytest.raises(commands.Invalid) as refused:
        commands.validate_sampling(body)
    # The reason names the four on offer, in the reader's own words.
    assert "10 s" in str(refused.value) or "seconds" in str(refused.value)


def test_the_sampling_choices_are_written_the_way_the_dock_writes_them():
    assert [label for _, label in commands.sampling_choices()] == [
        "10 s",
        "1 s",
        "0.1 s",
        "0.01 s",
    ]
    assert [value for value, _ in commands.sampling_choices()] == [
        "10",
        "1",
        "0.1",
        "0.01",
    ]


def test_the_three_new_summaries_read_as_the_log_will_print_them():
    assert commands.summarise("start", {}) == "acquisition started"
    assert commands.summarise("stop", {}) == "acquisition stopped"
    assert commands.summarise("sampling", {"seconds": 10.0}) == "sampling 10 s"
    assert commands.summarise("sampling", {"seconds": 0.1}) == "sampling 0.1 s"
    assert commands.summarise("sampling", {"seconds": 0.01}) == "sampling 0.01 s"


def test_an_unknown_kind_is_refused():
    with pytest.raises(commands.Invalid):
        commands.validate("launch", {})


def test_a_name_is_reduced_to_something_safe_to_print():
    assert commands.clean_actor("  Arseniy ") == "Arseniy"
    assert commands.clean_actor("<b>hack</b>") == "bhackb"
    assert commands.clean_actor("x" * 100) == "x" * commands.ACTOR_MAX
    assert commands.clean_actor(None) == ""


# -- who may press what -------------------------------------------------------


#: Every kind the switch and the operator lock stand in front of.
GATED = [
    "start",
    "stop",
    "sampling",
    "mfc",
    "plasma",
    "cathode",
    "gauge",
    "sync",
    "zero",
]


@pytest.mark.parametrize("kind", GATED)
def test_setting_needs_the_switch_and_nothing_else(kind):
    """The switch on the rig authorises; a name is a label, never a gate."""
    assert commands.refusal(kind, False, "queezz") == commands.NO_REMOTE
    assert commands.refusal(kind, True, "queezz") == ""
    assert commands.refusal(kind, True, "") == ""


def test_stopping_is_allowed_with_neither():
    assert commands.refusal("stop_all", False, "") == ""


# -- the operator lock --------------------------------------------------------


def held(actor, origin, since=None):
    return {"holder": actor, "origin": origin, "since": since}


def test_the_first_setter_queued_takes_control():
    desk = commands.CommandQueue()
    assert desk.control.read()["holder"] == ""
    desk.submit("mfc", {"n": 1, "mv": 100}, actor="Arseniy", origin="10.249.254.30")
    now = desk.control.read()
    assert now["holder"] == "Arseniy"
    assert now["origin"] == "10.249.254.30"
    assert now["since"] > 0


def test_a_second_setter_from_the_holder_keeps_control_where_it_is():
    desk = commands.CommandQueue()
    desk.submit("sync", {"on": True}, actor="Arseniy", origin="10.249.254.30")
    since = desk.control.read()["since"]
    desk.submit("sync", {"on": False}, actor="Arseniy", origin="10.249.254.30")
    assert desk.control.read()["since"] == since


def test_stopping_the_outputs_neither_takes_control_nor_needs_it():
    desk = commands.CommandQueue()
    desk.submit("stop_all", {}, actor="Ivan", origin="10.249.254.31")
    assert desk.control.read()["holder"] == ""
    desk.submit("mfc", {"n": 1, "mv": 100}, actor="Arseniy", origin="10.249.254.30")
    assert (
        commands.refusal(
            "stop_all", True, "Ivan", origin="10.249.254.31", control=desk.control
        )
        == ""
    )


@pytest.mark.parametrize("kind", GATED)
def test_a_second_person_is_refused_with_the_holder_sentence(kind):
    desk = commands.CommandQueue()
    desk.submit("mfc", {"n": 1, "mv": 100}, actor="Arseniy", origin="10.249.254.30")
    reason = commands.refusal(
        kind, True, "Ivan", origin="10.249.254.31", control=desk.control
    )
    assert reason == commands.holder_sentence(desk.control.read())
    assert reason.startswith("Arseniy has control since ")
    assert reason.endswith(" from 10.249.254.30")


def test_the_same_name_from_another_address_is_another_person():
    """Two laptops sharing one name are still two people at one plasma."""
    desk = commands.CommandQueue()
    desk.submit("sync", {"on": True}, actor="Arseniy", origin="10.249.254.30")
    assert desk.control.held_by("Arseniy", "10.249.254.30") is True
    assert desk.control.held_by("Arseniy", "10.249.254.31") is False
    assert (
        commands.refusal(
            "sync", True, "Arseniy", origin="10.249.254.31", control=desk.control
        )
        != ""
    )


def test_the_holder_may_go_on_setting():
    desk = commands.CommandQueue()
    desk.submit("sync", {"on": True}, actor="Arseniy", origin="10.249.254.30")
    assert (
        commands.refusal(
            "sync", True, "Arseniy", origin="10.249.254.30", control=desk.control
        )
        == ""
    )


def test_with_no_lock_at_hand_the_switch_and_the_name_are_the_whole_gate():
    assert commands.refusal("sync", True, "Arseniy") == ""


def test_a_take_over_moves_control_and_names_who_had_it():
    desk = commands.CommandQueue()
    desk.submit("sync", {"on": True}, actor="Arseniy", origin="10.249.254.30")
    changed, previous = desk.control.take_over("Ivan", "10.249.254.31")
    assert changed is True
    assert previous == "Arseniy"
    assert desk.control.read()["holder"] == "Ivan"
    assert (
        commands.refusal(
            "sync", True, "Arseniy", origin="10.249.254.30", control=desk.control
        )
        != ""
    )


def test_taking_over_from_nobody_simply_takes_it():
    desk = commands.CommandQueue()
    changed, previous = desk.control.take_over("Ivan", "10.249.254.31")
    assert changed is True
    assert previous == ""
    assert desk.control.read()["holder"] == "Ivan"


def test_taking_over_what_you_already_hold_changes_nothing():
    desk = commands.CommandQueue()
    desk.control.take_over("Ivan", "10.249.254.31")
    since = desk.control.read()["since"]
    changed, previous = desk.control.take_over("Ivan", "10.249.254.31")
    assert changed is False
    assert previous == "Ivan"
    assert desk.control.read()["since"] == since


def test_the_holder_sentence_is_one_sentence_in_the_reader_s_words():
    assert commands.holder_sentence(None) == commands.NOBODY
    assert commands.holder_sentence(held("", "", None)) == commands.NOBODY
    line = commands.holder_sentence(held("Arseniy", "10.249.254.30", 1757000000.0))
    assert line.startswith("Arseniy has control since ")
    assert line.endswith(" from 10.249.254.30")
    # A name and nothing else still reads as a sentence.
    assert commands.holder_sentence(held("Arseniy", "", None)) == "Arseniy has control"


def test_a_browser_with_neither_name_nor_address_takes_nothing():
    """There is nobody to name, so there is nobody to hold the rig."""
    desk = commands.CommandQueue()
    assert desk.control.claim("", "") is False
    assert desk.control.read()["holder"] == ""


def test_starting_a_run_claims_control_like_any_other_setter():
    """Whoever stopped the run takes the lock back by starting the next one."""
    desk = commands.CommandQueue()
    desk.submit("start", {}, actor="Arseniy", origin="10.249.254.30")
    assert desk.control.read()["holder"] == "Arseniy"


def test_start_stop_all_and_gauge_setup_work_without_workers():
    assert commands.needs_acquisition("stop_all") is False
    # Starting is the one command that means something only while idle.
    assert commands.needs_acquisition("start") is False
    assert commands.needs_acquisition("gauge") is False
    for kind in ("stop", "sampling", "mfc", "plasma", "cathode", "sync", "zero"):
        assert commands.needs_acquisition(kind) is True


def test_starting_is_the_one_command_that_wants_an_idle_rig():
    assert commands.needs_idle("start") is True
    for kind in commands.KINDS:
        if kind != "start":
            assert commands.needs_idle(kind) is False


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

    def findText(self, text):
        return self.items.index(text) if text in self.items else -1


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
        self.cathode_spin_box = SpinBox(0)


class ControlDock(object):
    def __init__(self):
        self.IGmode = ComboBox(["Torr", "Pa"])
        self.IGrange = SpinBox(-3)
        self.qmsSigSw = Switch()
        self.OnOffSW = Switch()


class SettingsDock(object):
    def __init__(self):
        self.samplingCb = ComboBox(
            [commands.sampling_label(s) for s in commands.SAMPLING_CHOICES]
        )
        # The real dock rests on 0.1 s, its third item.
        self.samplingCb.setCurrentIndex(2)


class FakeApp(object):
    """Everything `commands.drain` is allowed to touch, and nothing else."""

    def __init__(self, running=True):
        self.workers = {"ADC": object()} if running else {}
        self.gasflow_dock = GasFlowDock()
        self.plasma_control_dock = PlasmaDock()
        self.control_dock = ControlDock()
        self.settings_dock = SettingsDock()
        self.web_status = RigStatus(names=NAMES)
        self.web_status.set_acquiring(running)
        self.control_dock.OnOffSW.setChecked(running)
        self.web_commands = commands.CommandQueue()
        self.calls = []
        self.messages = []

    def turn_off_voltages(self):
        self.calls.append(("turn_off_voltages",))

    #: The two halves of what the on/off switch on the rig's screen does, as
    #: `MainApp` splits them, standing in for the workers they start and stop.
    def start_acquisition(self):
        self.workers = {"ADC": object()}
        self.web_status.set_acquiring(True)
        self.calls.append(("start_acquisition",))

    def stop_acquisition(self):
        self.workers = {}
        self.web_status.set_acquiring(False)
        # What `abort_all_threads` does, and all it does, to browser control:
        # the Remote switch is never touched here.
        commands.release(self, "acquisition stopped")
        self.calls.append(("stop_acquisition",))

    def set_sampling(self, seconds):
        index = self.settings_dock.samplingCb.findText(
            commands.sampling_label(seconds)
        )
        if index >= 0:
            self.settings_dock.samplingCb.setCurrentIndex(index)
        self.calls.append(("set_sampling", seconds))

    def set_mfc_goal(self, number):
        self.calls.append(("set_mfc_goal", number, self.gasflow_dock.millivolts(number)))

    def set_currentcontrol_voltage(self):
        self.calls.append(
            ("set_currentcontrol_voltage", self.plasma_control_dock.ampere_spin_box.value())
        )

    def turn_off_currentcontrol_voltage(self):
        self.calls.append(("turn_off_currentcontrol_voltage",))

    def set_cathode_drive(self):
        self.calls.append(
            ("set_cathode_drive", self.plasma_control_dock.cathode_spin_box.value())
        )

    def turn_off_cathode_drive(self):
        self.calls.append(("turn_off_cathode_drive",))

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
    app.plasma_control_dock.cathode_spin_box.setValue(1900)
    app.gasflow_dock.mfc_spinboxes[1][0].setValue(4)
    app.web_commands.submit("stop_all", {})
    commands.drain(app)
    assert app.calls == [("turn_off_voltages",)]
    assert app.plasma_control_dock.ampere_spin_box.value() == 0.0
    assert app.plasma_control_dock.cathode_spin_box.value() == 0
    assert app.gasflow_dock.millivolts(1) == 0


def test_a_cathode_command_sets_the_dock_box_then_the_drive():
    """The manual mode: the same path the Cathode dock's own Set takes."""
    app = FakeApp()
    app.web_commands.submit("cathode", {"mv": 1900}, actor="queezz")
    commands.drain(app)
    assert app.plasma_control_dock.cathode_spin_box.value() == 1900
    assert app.calls == [("set_cathode_drive", 1900)]
    assert app.messages[-1] == "Remote: queezz: cathode drive 1900 mV"


def test_cathode_off_takes_the_same_path_the_off_button_takes():
    app = FakeApp()
    app.web_commands.submit("cathode", {"off": True}, actor="queezz")
    commands.drain(app)
    assert app.calls == [("turn_off_cathode_drive",)]
    assert app.messages[-1] == "Remote: queezz: cathode drive off"


def test_starting_a_run_sets_the_switch_then_takes_the_switch_s_own_path():
    app = FakeApp(running=False)
    app.web_commands.submit("start", {}, actor="queezz")
    commands.drain(app)
    assert app.calls == [("start_acquisition",)]
    # The rig's own screen agrees with what the browser did.
    assert app.control_dock.OnOffSW.isChecked() is True
    assert app.web_status.read()["acquiring"] is True
    assert app.messages[-1] == "Remote: queezz: acquisition started"


def test_starting_a_run_that_is_already_running_is_refused_on_the_main_thread():
    """A second press, one poll apart, must not lay workers over workers."""
    app = FakeApp(running=True)
    app.web_commands.submit("start", {}, actor="queezz")
    commands.drain(app)
    assert app.calls == []
    record = app.web_status.read()["last_command"]
    assert record["outcome"] == commands.REFUSED
    assert record["reason"] == commands.ALREADY_ACQUIRING


def test_stopping_a_run_sets_the_switch_then_takes_the_switch_s_own_path():
    app = FakeApp(running=True)
    app.web_commands.submit("stop", {}, actor="queezz")
    commands.drain(app)
    assert app.calls == [("stop_acquisition",)]
    assert app.control_dock.OnOffSW.isChecked() is False
    assert app.web_status.read()["acquiring"] is False
    assert app.messages[-1] == "Remote: queezz: acquisition stopped"


def test_stopping_a_run_leaves_the_remote_switch_exactly_where_it_was():
    """The switch is the rig's own; a browser's Stop never takes it down."""
    app = FakeApp(running=True)
    app.web_status.set_remote(True)
    app.web_commands.submit("stop", {}, actor="queezz", origin="10.0.0.5")
    commands.drain(app)
    assert app.web_status.read()["remote"] is True
    # Control is let go of, though, so the next browser is not shut out.
    assert app.web_commands.control.read()["holder"] == ""
    assert "Control released (acquisition stopped)" in app.messages


def test_stopping_a_run_that_is_not_running_is_refused():
    app = FakeApp(running=False)
    app.web_commands.submit("stop", {}, actor="queezz")
    commands.drain(app)
    assert app.calls == []
    record = app.web_status.read()["last_command"]
    assert record["outcome"] == commands.REFUSED
    assert record["reason"] == commands.NO_ACQUISITION


def test_a_sampling_command_sets_the_combo_then_the_one_method():
    app = FakeApp(running=True)
    app.web_commands.submit("sampling", {"seconds": 10.0}, actor="queezz")
    commands.drain(app)
    assert app.calls == [("set_sampling", 10.0)]
    assert app.settings_dock.samplingCb.currentText() == "10 s"
    assert app.messages[-1] == "Remote: queezz: sampling 10 s"


def test_a_sampling_command_without_a_run_is_refused():
    app = FakeApp(running=False)
    app.web_commands.submit("sampling", {"seconds": 1.0}, actor="queezz")
    commands.drain(app)
    assert app.calls == []
    assert app.web_status.read()["last_command"]["reason"] == commands.NO_ACQUISITION


def test_a_browser_may_stop_and_start_again_in_one_drain():
    """The pair a person actually presses: end the run, begin the next."""
    app = FakeApp(running=True)
    app.web_commands.submit("stop", {}, actor="queezz")
    app.web_commands.submit("start", {}, actor="queezz")
    assert commands.drain(app) == 2
    assert [call[0] for call in app.calls] == ["stop_acquisition", "start_acquisition"]
    assert app.web_status.read()["acquiring"] is True
    assert app.control_dock.OnOffSW.isChecked() is True


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


def test_a_take_over_is_a_command_in_its_own_right():
    """It moves no hardware, and it is logged with the name, address and time."""
    app = FakeApp()
    app.web_commands.submit("sync", {"on": True}, actor="Arseniy", origin="10.249.254.30")
    app.web_commands.control.take_over("Ivan", "10.249.254.31")
    app.web_commands.submit(
        "take_over", {"from": "Arseniy"}, actor="Ivan", origin="10.249.254.31"
    )
    commands.drain(app)
    assert app.calls == [("_toggle_led_status", True)]
    assert app.messages[-1] == (
        "Remote: Ivan from 10.249.254.31: took control from Arseniy"
    )
    assert app.web_status.read()["last_command"]["outcome"] == commands.APPLIED


def test_a_take_over_from_nobody_says_so_without_naming_a_ghost():
    app = FakeApp()
    app.web_commands.submit("take_over", {"from": ""}, actor="Ivan", origin="10.0.0.4")
    commands.drain(app)
    assert app.messages[-1] == "Remote: Ivan from 10.0.0.4: took control"


def test_a_take_over_runs_with_no_acquisition_because_it_moves_nothing():
    app = FakeApp(running=False)
    app.web_commands.submit("take_over", {}, actor="Ivan", origin="10.0.0.4")
    commands.drain(app)
    assert app.web_status.read()["last_command"]["outcome"] == commands.APPLIED


@pytest.mark.parametrize(
    "reason", ["acquisition stopped", "Remote switch off"]
)
def test_the_main_thread_releases_control_and_says_why(reason):
    app = FakeApp()
    app.web_commands.submit("mfc", {"n": 1, "mv": 10}, actor="Arseniy", origin="10.0.0.5")
    assert commands.release(app, reason) == "Arseniy"
    assert app.web_commands.control.read()["holder"] == ""
    assert app.messages[-1] == "Control released ({})".format(reason)


def test_releasing_what_nobody_held_says_nothing():
    app = FakeApp()
    assert commands.release(app, "acquisition stopped") == ""
    assert app.messages == []


def test_releasing_on_an_app_with_no_queue_does_nothing():
    class Bare(object):
        pass

    assert commands.release(Bare(), "acquisition stopped") == ""


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


def app_for(status, tmp_path, desk=None, home=None, fence_home=None, fence_clock=None):
    """An app whose machine knows nothing it was not given here.

    The fence's home is pointed at nothing by default, so this suite tests a
    machine with no word of its own however the developer's own machine
    happens to be set up. `fence_clock` is for the one test that has to see
    the word change without waiting a real second for it.
    """
    nowhere = tmp_path / "nowhere"
    return create_app(
        status=status,
        board=NeighbourBoard(home=nowhere),
        commands=desk if desk is not None else commands.CommandQueue(),
        roster=Roster(home=nowhere if home is None else home),
        fence=Fence(
            home=nowhere if fence_home is None else fence_home,
            clock=fence_clock if fence_clock is not None else time.monotonic,
        ),
    )


SETTERS = [
    ("/api/acquisition/stop", {}),
    ("/api/sampling", {"seconds": 1}),
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
def test_with_the_switch_on_a_nameless_browser_may_still_set(path, body, tmp_path):
    """Nobody is kept from the rig for not having typed a name first."""
    client = app_for(rig(remote=True), tmp_path).test_client()
    response = client.post(path, json=body)
    assert response.status_code == 202


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
    if path == "/api/gauge":
        assert response.status_code == 202
    else:
        assert response.status_code == 409
        assert response.get_json()["reason"] == commands.NO_ACQUISITION


def test_a_browser_may_start_a_run_on_an_idle_rig(tmp_path):
    desk = commands.CommandQueue()
    client = app_for(rig(remote=True, acquiring=False), tmp_path, desk).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post("/api/acquisition/start", json={})
    assert response.status_code == 202
    assert response.get_json()["value"] == "acquisition started"
    assert [c.kind for c in desk.take_all()] == ["start"]


def test_starting_a_run_that_already_runs_is_a_conflict(tmp_path):
    """The one command refused for the opposite fact, in its own words."""
    desk = commands.CommandQueue()
    client = app_for(rig(remote=True, acquiring=True), tmp_path, desk).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post("/api/acquisition/start", json={})
    assert response.status_code == 409
    assert response.get_json()["reason"] == commands.ALREADY_ACQUIRING
    assert desk.take_all() == []


def test_starting_a_run_still_needs_the_switch_on_the_rig(tmp_path):
    client = app_for(rig(remote=False, acquiring=False), tmp_path).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post("/api/acquisition/start", json={})
    assert response.status_code == 403
    assert response.get_json()["reason"] == commands.NO_REMOTE


def test_a_sampling_time_the_rig_does_not_offer_is_a_four_hundred(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    client.set_cookie("actor", "queezz")
    response = client.post("/api/sampling", json={"seconds": 3})
    assert response.status_code == 400
    reason = response.get_json()["reason"]
    assert reason and reason[0].islower()
    assert "0.01 s" in reason


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/sampling", {}),
        ("/api/sampling", {"seconds": "quick"}),
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


ROSTER = """\
{"schema": "pihti-operators/v1",
 "operators": [{"username": "hashizuka", "display_name": "Hashizuka Takuma"},
               {"username": "queezz", "display_name": "Arseniy Kuzmin"}]}
"""


def with_roster(tmp_path):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "operators.json").write_text(ROSTER, encoding="utf-8")
    return app_for(rig(remote=True), tmp_path, home=home).test_client()


def test_identify_takes_a_name_the_lab_roster_carries(tmp_path):
    response = with_roster(tmp_path).post(
        "/api/identify", json={"name": "Hashizuka Takuma"}
    )
    assert response.status_code == 200
    assert response.get_json()["actor"] == "Hashizuka Takuma"
    assert "actor=" in response.headers["Set-Cookie"]


def test_identify_sends_an_unknown_name_back_to_the_roster(tmp_path):
    """The list is a courtesy so one person is spelled one way, so a name
    beside it is refused with the one thing worth saying about it."""
    response = with_roster(tmp_path).post("/api/identify", json={"name": "Somebody"})
    assert response.status_code == 400
    assert response.get_json()["reason"] == "choose a name from the lab's roster"
    assert "Set-Cookie" not in response.headers


def test_identify_takes_any_name_on_a_machine_with_no_roster(tmp_path):
    """A name is a label for the log, never a credential: a rig that has
    never been handed the roster still lets a person say who they are."""
    client = app_for(rig(remote=True), tmp_path).test_client()
    response = client.post("/api/identify", json={"name": "Somebody"})
    assert response.status_code == 200
    assert response.get_json()["actor"] == "Somebody"


def test_the_roster_route_lists_the_names_this_machine_holds(tmp_path):
    assert with_roster(tmp_path).get("/api/roster").get_json() == {
        "names": ["Hashizuka Takuma", "Arseniy Kuzmin"]
    }


def test_the_roster_route_is_empty_where_there_is_no_roster(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    assert client.get("/api/roster").get_json() == {"names": []}


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


# -- the operator lock, over the wire -----------------------------------------


@pytest.mark.parametrize("path, body", SETTERS)
def test_a_second_person_is_refused_over_the_wire(path, body, tmp_path):
    desk = commands.CommandQueue()
    app = app_for(rig(remote=True), tmp_path, desk)
    first = app.test_client()
    first.set_cookie("actor", "Arseniy")
    assert (
        first.post(
            "/api/mfc/1", json={"mv": 100}, environ_base={"REMOTE_ADDR": "10.249.254.30"}
        ).status_code
        == 202
    )

    second = app.test_client()
    second.set_cookie("actor", "Ivan")
    answer = second.post(path, json=body, environ_base={"REMOTE_ADDR": "10.249.254.31"})
    assert answer.status_code == 403
    reason = answer.get_json()["reason"]
    assert reason.startswith("Arseniy has control since ")
    assert reason.endswith(" from 10.249.254.30")


def test_the_holder_goes_on_setting_and_stop_all_is_never_gated(tmp_path):
    desk = commands.CommandQueue()
    app = app_for(rig(remote=True), tmp_path, desk)
    holder = app.test_client()
    holder.set_cookie("actor", "Arseniy")
    for _ in range(2):
        answer = holder.post(
            "/api/sync", json={"on": True}, environ_base={"REMOTE_ADDR": "10.249.254.30"}
        )
        assert answer.status_code == 202

    other = app.test_client()
    other.set_cookie("actor", "Ivan")
    assert (
        other.post(
            "/api/stop-all", json={}, environ_base={"REMOTE_ADDR": "10.249.254.31"}
        ).status_code
        == 202
    )
    # Stopping the outputs left control exactly where it was.
    assert desk.control.read()["holder"] == "Arseniy"


def test_take_over_moves_control_and_queues_its_own_log_line(tmp_path):
    desk = commands.CommandQueue()
    app = app_for(rig(remote=True), tmp_path, desk)
    first = app.test_client()
    first.set_cookie("actor", "Arseniy")
    first.post(
        "/api/mfc/1", json={"mv": 100}, environ_base={"REMOTE_ADDR": "10.249.254.30"}
    )
    desk.take_all()

    second = app.test_client()
    second.set_cookie("actor", "Ivan")
    answer = second.post(
        "/api/take-over", json={}, environ_base={"REMOTE_ADDR": "10.249.254.31"}
    )
    assert answer.status_code == 200
    body = answer.get_json()
    assert body["changed"] is True
    assert body["control"]["holder"] == "Ivan"
    assert body["control"]["mine"] is True
    queued = desk.take_all()
    assert [c.kind for c in queued] == ["take_over"]
    assert queued[0].summary() == "took control from Arseniy"


def test_taking_over_what_you_hold_is_a_no_op_that_still_answers(tmp_path):
    desk = commands.CommandQueue()
    client = app_for(rig(remote=True), tmp_path, desk).test_client()
    client.set_cookie("actor", "Ivan")
    client.post("/api/take-over", json={}, environ_base={"REMOTE_ADDR": "10.0.0.4"})
    desk.take_all()
    answer = client.post(
        "/api/take-over", json={}, environ_base={"REMOTE_ADDR": "10.0.0.4"}
    )
    assert answer.status_code == 200
    assert answer.get_json()["changed"] is False
    assert desk.take_all() == []


def test_taking_over_needs_the_switch_and_a_name(tmp_path):
    off = app_for(rig(remote=False), tmp_path).test_client()
    off.set_cookie("actor", "Ivan")
    answer = off.post("/api/take-over", json={})
    assert answer.status_code == 403
    assert answer.get_json()["reason"] == commands.NO_REMOTE

    nameless = app_for(rig(remote=True), tmp_path).test_client()
    answer = nameless.post("/api/take-over", json={})
    assert answer.status_code == 200


def test_state_carries_who_has_control_and_whether_it_is_this_browser(tmp_path):
    desk = commands.CommandQueue()
    app = app_for(rig(remote=True), tmp_path, desk)
    holder = app.test_client()
    holder.set_cookie("actor", "Arseniy")
    holder.post(
        "/api/sync", json={"on": True}, environ_base={"REMOTE_ADDR": "10.249.254.30"}
    )

    mine = holder.get(
        "/api/state", environ_base={"REMOTE_ADDR": "10.249.254.30"}
    ).get_json()["control"]
    assert mine["holder"] == "Arseniy"
    assert mine["origin"] == "10.249.254.30"
    assert mine["since"] > 0
    assert mine["mine"] is True
    assert mine["line"].startswith("Arseniy has control since ")

    other = app.test_client()
    other.set_cookie("actor", "Ivan")
    theirs = other.get(
        "/api/state", environ_base={"REMOTE_ADDR": "10.249.254.31"}
    ).get_json()["control"]
    assert theirs["mine"] is False
    assert theirs["line"] == mine["line"]


def test_an_untouched_rig_says_nobody_has_control(tmp_path):
    body = app_for(rig(), tmp_path).test_client().get("/api/state").get_json()
    assert body["control"]["holder"] == ""
    assert body["control"]["since"] is None
    assert body["control"]["mine"] is False
    assert body["control"]["line"] == commands.NOBODY


@pytest.mark.parametrize(
    "path",
    [
        "/api/stop-all",
        "/api/gauge",
        "/api/identify",
        "/api/take-over",
        "/api/acquisition/start",
        "/api/acquisition/stop",
        "/api/sampling",
    ],
)
def test_a_command_route_answers_nothing_to_a_get(path, tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    assert client.get(path).status_code == 405


def test_no_answer_from_a_command_route_is_ever_stored(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    response = client.post("/api/stop-all", json={})
    assert response.headers["Cache-Control"] == "no-store"


def test_the_version_the_pages_key_their_assets_to_moved(tmp_path):
    assert __version__ >= "0.7.0"


# -- a name labels, an address holds -----------------------------------------


def test_a_nameless_browser_holds_control_under_its_own_address():
    """Somebody who typed no name is named by where they are sitting."""
    lock = commands.OperatorLock(clock=lambda: 1000.0)
    assert lock.claim("", "10.249.254.8") is True
    held = lock.read()
    assert held["holder"] == "10.249.254.8"
    # Named once by the address, never twice.
    assert commands.holder_sentence(held).count("10.249.254.8") == 1


def test_saving_a_name_does_not_lock_a_holder_out_of_their_own_session():
    lock = commands.OperatorLock(clock=lambda: 1000.0)
    lock.claim("", "10.249.254.8")
    lock.claim("Arseniy", "10.249.254.8")  # the same browser, now with a name
    assert lock.blocks("Arseniy", "10.249.254.8") is None
    assert lock.read()["holder"] == "Arseniy"


def test_another_laptop_is_another_person_however_it_signs():
    lock = commands.OperatorLock(clock=lambda: 1000.0)
    lock.claim("Arseniy", "10.249.254.8")
    for name in ("Arseniy", "Ivan", ""):
        assert lock.blocks(name, "10.249.254.31") is not None


def test_a_nameless_command_is_logged_under_its_address_once():
    """"someone from 127.0.0.1" says one person twice; the address is the name."""
    command = commands.Command(1, "mfc", {"n": 1, "mv": 1234}, actor="", origin="10.0.0.5")
    line = commands.describe(command, commands.APPLIED, "")
    assert line == "Remote: 10.0.0.5: H2 flow 1234 mV"
    assert line.count("10.0.0.5") == 1

    named = commands.Command(2, "mfc", {"n": 1, "mv": 1234}, actor="Arseniy", origin="10.0.0.5")
    assert commands.describe(named, commands.APPLIED, "") == (
        "Remote: Arseniy from 10.0.0.5: H2 flow 1234 mV"
    )


# -- the lab's word, over the wire --------------------------------------------

WORD = "plasmabox"


def fenced(tmp_path):
    """A machine that holds the lab's word, with its switch already on."""
    fence_home = tmp_path / ".controlunit-fence"
    fence_home.mkdir()
    (fence_home / "fence.txt").write_text(WORD + "\n", encoding="utf-8")
    return fence_home


def test_with_no_fence_the_word_route_says_so_and_stores_nothing(tmp_path):
    """Every machine that holds no word behaves exactly as it always has."""
    client = app_for(rig(remote=True), tmp_path).test_client()
    answer = client.post("/api/fence", json={"word": "anything"})
    assert answer.status_code == 200
    assert answer.get_json() == {"fenced": False}
    assert "Set-Cookie" not in answer.headers


@pytest.mark.parametrize("path, body", SETTERS)
def test_with_no_fence_every_setter_behaves_as_before(path, body, tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    client.set_cookie("actor", "queezz")
    assert client.post(path, json=body).status_code == 202


def test_with_no_fence_state_says_none_is_needed(tmp_path):
    body = app_for(rig(remote=True), tmp_path).test_client().get("/api/state")
    assert body.get_json()["fence"] == {"needed": False, "passed": False}


@pytest.mark.parametrize("path, body", SETTERS)
def test_behind_a_fence_a_setter_without_the_word_is_refused(path, body, tmp_path):
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    client.set_cookie("actor", "queezz")
    answer = client.post(path, json=body)
    assert answer.status_code == 403
    assert answer.get_json()["reason"] == commands.NO_FENCE_WORD


def test_the_switch_is_the_reason_before_the_word_is(tmp_path):
    """A person can walk to the rig and throw the switch; the word is the
    smaller fact, so it is not the one they are sent away with."""
    client = app_for(
        rig(remote=False), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    answer = client.post("/api/sync", json={"on": True})
    assert answer.status_code == 403
    assert answer.get_json()["reason"] == commands.NO_REMOTE


@pytest.mark.parametrize("path, body", SETTERS)
def test_the_word_opens_the_fence_and_the_setter_is_then_queued(path, body, tmp_path):
    desk = commands.CommandQueue()
    client = app_for(
        rig(remote=True), tmp_path, desk, fence_home=fenced(tmp_path)
    ).test_client()
    client.set_cookie("actor", "queezz")
    assert client.post(path, json=body).status_code == 403

    opened = client.post("/api/fence", json={"word": " plasmabox "})
    assert opened.status_code == 200
    assert opened.get_json() == {"fenced": True}
    assert "fence=plasmabox" in opened.headers["Set-Cookie"]
    assert "HttpOnly" in opened.headers["Set-Cookie"]

    assert client.post(path, json=body).status_code == 202
    assert len(desk.take_all()) == 1


def test_a_wrong_word_is_refused_and_nothing_is_carried(tmp_path):
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    answer = client.post("/api/fence", json={"word": "sesame"})
    assert answer.status_code == 403
    assert answer.get_json()["reason"] == commands.WRONG_FENCE_WORD
    assert "Set-Cookie" not in answer.headers
    assert client.post("/api/sync", json={"on": True}).status_code == 403


def test_taking_over_is_behind_the_fence_too(tmp_path):
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    client.set_cookie("actor", "Ivan")
    answer = client.post("/api/take-over", json={})
    assert answer.status_code == 403
    assert answer.get_json()["reason"] == commands.NO_FENCE_WORD

    client.post("/api/fence", json={"word": WORD})
    assert client.post("/api/take-over", json={}).status_code == 200


def test_stopping_the_outputs_is_never_behind_the_fence(tmp_path):
    """A person who can see the rig must be able to zero it, word or no word."""
    desk = commands.CommandQueue()
    client = app_for(
        rig(remote=True), tmp_path, desk, fence_home=fenced(tmp_path)
    ).test_client()
    assert client.post("/api/stop-all", json={}).status_code == 202
    assert [c.kind for c in desk.take_all()] == ["stop_all"]


def test_naming_yourself_is_never_behind_the_fence(tmp_path):
    """The word gates setting, not saying who you are."""
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    assert client.post("/api/identify", json={"name": "Ivan"}).status_code == 200


def test_reading_is_never_behind_the_fence(tmp_path):
    """Reading is open to anyone on the lab network, as it always was."""
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    for path in ("/", "/control", "/log", "/lab", "/api/state", "/api/health"):
        assert client.get(path).status_code == 200


def test_state_says_where_this_browser_stands_against_the_fence(tmp_path):
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    assert client.get("/api/state").get_json()["fence"] == {
        "needed": True,
        "passed": False,
    }
    client.post("/api/fence", json={"word": WORD})
    assert client.get("/api/state").get_json()["fence"] == {
        "needed": True,
        "passed": True,
    }


def test_the_word_itself_is_never_carried_to_a_browser(tmp_path):
    """The page is told where it stands, never what the fence is made of."""
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fenced(tmp_path)
    ).test_client()
    client.post("/api/fence", json={"word": WORD})
    for path in ("/api/state", "/control"):
        assert WORD not in client.get(path).get_data(as_text=True)


def test_a_changed_word_shuts_the_fence_on_the_old_one(tmp_path):
    """The cookie carries the word, so a word changed in the lab closes the
    fence again on every browser that had passed the old one."""
    fence_home = fenced(tmp_path)
    now = [0.0]
    client = app_for(
        rig(remote=True), tmp_path, fence_home=fence_home, fence_clock=lambda: now[0]
    ).test_client()
    client.post("/api/fence", json={"word": WORD})
    assert client.get("/api/state").get_json()["fence"]["passed"] is True

    path = fence_home / "fence.txt"
    path.write_text("sputterhut\n", encoding="utf-8")
    os.utime(path, ns=(10**9, 5 * 10**9))
    now[0] = 60.0  # past the once-a-second bound the fence rereads on
    assert client.get("/api/state").get_json()["fence"]["passed"] is False
    assert client.post("/api/sync", json={"on": True}).status_code == 403


def test_the_fence_route_answers_nothing_to_a_get(tmp_path):
    client = app_for(rig(remote=True), tmp_path).test_client()
    assert client.get("/api/fence").status_code == 405


def test_gauge_settings_prepare_idle_rig_and_publish_before_start():
    from controlunit.main import MainApp
    app = FakeApp(running=False)
    # Exercise the real updater paths, with no workers available to touch.
    app.update_ig_mode = lambda: MainApp.update_ig_mode(app)
    app.update_ig_range = lambda: MainApp.update_ig_range(app)
    app.web_commands.submit("gauge", {"mode": "Pa", "range": -7}, actor="queezz")
    commands.drain(app)
    assert app.control_dock.IGrange.value() == -7
    assert app.control_dock.IGmode.currentText() == "Pa"
    assert app.web_status.read()["setpoints"]["ig_range"] == -7
    assert app.web_status.read()["setpoints"]["ig_mode"] == "Pa"
    assert not app.workers

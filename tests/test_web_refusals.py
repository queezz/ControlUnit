"""Refused web presses reach the Log, through the main thread, once a minute.

The web thread answers a refusal (`403`, `409`) and used to leave nothing
else, so what a student was refused, and why, could not be read afterwards.
Each refusal now leaves one line on the command desk, and the main thread's
drain writes it with the commands. These go through the Flask test client;
the drain is handed a stand-in for the window that only collects lines.
"""

import time

import pytest

from controlunit.web import commands
from controlunit.web.fence import Fence
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.roster import Roster
from controlunit.web.server import create_app
from controlunit.web.status import RigStatus

STUDENT = "10.249.254.8"
OWNER = "10.249.254.5"
DASH = "-"


def rig(remote=True, acquiring=True):
    status = RigStatus(channels=8, sampling=0.1, names=("Ip", "Pu", "Pd"))
    status.set_acquiring(acquiring)
    status.set_remote(remote)
    return status


def client_for(status, tmp_path, desk, fence_home=None):
    nowhere = tmp_path / "nowhere"
    return create_app(
        status=status,
        board=NeighbourBoard(home=nowhere),
        commands=desk,
        roster=Roster(home=nowhere),
        fence=Fence(home=nowhere if fence_home is None else fence_home),
    ).test_client()


def press(client, path, body, origin=STUDENT, actor="Kawabata Rei"):
    if actor:
        client.set_cookie("actor", actor)
    return client.post(path, json=body, environ_base={"REMOTE_ADDR": origin})


class Window:
    """Everything `commands.drain` touches, and a list of Log lines."""

    def __init__(self, desk):
        self.web_commands = desk
        self.web_status = RigStatus()
        self.workers = {}
        self.lines = []

    def log_message(self, message, htmltag="p"):
        self.lines.append(message)


def test_someone_else_holding_control_names_both_people(tmp_path):
    desk = commands.CommandQueue()
    desk.control.take_over("Kuzmin Arseniy", OWNER)
    client = client_for(rig(), tmp_path, desk)
    answer = press(client, "/api/plasma-current", {"a": 1.5})
    assert answer.status_code == 403
    # The browser is told the holder line, as before.
    assert answer.get_json()["reason"].startswith("Kuzmin Arseniy has control since ")
    assert desk.refusals.take() == [
        "Refused from 10.249.254.8 (Kawabata Rei): plasma current 1.50 A " + DASH
        + " Kawabata Rei does not hold control (Kuzmin Arseniy does)"
    ]


def test_the_drain_writes_the_line_on_the_main_thread(tmp_path):
    desk = commands.CommandQueue()
    client = client_for(rig(remote=False), tmp_path, desk)
    press(client, "/api/mfc/1", {"mv": 1200})
    window = Window(desk)
    commands.drain(window)
    assert window.lines == [
        "Refused from 10.249.254.8 (Kawabata Rei): H2 flow 1200 mV " + DASH
        + " the Remote switch on the rig's screen is off"
    ]
    commands.drain(window)  # written once, not at every drain
    assert len(window.lines) == 1


@pytest.mark.parametrize(
    "remote, acquiring, path, body, code, said",
    [
        (False, True, "/api/acquisition/stop", {}, 403,
         "stop acquisition " + DASH + " the Remote switch on the rig's screen is off"),
        (True, False, "/api/zero", {"channel": "Ip"}, 409,
         "baseline of Ip " + DASH + " no acquisition running"),
        (True, True, "/api/acquisition/start", {}, 409,
         "start acquisition " + DASH + " acquisition is already running"),
        (True, True, "/api/cathode-output", {"on": True}, 409,
         "cathode output on " + DASH + " the supply is not answering; turn it on at the supply"),
        (True, True, "/api/cathode", {"mv": 2200}, 202, None),
    ],
)
def test_each_refusal_is_said_in_the_reason_the_browser_was_given(
    tmp_path, remote, acquiring, path, body, code, said
):
    desk = commands.CommandQueue()
    client = client_for(rig(remote=remote, acquiring=acquiring), tmp_path, desk)
    answer = press(client, path, body)
    assert answer.status_code == code
    lines = desk.refusals.take()
    if said is None:
        assert lines == []  # a press that went through is the command's own line
    else:
        assert lines == ["Refused from 10.249.254.8 (Kawabata Rei): " + said]


def test_take_over_refused_is_said_too(tmp_path):
    desk = commands.CommandQueue()
    client = client_for(rig(remote=False), tmp_path, desk)
    answer = press(client, "/api/take-over", {}, actor="")
    assert answer.status_code == 403
    assert desk.refusals.take() == [
        "Refused from 10.249.254.8: take control " + DASH
        + " the Remote switch on the rig's screen is off"
    ]


def test_the_lab_s_word_is_never_written_only_whether_one_was_carried(tmp_path):
    folder = tmp_path / ".controlunit"
    folder.mkdir()
    (folder / "fence.txt").write_text("plasmabox\n", encoding="utf-8")
    desk = commands.CommandQueue()
    client = client_for(rig(), tmp_path, desk, fence_home=folder)

    assert press(client, "/api/sync", {"on": True}).status_code == 403
    client.set_cookie("fence", "plasmaboks")
    assert press(client, "/api/take-over", {}).status_code == 403
    # The same kind of reason for the same press inside the minute: held.
    assert press(client, "/api/sync", {"on": True}).status_code == 403
    lines = desk.refusals.take()
    assert lines == [
        "Refused from 10.249.254.8 (Kawabata Rei): QMS sync on " + DASH + " lab word not typed",
        "Refused from 10.249.254.8 (Kawabata Rei): take control " + DASH + " wrong lab word",
    ]
    assert not any("plasmabo" in line for line in lines)


def test_a_name_changed_at_every_press_is_still_one_line_a_minute(tmp_path):
    """The review of 2026-11-13: the lock's reason carries the name the
    browser's cookie sends, and the repeat was keyed by that text, so fifty
    presses under fifty names were fifty lines inside the minute."""
    desk = commands.CommandQueue()
    desk.control.take_over("Owner", OWNER)
    client = client_for(rig(), tmp_path, desk)
    for number in range(50):
        assert press(client, "/api/plasma-current", {"a": 1.0},
                     actor="x{}".format(number)).status_code == 403
    for _ in range(50):
        press(client, "/api/plasma-current", {"a": 1.0}, actor="same")
    lines = desk.refusals.take()
    assert lines == [
        "Refused from 10.249.254.8 (x0): plasma current 1.00 A " + DASH
        + " x0 does not hold control (Owner does)"
    ]


@pytest.mark.parametrize("reason, kind", [
    (commands.NO_REMOTE, "remote off"),
    (commands.FENCE_NOT_TYPED, "fence"),
    (commands.FENCE_WRONG, "fence"),
    (commands.NO_FENCE_WORD, "fence"),
    (commands.NO_ACQUISITION, "needs acquisition"),
    (commands.ALREADY_ACQUIRING, "already acquiring"),
    (commands.NO_SUPPLY_ANSWER, "supply"),
    (commands.TOO_MANY, "too many"),
    ("Kawabata Rei does not hold control (Kuzmin Arseniy does)", "not holder"),
    ("Kuzmin Arseniy has control since 16:20", "not holder"),
])
def test_each_reason_falls_in_one_kind(reason, kind):
    assert commands.refusal_kind(reason) == kind


def test_a_log_that_fails_with_its_terminal_gone_never_raises_out_of_the_drain(
    tmp_path, monkeypatch
):
    """After SIGHUP every print raises; the drain's own complaint about a
    Log line that failed must not take the timer's slot with it."""
    import sys

    class Gone:
        def write(self, text):
            raise OSError(5, "Input/output error")

        def flush(self):
            raise OSError(5, "Input/output error")

    desk = commands.CommandQueue()
    desk.refusals.note("plasma", {"a": 1.0}, "Kawabata Rei", STUDENT, commands.NO_REMOTE)
    window = Window(desk)

    def broken(message, htmltag="p"):
        raise OSError(28, "No space left on device")

    window.log_message = broken
    monkeypatch.setattr(sys, "stdout", Gone())
    assert commands.drain(window) == 0


def test_a_body_the_rig_does_not_accept_is_not_a_refused_press(tmp_path):
    desk = commands.CommandQueue()
    client = client_for(rig(remote=False), tmp_path, desk)
    assert press(client, "/api/plasma-current", {"a": 9}).status_code == 400
    assert desk.refusals.take() == []


def test_the_same_refusal_is_written_once_a_minute(tmp_path):
    now = {"t": 1000.0}
    desk = commands.CommandQueue()
    desk.refusals = commands.RefusalLog(
        clock=lambda: now["t"], wall=lambda: time.mktime((2026, 11, 13, 16, 20, 5, 0, 0, -1))
    )
    client = client_for(rig(remote=False), tmp_path, desk)
    for _ in range(5):
        press(client, "/api/plasma-current", {"a": 1.5})
        now["t"] += 5.0
    assert len(desk.refusals.take()) == 1

    # Another address, another kind, or another reason is its own line.
    press(client, "/api/plasma-current", {"a": 1.5}, origin="10.249.254.9")
    press(client, "/api/mfc/2", {"mv": 300})
    assert len(desk.refusals.take()) == 2

    now["t"] += 60.0
    press(client, "/api/plasma-current", {"a": 1.5})
    assert desk.refusals.take() == [
        "Refused from 10.249.254.8 (Kawabata Rei): plasma current 1.50 A " + DASH
        + " the Remote switch on the rig's screen is off; 4 more like it since 16:20:05"
    ]


def test_stop_all_and_the_output_off_are_never_refused_or_logged_as_such(tmp_path):
    desk = commands.CommandQueue()
    client = client_for(rig(remote=False, acquiring=False), tmp_path, desk, None)
    assert press(client, "/api/stop-all", {}, actor="").status_code == 202
    assert press(client, "/api/cathode-output", {"on": False}, actor="").status_code == 202
    assert desk.refusals.take() == []

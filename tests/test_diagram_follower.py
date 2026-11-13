"""The gauges follow the PIHTI Diagram: the asking, the edges, the checks.

queezz, 2026-11-13: "Gauge left off, maybe we sync from the journal? Why
should we turn that off twice??", and the same day: "When the diagram says
the gauge is off, but the signal doesn't change, we should warn."

Everything here runs without Qt and without the LAN. The Diagram is either
an injected function or a stand-in HTTP server on this machine's loopback,
on a port the system picks, so nothing reaches the rig's Diagram. The Qt
half, where an answer moves the dock's selector, is in
`test_qt_acquisition.py`.
"""

import datetime
import http.server
import json
import socket
import threading

import numpy as np
import pytest

from controlunit import diagram_follower as follow
from controlunit import readsettings

PD = "downstream-ionization-gauge"
PU2 = "bypass-ionization-gauge"


# -- the mapping, in the channel map -----------------------------------------


def test_the_packaged_settings_map_both_ion_gauges_to_the_diagram():
    config = readsettings.select_settings()
    assert readsettings.gauge_diagram_elements(config) == {"Pd": PD, "Pu2": PU2}


def test_a_gauge_without_the_key_is_not_followed():
    config = {
        "ADC Channels": {
            "Pd": {"Conversion Function": "Ionization Gauge",
                   "Diagram Element": " downstream-ionization-gauge "},
            "Pu2": {"Conversion Function": "Ionization Gauge"},
            "Px": {"Conversion Function": "Ionization Gauge", "Diagram Element": ""},
            # Only an ion gauge has a mode to follow.
            "Bu": {"Conversion Function": "Baratron", "Diagram Element": "baratron"},
        }
    }
    assert readsettings.gauge_diagram_elements(config) == {"Pd": PD}


def test_the_initialised_channel_carries_its_element():
    config = readsettings.init_configuration()
    props = config["Adc Channel Properties"]
    assert props["Pd"].diagram_element == PD
    assert props["Pu2"].diagram_element == PU2
    assert props["Bu"].diagram_element is None


# -- where the Diagram is -----------------------------------------------------


def test_the_address_is_the_neighbours_file_s(tmp_path):
    (tmp_path / "neighbours.yml").write_text(
        "pihti-diagram:\n  url: http://rig.example:5000/\n", encoding="utf-8"
    )
    assert follow.diagram_url(tmp_path) == "http://rig.example:5000"
    assert follow.diagram_url(tmp_path / "nowhere") is None


@pytest.mark.parametrize(
    "url, mine",
    [
        ("http://127.0.0.1:5000", True),
        ("http://localhost:5000", True),
        ("http://[::1]:5000", True),
        ("http://diagram.localhost", True),
        ("http://pihti:5000", False),
        ("http://pihti.local:5000", False),
        ("http://10.249.254.21:5000", False),
        ("", False),
    ],
)
def test_dummy_hardware_asks_only_a_diagram_on_this_machine(url, mine):
    assert follow.is_loopback(url) is mine


# -- the edges ----------------------------------------------------------------


def following():
    return follow.GaugeFollowing({"Pd": PD, "Pu2": PU2})


def test_the_first_answer_is_a_change_from_not_knowing():
    watch = following()
    changes, notes = watch.read({PD: "inactive", PU2: "active", "turbo": "active"})
    assert changes == [("Pd", "inactive"), ("Pu2", "active")]
    assert notes == []


def test_an_unchanged_word_is_not_a_change():
    watch = following()
    watch.read({PD: "inactive", PU2: "active"})
    for _ in range(3):
        assert watch.read({PD: "inactive", PU2: "active"}) == ([], [])
    assert watch.read({PD: "active", PU2: "active"}) == ([("Pd", "active")], [])


def test_an_element_the_mapping_does_not_name_is_ignored():
    watch = follow.GaugeFollowing({"Pd": PD})
    changes, _ = watch.read({PD: "active", PU2: "inactive"})
    assert changes == [("Pd", "active")]


def test_silence_changes_nothing_and_is_said_once_then_once_again_when_it_ends():
    watch = following()
    watch.read({PD: "active", PU2: "active"})
    changes, notes = watch.read(None, "no answer within two seconds")
    assert changes == []
    assert notes == [
        "Gauges not following the Diagram: no answer within two seconds;"
        " gauge modes left as they are"
    ]
    for _ in range(3):
        assert watch.read(None, "refused the connection") == ([], [])
    # Back, and nothing changed meanwhile: nothing to apply.
    assert watch.read({PD: "active", PU2: "active"}) == (
        [], ["Gauges following the Diagram again"])
    # Back, and something did: only that.
    watch.read(None, "no answer within two seconds")
    changes, notes = watch.read({PD: "inactive", PU2: "active"})
    assert changes == [("Pd", "inactive")]
    assert notes == ["Gauges following the Diagram again"]


def test_an_answer_that_is_not_an_object_is_silence_with_a_reason():
    watch = following()
    changes, notes = watch.read(["active"])
    assert changes == []
    assert notes == [
        "Gauges not following the Diagram: answered, but not with the"
        " elements' states; gauge modes left as they are"
    ]


def test_a_mapped_element_missing_from_the_answer_is_not_read_as_off():
    """The Diagram reads a missing element as inactive; this does not, so a
    renamed id there can never declare a working gauge off here."""
    watch = following()
    changes, notes = watch.read({PU2: "active"})
    assert changes == [("Pu2", "active")]
    assert notes == [
        "Pd not following the Diagram: its answer has no active or inactive"
        " for downstream-ionization-gauge"
    ]
    # Said once, not at every poll.
    assert watch.read({PU2: "active", PD: "on"}) == ([], [])
    assert watch.read({PU2: "active", PD: "inactive"}) == ([("Pd", "inactive")], [])


# -- the asking, against a stand-in Diagram on loopback -----------------------


class StandIn:
    """A Diagram on 127.0.0.1 that answers `/elements-state` with `body`."""

    def __init__(self, body=b"{}", status=200):
        self.body = body
        self.status = status
        self.asked = 0
        stand_in = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 -- http.server's own name
                stand_in.asked += 1
                if self.path != follow.STATE_PATH:
                    self.send_error(404)
                    return
                self.send_response(stand_in.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(stand_in.body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:{}".format(self.server.server_address[1])
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stand_in():
    servers = []

    def make(body, status=200):
        server = StandIn(body, status)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_the_states_are_read_as_the_diagram_serves_them(stand_in):
    diagram = stand_in(json.dumps({PD: "inactive", PU2: "active"}).encode())
    assert follow.fetch_elements_state(diagram.url) == {PD: "inactive", PU2: "active"}


@pytest.mark.parametrize(
    "body, status, reason",
    [
        (b"{not json", 200, "answered, but not with the elements' states"),
        (b'["active"]', 200, "answered, but not with the elements' states"),
        (b"\xff\xfe", 200, "answered, but not with the elements' states"),
        (b"{}", 500, "answered with an error, code 500"),
    ],
)
def test_an_answer_that_is_not_the_states_is_refused_with_its_reason(
    stand_in, body, status, reason
):
    diagram = stand_in(body, status)
    with pytest.raises(follow.DiagramUnanswered) as raised:
        follow.fetch_elements_state(diagram.url)
    assert str(raised.value) == reason


def test_nobody_listening_is_a_reason_not_a_crash():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # Nothing listens there now; Windows may wait out its retries first.
    with pytest.raises(follow.DiagramUnanswered) as raised:
        follow.fetch_elements_state("http://127.0.0.1:{}".format(port), timeout=3)
    assert str(raised.value) in (
        "refused the connection", "no answer within two seconds")


def test_the_follower_asks_on_its_own_thread_and_keeps_the_newest(stand_in):
    diagram = stand_in(json.dumps({PD: "active"}).encode())
    asked_from = []
    answered = threading.Event()

    def fetch():
        asked_from.append(threading.current_thread())
        states = follow.fetch_elements_state(diagram.url)
        answered.set()
        return states

    follower = follow.DiagramFollower(diagram.url, fetch=fetch, interval=0.01)
    assert follower.take() is None
    follower.start()
    try:
        assert answered.wait(5)
        deadline = datetime.datetime.now() + datetime.timedelta(seconds=5)
        while diagram.asked < 3 and datetime.datetime.now() < deadline:
            answered.clear()
            answered.wait(1)
        assert diagram.asked >= 3
        answer = follower.take()
        assert answer.states == {PD: "active"} and answer.reason == ""
        assert isinstance(answer.at, datetime.datetime)
    finally:
        assert follower.stop()
    assert not follower.thread.is_alive()
    # Never on the caller's thread: every ask came from the follower's own.
    assert asked_from
    assert all(thread is follower.thread for thread in asked_from)
    assert threading.main_thread() not in asked_from
    # Taken once; a stopped follower hands nothing more.
    follower.take()
    assert follower.take() is None


def test_a_failing_ask_is_an_answer_with_a_reason():
    def fetch():
        raise follow.DiagramUnanswered("refused the connection")

    follower = follow.DiagramFollower("http://127.0.0.1:9", fetch=fetch, interval=60)
    follower.start()
    try:
        deadline = datetime.datetime.now() + datetime.timedelta(seconds=5)
        answer = None
        while answer is None and datetime.datetime.now() < deadline:
            answer = follower.take()
        assert answer.states is None
        assert answer.reason == "refused the connection"
    finally:
        # Asleep for a minute between asks, and still stops at once.
        started = datetime.datetime.now()
        assert follower.stop()
        assert datetime.datetime.now() - started < datetime.timedelta(seconds=1)


def test_a_stop_does_not_wait_out_a_slow_ask():
    release = threading.Event()

    def fetch():
        release.wait(10)
        return {}

    follower = follow.DiagramFollower("http://127.0.0.1:9", fetch=fetch)
    follower.start()
    started = datetime.datetime.now()
    assert follower.stop(timeout=0.1) is False  # still in its one request
    assert datetime.datetime.now() - started < datetime.timedelta(seconds=1)
    assert follower.thread.daemon
    release.set()
    follower.thread.join(5)
    assert not follower.thread.is_alive()
    # A stop that arrived mid-ask leaves no answer behind it.
    assert follower.take() is None


# -- the signal's say ---------------------------------------------------------

EDGE = datetime.datetime(2026, 11, 13, 14, 43, 20)


def signal(points, step=1.0, start=-60.0):
    """Rows every `step` seconds from `start` around EDGE; `points(t)` gives
    the raw volts at t seconds after the edge."""
    offsets = np.arange(start, 120.0 + step, step)
    times = np.array(
        [np.datetime64(EDGE + datetime.timedelta(seconds=float(t)), "ns") for t in offsets]
    )
    volts = np.array([points(float(t)) for t in offsets], dtype=float)
    return times, volts


def after(seconds):
    return EDGE + datetime.timedelta(seconds=seconds)


def check(status):
    return follow.SwitchCheck("Pd", status, EDGE, "downstream ion gauge")


def live_then_decay(t):
    """The upstream controller of 2026-10-07: live, then a swing to -1.56 V
    as it lost power, decaying to zero over about 15 s, then the floor."""
    if t < 20:
        return 1.53
    if t < 35:
        return -1.56 * (35 - t) / 15
    return 0.002


def test_an_off_edge_the_signal_follows_is_confirmed_without_a_line():
    times, volts = signal(live_then_decay)
    switch = check("inactive")
    # Not yet: still decaying, and the window is open.
    assert switch.verdict(times[times <= np.datetime64(after(30))],
                          volts[times <= np.datetime64(after(30))], after(30)) == (
        follow.PENDING, "")
    assert switch.verdict(times, volts, after(45)) == (follow.CONFIRMED, "")


def test_an_off_edge_the_signal_does_not_follow_warns_once_the_window_ends():
    times, volts = signal(lambda t: 1.53)
    switch = check("inactive")
    assert switch.verdict(times, volts, after(89)) == (follow.PENDING, "")
    verdict, line = switch.verdict(times, volts, after(91))
    assert verdict == follow.UNCONFIRMED
    assert line == (
        "<font color='red'>Pd: the Diagram shows the downstream ion gauge"
        " off</font>, but Pd still reads 1.53 V, a live gauge's signal; is its"
        " controller still on, or was another gauge recorded?"
    )
    assert line.isascii()


def test_a_signal_that_fell_before_the_edge_is_confirmed():
    """Operators record a switch up to a minute after flipping it."""
    times, volts = signal(lambda t: 1.53 if t < -50 else 0.001)
    assert check("inactive").verdict(times, volts, after(1)) == (follow.CONFIRMED, "")


def test_a_signal_that_fell_long_before_the_window_still_counts_inside_it():
    times, volts = signal(lambda t: 0.0, start=-600.0)
    assert check("inactive").verdict(times, volts, after(1)) == (follow.CONFIRMED, "")


def test_an_on_edge_the_signal_follows_is_confirmed():
    times, volts = signal(lambda t: 0.002 if t < 40 else 2.1)
    assert check("active").verdict(times, volts, after(91)) == (follow.CONFIRMED, "")


def test_an_on_edge_the_signal_does_not_follow_warns_once_the_window_ends():
    times, volts = signal(lambda t: 0.002)
    verdict, line = check("active").verdict(times, volts, after(91))
    assert verdict == follow.UNCONFIRMED
    assert line == (
        "<font color='red'>Pd: the Diagram shows the downstream ion gauge"
        " on</font>, but Pd still reads 0.002 V, its floor; is its controller"
        " on?"
    )


def test_a_moment_at_the_floor_is_not_a_switch():
    """The -1.56 V swing crosses zero: one sample there proves nothing."""
    times, volts = signal(lambda t: 0.0 if t in (10.0, 11.0, 12.0) else 1.53)
    assert check("inactive").verdict(times, volts, after(91))[0] == follow.UNCONFIRMED
    times, volts = signal(lambda t: 0.0 if 10 <= t <= 15 else 1.53)
    assert check("inactive").verdict(times, volts, after(91))[0] == follow.CONFIRMED


def test_a_floor_outside_the_window_does_not_confirm():
    times, volts = signal(lambda t: 0.0 if t < -70 or t > 100 else 1.53, start=-120.0)
    assert check("inactive").verdict(times, volts, after(121))[0] == follow.UNCONFIRMED


def test_ten_second_sampling_needs_two_rows_at_the_floor():
    times, volts = signal(lambda t: 0.001 if t >= 30 else 1.5, step=10.0)
    assert check("inactive").verdict(times, volts, after(91))[0] == follow.CONFIRMED
    times, volts = signal(lambda t: 0.001 if t == 80 else 1.5, step=10.0)
    assert check("inactive").verdict(times, volts, after(91))[0] == follow.UNCONFIRMED


def test_a_sample_that_is_not_a_number_breaks_a_stretch():
    times, volts = signal(lambda t: float("nan") if t % 3 == 0 else 0.0)
    assert check("inactive").verdict(times, volts, after(91))[0] == follow.UNCONFIRMED


def test_no_sample_in_the_window_is_nothing_to_say():
    assert check("inactive").verdict(None, None, after(91)) == (follow.UNCHECKED, "")
    empty = np.array([], dtype="datetime64[ns]")
    assert check("inactive").verdict(empty, np.array([]), after(91)) == (
        follow.UNCHECKED, "")
    assert check("inactive").verdict(None, None, after(10)) == (follow.PENDING, "")


# -- the Diagram's own time for a switch --------------------------------------
#
# queezz, 2026-11-13: "The diagram has no timestamp? But it has history. So
# it has time..." `/elements-state` has none; `/history/events` has every
# press with its time and initials, and is asked only when the states change.


def test_the_history_gives_each_element_s_latest_switch_each_way():
    events = [
        {"ts": "2026-11-13 14:40:00", "user": "KR", "changes": [{"id": PD, "state": False}]},
        {"ts": "2026-11-13 14:43:20", "user": "KAA", "changes": [{"id": PD, "state": False}]},
        {"ts": "2026-11-13 15:00:00", "user": "KAA", "changes": [{"id": PD, "state": True}]},
        {"ts": "not a time", "user": "X", "changes": [{"id": PD, "state": False}]},
        {"ts": "2026-11-13 16:00:00", "user": "X", "changes": [{"id": PD, "state": "off"}]},
        "not an event",
    ]
    found = follow.recorded_switches(events)
    assert found[PD]["inactive"] == (datetime.datetime(2026, 11, 13, 14, 43, 20), "KAA")
    assert found[PD]["active"] == (datetime.datetime(2026, 11, 13, 15, 0, 0), "KAA")
    assert follow.recorded_switches({"not": "a list"}) == {}


def test_the_history_is_asked_only_when_the_states_change():
    answers = iter([{PD: "active"}, {PD: "active"}, {PD: "inactive"}, {PD: "inactive"}])
    histories = []

    def history():
        histories.append(1)
        return {PD: {"inactive": (datetime.datetime(2026, 11, 13, 14, 43, 20), "KAA")}}

    follower = follow.DiagramFollower(
        "http://127.0.0.1:9", fetch=lambda: next(answers), interval=60, history=history
    )
    first = follower._ask()
    second = follower._ask()
    third = follower._ask()
    fourth = follower._ask()
    assert len(histories) == 2                       # the first answer, and the change
    assert first.recorded is not None and second.recorded is None
    assert third.recorded[PD]["inactive"][1] == "KAA" and fourth.recorded is None


def test_a_history_that_cannot_be_had_still_follows_the_states():
    def history():
        raise OSError("refused")

    follower = follow.DiagramFollower(
        "http://127.0.0.1:9", fetch=lambda: {PD: "inactive"}, interval=60, history=history
    )
    answer = follower._ask()
    assert answer.states == {PD: "inactive"} and answer.recorded is None

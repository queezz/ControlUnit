"""Neighbour states: answered, answered badly, silent, and never configured.

`down` and `unreachable` are different facts about different failures, and
neither is "not configured". These tests hold the three apart, and hold the
board to answering without waiting for any of them: the probe runs behind
the answer, and `wait()` is what stands still for it here.

The mapping from a failure to a state is the ensemble's shared word, so each
branch of it is pinned here against a stand-in `urlopen` rather than left to
whatever the LAN happens to do on the day.
"""

import io
import json
import socket
import threading
import urllib.error

import pytest

from controlunit.web import neighbours as neighbourhood
from controlunit.web.neighbours import NeighbourBoard, read_addresses
from controlunit.web.server import create_app

SETTINGS = """\
Settings Version: 1.3
Neighbours:
  pihti-log: "http://vault.example:4310"
  pihti-diagram:
    url: "http://rig.example:4186/"
"""


def write_settings(home, text=SETTINGS):
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.yml").write_text(text, encoding="utf-8")
    return home


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def answering(bodies):
    """A urlopen stand-in: alias substring -> health report or exception."""

    def opener(url, timeout=None):
        for key, outcome in bodies.items():
            if key in url:
                if isinstance(outcome, Exception):
                    raise outcome
                return FakeResponse(json.dumps(outcome).encode("utf-8"))
        raise urllib.error.URLError("no route")

    return opener


def probed(board):
    """The rows once the probe the first call started has finished.

    The first call never waits on the network, so a test that wants the
    answer asks twice with a `wait()` between: the same two steps the page
    takes, with the second one arriving on a timer rather than here.
    """
    board.neighbours()
    assert board.wait(timeout=10)
    return {row["alias"]: row for row in board.neighbours()}


def test_addresses_come_from_the_local_settings_file(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    addresses = read_addresses(home)
    assert addresses == {
        "pihti-log": "http://vault.example:4310",
        "pihti-diagram": "http://rig.example:4186",
    }


NEIGHBOURS_FILE = """\
pihti-log:
  url: "http://vault.example:4310"
  where: on the office Windows PC
  start_how: from the office PC, as lab pihti-log
  start: lab pihti-log
pihti-diagram:
  url: "http://rig.example:4186"
  start: sudo systemctl start pihti.service
"""


def test_starting_is_two_facts_read_from_the_local_file(tmp_path):
    """The plain words and the literal line are separate keys: the card
    leads with the words and keeps the line behind its toggle."""
    home = tmp_path / ".controlunit"
    home.mkdir(parents=True)
    (home / "neighbours.yml").write_text(NEIGHBOURS_FILE, encoding="utf-8")

    entries = neighbourhood.read_neighbours(home)
    assert entries["pihti-log"]["start_how"] == "from the office PC, as lab pihti-log"
    assert entries["pihti-log"]["start"] == "lab pihti-log"
    # A file that gives only the command leaves the words empty rather than
    # inventing them; the card says so in words of its own.
    assert entries["pihti-diagram"]["start_how"] == ""
    assert entries["pihti-diagram"]["start"] == "sudo systemctl start pihti.service"


def test_every_row_carries_both_start_facts(tmp_path):
    """Both keys on every row, whatever the local file happened to say, so
    neither the page nor the template has to ask whether a key is there."""
    home = tmp_path / ".controlunit"
    home.mkdir(parents=True)
    (home / "neighbours.yml").write_text(NEIGHBOURS_FILE, encoding="utf-8")
    board = NeighbourBoard(home=home, prober=lambda: None)
    client = create_app(board=board).test_client()

    rows = client.get("/api/neighbours").get_json()["services"]
    for row in rows:
        assert set(row) >= {"where", "start_how", "start"}
    by_alias = {row["alias"]: row for row in rows}
    assert by_alias["pihti-log"]["start_how"] == "from the office PC, as lab pihti-log"
    assert by_alias["pihti-diagram"]["start_how"] == ""
    # This program starts with its own GUI, from the rig's desktop shortcut.
    assert "rig's own screen" in by_alias["controlunit"]["start_how"]
    assert by_alias["controlunit"]["start"] == "scripts/run_controlunit.sh"


def test_a_missing_settings_file_configures_nothing(tmp_path):
    assert read_addresses(tmp_path / "nowhere") == {}


def test_a_settings_file_without_the_block_configures_nothing(tmp_path):
    home = write_settings(tmp_path / ".controlunit", "Settings Version: 1.3\n")
    assert read_addresses(home) == {}


def test_no_addresses_means_not_configured_not_unreachable(tmp_path):
    rows = NeighbourBoard(home=tmp_path / "nowhere").neighbours()
    assert [row["alias"] for row in rows] == ["pihti-log", "pihti-diagram"]
    assert {row["state"] for row in rows} == {"not configured"}
    assert all(row["url"] == "" for row in rows)


def test_a_service_that_answers_reports_its_own_state(tmp_path, monkeypatch):
    home = write_settings(tmp_path / ".controlunit")
    monkeypatch.setattr(
        neighbourhood.urllib.request,
        "urlopen",
        answering(
            {
                "vault.example": {
                    "service": "pihti-log",
                    "version": "0.6.1",
                    "status": "ok",
                    "detail": "vault open",
                },
                "rig.example": {
                    "service": "pihti",
                    "version": "1.2.0",
                    "status": "down",
                    "detail": "no data directory",
                },
            }
        ),
    )
    rows = probed(NeighbourBoard(home=home))
    assert rows["pihti-log"]["state"] == "ok"
    assert rows["pihti-log"]["version"] == "0.6.1"
    assert rows["pihti-log"]["detail"] == "vault open"
    assert rows["pihti-diagram"]["state"] == "down"


def test_silence_is_unreachable_never_down(tmp_path, monkeypatch):
    home = write_settings(tmp_path / ".controlunit")
    monkeypatch.setattr(
        neighbourhood.urllib.request,
        "urlopen",
        answering(
            {
                "vault.example": urllib.error.URLError("timed out"),
                "rig.example": OSError("no route to host"),
            }
        ),
    )
    rows = probed(NeighbourBoard(home=home))
    assert rows["pihti-log"]["state"] == "unreachable"
    assert rows["pihti-diagram"]["state"] == "unreachable"
    assert rows["pihti-log"]["detail"] == "no answer within two seconds"


def test_an_http_error_is_down_because_something_answered(tmp_path, monkeypatch):
    home = write_settings(tmp_path / ".controlunit")
    monkeypatch.setattr(
        neighbourhood.urllib.request,
        "urlopen",
        answering(
            {
                "vault.example": urllib.error.HTTPError(
                    "http://vault.example:4310/api/health", 503, "busy", {}, None
                ),
                "rig.example": {"status": "ok", "version": "1.2.0", "detail": ""},
            }
        ),
    )
    rows = probed(NeighbourBoard(home=home))
    assert rows["pihti-log"]["state"] == "down"
    assert rows["pihti-diagram"]["state"] == "ok"


def test_an_answer_that_is_not_a_health_report_is_degraded(tmp_path, monkeypatch):
    home = write_settings(tmp_path / ".controlunit")

    def opener(url, timeout=None):
        return FakeResponse(b"<html>hello</html>")

    monkeypatch.setattr(neighbourhood.urllib.request, "urlopen", opener)
    rows = probed(NeighbourBoard(home=home))
    assert rows["pihti-log"]["state"] == "degraded"
    assert rows["pihti-log"]["detail"] == "answered, but not with a health report"


@pytest.mark.parametrize(
    "failure, state, detail",
    [
        (
            ConnectionRefusedError(111, "Connection refused"),
            "down",
            "refused the connection",
        ),
        (
            urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")),
            "down",
            "refused the connection",
        ),
        (
            socket.gaierror(-2, "Name or service not known"),
            "unreachable",
            "the name did not resolve",
        ),
        (
            urllib.error.URLError(socket.gaierror(-2, "Name or service not known")),
            "unreachable",
            "the name did not resolve",
        ),
        (socket.timeout("timed out"), "unreachable", "no answer within two seconds"),
        (
            urllib.error.URLError(socket.timeout("timed out")),
            "unreachable",
            "no answer within two seconds",
        ),
        (
            urllib.error.HTTPError(
                "http://vault.example:4310/api/health", 503, "busy", {}, None
            ),
            "down",
            "answered with an error, code 503",
        ),
    ],
)
def test_a_failure_is_named_by_what_actually_failed(
    tmp_path, monkeypatch, failure, state, detail
):
    """A refused connection is a machine that answered the knock with a shut
    door, so it is `down`; nothing answering at all is `unreachable`. The
    three surfaces of the ensemble word these the same way."""
    home = write_settings(tmp_path / ".controlunit")
    monkeypatch.setattr(
        neighbourhood.urllib.request,
        "urlopen",
        answering({"vault.example": failure, "rig.example": failure}),
    )
    rows = probed(NeighbourBoard(home=home))
    assert rows["pihti-log"]["state"] == state
    assert rows["pihti-log"]["detail"] == detail


def test_the_board_is_cached_so_a_poll_does_not_hammer_the_lan(tmp_path, monkeypatch):
    home = write_settings(tmp_path / ".controlunit")
    calls = []

    def opener(url, timeout=None):
        calls.append(url)
        return FakeResponse(json.dumps({"status": "ok", "version": "1.0"}).encode())

    monkeypatch.setattr(neighbourhood.urllib.request, "urlopen", opener)
    now = [0.0]
    board = NeighbourBoard(home=home, clock=lambda: now[0])

    board.neighbours()
    assert board.wait(timeout=10)
    assert len(calls) == 2
    now[0] = 5.0  # inside the ten-second window: no new requests
    board.neighbours()
    assert board.wait(timeout=10)
    assert len(calls) == 2
    now[0] = 30.0  # the window has passed
    board.neighbours()
    assert board.wait(timeout=10)
    assert len(calls) == 4


def test_the_route_lists_this_service_first_then_the_two_neighbours(tmp_path):
    board = NeighbourBoard(home=tmp_path / "nowhere")
    client = create_app(board=board).test_client()
    payload = client.get("/api/neighbours").get_json()
    rows = payload["services"]
    assert [row["alias"] for row in rows] == [
        "controlunit",
        "pihti-log",
        "pihti-diagram",
    ]
    assert [row["name"] for row in rows] == [
        "ControlUnit",
        "PIHTI Log",
        "PIHTI diagram",
    ]
    for row in rows:
        assert set(row) >= {"name", "url", "state", "version", "detail"}
    assert rows[0]["state"] in {"ok", "degraded"}
    assert rows[1]["state"] == "not configured"


@pytest.mark.parametrize(
    "state",
    ["ok", "degraded", "down", "unreachable", "not configured", "checking"],
)
def test_every_state_the_page_can_show_has_a_legend_line(state):
    from controlunit.web.server import STATE_LEGEND

    assert state in {name for name, _ in STATE_LEGEND}


# -- the board answers now, and asks behind the answer ------------------------


def slow_prober(started, release, rows, counted):
    """A stand-in probe that blocks until the test lets it finish."""

    def probe():
        counted.append(1)
        started.set()
        release.wait(10)
        return rows

    return probe


ROWS = [
    {
        "alias": "pihti-log",
        "name": "PIHTI Log",
        "url": "http://vault.example:4310",
        "state": "ok",
        "version": "0.6.1",
        "detail": "vault open",
        "where": "",
        "start": "",
    },
    {
        "alias": "pihti-diagram",
        "name": "PIHTI diagram",
        "url": "http://rig.example:4186",
        "state": "unreachable",
        "version": "",
        "detail": "no answer within two seconds",
        "where": "",
        "start": "",
    },
]


def test_the_first_call_answers_checking_without_waiting_for_the_lan(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    started, release, counted = threading.Event(), threading.Event(), []
    board = NeighbourBoard(
        home=home, prober=slow_prober(started, release, ROWS, counted)
    )

    rows = board.neighbours()
    assert [row["state"] for row in rows] == ["checking", "checking"]
    # The address is known from the local file, so the card is complete
    # except for what only the neighbour itself can say.
    assert rows[0]["url"] == "http://vault.example:4310"
    assert [row["version"] for row in rows] == ["", ""]
    assert [row["detail"] for row in rows] == ["", ""]
    assert started.wait(10)

    release.set()
    assert board.wait(timeout=10)
    assert [row["state"] for row in board.neighbours()] == ["ok", "unreachable"]
    assert counted == [1]


def test_a_neighbour_with_no_address_is_not_configured_from_the_first_paint(tmp_path):
    """Nobody is being asked about it, so `checking` would promise nothing."""
    started, release, counted = threading.Event(), threading.Event(), []
    board = NeighbourBoard(
        home=tmp_path / "nowhere",
        prober=slow_prober(started, release, ROWS, counted),
    )
    assert {row["state"] for row in board.neighbours()} == {"not configured"}
    release.set()
    board.wait(timeout=10)


def test_a_stale_cache_is_answered_as_it_stands_and_refreshed_behind_it(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    now = [0.0]
    counted = []

    def probe():
        counted.append(len(counted) + 1)
        return [dict(row, version=str(len(counted))) for row in ROWS]

    board = NeighbourBoard(home=home, clock=lambda: now[0], prober=probe)
    board.neighbours()
    assert board.wait(timeout=10)

    now[0] = 300.0  # far outside the window
    stale = board.neighbours()
    assert [row["version"] for row in stale] == ["1", "1"]  # as it stands
    assert board.wait(timeout=10)
    assert counted == [1, 2]  # exactly one refresh, started behind the answer
    assert [row["version"] for row in board.neighbours()] == ["2", "2"]


def test_two_callers_arriving_together_start_one_probe(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    started, release, counted = threading.Event(), threading.Event(), []
    board = NeighbourBoard(
        home=home, prober=slow_prober(started, release, ROWS, counted)
    )

    first = board.neighbours()
    assert started.wait(10)
    second = board.neighbours()  # while the first probe is still in flight
    assert [row["state"] for row in first] == ["checking", "checking"]
    assert [row["state"] for row in second] == ["checking", "checking"]
    assert counted == [1]

    release.set()
    assert board.wait(timeout=10)
    assert counted == [1]


def test_a_probe_that_fails_leaves_the_last_answer_standing(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    now = [0.0]
    tries = []

    def probe():
        tries.append(1)
        if len(tries) > 1:
            raise OSError("the network went away")
        return ROWS

    board = NeighbourBoard(home=home, clock=lambda: now[0], prober=probe)
    board.neighbours()
    assert board.wait(timeout=10)

    now[0] = 300.0
    board.neighbours()
    assert board.wait(timeout=10)
    assert [row["state"] for row in board.neighbours()] == ["ok", "unreachable"]


def test_the_route_answers_without_waiting_for_the_lan(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    started, release, counted = threading.Event(), threading.Event(), []
    board = NeighbourBoard(
        home=home, prober=slow_prober(started, release, ROWS, counted)
    )
    client = create_app(board=board).test_client()
    rows = client.get("/api/neighbours").get_json()["services"]
    assert [row["state"] for row in rows[1:]] == ["checking", "checking"]
    release.set()
    board.wait(timeout=10)


# -- when this machine last heard back, and asking again ----------------------


def stamps(times):
    """A wall clock that hands out the given times, in order."""
    given = list(times)
    return lambda: given.pop(0) if len(given) > 1 else given[0]


def test_nothing_has_been_checked_until_a_probe_has_finished(tmp_path):
    """`None` is "no answer has ever landed here", not "an old one did"."""
    board = NeighbourBoard(
        home=write_settings(tmp_path / ".controlunit"),
        prober=lambda: ROWS,
        stamp=stamps(["14:02:57"]),
    )
    assert board.checked_at() is None
    board.neighbours()
    assert board.wait(timeout=10)
    assert board.checked_at() == "14:02:57"


def test_asking_again_drops_the_answer_and_keeps_when_the_last_one_landed(tmp_path):
    """Two facts, neither standing in for the other: every row says it is
    being asked again, and the line still says when the last answer came."""
    now = [0.0]
    board = NeighbourBoard(
        home=write_settings(tmp_path / ".controlunit"),
        clock=lambda: now[0],
        prober=lambda: ROWS,
        stamp=stamps(["14:02:57", "14:03:20"]),
    )
    board.neighbours()
    assert board.wait(timeout=10)
    assert [row["state"] for row in board.neighbours()] == ["ok", "unreachable"]

    board.invalidate()
    assert board.checked_at() == "14:02:57"
    assert [row["state"] for row in board.neighbours()] == ["checking", "checking"]
    assert board.wait(timeout=10)
    assert board.checked_at() == "14:03:20"


def test_the_route_carries_the_time_of_the_last_check(tmp_path):
    started, release, counted = threading.Event(), threading.Event(), []
    board = NeighbourBoard(
        home=write_settings(tmp_path / ".controlunit"),
        prober=slow_prober(started, release, ROWS, counted),
        stamp=stamps(["14:02:57"]),
    )
    client = create_app(board=board).test_client()
    # The first read is served while the probe it started is still out.
    assert client.get("/api/neighbours").get_json()["checked_at"] is None
    release.set()
    assert board.wait(timeout=10)
    assert client.get("/api/neighbours").get_json()["checked_at"] == "14:02:57"


def test_fresh_answers_at_once_with_checking_rows(tmp_path):
    """The press must not hang the page it was pressed on: `?fresh=1` starts
    the probe behind an answer it does not wait for."""
    home = write_settings(tmp_path / ".controlunit")
    started, release, counted = threading.Event(), threading.Event(), []
    board = NeighbourBoard(
        home=home, prober=slow_prober(started, release, ROWS, counted)
    )
    client = create_app(board=board).test_client()

    client.get("/api/neighbours")
    release.set()
    assert board.wait(timeout=10)
    assert [row["state"] for row in board.neighbours()] == ["ok", "unreachable"]

    started.clear()
    release.clear()
    payload = client.get("/api/neighbours?fresh=1").get_json()
    assert [row["state"] for row in payload["services"][1:]] == ["checking", "checking"]
    assert started.wait(10)
    assert counted == [1, 1]  # the press asked the LAN again, exactly once

    release.set()
    board.wait(timeout=10)


def test_a_plain_read_does_not_ask_again(tmp_path):
    """Only the press invalidates; a poll inside the window asks nobody."""
    now = [0.0]
    counted = []

    def probe():
        counted.append(1)
        return ROWS

    board = NeighbourBoard(
        home=write_settings(tmp_path / ".controlunit"),
        clock=lambda: now[0],
        prober=probe,
    )
    client = create_app(board=board).test_client()
    client.get("/api/neighbours")
    assert board.wait(timeout=10)
    client.get("/api/neighbours")
    assert board.wait(timeout=10)
    assert counted == [1]

    client.get("/api/neighbours?fresh=1")
    assert board.wait(timeout=10)
    assert counted == [1, 1]

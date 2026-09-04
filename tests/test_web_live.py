"""The Live and Log tabs' backing: the ring of samples, the log tail, and the
three routes that serve them. Freshness is a fact about the clock, never a
guess, so the clock is injected."""

import pytest

from controlunit._version import __version__
from controlunit.web import status as status_module
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.server import create_app
from controlunit.web.status import RigStatus, data_state, health_body, state_body

NAMES = ["Ip", "Pu", "Pd", "Bu", "Bd"]
UNITS = {"Ip": "A", "Pu": "Torr", "Pd": "Torr", "Bu": "Torr", "Bd": "Torr"}


class Clock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


@pytest.fixture
def real_hardware(monkeypatch):
    monkeypatch.setattr(status_module, "dummy_hardware_loaded", lambda: False)


def rig(clock=None, keep=7200):
    return RigStatus(
        channels=5, sampling=0.1, names=NAMES, units=UNITS, keep_seconds=keep, clock=clock or Clock()
    )


def feed(status, start, count, step=0.1):
    times = [start + i * step for i in range(count)]
    values = {name: [float(i) for i in range(count)] for name in NAMES}
    status.record_samples(times, values)


# -- the ring --------------------------------------------------------------


def test_samples_land_in_the_latest_values_and_the_count():
    status = rig()
    status.start_run("cu_20260904_120000.csv")
    status.record_samples([1.0, 2.0], {"Ip": [0.5, 0.75], "Pu": [1e-3, 2e-3]})
    snapshot = status.read()
    assert snapshot["values"] == {"Ip": 0.75, "Pu": 2e-3}
    assert snapshot["samples"] == 2
    assert snapshot["file"] == "cu_20260904_120000.csv"


def test_a_new_run_empties_the_ring():
    status = rig()
    status.start_run("first.csv")
    feed(status, 0.0, 10)
    status.start_run("second.csv")
    assert status.read()["samples"] == 0
    assert status.series()["count"] == 0
    assert status.read()["values"] == {}


def test_the_ring_forgets_what_is_older_than_it_keeps():
    status = rig(keep=60)
    feed(status, 0.0, 100, step=1.0)  # 100 s of one-second samples
    body = status.series(window_seconds=0)
    assert body["from"] >= 99.0 - 60.0
    assert body["to"] == 99.0


def test_a_window_cuts_by_time_and_thinning_keeps_the_last_point():
    status = rig()
    feed(status, 0.0, 3000)  # 300 s at 10 Hz
    body = status.series(window_seconds=60, max_points=100)
    points = body["channels"]["Ip"]
    assert body["from"] == pytest.approx(3000 * 0.1 - 0.1 - 60.0, abs=0.11)
    assert len(points) <= 101
    assert points[-1][0] == pytest.approx(299.9)
    assert points[0][0] >= 239.8


def test_full_window_costs_the_same_as_a_short_one():
    status = rig()
    feed(status, 0.0, 20000)
    body = status.series(window_seconds=0, max_points=600)
    for name in NAMES:
        assert len(body["channels"][name]) <= 601


def test_a_value_that_is_not_a_number_is_kept_as_null():
    status = rig()
    status.record_samples([1.0], {"Ip": ["nope"], "Pu": [None]})
    assert status.read()["values"] == {"Ip": None, "Pu": None}


# -- freshness --------------------------------------------------------------


def test_idle_stale_and_live_are_three_different_facts():
    clock = Clock()
    status = rig(clock=clock)
    assert data_state(status.read()) == "idle"

    status.set_acquiring(True)
    assert data_state(status.read()) == "stale"  # running, but nothing yet

    feed(status, clock.now, 3)
    assert data_state(status.read()) == "live"

    clock.now += 1.9
    assert data_state(status.read()) == "live"
    clock.now += 0.2
    assert data_state(status.read()) == "stale"

    status.set_acquiring(False)
    assert data_state(status.read()) == "idle"


def test_the_stale_line_is_never_tighter_than_two_seconds():
    assert status_module.stale_after(0.1) == 2.0
    assert status_module.stale_after(1.0) == 5.0
    assert status_module.stale_after(None) == 2.0


# -- the log ------------------------------------------------------------------


def test_the_log_is_read_back_from_a_sequence_number():
    status = rig()
    status.log("App started", "2026-09-04 12:00:00")
    status.log("Starting acquisition", "2026-09-04 12:00:05")
    everything = status.log_since(0)
    assert [line["text"] for line in everything["lines"]] == [
        "App started",
        "Starting acquisition",
    ]
    assert everything["last"] == 2
    newer = status.log_since(1)
    assert [line["seq"] for line in newer["lines"]] == [2]
    assert status.log_since(2)["lines"] == []


def test_the_log_keeps_only_its_tail():
    status = rig()
    for i in range(status_module.LOG_LINES + 5):
        status.log("line {}".format(i))
    body = status.log_since(0)
    assert body["held"] == status_module.LOG_LINES
    assert body["lines"][0]["text"] == "line 5"


# -- health grows one fact ----------------------------------------------------


def test_health_mentions_the_plasma_pid_when_it_is_on(real_hardware):
    status = rig()
    status.set_acquiring(True)
    status.record_setpoints(plasma_a=1.2)
    assert health_body(status, __version__)["detail"] == (
        "acquiring 5 channels at 10 Hz, plasma PID on"
    )


def test_an_unknown_setpoint_name_is_ignored():
    status = rig()
    status.record_setpoints(nonsense=1)
    assert "nonsense" not in status.read()["setpoints"]


# -- the routes ---------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    clock = Clock()
    status = rig(clock=clock)
    status.start_run("cu_20260904_120000.csv")
    status.set_acquiring(True)
    feed(status, clock.now - 30.0, 300)
    status.log("App started", "2026-09-04 12:00:00")
    app = create_app(status=status, board=NeighbourBoard(home=tmp_path / "nowhere"))
    return app.test_client()


def test_state_carries_values_run_facts_and_freshness(client, real_hardware):
    body = client.get("/api/state").get_json()
    assert body["acquiring"] is True
    assert body["data"]["state"] == "live"
    assert body["run"]["file"] == "cu_20260904_120000.csv"
    assert body["run"]["samples"] == 300
    assert body["run"]["rate"] == "10 Hz"
    assert [c["name"] for c in body["channels"]] == NAMES
    assert body["channels"][0]["unit"] == "A"


def test_state_names_a_file_but_never_a_path(client):
    text = repr(client.get("/api/state").get_json())
    assert "cu_20260904_120000.csv" in text
    for leak in ("/", "\\", "http", "~"):
        assert leak not in text.replace("controlunit", "")


def test_series_honours_the_window_and_the_point_cap(client):
    body = client.get("/api/series?window=10&points=50").get_json()
    assert body["window"] == 10
    assert set(body["channels"]) == set(NAMES)
    assert len(body["channels"]["Ip"]) <= 51
    assert body["to"] - body["from"] <= 10.0 + 0.11


def test_series_clamps_nonsense_to_its_defaults(client):
    body = client.get("/api/series?window=banana&points=99999").get_json()
    assert body["window"] == 300
    assert len(body["channels"]["Ip"]) <= 301


def test_log_route_reads_from_a_sequence_number(client):
    body = client.get("/api/log").get_json()
    assert body["last"] == 1
    assert body["lines"][0]["text"] == "App started"
    assert client.get("/api/log?since=1").get_json()["lines"] == []


@pytest.mark.parametrize("path", ["/", "/log", "/lab", "/api/state", "/api/series", "/api/log"])
def test_every_response_forbids_storage(path, client):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_state_body_survives_an_empty_rig():
    body = state_body(RigStatus(), __version__)
    assert body["data"]["state"] == "idle"
    assert body["run"]["file"] == ""
    assert body["channels"] == []

"""The health report's shape, its status mapping, and the freshness header."""

import pytest

from controlunit._version import __version__
from controlunit.web import status as status_module
from controlunit.web.server import create_app
from controlunit.web.status import RigStatus, health_body


@pytest.fixture
def real_hardware(monkeypatch):
    """Pretend the real boards are attached, whatever this machine has."""
    monkeypatch.setattr(status_module, "dummy_hardware_loaded", lambda: False)


@pytest.fixture
def dummy_hardware(monkeypatch):
    monkeypatch.setattr(status_module, "dummy_hardware_loaded", lambda: True)


def test_health_has_exactly_the_agreed_keys(real_hardware):
    body = health_body(RigStatus(channels=9, sampling=0.1), __version__)
    assert set(body) == {"service", "version", "status", "detail"}
    assert body["service"] == "controlunit"
    assert body["version"] == __version__


def test_acquiring_on_real_hardware_is_ok(real_hardware):
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(True)
    body = health_body(rig, __version__)
    assert body["status"] == "ok"
    assert body["detail"] == "acquiring 9 channels at 10 Hz"


def test_online_and_idle_is_ok_never_degraded(real_hardware):
    """The rig up and recording nothing is the rig waiting to be started.

    Owner correction 2026-09-07, relayed as letter `20260907-86d2c305-2815fa`:
    "It's up and not doing a thing, not degraded." Inactivity is not a
    failure, and an idle rig used to paint the lab's shared board amber all
    night.
    """
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(False)
    body = health_body(rig, __version__)
    assert body["status"] == "ok"
    assert body["detail"] == "idle, not recording"


def test_a_run_that_stopped_delivering_samples_is_degraded(real_hardware):
    """The one failure this record can name today: the reader died.

    A run whose last sample is older than the stale bound has an impaired
    capability — it is recording nothing while believing it is recording —
    which is what happened to Mizuno-kun's depositions on 2026-08-19.
    """
    clock = [1000.0]
    rig = RigStatus(channels=9, sampling=0.1, clock=lambda: clock[0])
    rig.set_acquiring(True)
    rig.record_samples([1000.0], {"Ip": [0.5]})
    assert health_body(rig, __version__)["status"] == "ok"
    clock[0] = 1100.0
    body = health_body(rig, __version__)
    assert body["status"] == "degraded"
    assert "no new reading" in body["detail"]


def test_a_run_whose_first_sample_has_not_landed_is_not_called_degraded(real_hardware):
    """Nothing measured is not a failure measured.

    At ten seconds a sample, the gap between Start and the first reading is
    ordinary; degrading through it would cry wolf every time somebody
    presses Start.
    """
    rig = RigStatus(channels=9, sampling=10.0)
    rig.set_acquiring(True)
    assert health_body(rig, __version__)["status"] == "ok"


def test_dummy_hardware_is_degraded_because_nothing_is_attached(dummy_hardware):
    """Not an invented failure: a capability this process really lacks.

    Dummy devices stand in for the instruments off the rig, so the web
    server is perfectly well and there is nothing for it to read. The board
    says so in the state and names it in the detail; the Pi never sees it.
    """
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(True)
    body = health_body(rig, __version__)
    assert body["status"] == "degraded"
    assert body["detail"] == "acquiring 9 channels at 10 Hz, dummy hardware"


def test_idle_on_dummy_hardware_names_the_stand_in(dummy_hardware):
    body = health_body(RigStatus(channels=9, sampling=0.1), __version__)
    assert body["status"] == "degraded"
    assert body["detail"] == "idle, dummy hardware"


def test_detail_survives_an_unknown_sampling_time(real_hardware):
    rig = RigStatus(channels=9, sampling=None)
    rig.set_acquiring(True)
    assert health_body(rig, __version__)["detail"] == "acquiring 9 channels"


def test_health_route_answers_the_same_body(real_hardware):
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(True)
    client = create_app(status=rig).test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {
        "service": "controlunit",
        "version": __version__,
        "status": "ok",
        "detail": "acquiring 9 channels at 10 Hz",
    }


@pytest.mark.parametrize("path", ["/", "/api/health", "/api/neighbours"])
def test_every_response_forbids_storage(path, tmp_path):
    from controlunit.web.neighbours import NeighbourBoard

    client = create_app(board=NeighbourBoard(home=tmp_path)).test_client()
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_health_body_carries_no_address_or_path(real_hardware):
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(True)
    text = repr(health_body(rig, __version__))
    for leak in ("http", "/", "\\", "@"):
        assert leak not in text.replace("controlunit", "")

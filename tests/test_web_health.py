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


# -- what the rig is actually doing -------------------------------------------
#
# Owner direction 2026-09-07: "If the rig is running. And if it's measuring
# only or have some gas/plasma on." The health report said acquiring or idle
# and nothing about the apparatus, so a rig holding gas and cathode with the
# reader dead read exactly like a rig standing still — which is what the
# 2026-08-19 reader death actually left behind.


def test_nothing_running_and_nothing_driven_is_stopped(real_hardware):
    rig = RigStatus(channels=9, sampling=0.1)
    assert status_module.operating_state(rig.read()) == "stopped"
    assert health_body(rig, __version__)["detail"] == "idle, not recording"


def test_a_run_with_every_output_at_zero_is_measuring_only(real_hardware):
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(True)
    rig.record_setpoints(mfc1_v=0, mfc2_v=0, plasma_a=0.0, cathode_mv=0.0)
    snapshot = rig.read()
    assert status_module.operating_state(snapshot) == "measuring"
    assert status_module.live_outputs(snapshot) == []
    assert health_body(rig, __version__)["detail"] == "acquiring 9 channels at 10 Hz"


@pytest.mark.parametrize(
    "setpoint, value, words",
    [
        ("mfc1_v", 1200, "gas flow H₂"),
        ("mfc2_v", 300, "gas flow O₂"),
        ("cathode_mv", 2520.0, "cathode drive"),
        ("plasma_a", 1.2, "plasma current PID"),
    ],
)
def test_each_output_on_its_own_is_named(real_hardware, setpoint, value, words):
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(True)
    rig.record_setpoints(**{setpoint: value})
    snapshot = rig.read()
    assert status_module.operating_state(snapshot) == "outputs live"
    assert status_module.live_outputs(snapshot) == [words]
    assert health_body(rig, __version__)["detail"] == (
        "acquiring 9 channels at 10 Hz, outputs live: " + words
    )


def test_a_driven_cathode_with_nothing_recording_is_the_dangerous_one(real_hardware):
    """The 2026-08-19 shape: the DAC holds its voltage, the reader is gone.

    Acquisition is off, so every earlier version of this report said "idle,
    not recording" — which reads as safe to restart and was not. The state
    is `outputs live` whatever the acquisition flag says, and the detail
    names what is driven.
    """
    rig = RigStatus(channels=9, sampling=0.1)
    rig.set_acquiring(False)
    rig.record_setpoints(cathode_mv=2520.0, mfc1_v=1200)
    snapshot = rig.read()
    assert status_module.operating_state(snapshot) == "outputs live"
    body = health_body(rig, __version__)
    assert body["detail"] == (
        "not recording, outputs live: gas flow H₂, cathode drive"
    )
    # And it is still not a fault of this program's: nobody pressed Start.
    assert body["status"] == "ok"


def test_the_operating_state_carries_no_value_or_address(real_hardware):
    """Names only. This answer travels to the other two surfaces."""
    rig = RigStatus(channels=9, sampling=0.1)
    rig.record_setpoints(cathode_mv=2520.0, plasma_a=1.2)
    text = repr(status_module.live_outputs(rig.read()))
    for leak in ("2520", "1.2", "http", "/"):
        assert leak not in text


def test_a_setpoint_that_is_not_a_number_is_not_a_live_output(real_hardware):
    """Nothing here may raise into a request, and a gauge mode is a word."""
    rig = RigStatus(channels=9, sampling=0.1)
    rig.record_setpoints(ig_mode="Torr", ig_range=-8, cathode_mv="")
    assert status_module.live_outputs(rig.read()) == []


def test_the_served_view_keeps_request_lines_out_of_stderr():
    """One line per poll was filling the rig's stderr file (2026-09-10)."""
    import logging

    from controlunit.web import server

    logging.getLogger("werkzeug").setLevel(logging.NOTSET)
    server.quiet_request_log()
    assert logging.getLogger("werkzeug").getEffectiveLevel() == logging.WARNING
    assert not logging.getLogger("werkzeug").isEnabledFor(logging.INFO)

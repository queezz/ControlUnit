"""Neighbour states: answered, answered badly, silent, and never configured.

`down` and `unreachable` are different facts about different failures, and
neither is "not configured". These tests hold the three apart.
"""

import io
import json
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


def test_addresses_come_from_the_local_settings_file(tmp_path):
    home = write_settings(tmp_path / ".controlunit")
    addresses = read_addresses(home)
    assert addresses == {
        "pihti-log": "http://vault.example:4310",
        "pihti-diagram": "http://rig.example:4186",
    }


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
    rows = {row["alias"]: row for row in NeighbourBoard(home=home).neighbours()}
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
    rows = {row["alias"]: row for row in NeighbourBoard(home=home).neighbours()}
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
    rows = {row["alias"]: row for row in NeighbourBoard(home=home).neighbours()}
    assert rows["pihti-log"]["state"] == "down"
    assert rows["pihti-diagram"]["state"] == "ok"


def test_an_answer_that_is_not_a_health_report_is_degraded(tmp_path, monkeypatch):
    home = write_settings(tmp_path / ".controlunit")

    def opener(url, timeout=None):
        return FakeResponse(b"<html>hello</html>")

    monkeypatch.setattr(neighbourhood.urllib.request, "urlopen", opener)
    rows = {row["alias"]: row for row in NeighbourBoard(home=home).neighbours()}
    assert rows["pihti-log"]["state"] == "degraded"
    assert rows["pihti-log"]["detail"] == "answered, but not with a health report"


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
    assert len(calls) == 2
    now[0] = 5.0  # inside the ten-second window: no new requests
    board.neighbours()
    assert len(calls) == 2
    now[0] = 30.0  # the window has passed
    board.neighbours()
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
    "state", ["ok", "degraded", "down", "unreachable", "not configured"]
)
def test_every_state_the_page_can_show_has_a_legend_line(state):
    from controlunit.web.server import STATE_LEGEND

    assert state in {name for name, _ in STATE_LEGEND}

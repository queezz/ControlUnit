"""The four pages render, share one tab bar, and keep their assets local."""

import re

import pytest

from controlunit._version import __version__
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.server import create_app


@pytest.fixture
def client(tmp_path):
    return create_app(board=NeighbourBoard(home=tmp_path / "nowhere")).test_client()


@pytest.fixture
def live(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


@pytest.fixture
def lab(client):
    response = client.get("/lab")
    assert response.status_code == 200
    return response.get_data(as_text=True)


@pytest.fixture
def log(client):
    response = client.get("/log")
    assert response.status_code == 200
    return response.get_data(as_text=True)


@pytest.fixture
def control(client):
    response = client.get("/control")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_live_is_home_and_shows_the_five_pens(live):
    assert 'aria-current="page">Live<' in live
    for name in ("Ip", "Pu", "Pd", "Bu", "Bd"):
        assert 'data-readout="{}"'.format(name) in live
    assert 'id="chart-plasma"' in live
    assert 'id="chart-pressure"' in live


def test_live_offers_the_same_windows_as_the_rig(live):
    for seconds in (20, 60, 300, 900, 1800, 3600, 7200, 0):
        assert 'data-window="{}"'.format(seconds) in live


def test_the_tab_bar_leads_to_every_tab_and_marks_none_unbuilt(live, log, lab, control):
    for page in (live, log, lab, control):
        assert "tab-mark" not in page
        assert 'href="/control"' in page
        assert 'href="/log"' in page
        assert 'href="/lab"' in page


def test_control_is_the_current_tab_on_its_own_page(control):
    assert 'aria-current="page">Control<' in control


def test_control_carries_its_five_groups_as_jump_targets(control):
    for anchor in (
        "sec-acquisition",
        "sec-gas",
        "sec-plasma",
        "sec-gauge",
        "sec-baselines",
    ):
        assert 'id="{}"'.format(anchor) in control
        assert 'href="#{}"'.format(anchor) in control


def test_control_offers_every_command_the_slice_built(control):
    assert 'data-role="stop-all"' in control
    for number in (1, 2):
        assert 'data-mfc="{}"'.format(number) in control
    assert 'data-role="plasma-set"' in control
    assert 'data-role="plasma-off"' in control
    assert 'data-role="gauge-mode"' in control
    assert 'data-role="gauge-range"' in control
    assert 'data-role="sync"' in control
    for channel in ("Ip", "Bu", "Bd"):
        assert 'data-zero="{}"'.format(channel) in control


def test_control_offers_the_same_gauge_range_the_rig_does(control):
    for decade in range(-8, -2):
        assert 'data-range="{}"'.format(decade) in control


def test_the_gate_is_explained_in_exactly_one_place(control):
    """The Remote card teaches once; no row carries its own reason."""
    assert control.count("Setting is off until the switch on the rig is on.") == 1
    assert control.count('data-role="remote-why"') == 1
    assert control.count('data-role="status"') == 1


def test_control_asks_state_and_posts_the_command_routes(client):
    script = client.get("/static/js/control.js").get_data(as_text=True)
    assert "/api/state" in script
    for route in (
        "/api/identify",
        "/api/stop-all",
        "/api/mfc/",
        "/api/plasma-current",
        "/api/gauge",
        "/api/sync",
        "/api/zero",
    ):
        assert route in script


def test_the_lab_page_names_the_three_services(lab):
    for name in ("ControlUnit", "PIHTI Log", "PIHTI diagram"):
        assert name in lab


def test_the_lab_page_asks_the_neighbours_route_for_its_refresh(client):
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert "/api/neighbours" in script


def test_the_live_page_polls_state_and_series(client):
    script = client.get("/static/js/live.js").get_data(as_text=True)
    assert "/api/state" in script
    assert "/api/series" in script


def test_an_unconfigured_neighbour_says_nothing_about_starting(lab):
    # With no local config there is no `where` and no `start`, so the card
    # carries no start line rather than a guessed one.
    assert "lab pihti-log" not in lab
    assert "lab pihti-diagram" not in lab
    assert "scripts/run_controlunit.sh" in lab  # this program's own launcher


def test_assets_are_keyed_to_the_version(live, log, lab, control):
    for page, asset in (
        (live, "js/live.js"),
        (log, "js/log.js"),
        (lab, "js/lab.js"),
        (control, "js/control.js"),
    ):
        assert re.search(re.escape("css/controlunit.css") + r"\?v=" + re.escape(__version__), page)
        assert re.search(re.escape(asset) + r"\?v=" + re.escape(__version__), page)


@pytest.mark.parametrize("path", ["/", "/control", "/log", "/lab"])
def test_the_pages_fetch_nothing_from_the_internet(client, path):
    page = client.get(path).get_data(as_text=True)
    assert "//" not in page.replace("http://", "").replace("https://", "")
    assert "cdn" not in page.lower()


@pytest.mark.parametrize("path", ["/", "/control", "/log", "/lab"])
def test_every_page_uses_the_three_track_grid_with_both_rails(client, path):
    page = client.get(path).get_data(as_text=True)
    assert 'class="page"' in page
    assert "rail-left" in page
    assert "rail-right" in page


def test_the_neighbour_states_are_explained_in_exactly_one_place(lab):
    """The rail legend teaches once; every chip elsewhere only states."""
    for meaning in (
        "nothing answered from this machine",
        "answered, and said it is not working",
    ):
        assert lab.count(meaning) == 1


def test_the_data_states_are_explained_in_exactly_one_place(live):
    for meaning in ("without a sample", "when acquisition is off"):
        assert live.count(meaning) == 1


def test_the_data_card_shows_one_pill_only(live):
    """The chip is the reading; the other states are words, never pills."""
    card = live[live.index('class="rail-label">Data<'):]
    card = card[:card.index("</section>")]
    assert card.count('class="chip') == 1

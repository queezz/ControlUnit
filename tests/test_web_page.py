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


def test_the_two_kinds_of_gauge_get_a_panel_each(live):
    """One axis could not serve both, so neither was readable."""
    assert "Ion gauges, Torr" in live
    assert "Baratrons, Torr" in live
    assert 'id="chart-ig"' in live
    assert 'id="chart-bar"' in live
    assert 'data-channels="Pu,Pd"' in live
    assert 'data-channels="Bu,Bd"' in live
    assert "chart-pressure" not in live


def test_the_scales_card_offers_an_axis_for_each_panel(live):
    for choice in ("log", "lin"):
        assert 'data-scale-ig="{}"'.format(choice) in live
        assert 'data-scale-bar="{}"'.format(choice) in live
    assert "Ion gauges<" in live
    assert "Baratrons<" in live
    # Log leads the ion gauges, linear the Baratrons, because of the
    # offsets a Baratron reads around.
    assert 'data-scale-ig="log" aria-pressed="true"' in live
    assert 'data-scale-bar="lin" aria-pressed="true"' in live


def test_live_offers_the_smoothing_the_current_needs(live):
    assert 'class="rail-label">Smoothing ' in live
    for samples in (0, 5, 15, 51):
        assert 'data-smooth="{}"'.format(samples) in live
    # What the choice does is said once, on the card's own heading line.
    assert live.count("median of N samples") == 1


def test_the_three_zeroable_channels_say_what_they_took_off(live):
    """A reader must not have to guess whether a value is adjusted."""
    for name in ("Ip", "Bu", "Bd"):
        card = live[live.index('data-readout="{}"'.format(name)):]
        card = card[:card.index("</div>")]
        assert 'data-role="zero"' in card
    for name in ("Pu", "Pd"):
        card = live[live.index('data-readout="{}"'.format(name)):]
        card = card[:card.index("</div>")]
        assert 'data-role="zero"' not in card
    assert live.count('data-role="zero"') == 3
    # Reserved on all three, whatever the rig currently holds, so a zero
    # taken while the page is open moves nothing.
    assert live.count(">as measured<") == 3


def test_the_zero_is_explained_in_exactly_one_place(live):
    assert live.count("the data file keeps the signal as measured") == 1


def test_the_readout_cards_carry_their_own_pen(live):
    """The card's colour comes from the pen list the charts draw with."""
    for colour in ("#8d3de3", "#c9004d", "#6ac600", "#ffb405", "#00a3af"):
        assert "--pen: {}".format(colour) in live


def test_the_window_says_once_that_full_is_this_browser(live):
    assert live.count("Full is what this browser has seen") == 1


def test_live_offers_the_same_windows_as_the_rig(live):
    for seconds in (20, 60, 300, 900, 1800, 3600, 7200, 0):
        assert 'data-window="{}"'.format(seconds) in live


def test_live_offers_a_readout_size_and_a_poll_rate(live):
    assert 'class="rail-label">Display<' in live
    assert 'class="rail-label">Poll ' in live
    for choice in ("display", "poll"):
        assert 'data-{}="normal"'.format(choice) in live
    assert 'data-display="big"' in live
    assert 'data-poll="fast"' in live
    # That the fast poll does not survive a reload is said once, on the
    # card's own heading line, and nowhere else on the page.
    assert live.count("forgotten on reload") == 1


def test_the_big_readouts_are_one_class_over_the_same_dom(client, live):
    """Nothing appears or leaves when big is pressed: only a class changes."""
    script = client.get("/static/js/live.js").get_data(as_text=True)
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    assert "live--big" in script
    assert ".live--big" in css
    assert live.count('class="readout"') == 5


def test_the_fast_poll_is_not_remembered_and_the_big_readouts_are(client):
    """A page opened tomorrow must not still be asking four times a second."""
    script = client.get("/static/js/live.js").get_data(as_text=True)
    assert "JSON.stringify(view)" in script  # `view` is what is stored
    assert "view.big" in script
    assert "view.fast" not in script


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


def test_control_says_who_has_the_rig_in_exactly_one_line(control):
    """The lock is explained once, in the Remote card, and never on a row."""
    assert control.count('data-role="holder"') == 1
    assert control.count("Nobody has control") == 1
    assert control.count('data-role="take-over"') == 1
    assert control.count(">Take over<") == 1


def test_the_take_over_button_rests_disabled_until_the_gate_opens(control):
    """With the switch off nobody may take anything, so it cannot be pressed."""
    card = control[control.index('class="rail-label">Remote control<'):]
    card = card[:card.index("</section>")]
    assert 'data-role="take-over"' in card
    assert "disabled" in card


def test_control_asks_state_and_posts_the_command_routes(client):
    script = client.get("/static/js/control.js").get_data(as_text=True)
    assert "/api/state" in script
    for route in (
        "/api/identify",
        "/api/take-over",
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


def test_the_live_page_fills_once_and_then_asks_only_for_the_new(client):
    """A page open all afternoon costs the Pi the newest rows, not the
    afternoon it already holds."""
    script = client.get("/static/js/live.js").get_data(as_text=True)
    assert "window=0&points=" in script
    assert '"since=" + encodeURIComponent(newest)' in script
    # The window cuts what is already here; it sends nothing.
    assert "STORE_SECONDS = 24 * 60 * 60" in script


def test_the_readouts_are_written_as_a_real_power_of_ten(client):
    script = client.get("/static/js/live.js").get_data(as_text=True)
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    assert '"×10<sup>"' in script
    # The canvas has no markup to lift an exponent with, so its axis
    # labels carry the superscript glyphs themselves.
    assert '"10" + superText(' in script
    # The lift cannot make the line box taller, so a value crossing into
    # exponent form never changes the card's height.
    assert ".readout-value sup" in css
    assert "line-height: 0" in css


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

"""The four pages render, share one tab bar, and keep their assets local."""

import re

import pytest

from controlunit._version import __version__
from controlunit.web.fence import Fence
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.roster import Roster
from controlunit.web.server import create_app

ROSTER = """\
{"schema": "pihti-operators/v1",
 "operators": [{"username": "hashizuka", "display_name": "Hashizuka Takuma"},
               {"username": "queezz", "display_name": "Arseniy Kuzmin"}]}
"""

WORD = "plasmabox"


def app_for(tmp_path, home=None, fence_home=None):
    """A client whose machine knows nothing it was not given here."""
    nowhere = tmp_path / "nowhere"
    return create_app(
        board=NeighbourBoard(home=nowhere),
        roster=Roster(home=nowhere if home is None else home),
        fence=Fence(home=nowhere if fence_home is None else fence_home),
    ).test_client()


def with_a_word(tmp_path):
    """A machine that holds the lab's word, as the rig will."""
    fence_home = tmp_path / ".controlunit-fence"
    fence_home.mkdir()
    (fence_home / "fence.txt").write_text(WORD + "\n", encoding="utf-8")
    return app_for(tmp_path, fence_home=fence_home)


@pytest.fixture
def client(tmp_path):
    return app_for(tmp_path)


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
    # One card for both, because six rail cards outgrew a 700px window.
    assert 'class="rail-label">Readouts ' in live
    assert 'aria-label="Readout size"' in live and 'aria-label="Poll rate"' in live
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
    assert 'data-role="acq-start"' in control
    assert 'data-role="acq-stop"' in control
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


def test_control_offers_the_same_sampling_times_the_rig_does(control):
    """The four the Settings dock offers, written the way it writes them."""
    for value in ("10", "1", "0.1", "0.01"):
        assert 'data-seconds="{}"'.format(value) in control
        assert ">{} s<".format(value) in control
    assert control.count('data-role="sampling"') == 4
    assert control.count('data-role="sampling-now"') == 1


def test_acquisition_no_longer_says_it_can_only_be_run_from_the_rig(control):
    """The group's note is the one place the new rule is stated."""
    assert "never from here" not in control
    assert control.count(
        "Started and stopped here or at the rig; stopping closes the data "
        "file and turns every output off."
    ) == 1


def test_the_run_controls_sit_under_the_run_s_own_facts(control):
    """Nothing is inserted above a control the reader will press again."""
    group = control[control.index('id="sec-acquisition"'):]
    group = group[:group.index("</section>")]
    assert group.index('data-fact="samples"') < group.index('data-role="acq-start"')
    assert group.index('data-role="acq-start"') < group.index('data-role="acq-stop"')
    assert group.index('data-role="acq-stop"') < group.index('data-role="sampling"')


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
        "/api/acquisition/start",
        "/api/acquisition/stop",
        "/api/sampling",
        "/api/mfc/",
        "/api/plasma-current",
        "/api/gauge",
        "/api/sync",
        "/api/zero",
    ):
        assert route in script


def test_stopping_a_run_from_the_browser_asks_once_before_it_sends(client):
    """The one destructive press on the page, in the group's own words."""
    script = client.get("/static/js/control.js").get_data(as_text=True)
    assert "window.confirm(STOP_QUESTION)" in script
    assert "closes the data file and turns every output off" in script
    assert script.count("STOP_QUESTION") == 2  # declared once, asked once


def test_start_is_the_one_control_the_idle_rig_enables(client):
    """Every other control needs a run; the reason says so in one place."""
    script = client.get("/static/js/control.js").get_data(as_text=True)
    assert "Nothing is running; you may start acquisition." in script
    assert 'root.querySelector(\'[data-role="acq-start"]\')' in script
    assert "!state.acquiring" in script


def test_the_lab_page_names_the_three_services(lab):
    for name in ("ControlUnit", "PIHTI Log", "PIHTI diagram"):
        assert name in lab


def test_the_lab_page_asks_the_neighbours_route_for_its_refresh(client):
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert "/api/neighbours" in script


def test_the_lab_left_rail_carries_the_one_control_this_tab_has(lab):
    """Controls left, on this tab as on every other: asking again is a press,
    and the line beneath it says when this machine last heard back."""
    card = lab[lab.index('class="rail-label">Check<'):]
    card = card[:card.index("</section>")]
    assert 'data-role="refresh"' in card
    assert ">Ask again now</button>" in card
    assert 'data-role="checked"' in card


def test_the_lab_checked_line_says_so_before_anything_has_been_checked(tmp_path):
    """Nothing has landed yet, which is not the same as an old answer."""
    nowhere = tmp_path / "nowhere"
    board = NeighbourBoard(home=nowhere, prober=lambda: None)
    reader = create_app(board=board, roster=Roster(home=nowhere)).test_client()
    assert "Not checked yet." in reader.get("/lab").get_data(as_text=True)


def test_the_lab_checked_line_names_the_time_once_a_check_has_landed(tmp_path):
    nowhere = tmp_path / "nowhere"
    board = NeighbourBoard(home=nowhere, stamp=lambda: "14:02:57")
    reader = create_app(board=board, roster=Roster(home=nowhere)).test_client()
    reader.get("/lab")  # the first read starts the probe
    assert board.wait(timeout=10)
    assert "Checked 14:02:57." in reader.get("/lab").get_data(as_text=True)


def test_a_service_card_says_its_version_what_it_said_and_how_it_starts(lab):
    """The facts a person asks for, in the order they ask them."""
    card = lab[lab.index('data-alias="controlunit"'):]
    card = card[:card.index("</article>")]
    for term in ("<dt>Version</dt>", "<dt>Says</dt>", "<dt>Runs</dt>", "<dt>Start</dt>"):
        assert term in card
    assert "scripts/run_controlunit.sh" in card
    assert "This is the service you are reading." in card


def test_this_program_is_started_from_the_rigs_own_screen(lab):
    """ControlUnit starts with its own GUI, from the desktop shortcut. There
    is no `lab controlunit` alias, so the card never offers one (owner
    report 2026-09-07, relayed from PIHTI Log)."""
    card = lab[lab.index('data-alias="controlunit"'):]
    card = card[:card.index("</article>")]
    assert "rig&#39;s own screen" in card or "rig's own screen" in card
    assert "desktop shortcut starts the whole program" in card
    assert "lab controlunit" not in lab


def test_the_start_row_leads_with_words_and_hides_the_command(lab):
    """Meaning first; machinery behind a toggle (fleet's WEBUI.md). The
    command is in the markup and hidden until the reader asks for it."""
    card = lab[lab.index('data-alias="controlunit"'):]
    card = card[:card.index("</article>")]
    row = card[card.index("<dt>Start</dt>"):]
    assert 'data-role="start-how"' in row
    assert 'data-role="start-toggle"' in row
    assert 'aria-expanded="false"' in row
    assert 'aria-controls="start-controlunit"' in row
    assert ">show</button>" in row
    # The words come before the toggle, and the command after both.
    assert row.index('data-role="start-how"') < row.index('data-role="start-toggle"')
    assert row.index('data-role="start-toggle"') < row.index('id="start-controlunit"')
    assert 'data-role="start" hidden>scripts/run_controlunit.sh</code>' in row


def test_a_service_with_no_command_reserves_no_toggle(lab):
    """Nothing is configured here, so the row ends at the em dash: no
    toggle, no command line, nothing held open for a line that is not
    coming."""
    card = lab[lab.index('data-alias="pihti-log"'):]
    card = card[:card.index("</article>")]
    row = card[card.index("<dt>Start</dt>"):]
    assert 'data-role="start-toggle"' in row and "hidden>show</button>" in row
    assert 'data-role="start" hidden></code>' in row


def test_a_refresh_never_closes_an_open_disclosure(client):
    """The board repaints every two seconds while a state is checking. What
    the reader opened is kept and re-applied, never reset by an answer."""
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert "sessionStorage" in script
    assert "applyStart(card, service.alias, command)" in script
    assert "opened[alias]" in script


def test_a_neighbour_with_no_address_says_so_rather_than_linking_nowhere(lab):
    card = lab[lab.index('data-alias="pihti-log"'):]
    card = card[:card.index("</article>")]
    assert "No address on this machine." in card
    assert ">Open PIHTI Log</a>" in card  # rendered, hidden, and ready
    assert 'data-role="open"' in card and "hidden>Open" in card


def test_the_lab_page_can_ask_the_lan_again_without_waiting_for_it(client):
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert "/api/neighbours?fresh=1" in script
    assert "button.disabled = true" in script
    assert "Not checked yet." in script


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
    from controlunit.web.server import STATE_LEGEND

    for _, meaning in STATE_LEGEND:
        assert lab.count(meaning) == 1


def test_the_rail_teaches_at_a_glance_with_the_chips_the_cards_wear(lab):
    """One lead line, then the six states as chips with a few words each —
    the whole legend read at a glance rather than three muted paragraphs
    (owner report 2026-09-07). `checking` is there because a page served
    before the LAN answered shows it."""
    from controlunit.web.server import STATE_LEGEND

    card = lab[lab.index('class="rail-label">The ensemble<'):]
    card = card[:card.index("</section>")]
    assert "What this machine can reach right now." in card
    for state, meaning in STATE_LEGEND:
        chip = '<span class="chip chip-{}">{}</span>'.format(
            state.replace(" ", "-"), state
        )
        assert card.count(chip) == 1
        assert card.count("<dd>{}</dd>".format(meaning)) == 1
    # Every state the board can paint has a line, `checking` included.
    assert {state for state, _ in STATE_LEGEND} == {
        "ok", "degraded", "down", "unreachable", "not configured", "checking",
    }


def test_the_rest_of_the_ensemble_card_sits_behind_one_more_press(lab):
    """One toggle, one stable position: it is the last thing above the
    panel it reveals, so nothing over it moves when it is pressed."""
    card = lab[lab.index('class="rail-label">The ensemble<'):]
    card = card[:card.index("</section>")]
    assert 'data-role="more"' in card
    assert 'aria-expanded="false"' in card
    assert 'aria-controls="ensemble-more"' in card
    assert ">More</button>" in card
    assert 'id="ensemble-more" hidden' in card
    assert card.index('data-role="more"') < card.index('id="ensemble-more"')
    assert "Three surfaces stand side by side" in card
    assert "started on its own machine" in card


def test_the_more_press_is_remembered_and_flips_its_own_word(client):
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert '"Less" : "More"' in script
    assert "MORE_KEY" in script


def test_the_lab_page_asks_again_while_a_state_is_still_checking(client):
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert '"checking"' in script


def test_the_acting_as_field_is_free_text_without_a_roster(control):
    card = control[control.index('class="rail-label">Acting as<'):]
    assert '<input type="text" id="actor-name"' in card
    assert "Written in the log beside what you" in card
    assert "the lab's roster" not in card


def test_the_acting_as_field_offers_the_roster_when_this_machine_has_one(tmp_path):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "operators.json").write_text(ROSTER, encoding="utf-8")
    page = app_for(tmp_path, home=home).get("/control").get_data(as_text=True)
    card = page[page.index('class="rail-label">Acting as<'):]
    assert '<select id="actor-name"' in card
    assert "— choose —" in card
    assert '<option value="Hashizuka Takuma"' in card
    assert '<option value="Arseniy Kuzmin"' in card
    # No note under the list: the list says where its names come from.
    assert "Names come from the lab's roster." not in card
    assert '<input type="text" id="actor-name"' not in card


def test_the_data_states_are_explained_in_exactly_one_place(live):
    for meaning in ("without a sample", "when acquisition is off"):
        assert live.count(meaning) == 1


def test_the_data_card_shows_one_pill_only(live):
    """The chip is the reading; the other states are words, never pills."""
    card = live[live.index('class="rail-label">Data<'):]
    card = card[:card.index("</section>")]
    assert card.count('class="chip') == 1


def test_a_neighbour_opens_beside_this_page_not_in_its_place(lab):
    """The rig's view stays open when a neighbour is opened (walk 2026-09-07)."""
    assert 'data-role="open"' in lab
    assert lab.count('target="_blank" rel="noopener"') == lab.count('data-role="open"')


# -- the lab's word ------------------------------------------------------------


def test_no_fence_row_on_a_machine_that_holds_no_word(control):
    """Every off-rig run is exactly the page it was before this existed."""
    assert 'id="fence-word"' not in control
    assert 'data-role="save-fence"' not in control
    assert "the lab's word" not in control


def test_the_fence_row_appears_only_where_the_machine_holds_a_word(tmp_path):
    page = with_a_word(tmp_path).get("/control").get_data(as_text=True)
    card = page[page.index('class="rail-label">Acting as<'):]
    card = card[:card.index("</section>")]
    assert '<input type="password" id="fence-word"' in card
    assert 'data-role="save-fence"' in card
    assert 'placeholder="the lab&#39;s word"' in card


def test_the_word_is_explained_once_and_named_a_fence_not_a_secret(tmp_path):
    page = with_a_word(tmp_path).get("/control").get_data(as_text=True)
    assert page.count("A word from the lab, not a secret") == 1
    assert page.count('data-role="save-fence"') == 1


def test_a_browser_past_the_fence_still_has_a_field_to_type_in(tmp_path):
    """A word changed in the lab has to be typable again."""
    client = with_a_word(tmp_path)
    assert client.post("/api/fence", json={"word": WORD}).status_code == 200
    page = client.get("/control").get_data(as_text=True)
    assert '<input type="password" id="fence-word"' in page
    assert 'placeholder="word saved"' in page


def test_the_take_over_button_is_shut_behind_the_fence_too(tmp_path):
    page = with_a_word(tmp_path).get("/control").get_data(as_text=True)
    card = page[page.index('class="rail-label">Remote control<'):]
    card = card[:card.index("</section>")]
    assert 'data-role="take-over"' in card
    assert "disabled" in card


def test_the_gate_states_the_word_as_one_more_reason_in_one_place(client):
    """The reason order is the switch, then the word, then the run and the
    lock; each is a sentence the Remote card says once."""
    script = client.get("/static/js/control.js").get_data(as_text=True)
    assert script.count(
        "Setting is off until you type the lab's word below."
    ) == 1
    switch = script.index("Setting is off until the switch on the rig is on.")
    word = script.index("Setting is off until you type the lab's word below.")
    running = script.index("Setting is off while no acquisition is running.")
    assert switch < word < running


def test_control_posts_the_fence_route(client):
    script = client.get("/static/js/control.js").get_data(as_text=True)
    assert "/api/fence" in script
    assert "the fence is open" in script


def test_every_page_carries_the_tile_favicon(live, log, lab, control):
    """One icon, the tool's own, on every page (queezz, 2026-09-07)."""
    for page in (live, log, lab, control):
        assert 'rel="icon" type="image/svg+xml"' in page
        assert "/static/favicon.svg?v=" in page


def test_the_favicon_is_served_and_hand_drawn(client):
    answer = client.get("/static/favicon.svg")
    assert answer.status_code == 200
    body = answer.get_data(as_text=True)
    assert "<svg" in body and ">CU<" in body
    assert answer.headers["Cache-Control"] == "no-store"

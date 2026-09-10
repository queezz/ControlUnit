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
    assert 'aria-current="page">ControlUnit ' in live
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
    # Log leads the ion gauges, linear the Baratrons, because of the
    # offsets a Baratron reads around.
    compact = " ".join(live.split())
    assert 'data-scale-ig="log" aria-pressed="true"' in compact
    assert 'data-scale-bar="lin" aria-pressed="true"' in compact
    # Each scale belongs to its chart, not the distant rail.
    for title, axis in (("Ion gauges, Torr", "ig"), ("Baratrons, Torr", "bar")):
        chart = live[live.index('aria-label="{}"'.format(title)):]
        chart = chart[:chart.index("</section>")]
        assert 'data-scale-{}="log"'.format(axis) in chart
        assert 'data-scale-{}="lin"'.format(axis) in chart


def test_live_offers_the_smoothing_the_current_needs(live):
    """The median remains a single choice affecting curves and readouts."""
    assert 'class="rail-label">Median<' in live
    for samples in (0, 5, 15, 51):
        assert 'data-smooth="{}"'.format(samples) in live
    assert live.count('data-scale-ig="log"') == 1
    assert live.count('data-scale-bar="lin"') == 1
    assert "Median smooths the curves and the readouts." not in live


def test_a_readout_card_is_a_name_a_number_a_unit_and_one_tag(live):
    """Nothing else, and the same four on every card: what a card says can
    change, how tall it stands cannot."""
    for name in ("Ip", "Pu", "Pd", "Bu", "Bd"):
        card = live[live.index('data-readout="{}"'.format(name)):]
        card = card[:card.index("</div>")]
        assert 'class="readout-name"' in card
        assert 'data-role="value"' in card
        assert 'data-role="unit"' in card
        assert 'data-role="readout-note"' in card
    assert live.count('data-role="readout-note"') == 5
    # The tag is written by the page from what the rig reports, so the
    # markup ships it empty and no card holds a line open for it.
    assert '<span class="readout-note" data-role="readout-note"></span>' in live


def test_nothing_on_a_card_lectures_or_reserves_a_line(live):
    """"as measured" said nothing — every signal on this page is as
    measured — and the residual line and the detection-limit paragraph
    were the tiny manual the owner asked to be rid of (2026-09-10)."""
    assert ">as measured<" not in live
    assert 'data-role="zero"' not in live
    assert 'data-role="residual"' not in live
    assert "readout-residual" not in live
    assert "Detection limit not characterized" not in live
    assert "measurement-note" not in live


def test_the_zero_is_explained_in_the_docs_not_on_the_page(live):
    assert "the data file keeps the signal as measured" not in live


def test_the_readout_cards_carry_their_own_pen(live):
    """The card's colour comes from the pen list the charts draw with."""
    for colour in ("#8d3de3", "#c9004d", "#6ac600", "#ffb405", "#00a3af"):
        assert "--pen: {}".format(colour) in live


def test_the_window_does_not_explain_full_on_the_page(live):
    assert "Full is what this browser has seen" not in live


def test_live_offers_the_same_windows_as_the_rig(live):
    for seconds in (20, 60, 300, 900, 1800, 3600, 7200, 0):
        assert 'data-window="{}"'.format(seconds) in live


def test_live_offers_a_readout_size_and_a_poll_rate(live):
    # One card for both, because six rail cards outgrew a 700px window.
    assert 'class="rail-label">Polling<' in live
    main = live[live.index('<main'):live.index('</main>')]
    assert main.count('data-display="normal"') == 1
    assert main.count('data-display="big"') == 1
    assert 'aria-label="Readout size"' in live and 'aria-label="Poll rate"' in live
    for choice in ("display", "poll"):
        assert 'data-{}="normal"'.format(choice) in live
    assert 'data-display="big"' in live
    assert 'data-poll="fast"' in live
    # That the fast poll does not survive a reload is said once, on the
    # card's own heading line, and nowhere else on the page.
    assert "forgotten on reload" not in live


def test_the_big_readouts_are_one_class_over_the_same_dom(client, live):
    """Nothing appears or leaves when big is pressed: only a class changes."""
    script = client.get("/static/js/live.js").get_data(as_text=True)
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    assert "live--big" in script
    assert ".live--big" in css
    assert live.count('class="readout"') == 5


def test_small_readouts_reserve_no_room_they_are_not_using(client):
    """queezz, 2026-09-10: "Small now have large boxes small font. Which
    defeats the purpose." A small card is two rows of content and the
    padding around them, in Operate as everywhere else."""
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    # The rules, not the comments beside them: this file explains its own
    # arithmetic, and an explanation naming a property is not that property.
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def block(selector):
        start = rules.index(selector + " {")
        return rules[start:rules.index("}", start)]

    for selector in (".readout", ".live--big .readout"):
        assert "min-height" not in block(selector)
    # The line that reserved two lines under every card, and the residual
    # line beneath the Baratrons, are gone rather than merely emptied.
    assert "readout-zero" not in rules
    assert "readout-residual" not in rules
    assert "measurement-note" not in rules
    # The tag rides in the name row and cannot leave it, whatever it says.
    note = block(".readout-note")
    assert "grid-row: 1" in note and "white-space: nowrap" in note
    # Operate keeps the same compact card; nothing here re-inflates it.
    assert ".control-workspace:not(.live--big) .readout { padding: 6px 5px;" in rules


def test_the_fast_poll_is_not_remembered_and_the_big_readouts_are(client):
    """A page opened tomorrow must not still be asking four times a second."""
    script = client.get("/static/js/live.js").get_data(as_text=True)
    assert "JSON.stringify(view)" in script  # `view` is what is stored
    assert "view.big" in script
    assert "view.fast" not in script


def test_the_tab_bar_leads_to_every_tab_and_marks_none_unbuilt(live, log, lab, control):
    for page in (live, log, lab, control):
        assert "tab-mark" not in page
        assert 'href="/control"' not in page
        assert page.count('href="/"') == 1
        assert 'href="/log"' in page
        assert 'href="/lab"' in page


def test_control_is_the_current_tab_on_its_own_page(control):
    assert 'aria-current="page">ControlUnit ' in control


def test_control_carries_its_five_groups_as_jump_targets(control):
    for anchor in (
        "sec-acquisition",
        "sec-gas",
        "sec-plasma",
        "sec-gauge",
        "sec-sync",
    ):
        assert 'id="{}"'.format(anchor) in control
        assert control.count('id="{}"'.format(anchor)) == 1


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
    """The consequence is stated once beside Start and Stop."""
    assert "never from here" not in control
    assert control.count("Stop ends recording + outputs.") == 1


def test_the_run_controls_stand_together_and_their_numbers_beside_them(control):
    """The faceplate is presses in operating order; the numbers they are
    read against stand in the readings column, never between two presses
    (queezz, 2026-09-07: "spread nicely but thin. Not on a glance")."""
    group = control[control.index('id="sec-acquisition"'):]
    group = group[:group.index("</section>")]
    rail = control[:control.index("<main")]
    assert rail.index('data-role="acq-start"') < rail.index('data-role="acq-stop"')
    assert 'data-role="sampling"' in group
    # No reading is inserted among the presses.
    assert "data-fact=" not in group
    assert 'data-role="sampling-now"' not in group
    # It is read beside them instead.
    readings = control[control.index('class="run-details"'):]
    assert 'data-role="sampling-now"' in readings
    assert 'data-fact="samples"' in readings


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
    gate = control[control.index('class="gate"'):]
    gate = gate[:gate.index("</div>")]
    assert 'data-role="take-over"' in gate
    assert "disabled" in gate


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
    """The three facts every surface of the ensemble shows, in one order.

    Where a service runs is not a fourth row: the start words already name
    the machine, and three cards across a reading column have no room to
    say it twice (owner direction 2026-09-07, the identical trio board).
    """
    card = lab[lab.index('data-alias="controlunit"'):]
    card = card[:card.index("</article>")]
    for term in ("<dt>Version</dt>", "<dt>Says</dt>", "<dt>Start</dt>"):
        assert term in card
    assert "<dt>Runs</dt>" not in card
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
    assert 'class="page"' in page or 'class="page control-workspace"' in page
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
    assert "What this rig reached just now." in card
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
    card = control[control.index('<h2 class="rail-label">Acting as '):]
    assert '<input type="text" id="actor-name"' in card
    # What the name is for is on the field itself, where it costs the
    # faceplate no line of its own.
    assert 'placeholder="your name, for the log"' in card
    assert "the lab's roster" not in card


def test_the_acting_as_field_offers_the_roster_when_this_machine_has_one(tmp_path):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "operators.json").write_text(ROSTER, encoding="utf-8")
    page = app_for(tmp_path, home=home).get("/control").get_data(as_text=True)
    card = page[page.index('<h2 class="rail-label">Acting as '):]
    assert '<select id="actor-name"' in card
    assert "— choose —" in card
    assert '<option value="Hashizuka Takuma"' in card
    assert '<option value="Arseniy Kuzmin"' in card
    # No note under the list: the list says where its names come from.
    assert "Names come from the lab's roster." not in card
    assert '<input type="text" id="actor-name"' not in card


def test_the_data_states_are_not_explained_on_the_page(live):
    """The chip states; the docs explain (queezz, 2026-09-10)."""
    for meaning in ("without a sample", "when acquisition is off"):
        assert meaning not in live


def test_saved_roster_identity_matches_normalized_option_on_reload(tmp_path):
    home = tmp_path / ".controlunit"
    home.mkdir()
    label = "Arseniy Kuzmin (lab)"
    (home / "operators.json").write_text(ROSTER.replace("Arseniy Kuzmin", label), encoding="utf-8")
    client = app_for(tmp_path, home=home)
    answer = client.post("/api/identify", json={"name": label})
    assert answer.status_code == 200
    actor = answer.get_json()["actor"]
    assert actor != label
    page = client.get("/control").get_data(as_text=True)
    assert '<option value="{}" selected>{}</option>'.format(actor, label) in page
    assert 'data-role="actor-summary">{}</span>'.format(label) in page


def test_the_rail_carries_no_explainer_card(live):
    """The reasoning lives in the docs, never in a card of the control
    surface (queezz, 2026-09-10: "the towel of explanation text belongs in
    docs or in pihti-log, not in a card of control UI")."""
    assert "Reading this page" not in live
    assert 'data-role="stale-after"' not in live


def test_the_head_of_the_column_carries_the_two_readings(live):
    """What the rig is doing, and how fresh the numbers are. Two pills,
    each stated once on the page (owner direction 2026-09-07)."""
    pills = live[live.index('class="pills"'):]
    pills = pills[:pills.index("</div>")]
    assert pills.count('class="chip') == 2
    assert 'data-role="operating"' in pills
    assert 'data-role="operating-outputs"' in pills
    assert live.count('data-role="data-state"') == 1


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
    card = page[page.index('<h2 class="rail-label">Acting as '):]
    card = card[:card.index("</section>")]
    assert '<input type="password" id="fence-word"' in card
    assert 'data-role="save-fence"' in card
    assert "placeholder=\"the lab&#39;s word, not a secret\"" in card


def test_the_word_is_explained_once_and_named_a_fence_not_a_secret(tmp_path):
    """What the word is rides on the field itself: a fence, not anybody's
    password, said once and costing the faceplate no line."""
    page = with_a_word(tmp_path).get("/control").get_data(as_text=True)
    assert page.count("not a secret") == 1
    assert page.count('data-role="save-fence"') == 1


def test_a_browser_past_the_fence_still_has_a_field_to_type_in(tmp_path):
    """A word changed in the lab has to be typable again."""
    client = with_a_word(tmp_path)
    assert client.post("/api/fence", json={"word": WORD}).status_code == 200
    page = client.get("/control").get_data(as_text=True)
    assert '<input type="password" id="fence-word"' in page
    assert 'placeholder="word saved"' in page
    assert 'data-role="fence-editor" hidden' in page
    assert 'data-role="change-fence"' in page
    assert 'Access saved' in page


def test_the_take_over_button_is_shut_behind_the_fence_too(tmp_path):
    page = with_a_word(tmp_path).get("/control").get_data(as_text=True)
    gate = page[page.index('class="gate"'):]
    gate = gate[:gate.index("</div>")]
    assert 'data-role="take-over"' in gate
    assert "disabled" in gate


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


# -- two counts, two labels (the Mac audit of 2026-09-07) ---------------------


def test_the_log_card_names_what_it_is_retaining_and_what_is_on_screen(log):
    """One word for two numbers was the defect.

    With seven messages held, a search for "sampling" left two rows on the
    page, the Find card said "2 of 7 lines", and this card still said "Lines
    shown 7" (PIHTI Log's Mac audit, letter `20260907-023785d0`). Retained is
    what the rig holds; Shown is what survived the Find, and the page keeps
    it current on every keystroke and every new line.
    """
    assert "Lines shown" not in log
    assert "<dt>Retained</dt>" in log
    assert "<dt>Shown</dt>" in log
    assert 'data-fact="shown"' in log


def test_a_filter_that_matches_nothing_says_so_rather_than_looking_empty(log):
    """An empty column reads exactly like a log with nothing in it, and they
    are not the same fact."""
    assert 'id="log-nomatch"' in log
    assert "No message here holds that word." in log

    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[1]
        / "controlunit" / "web" / "static" / "js" / "log.js"
    ).read_text(encoding="utf-8")
    # Both counts move with the filter and with a line arriving under it.
    assert 'data-fact="shown"' in script
    assert "noMatch.hidden = !(total > 0 && shown === 0)" in script


# -- the board of three, as all three surfaces draw it ------------------------


def _stylesheet():
    from pathlib import Path

    return (
        Path(__file__).resolve().parents[1]
        / "controlunit" / "web" / "static" / "css" / "controlunit.css"
    ).read_text(encoding="utf-8")


def test_the_board_breaks_where_the_other_two_surfaces_break():
    """One board across three surfaces means one set of numbers.

    The card width, the gap between cards and the rails on either side are
    the whole arithmetic of where the board goes from two-plus-one to three
    across. This surface carried its own numbers for one release — 190px
    cards between 17rem rails — and broke 32px later than the diagram and
    the journal, which put the owner's 1440px Mac on the wrong side of the
    line (Commander's correction 2026-09-07). These four values are the
    reference's own.
    """
    css = _stylesheet()
    board = css[css.index(".services {"):]
    board = board[:board.index("}")]
    assert "repeat(auto-fit, minmax(260px, 1fr))" in board
    assert "gap: 14px" in board
    assert "--rail-w: 16rem" in css


def test_a_service_card_reads_its_facts_across_not_down():
    """At the reference's card width a label stands beside its value.

    They were stacked for one release, when a 203px card left the value a
    hundred pixels; at 260px and up the two-column list the rest of this
    page uses fits, so the card does not need a list shape of its own.
    """
    css = _stylesheet()
    assert ".service dl.facts {" not in css


def test_a_card_says_which_address_your_own_browser_will_open(lab):
    """The chip is what this rig reached; the link is what the laptop will
    try, and on 2026-09-07 those were two different names — the Pi resolves
    `pihti`, the owner's Mac does not (PIHTI Log's audit). The card names the
    address rather than leaving the reader to find out by a dead link."""
    assert 'data-role="opens-at"' in lab
    # And the rail says the distinction once, for the whole surface.
    assert "What this rig reached just now." in lab


# -- the Control faceplate -----------------------------------------------------


def test_control_combines_setters_feedback_and_shared_live_charts(control):
    operations = control[:control.index("<main")]
    main = control[control.index("<main"):control.index("</main>")]
    access = control[control.index('aria-label="Access and display"'):]
    assert main.count('data-role="zero-now"') == 3
    assert 'class="chart-zero sets"' in main
    # The left rail is the gas and the plasma, the two a shift has its hand
    # on all day; the three it reaches for rarely stand in the right rail's
    # folded Settings group (queezz, 2026-09-10: "the left becomes
    # gas/plasma real control").
    for role in ("acq-start", "acq-stop", "mfc-set", "plasma-set", "stop-all"):
        assert 'data-role="{}"'.format(role) in operations
        assert 'data-role="{}"'.format(role) not in main
    for role in ("sampling", "gauge-mode", "gauge-range", "sync"):
        assert 'data-role="{}"'.format(role) in access
        assert 'data-role="{}"'.format(role) not in operations
        assert 'data-role="{}"'.format(role) not in main
    for role in ("mfc-setpoint", "mfc-measured", "plasma-setpoint"):
        assert 'data-role="{}"'.format(role) in operations
    assert 'data-role="save-actor"' in access
    assert 'data-role="save-actor"' not in operations
    for chart in ("chart-plasma", "chart-ig", "chart-bar"):
        assert main.count('id="{}"'.format(chart)) == 1
    for channel in ("Ip", "Pu", "Pd", "Bu", "Bd"):
        assert main.count('data-readout="{}"'.format(channel)) == 1
    assert 'data-live' in control


def test_the_name_and_the_word_are_outside_the_block_the_gate_shuts(control):
    """They are how a person opens the gate, so the gate can never switch
    them off: the blanket names the block it governs, not the column."""
    sets = control[control.index('class="sets"'):]
    sets = sets[:sets.index('<main')]
    assert 'id="actor-name"' not in sets
    assert 'data-role="save-actor"' not in sets
    script = _control_js()
    assert '.querySelectorAll(".sets button, .sets input")' in script
    assert ".page-main button" not in script


def test_the_one_always_allowed_press_is_still_the_rail_s(control):
    """Stop all outputs is not the faceplate's: it is allowed when nothing
    else is, and it must be findable without reading anything."""
    rail = control[control.index('class="rail rail-left operation-rail"'):]
    rail = rail[:rail.index("<main")]
    assert 'data-role="stop-all"' in rail
    assert control.count('data-role="stop-all"') == 1


def test_each_of_the_run_s_facts_is_read_in_exactly_one_place(control):
    """The rail keeps what the faceplate does not carry; nothing is said
    twice on one page."""
    for fact in ("samples", "file", "started", "hardware"):
        assert control.count('data-fact="{}"'.format(fact)) == 1
    assert control.count('data-role="sampling-now"') == 1


def test_the_left_rail_is_the_run_the_gas_and_the_plasma_and_nothing_else(control):
    """queezz, 2026-09-10, looking at 4.11.2 on the rig: "Left rail got a bit
    crowded. QMS signal, sampling, and IG panel can stay on the right, and I
    don't use those often. And then the left becomes gas/plasma real
    control." Four things stand there now, in operating order."""
    rail = control[control.index('id="live-controls"'):]
    rail = rail[:rail.index("<main")]
    assert 'id="sec-gas"' in rail
    assert 'id="sec-plasma"' in rail
    # And the three that moved are not in it any more.
    for anchor in ("sec-sync", "sec-acquisition", "sec-gauge"):
        assert 'id="{}"'.format(anchor) not in rail
    order = [
        rail.index('data-role="acq-start"'),
        rail.index('id="sec-gas"'),
        rail.index('id="sec-plasma"'),
        rail.index('data-role="stop-all"'),
    ]
    assert order == sorted(order)


def test_the_cathode_heading_carries_its_mode_switch_on_one_line(control):
    """queezz, 2026-09-10, looking at 4.12.0 on the rig: "Can we make Cathode
    / mode PID Manual bit better? I.e. one line: Cathode PID/Manual toggle?"
    The Mode row is gone; the word Cathode and the switch share the group's
    own heading line."""
    plasma = control[control.index('id="sec-plasma"'):]
    plasma = plasma[: plasma.index("</section>")]
    head = plasma[plasma.index('class="group-head"'):plasma.index("</div>")]
    assert "<h2>Cathode</h2>" in head
    assert 'class="seg-toggle"' in head
    assert head.count('data-role="cathode-mode"') == 2
    # No row of its own any more, and no name in the row-name column for it.
    assert ">Mode</span>" not in plasma
    assert plasma.index('class="group-head"') < plasma.index("cathode-pid-row")


def test_the_mode_switch_is_one_control_the_keyboard_and_the_gate_reach(control):
    """queezz, same message: "for toggles I like visual toggles, not two
    buttons which happen to be linked under the hood in the code." One track,
    one thumb — and still two real buttons carrying aria-pressed, so Tab
    reaches them and the `.sets` blanket switches them off."""
    plasma = control[control.index('id="sec-plasma"'):]
    plasma = plasma[: plasma.index("</section>")]
    head = plasma[plasma.index('class="group-head"'):plasma.index("</div>")]
    assert 'role="group" aria-label="Cathode mode"' in head
    assert head.count('class="seg-thumb"') == 1
    assert head.count("<button type=") == 2
    assert 'aria-pressed="true">PID<' in head
    assert 'aria-pressed="false">Manual<' in head
    # Inside the block the gate names, exactly as the two buttons were.
    sets = control[control.index('class="sets"'):control.index("<main")]
    assert 'class="seg-toggle"' in sets


def test_the_segmented_switch_is_a_component_and_not_this_group_s_dressing(client):
    """Built so the next two-state control on this page wears the same thing:
    the thumb follows aria-pressed by position, never by the cathode's own
    words, and the track keeps one border around both sides."""
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def block(selector):
        start = rules.index(selector + " {")
        return rules[start:rules.index("}", start)]

    # No rule in this component knows what the Cathode's two sides are called.
    assert "data-cathode-mode" not in rules
    assert (
        '.seg-toggle:has(> .seg-option:last-child[aria-pressed="true"])'
        " .seg-thumb {" in rules
    )
    track = block(".seg-toggle")
    assert "border: 1px solid var(--line)" in track
    # The halves are equal, so the thumb's travel is its own width and the
    # track's width cannot change with the choice.
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in track
    option = block(".seg-option")
    assert "border: 0" in option
    # One weight on both sides: pressing must not reflow the heading row.
    assert "font-weight" in option
    assert "font-weight" not in block('.seg-option[aria-pressed="true"]')
    # The thumb slides, and the page's reduced-motion blanket already stops it.
    assert "transition: transform" in block(".seg-thumb")
    assert "* { transition: none !important; animation: none !important; }" in css


def test_settings_gathers_the_three_a_shift_reaches_for_rarely(control):
    """One group, after Display and before This run — open on arrival, and
    foldable (queezz, 2026-09-10: "I don't like IGs hidden by default. But
    hiding possibility is a right shape, sure.")."""
    right = control[control.index('id="live-context"'):]
    groups = [
        right.index("<summary>Operator and access"),
        right.index("<summary>Display</summary>"),
        right.index("<summary>Settings</summary>"),
        right.index("<summary>This run</summary>"),
    ]
    assert groups == sorted(groups)

    settings = right[right.index('<details class="settings-group"'):]
    settings = settings[: settings.index("<summary>This run</summary>")]
    # The group arrives open; the Gauges fold inside it is open too, so the
    # mode and the range are read without a second press.
    assert settings[: settings.index(">")] == (
        '<details class="settings-group" data-role="settings-group" open'
    )
    for anchor in ("sec-sync", "sec-acquisition", "sec-gauge"):
        assert 'id="{}"'.format(anchor) in settings
    # In that order, and each still gated by the blanket that names `.sets`.
    inside = [settings.index('id="sec-{}"'.format(name))
              for name in ("sync", "acquisition", "gauge")]
    assert inside == sorted(inside)
    assert 'class="sets row-actions"' in settings
    assert 'class="sets"' in settings


def test_nothing_moved_into_settings_is_left_behind_as_a_copy(control):
    """One DOM, moved rather than duplicated (fleet's WEBUI.md), so the
    wiring and the gate cannot drift from a twin."""
    for anchor in ("sec-sync", "sec-acquisition", "sec-gauge"):
        assert control.count('id="{}"'.format(anchor)) == 1
    assert control.count('data-role="sync-now"') == 1
    assert control.count('data-role="gauge-mode-now"') == 1
    assert control.count('data-role="gauge-range-now"') == 1
    assert control.count('data-role="settings-group"') == 1
    assert control.count("<summary>Settings</summary>") == 1


def test_the_settings_fold_is_remembered_in_this_browser_and_only_there():
    """Open for a browser that has never touched it, and for one that stores
    nothing at all; folded only for a browser that folded it. Read before the
    deep link, so a link into a moved section still opens the fold on its way
    in."""
    script = _control_js()
    assert '"controlunit.settings.open"' in script
    fold = script[script.index("function setupSettingsFold"):]
    fold = fold[: fold.index("function setupCathodeMode")]
    assert "window.localStorage.getItem(SETTINGS_KEY)" in fold
    assert "window.localStorage.setItem(SETTINGS_KEY" in fold
    # Only a browser that has actually chosen overrides the template's own
    # `open`; a missing key leaves the group exactly as the page shipped it.
    assert 'if (chosen !== null) group.open = chosen === "1";' in fold
    assert "group.open = window.localStorage" not in fold
    assert fold.count("catch (e)") == 2
    wiring = script[script.index("function wire() {"):script.index("function revealSection")]
    assert "setupSettingsFold();" in wiring
    opening = script[script.index("function setup() {"):]
    assert opening.index("wire();") < opening.index("revealSection();")
    # Nothing is sent to the rig by folding or unfolding a group.
    assert "send(" not in fold


def _control_js():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "controlunit" / "web" / "static" / "js" / "control.js"
    ).read_text(encoding="utf-8")

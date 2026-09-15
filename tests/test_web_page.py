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


def test_live_is_home_and_shows_the_six_pens(live):
    assert 'aria-current="page">ControlUnit ' in live
    for name in ("Ip", "Pu", "Pu2", "Pd", "Bu", "Bd"):
        assert 'data-readout="{}"'.format(name) in live
    assert 'id="chart-plasma"' in live


def test_the_web_pens_are_the_rig_screens_own():
    """One colour per curve on the rig's screen and on a laptop."""
    from controlunit.ui.widgets.graph import Graph
    from controlunit.web.server import PENS
    assert {name: colour for name, colour in PENS} == {
        name: Graph.pens[name]["color"] for name, _ in PENS
    }
    assert [name for name, _ in PENS] == ["Ip", *Graph.PRESSURE_CURVES]


def test_the_two_kinds_of_gauge_get_a_panel_each(live):
    """One axis could not serve both, so neither was readable."""
    assert "Ion gauges, Torr" in live
    assert "Baratrons, Torr" in live
    assert 'id="chart-ig"' in live
    assert 'id="chart-bar"' in live
    assert 'data-channels="Pu,Pu2,Pd"' in live
    assert 'data-channels="Bu,Bd"' in live
    assert "chart-pressure" not in live


def test_control_offers_each_ion_gauge_its_own_mode_and_range(control):
    """Two gauges, two blocks under their own names, each with a full set of
    modes and decades, and a folded line that names both."""
    for gauge, heading in (("Pd", "Downstream · Pd"), ("Pu2", "Upstream · Pu2")):
        assert '<h3 class="gauge-name">{}</h3>'.format(heading) in control
        assert 'class="mono gauge-now" data-gauge="{}"'.format(gauge) in control
        for mode in ("Torr", "Pa"):
            assert 'data-role="gauge-mode" data-gauge="{}"'.format(gauge) in control
            assert 'data-gauge="{}"\n                                            data-mode="{}"'.format(gauge, mode) in control
        for decade in range(-8, -2):
            assert 'data-gauge="{}"\n                                            data-range="{}"'.format(gauge, decade) in control
    assert control.count('data-role="gauge-range"') == 12
    assert control.count('data-role="gauge-mode"') == 4


def test_the_gauges_card_names_each_gauges_place(control):
    """The card is 'Ion gauges', not 'Gauges', and each block is headed by
    its place and its short name (owner direction 2026-09-15, "Ion Gauges:
    upstream/downstream is better"), with the short name kept beside it
    because the readout cards elsewhere on the page say Pu2 and Pd."""
    assert '<h2 class="fold-name">Ion gauges</h2>' in control
    assert '<h3 class="gauge-name">Upstream · Pu2</h3>' in control
    assert '<h3 class="gauge-name">Downstream · Pd</h3>' in control


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


def test_the_plasma_panel_draws_the_cathode_current_on_its_own_axis(live):
    """queezz, 2026-09-15: "We need to add cathode current to the current
    plot. So it'll be obvious when plasma is on... Is it the Hall sensor
    drifting or the plasma died."

    `Ic` is a curve of the plasma panel like Ip, with its own legend pill in
    the cathode's own colour — and on the panel's own right-hand axis,
    because a filament current of tens of amperes against tenths of an
    ampere of plasma current on one scale is Ip flat on the floor."""
    from controlunit.web.status import CATHODE_PEN

    chart = live[live.index('aria-label="Plasma current, A"'):]
    chart = chart[: chart.index("</details>")]
    assert 'data-channels="Ip,Ic"' in chart
    assert 'data-right-axis="Ic"' in chart
    assert 'data-channel="Ic"' in chart
    pill = chart[chart.index('data-channel="Ic"'):]
    pill = pill[: pill.index("</button>")]
    assert "--pen: {}".format(CATHODE_PEN) in pill
    # The other two panels keep one axis, and no Zero button appears for a
    # channel the rig does not take a baseline of.
    assert "data-right-axis" not in live[live.index('id="chart-ig"'):]
    assert 'data-zero="Ic"' not in live
    # The canvas draws from the pen table the page carries, so the curve and
    # its legend pill cannot wear two different colours.
    assert '["Ic", "{}"]'.format(CATHODE_PEN) in live


def test_the_plasma_chart_carries_its_own_scale_choice(live):
    """queezz, 2026-09-15: "plasma current when constant shows the noise
    instead of 0-1 or 0-3 A. Need some axis control, if possible." It sits in
    the chart's own legend row beside the curve pills, in the same shape the
    pressure panels' log/lin pair wears — which is where WEBUI.md's 2026-09-07
    amendment allows a control over that chart's own axis to live."""
    chart = live[live.index('aria-label="Plasma current, A"'):]
    chart = chart[: chart.index("</details>")]
    for choice, label in (("auto", "auto"), ("0-1", "0–1 A"), ("0-3", "0–3 A")):
        assert 'data-scale-plasma="{}"'.format(choice) in chart
        assert ">{}</button>".format(label) in chart
    # It stands in the legend row, not in a rail card away from the chart.
    legend = chart[chart.index('class="pen-legend"'):]
    for choice in ("auto", "0-1", "0-3"):
        assert 'data-scale-plasma="{}"'.format(choice) in legend
    compact = " ".join(live.split())
    assert 'data-scale-plasma="auto" aria-pressed="true"' in compact
    assert compact.count('data-scale-plasma=') == 3


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
    # Six channels and the cathode supply's two, which are the same card.
    assert live.count('data-role="readout-note"') == 8
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


def test_the_cathode_supply_is_two_more_cards_of_the_one_strip(client, live):
    """queezz, 2026-09-15, on the separate Kikusui panel: "Why separate? It's
    a control panel … it is the Cathode voltage current. That it happens to be
    kikusui and read differently is irrelevant for operation." So the supply's
    measured voltage and current are the seventh and eighth cards of the
    readouts strip, in one pen of their own, and the panel is gone from the
    page and from the stylesheet."""
    strip = live[live.index('<div class="readouts">'):]
    strip = strip[: strip.index("</details>")]
    for key, name, unit in (("voltage_v", "Cathode V", "V"),
                            ("current_a", "Cathode I", "A")):
        card = strip[strip.index('data-cathode-readout="{}"'.format(key)):]
        card = card[: card.index("</div>")]
        assert '<span class="readout-name">{}</span>'.format(name) in card
        assert '<span class="readout-unit mono">{}</span>'.format(unit) in card
        assert 'data-role="value"' in card and 'data-role="readout-note"' in card
    # One pen for the two of them, and a hue of its own: the first try wore
    # the left rail's violet and the owner threw it out at sight
    # (2026-09-15: "The cathode current colour is the same as plasma current.
    # Bad decision"). It is not one of the six, and it is not the rail's.
    assert strip.count("--pen: #ff6b35") == 2
    for taken in ("#8d3de3", "#c9004d", "#3b82f6", "#6ac600", "#ffb405",
                  "#00a3af", "#b48ae9", "#8a4be4"):
        assert taken != "#ff6b35"
    # It is the cathode's colour and nothing else's on the page: the two
    # cards, their two folded entries, and — since the Kikusui current became
    # a curve — the `Ic` pill in the plasma chart's legend and the two
    # entries of the pen table the canvas draws from.
    assert live.count("#ff6b35") == 7
    # And it is one constant, not a colour typed in five places.
    from controlunit.web.status import CATHODE_PEN
    assert CATHODE_PEN == "#ff6b35"
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    assert "--cathode-pen: {};".format(CATHODE_PEN) in css
    # The stylesheet names the variable rather than repeating the value.
    assert css.count(CATHODE_PEN) == 1
    for gone in ("kikusui-panel", "kikusui-readouts", "data-kikusui-readout",
                 "kikusui-status", "kikusui-fold"):
        assert gone not in live, gone
        assert gone not in css, gone


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
    assert live.count('class="readout"') == 8
    assert live.count("data-cathode-readout=") == 2


def test_the_number_is_the_loudest_thing_on_every_readout_card(client):
    """queezz, 2026-09-15, on the Live tab: "Big is somewhat smaller than
    small. The cards and all. It's very inconsistent… Big means BIG NUMBERS
    first. And recognizable." And on the panel whose sizing he did like: "I
    like the size and style of the Kikusui… feels better and bigger and more
    readable than the 'big' in the main numbers panel."

    So: two rows, the name, its tag and the unit on the first and the number
    alone on the second; the number 1.5rem in small — the Kikusui panel's own
    size — and about twice that in big; and nothing but the number changes
    between the two modes."""
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def block(selector):
        start = rules.index(selector + " {")
        return rules[start:rules.index("}", start)]

    # The card is a panel meter: the digits are the only thing in its flow,
    # and the small texts are pinned to its corners so they take no width
    # from them — the name and its tag at the top left, the unit at the
    # bottom right, under the exponent.
    card = block(".readout")
    assert "position: relative" in card
    assert "container-type: inline-size" in card
    cap = block(".readout-cap")
    assert "position: absolute" in cap and "top: 0.12rem" in cap and "left: 0.55rem" in cap
    unit = block(".readout-unit")
    assert "position: absolute" in unit and "right: 0.55rem" in unit and "bottom: 0.12rem" in unit
    value = block(".readout-value")
    # Centred, tall and unafraid of the corners (queezz, 2026-09-15: "the
    # number feels shy and hides in a corner of its own card").
    assert "text-align: center" in value and "white-space: nowrap" in value
    assert "min(1.5rem, 16cqi)" in value        # 1.5rem, capped by the card
    assert "clamp(2.4rem, 17cqi, 5rem)" in block(".live--big .readout-value")
    # The corners keep one size in both states, so "big" cannot come to mean
    # a bigger label again; the digits are the whole difference.
    for restyled in (".live--big .readout-name", ".live--big .readout-unit",
                     ".live--big .readout-note", ".live--big .readout-cap"):
        assert restyled not in rules
    assert "font-size: 0.64rem" in block(".readout-name")
    assert "font-size: 0.6rem" in block(".readout-note")
    # Eight cards laid by the room each needs, not by a column count.
    assert "repeat(auto-fit, minmax(9rem, 1fr))" in block(".readouts")
    assert "repeat(auto-fit, minmax(15rem, 1fr))" in block(".live--big .readouts")


def test_small_readouts_reserve_no_room_they_are_not_using(client):
    """queezz, 2026-09-10: "Small now have large boxes small font. Which
    defeats the purpose." A small card is its digits and the padding that
    keeps its corners clear of them, in Operate as everywhere else."""
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
    # The tag rides in the card's own corner beside the name and cannot
    # leave that line, whatever it says.
    note = block(".readout-note")
    assert "white-space: nowrap" in note and "text-overflow: ellipsis" in note
    # Operate carries the same card as Live, not a squeezed copy of it
    # (owner, 2026-09-15: "The cards and all. It's very inconsistent"). The
    # only thing that tab still says about a readout is the gap between them.
    assert ".control-workspace .readouts { gap: 8px; }" in rules
    for squeezed in (
        ".control-workspace:not(.live--big) .readout {",
        ".control-workspace:not(.live--big) .readout-name",
        ".control-workspace .readout-value {",
        ".control-workspace.live--big .readout-value",
    ):
        assert squeezed not in rules


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
    readings = control[control.index('class="run-details'):]
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
    # Three pieces on one baseline: the mantissa, `×10-` small, and the
    # decade at the mantissa's own size (owner sketch, 2026-09-15: "×10-
    # small, the n in ×10-n is BIG") — not a lifted superscript, because the
    # two numbers a reader compares are the mantissa and the decade.
    assert "\"readout-times\">×10' + minus" in script
    assert "\"readout-exp\">' + decade" in script
    # The canvas has no markup to size an exponent with, so its axis
    # labels carry the superscript glyphs themselves.
    assert '"10" + superText(' in script
    assert ".readout-times {" in css and "font-size: 0.5em" in css
    assert ".readout-exp { font-size: 1em; }" in css


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
    for role in ("acq-start", "acq-stop", "mfc-set", "plasma-set"):
        assert 'data-role="{}"'.format(role) in operations
        assert 'data-role="{}"'.format(role) not in main
    for role in ("sampling", "gauge-mode", "gauge-range", "sync", "stop-all"):
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


def test_the_one_always_allowed_press_is_out_of_the_hand_s_way(control):
    """queezz, 2026-09-14: Stop all outputs "is not a safety device (the
    physical switches are); it is the rare press that zeroes gas and cathode
    while the recording continues, and it must not sit where a thumb finds it
    during a good run." So it stands at the foot of Operator and access, and
    on a phone live.js moves that same element into the Menu — one element,
    never two, and still allowed when everything else is refused."""
    left = control[control.index('class="rail rail-left operation-rail"'):]
    left = left[:left.index("<main")]
    assert 'data-role="stop-all"' not in left
    assert control.count('data-role="stop-all"') == 1
    access = control[control.index('class="rail-card access-card fold"'):]
    access = access[: access.index("<details")]
    assert 'data-role="stop-all"' in access
    assert access.index("sec-who") < access.index('data-role="stop-all"')
    # Outside the block the gate shuts, exactly as it was in its own card.
    sets = control[control.index('class="sets"'):control.index("<main")]
    assert 'data-role="stop-all"' not in sets


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
    control." Three things stand there now, in operating order, since Stop
    all outputs left for the right rail in 4.14.0."""
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
    ]
    assert order == sorted(order)


def _cathode(page):
    """The Cathode card, which is the <details> that folds it."""
    plasma = page[page.index('id="sec-plasma"'):]
    return plasma[: plasma.index("</details>")]


def _cathode_head(page):
    """Its heading line: the summary the whole card folds on."""
    head = _cathode(page)
    return head[head.index('class="fold-head group-head"'):head.index("</summary>")]


def test_the_cathode_heading_carries_its_mode_switch_on_one_line(control):
    """queezz, 2026-09-10, looking at 4.12.0 on the rig: "Can we make Cathode
    / mode PID Manual bit better? I.e. one line: Cathode PID/Manual toggle?"
    The Mode row is gone; the word Cathode and the switch share the group's
    own heading line — which from 4.14.0 is also the line that folds the card,
    so the switch and the fold live on one row and not two."""
    plasma = _cathode(control)
    head = _cathode_head(control)
    assert '<h2 class="fold-name">Cathode</h2>' in head
    assert 'class="seg-toggle"' in head
    assert head.count('data-role="cathode-mode"') == 2
    # No row of its own any more, and no name in the row-name column for it.
    assert ">Mode</span>" not in plasma
    assert plasma.index('class="fold-head group-head"') < plasma.index("cathode-pid-row")


def test_the_mode_switch_is_one_control_the_keyboard_and_the_gate_reach(control):
    """queezz, same message: "for toggles I like visual toggles, not two
    buttons which happen to be linked under the hood in the code." One track,
    one thumb — and still two real buttons carrying aria-pressed, so Tab
    reaches them and the `.sets` blanket switches them off."""
    head = _cathode_head(control)
    assert 'role="group" aria-label="Cathode mode"' in head
    assert head.count('class="seg-thumb"') == 1
    assert head.count('class="seg-option"') == 2
    # Three buttons ride on this line now: the switch's two sides and the
    # supply's output lamp beside them (owner decision 2026-09-15).
    assert head.count("<button type=") == 3
    assert head.count('class="output-lamp"') == 1
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
        right.index('<h2 class="fold-name">Operator and access</h2>'),
        right.index('<h2 class="fold-name">Display</h2>'),
        right.index('<h2 class="fold-name">Settings</h2>'),
        right.index('<h2 class="fold-name">This run</h2>'),
    ]
    assert groups == sorted(groups)

    settings = right[right.index('<details class="settings-group'):]
    settings = settings[: settings.index('<h2 class="fold-name">This run</h2>')]
    # The group arrives open; the Gauges fold inside it is open too, so the
    # mode and the range are read without a second press.
    assert settings[: settings.index(">")] == (
        '<details class="settings-group fold" data-role="settings-group"'
        ' data-fold="settings" open'
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
    # One folded line per ionization gauge, each saying its own setting.
    assert control.count('data-role="gauge-mode-now"') == 2
    assert control.count('data-role="gauge-range-now"') == 2
    assert control.count('data-role="settings-group"') == 1
    assert control.count('<h2 class="fold-name">Settings</h2>') == 1


def test_every_card_on_the_live_page_folds_and_folds_the_same_way(control):
    """queezz, 2026-09-14, on his phone at the rig: "Minimized gas control
    takes too much space, which is a killer on my phone… Hide 'any' card then,
    not all. I need CONTROL and HIDE WHATEVER IN THE WAY." Every card is a
    <details> whose <summary> is its own heading line, and every one of them
    ships open, so nothing a shift wants is behind a press it has to
    discover."""
    cards = (
        "gas", "plasma",                                       # the left rail
        "readouts", "chart-plasma", "chart-ig", "chart-bar",   # the column
        "access", "display", "settings", "run-details",        # the right rail
        "gauge",
    )
    for card in cards:
        assert control.count('data-fold="{}"'.format(card)) == 1, card
        opened = control[control.index('data-fold="{}"'.format(card)):]
        opened = opened[: opened.index(">")]
        assert "open" in opened, card
    # One idiom, and there is never a second kind of fold beside it: every
    # fold on the page — these cards and the two gas lines inside Gas flow —
    # is a <details class="fold"> with a .fold-head summary.
    assert control.count("data-fold=") == len(cards)
    heads = control.count('class="fold-head') + control.count(' fold-head"')
    assert heads == len(cards) + 2
    assert control.count('class="gas-disclosure fold"') == 2
    # Every card names itself on its own row — except the readouts strip,
    # whose row is its six numbers and nothing else.
    assert control.count('class="fold-name"') == len(cards) - 1
    assert '<summary class="fold-head" aria-label="Readouts">' in control


def test_start_and_stop_is_the_one_card_that_does_not_fold(control):
    """queezz, 2026-09-14, looking at the first build of this: "Folding
    start/stop is not too good. I can simply scroll down, they are not in the
    way." It stays the plain card 4.13.0 left, with no mark on it."""
    rail = control[control.index('id="live-controls"'):control.index("<main")]
    run = rail[: rail.index('class="operation-setters"')]
    assert '<section class="rail-card">' in run
    assert 'data-role="acq-start"' in run
    assert "fold" not in run
    assert 'data-fold="run"' not in control
    assert 'data-role="fold-run"' not in control


def test_a_folded_card_is_one_line_that_still_carries_its_numbers(control):
    """Folded, a card says its name and the numbers a person wants without
    opening it — and they are painted by the same poll that paints the open
    card, never by a second reading of the rig."""
    for role in ("fold-gas", "fold-plasma"):
        assert control.count('data-role="{}"'.format(role)) == 1
    # The strip's six values, one per pen, in the order the cards stand in,
    # and the cathode supply's two after them under their shortest names.
    for channel in ("Ip", "Pu", "Pd", "Bu", "Bd"):
        assert control.count('data-fold-readout="{}"'.format(channel)) == 1
    for key in ("voltage_v", "current_a"):
        assert control.count('data-fold-cathode="{}"'.format(key)) == 1
    assert "<b>Uc</b>" in control and "<b>Ic</b>" in control
    assert control.count('data-role="fold-value"') == 8
    # A chart's folded line is the head it already had: its title and its
    # span. The legend, the axis switches and the canvas are body and go with
    # the fold (queezz, 2026-09-14: "The plasma current toggle is still
    # showing too much hidden").
    charts = control[control.index('class="chart fold"'):]
    head = charts[charts.index('class="chart-head fold-head"'):charts.index("</summary>")]
    assert '<h2 class="fold-name">' in head
    assert 'class="chart-span muted"' in head
    assert "pen-legend" not in head
    assert "chart-scale" not in head
    assert "<canvas" not in head
    css = _css()
    assert ".chart-head.fold-head { flex-wrap: nowrap" in css


def test_the_folded_readouts_row_is_the_numbers_and_nothing_else(client):
    """queezz, 2026-09-14, looking at the folded row on his phone: "Don't show
    big/small toggle when folded. Don't spell readouts. SHOW THEM small in a
    line with colors." The size switch belongs to the open strip; folded, the
    whole row is six values in their pens with the unit they share said once
    at the end, sized from the window so it never wraps or is cut."""
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    assert ".readouts-fold:not([open]) .readout-toolbar { display: none; }" in css
    # Sized from the strip's own width and not from the window's: at 850px of
    # window the column behind a 320px rail is 455px, and a vw ramp cut the
    # row there while reading the window as roomy.
    assert ".readouts-fold { container-type: inline-size; }" in css
    assert "font-size: min(0.68rem, 1.7cqi);" in css
    line = css[css.index(".fold-line {"):]
    line = line[: line.index("}")]
    assert "white-space: nowrap" in line
    source = _live_js()
    # Two significant figures and a plain exponent is what buys the room.
    fold = source[source.index("function foldValue"):source.index("function sharedUnit")]
    assert 'e.mantissa + "e" + e.exponent' in fold
    assert "function sharedUnit" in source
    assert 'units.textContent = shared' in source


def test_the_menu_carries_the_mode_switch_and_the_rare_press_on_a_phone():
    """queezz, 2026-09-14: the fixed Operate/Observe/Monitor bar "costs a
    permanent row… on mobile they belong maybe in the hamburger", and Stop all
    outputs "must not sit where a thumb finds it during a good run". Both are
    one element moved between its homes on the breakpoint — never a copy."""
    source = _live_js()
    dock = source[source.index("function dockTo"):source.index("function setupModes")]
    assert 'document.getElementById("main-tabs")' in dock
    assert "host.appendChild(el)" in dock
    assert "el.homeSlot" in dock
    # Looked up from the document, never from `root`: once it is docked into
    # the Menu it is outside the page element, and a root-scoped query would
    # never find it to bring it back.
    assert 'dockTo(document.querySelector(\'[data-role="mode-switch"]\'), modeSwitchHost())' in dock
    assert "root.querySelector('[data-role=\"mode-switch\"]')" not in source
    assert 'dockTo(document.querySelector(\'[data-role="stop-all"]\'), phone ? menu : null)' in dock
    assert "cloneNode" not in source
    assert "window.matchMedia(PHONE)" in source
    page = _client_page()
    assert page.count('data-role="mode-switch"') == 1
    assert page.count('class="view-toolbar"') == 1
    assert page.count('data-role="stop-all"') == 1
    css = _css()
    assert ".main-tabs > .view-toolbar {" in css
    assert ".main-tabs > .stop-all {" in css


def test_no_mode_is_a_room_without_a_door(client):
    """queezz, 2026-09-14, on his phone at the rig: "Observe trapped me. No
    tri-state toggle anywhere." Monitor removes the tab bar, and 4.14.0 had
    just moved the switch into the Menu inside it. The switch now docks in a
    strip the mode it is in actually renders, and Escape walks one mode back
    towards Operate besides."""
    source = _live_js()
    host = source[source.index("function modeSwitchHost"):source.index("function dockModes")]
    # Monitor keeps no tab bar, so the switch rides in the strip it does keep.
    assert 'mode === "monitor"' in host
    assert '[data-role="mode-actions"]' in host
    assert 'document.getElementById("main-tabs")' in host
    # And the choice is made again on every mode change, not once at startup.
    applied = source[source.index("function applyMode"):source.index("function setMode")]
    assert "dockModes();" in applied
    escape = source[source.index('if (event.key !== "Escape") return;'):]
    escape = escape[: escape.index("});")]
    assert escape.index("closeDrawers(); return;") < escape.index('setMode("observe")')
    assert 'else if (mode === "observe") setMode("operate");' in escape
    # An open phone Menu is navigation.js's to close, not this handler's.
    assert '.nav-toggle[aria-expanded="true"]' in escape
    css = _css()
    # Monitor is the one mode that takes the bar away; nothing else does.
    assert 'body[data-mode="monitor"] .tabbar { display: none; }' in css
    assert 'body[data-mode="observe"] .tabbar' not in css
    assert ".mode-actions > .view-toolbar {" in css
    # The strip the switch docks into in Monitor is the one Monitor shows.
    page = client.get("/?mode=monitor").get_data(as_text=True)
    assert 'data-role="mode-actions"' in page


def _client_page():
    from controlunit.web.neighbours import NeighbourBoard
    from controlunit.web.server import create_app

    nowhere = __import__("pathlib").Path("nowhere-at-all")
    app = create_app(board=NeighbourBoard(home=nowhere))
    return app.test_client().get("/").get_data(as_text=True)


def test_the_header_is_one_row_and_the_chevron_costs_it_nothing(client):
    """queezz, 2026-09-14, twice over: "that arrow for folding eats a line. On
    every card." and "do we need the arrow if the header works as a hide/show
    toggle? That arrow only wastes space." The title starts at the row's own
    left edge with nothing before it; the chevron is a small muted hint at the
    far end; the head is one flex line that cannot wrap."""
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    # Nothing stands before the title — that is what took the row.
    assert ".fold-head::before" not in css
    assert ".fold-name::before" not in css
    head = css[css.index(".fold-head {"):]
    head = head[: head.index("}")]
    assert "flex-wrap: nowrap" in head
    assert "min-height: 36px" in head
    # The chevron is one rule and one flip of it: delete the pair and every
    # fold on the page loses its hint and nothing else.
    hint = css[css.index(".fold-head::after {"):]
    hint = hint[: hint.index("}")]
    assert "margin-left: auto" in hint
    # Big enough to see on a real phone (queezz, 2026-09-14: "the toggle
    # indicator arrow could be a bit bigger, actually").
    assert "font-size: 1em" in hint
    assert "color: var(--muted)" in hint
    assert ".fold[open] > .fold-head::after { content: '▾'; }" in css
    assert css.count("content: '▸'") == 1
    assert css.count("content: '▾'") == 1
    # The row is the press target, and says so before and during the press.
    assert ".fold-head:hover {" in css
    assert ".fold-head:active {" in css


def test_a_fold_header_does_not_move_when_the_card_opens(client):
    """queezz, 2026-09-14, two screenshots of Gas flow: "Jumpy heading. Why not
    FIX it with minimum padding in the first place? Hate jumping UI." The card
    carries its minimum top padding in both states and the folded line keeps
    its box when it is hidden, so opening adds a body below the header and
    moves nothing above or inside it."""
    css = client.get("/static/css/controlunit.css").get_data(as_text=True)
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # Hidden, not removed: a line that left the row would move what follows it.
    assert ".fold[open] > .fold-head > .fold-line { visibility: hidden; }" in rules
    assert ".fold-head > .fold-line { display: none" not in rules
    # One top padding for both states; only the room under the body changes.
    same = rules[rules.index(".chart.fold { padding-top"):]
    same = same[: same.index("}")]
    assert "padding-top: 2px" in same and "padding-bottom: 2px" in same
    opened = rules[rules.index(".chart.fold[open] { padding-bottom"):]
    opened = opened[: opened.index("}")]
    assert "padding-top" not in opened


def test_a_gas_line_is_one_row_and_its_words_are_said_once(control):
    """queezz, 2026-09-14: 4.13.0's per-gas block was a heading plus a
    two-column Applied/Measured stack, about 90px a gas. Each gas is now one
    row — name, applied, measured — with the words said once for the group."""
    gas = control[control.index('id="sec-gas"'):]
    gas = gas[: gas.index('id="sec-plasma"')]
    assert gas.count("<small>") == 0
    assert gas.count("Applied") == 1
    assert gas.count("Measured") == 1
    assert gas.index("Applied") < gas.index('class="gas-disclosure fold"')
    for number in ("1", "2"):
        line = gas[gas.index('data-mfc="{}"'.format(number)):]
        line = line[: line.index("</summary>")]
        assert 'class="row-name"' in line
        assert 'data-role="mfc-setpoint"' in line
        assert 'data-role="mfc-measured"' in line
    # The legend and the rows stand on the same three tracks.
    css = _css()
    assert ".control-workspace .gas-disclosure > .fold-head,\n.flow-legend {" in css


def test_the_folded_numbers_are_written_by_the_poll_that_writes_the_card():
    """One source, two places to show it: the folded line is composed from the
    same values `paintGas`, `paintCathode` and `paintState` already wrote into
    the open card, so the two cannot drift."""
    script = _control_js()
    gas = script[script.index("function paintGas"):script.index("/* Which setter")]
    assert 'set(\'[data-role="fold-gas"]\', folded.join(" · "));' in gas
    cathode = script[script.index("function paintCathode"):script.index("function paintGauge")]
    assert 'set(\'[data-role="plasma-setpoint"]\', driving);' in cathode
    assert 'driving.replace("Held · ", "") + " · read " + current);' in cathode
    live = _live_js()
    assert '[data-fold-readout="\' + channel.name + \'"] [data-role="fold-value"]' in live


def test_a_fold_is_remembered_in_this_browser_and_only_there():
    """One code path, one key per card, `controlunit.fold.<card>`. Open for a
    browser that has never touched a card, and for one that stores nothing at
    all; folded only for a browser that folded it. Read before the deep link,
    so a link into a folded card still opens it on its way in."""
    script = _control_js()
    assert '"controlunit.fold."' in script
    fold = script[script.index("function setupFolds"):]
    fold = fold[: fold.index("function setupCathodeMode")]
    assert "window.localStorage.getItem(FOLD_KEY + fold.dataset.fold)" in fold
    assert "window.localStorage.setItem(FOLD_KEY + fold.dataset.fold" in fold
    # Only a browser that has actually chosen overrides the template's own
    # `open`; a missing key leaves the card exactly as the page shipped it.
    assert 'if (chosen !== null) fold.open = chosen === "1";' in fold
    assert "fold.open = window.localStorage" not in fold
    assert fold.count("catch (e)") == 2
    # The keyboard and a screen reader are told the same thing the mark says.
    assert 'head.setAttribute("aria-expanded", fold.open ? "true" : "false")' in script
    wiring = script[script.index("function wire() {"):script.index("function revealSection")]
    assert "setupFolds();" in wiring
    opening = script[script.index("function setup() {"):]
    assert opening.index("wire();") < opening.index("revealSection();")
    # Nothing is sent to the rig by folding or unfolding a card.
    assert "send(" not in fold


def test_a_control_on_a_heading_line_is_pressed_and_does_not_fold(control):
    """The cathode's switch, a chart's Zero buttons and the readouts' size
    ride on heading lines that are themselves the fold's press target. A press
    that lands on one of them presses it and leaves the fold alone."""
    # cathode mode, the supply's output lamp beside it, 2 charts, readouts
    assert control.count("data-fold-keep") == 6
    for owner in ('class="seg-toggle" data-fold-keep',
                  'class="output-lamp" data-fold-keep',
                  'class="chart-zero sets" data-fold-keep',
                  'class="readout-toolbar" data-fold-keep'):
        assert owner in control
    script = _control_js()
    guard = script[script.index("function pressedAControl"):]
    guard = guard[: guard.index("function setupFolds")]
    assert "target.dataset.foldKeep !== undefined" in guard
    assert "if (pressedAControl(head, event.target)) event.preventDefault();" in script


def _live_js():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "controlunit" / "web" / "static" / "js" / "live.js"
    ).read_text(encoding="utf-8")


def _css():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "controlunit" / "web" / "static" / "css" / "controlunit.css"
    ).read_text(encoding="utf-8")


def _control_js():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "controlunit" / "web" / "static" / "js" / "control.js"
    ).read_text(encoding="utf-8")

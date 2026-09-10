"""The Live and Log tabs' backing: the ring of samples, the log tail, and the
three routes that serve them. Freshness is a fact about the clock, never a
guess, so the clock is injected."""

import collections

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


class CountingRing(collections.deque):
    """A ring that says how many rows an iteration actually touched."""

    def __init__(self, items):
        collections.deque.__init__(self, items)
        self.visited = 0

    def __reversed__(self):
        for item in collections.deque.__reversed__(self):
            self.visited += 1
            yield item


def test_a_short_window_never_walks_the_old_rows():
    """The Live tab may ask four times a second; the Pi must not pay for the
    whole ring to answer a question about the last twenty seconds."""
    status = rig()
    feed(status, 0.0, 72000)  # two hours at 10 Hz, the ring at its fullest
    status._times = CountingRing(status._times)

    body = status.series(window_seconds=20, max_points=600)

    # 200 rows are inside a 20 s window at 10 Hz; one more ends the walk.
    assert status._times.visited <= 210
    assert body["to"] - body["from"] <= 20.0
    assert body["to"] == pytest.approx(7199.9)


def test_the_backwards_walk_cuts_where_a_cut_by_time_would():
    status = rig()
    feed(status, 0.0, 1000)  # 100 s at 10 Hz
    stamps = [point[0] for point in status.series(window_seconds=10, max_points=10000)["channels"]["Ip"]]
    assert stamps[-1] == pytest.approx(99.9)
    assert stamps[0] == pytest.approx(89.9, abs=0.11)
    assert len(stamps) == pytest.approx(101, abs=1)


def test_full_window_costs_the_same_as_a_short_one():
    status = rig()
    feed(status, 0.0, 20000)
    body = status.series(window_seconds=0, max_points=600)
    for name in NAMES:
        assert len(body["channels"][name]) <= 601


def test_since_answers_only_what_is_newer_than_the_stamp():
    """The Live tab holds its own history and asks for the rest."""
    status = rig()
    feed(status, 0.0, 1000)  # 100 s at 10 Hz
    body = status.series(since=99.05, max_points=600)
    stamps = [point[0] for point in body["channels"]["Ip"]]
    assert stamps[0] == pytest.approx(99.1)
    assert stamps[-1] == pytest.approx(99.9)
    assert body["from"] == pytest.approx(99.1)
    assert body["to"] == pytest.approx(99.9)
    assert body["count"] == 9


def test_since_is_thinned_the_way_a_window_is():
    status = rig()
    feed(status, 0.0, 1000)
    body = status.series(since=0.0, max_points=50)
    assert body["count"] == 999
    assert len(body["channels"]["Ip"]) <= 51
    assert body["channels"]["Ip"][-1][0] == pytest.approx(99.9)


def test_since_is_empty_when_nothing_is_newer():
    status = rig()
    feed(status, 0.0, 100)
    for mark in (10.0, 1000.0):
        body = status.series(since=mark)
        assert body == {
            "from": None,
            "to": None,
            "count": 0,
            "channels": {},
        }


def test_since_never_walks_the_rows_it_is_not_asked_for():
    """A browser an hour into a run costs the Pi the newest few rows."""
    status = rig()
    feed(status, 0.0, 72000)  # two hours at 10 Hz, the ring at its fullest
    status._times = CountingRing(status._times)

    status.series(since=7199.0, max_points=600)

    assert status._times.visited <= 20


def test_since_wins_over_a_window_that_came_with_it():
    status = rig()
    feed(status, 0.0, 1000)
    body = status.series(window_seconds=20, since=99.05, max_points=600)
    assert body["count"] == 9


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
    """The PID is one of the outputs the report names, not a fact of its own.

    It used to be the only one, worded "plasma PID on"; the rig can also be
    holding gas open or driving the cathode directly, and a person deciding
    whether the apparatus is safe to touch needs one list rather than one
    special case (owner direction 2026-09-07).
    """
    status = rig()
    status.set_acquiring(True)
    status.record_setpoints(plasma_a=1.2)
    assert health_body(status, __version__)["detail"] == (
        "acquiring 5 channels at 10 Hz, outputs live: plasma current PID"
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
    assert body["since"] is None
    assert len(body["channels"]["Ip"]) <= 301


def test_series_since_carries_only_the_newer_samples(client):
    """What the Live tab asks once it holds a history of its own."""
    whole = client.get("/api/series?window=0&points=3000").get_json()
    mark = whole["channels"]["Ip"][-4][0]

    body = client.get("/api/series?since={}".format(mark)).get_json()

    assert body["since"] == pytest.approx(mark)
    assert body["count"] == 3
    assert len(body["channels"]["Ip"]) == 3
    assert body["channels"]["Ip"][-1] == whole["channels"]["Ip"][-1]
    assert body["from"] > mark


def test_series_since_is_empty_when_the_browser_is_up_to_date(client):
    whole = client.get("/api/series?window=0").get_json()
    body = client.get("/api/series?since={}".format(whole["to"])).get_json()
    assert body["count"] == 0
    assert body["channels"] == {}
    assert body["to"] is None


def test_series_since_ignores_a_stamp_that_is_not_one(client):
    body = client.get("/api/series?since=banana&window=10").get_json()
    assert body["since"] is None
    assert body["to"] - body["from"] <= 10.0 + 0.11


def test_series_carries_the_whole_ring_at_full_resolution(client):
    """The one fill on page open must not thin what the rig holds."""
    assert status_module.MAX_POINTS == 3000
    body = client.get("/api/series?window=0&points=3000").get_json()
    assert body["count"] == 300
    assert len(body["channels"]["Ip"]) == 300


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


# -- the chart panels' own size, which is not the backing buffer's ------------


def _live_js():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "controlunit" / "web" / "static" / "js" / "live.js"
    ).read_text(encoding="utf-8")


def test_the_chart_code_never_reads_a_panels_height_attribute_back():
    """The Retina runaway, pinned where it can only come back deliberately.

    `canvas.height` *is* the `height` attribute: setting the backing buffer
    writes it. The old `prepare()` read that attribute as if it were the
    layout height and multiplied it by the device pixel ratio again on every
    redraw, so a 220px panel on the owner's Mac (ratio 2) reached a height
    attribute of 1,802,240px and a document of 2,540,001px before the plot
    failed white (PIHTI Log's audit, letter `20260907-023785d0`). At ratio 1
    the same code was stable, which is why nothing here ever saw it.

    The panel's height now comes from `data-height`, which nothing writes.
    """
    source = _live_js()
    assert 'getAttribute("height")' not in source
    assert "canvas.dataset.height" in source


def test_the_backing_buffer_is_bounded_and_a_refused_context_is_survived():
    """A browser refuses an oversized canvas and hands back nothing; the page
    draws no panel rather than throwing on every poll."""
    source = _live_js()
    assert "MAX_BUFFER" in source
    assert "if (!ctx) return null;" in source
    assert "if (!box) return;" in source


def test_every_chart_panel_declares_its_own_layout_height(client):
    """Two facts, two attributes, on all three panels.

    The three panels are one loop over a list on the server now, so this
    reads the rendered page rather than the template: what matters is that
    every canvas that reaches a browser carries both attributes and that
    they agree, not how the markup was written.
    """
    import re

    page = client.get("/").get_data(as_text=True)
    canvases = re.findall(r"<canvas[^>]*>", page)
    assert len(canvases) == 3
    for canvas in canvases:
        height = re.search(r'\bheight="(\d+)"', canvas).group(1)
        declared = re.search(r'data-height="(\d+)"', canvas).group(1)
        assert height == declared
    assert 'id="chart-plasma"' in page and 'data-height="220"' in page


# -- each chart carries its own curves' switches -------------------------------
#
# Owner report 2026-09-07: "all the little toggles on the Live view, hard to
# find the one I need", and "we need toggles, like in GUI, to show/hide
# plots". The five channel switches stood together in the left rail, away
# from the curves they turned off; each one now stands in the legend of the
# chart it belongs to.


def test_each_curve_has_exactly_one_switch_and_it_is_in_its_own_chart(client):
    import re

    page = client.get("/").get_data(as_text=True)
    for name in ("Ip", "Pu", "Pd", "Bu", "Bd"):
        assert page.count('data-channel="{}"'.format(name)) == 1
    # And each switch stands inside the panel that draws that curve.
    for block in re.findall(r'<section class="chart".*?</section>', page, re.S):
        drawn = re.search(r'data-channels="([^"]*)"', block).group(1).split(",")
        switches = re.findall(r'data-channel="([^"]*)"', block)
        assert switches == drawn


def test_no_channel_switch_is_left_in_the_rail(client):
    page = client.get("/").get_data(as_text=True)
    rail = page[page.index('class="rail rail-left operation-rail"'):]
    rail = rail[:rail.index("<main")]
    assert "data-channel=" not in rail


def test_a_flat_curve_leaves_the_axis_to_the_ones_that_move():
    """The broken SingleGauge sits at 1e-5 while the downstream gauge reads
    1e-8, and on one log axis the owner "can't see either" (2026-09-07). A
    curve whose whole excursion is smaller than its own last useful digit is
    left off the panel and out of its range, and says so beside its name.
    """
    source = _live_js()
    assert "FLAT_DECADES" in source and "FLAT_FRACTION" in source
    # Never on a panel that would empty itself: collapsing needs another
    # curve still moving.
    assert "moving.length && !view.pinned[s.name] && isFlat(s, logScale)" in source
    # The axis is computed from what is drawn, not from what was gathered.
    assert 'lines = series.filter(function (s) { return s.state === "drawn"; });' in source
    # Four states, each with its own word, and `drawn` says nothing at all.
    assert 'LEGEND_ASIDE = {off: "off", absent: "no data", nonpositive: "≤0 on log", flat: "flat", drawn: ""}' in source


def test_a_negative_reading_stays_a_number_in_its_own_slot():
    """queezz, 2026-09-10, on 4.11.0: "text jumps to numbers and back,
    terrible. We should keep that as a READOUT, not a tiny manual with many
    lines." So no word is ever written where the number goes, and the
    residual line that stood under it is gone."""
    source = _live_js()
    paint = source[source.index("function paintState"):source.index("function text(fact")]
    assert '.textContent = "Below zero"' not in paint
    assert 'querySelector(\'[data-role="residual"]\')' not in paint
    assert "readout--below-zero" not in source
    # One tag, in the row the name and unit already occupy, saying which of
    # the two states this number is in.
    assert 'data-role="readout-note"' in paint
    assert "tagForms(held, below)" in paint


def test_the_state_tag_is_measured_rather_than_clipped():
    """The narrowest card holds one word, not two, and at 1200px not even
    the long form of that one. Which form a card carries is read from the
    tag's own box, so a wider card keeps more of it and none is ever cut."""
    source = _live_js()
    tags = source[source.index("function tagForms"):source.index("function paintState")]
    for form in ('"zeroed · below zero"', '"below zero"', '"below 0"'):
        assert form in tags
    assert "narrowest.el.scrollWidth <= narrowest.el.clientWidth + 1" in tags
    # One wording for the whole strip, decided by the narrowest card in it
    # and by nothing about today's numbers.
    assert "paintTags(tags)" in source


def test_the_baratron_chart_carries_no_paragraph_of_its_own():
    """The detection-limit note was the lecture WEBUI.md's Teaching section
    forbids; the reasoning lives on the docs page."""
    page = _client().get("/").get_data(as_text=True)
    assert "Detection limit not characterized" not in page
    assert "measurement-note" not in page
    assert "measurement-note" not in _live_js()


def test_a_collapsed_curve_does_not_print_a_second_copy_of_its_value():
    """Every number on this page is read in its readout card; the legend
    says why a curve is missing, never what it last read."""
    source = _live_js()
    aside = source[source.index("function paintLegend"):]
    aside = aside[:aside.index("function drawAll")]
    assert "valueHtml" not in aside and "valueText" not in aside


# -- Monitor mode, and the presets that set the page for a kind of work -------


def _pressed(page, attribute):
    """Whether a button carrying `attribute` is pressed, however the
    template happened to wrap its attributes across lines."""
    button = page[page.index(attribute):]
    button = button[:button.index("</button>")]
    start = button.index('aria-pressed="') + len('aria-pressed="')
    return button[start:button.index('"', start)]


def _client():
    from pathlib import Path

    from controlunit.web.roster import Roster
    from controlunit.web.fence import Fence

    nowhere = Path(__file__).resolve().parent / "nowhere-there-is-none"
    return create_app(
        board=NeighbourBoard(home=nowhere),
        roster=Roster(home=nowhere),
        fence=Fence(home=nowhere),
    ).test_client()


def test_the_ordinary_page_is_the_ordinary_page():
    """No mode in the address is the page as it has always been."""
    page = _client().get("/").get_data(as_text=True)
    assert '<body data-mode="operate">' in page
    assert _pressed(page, 'class="choice" data-mode="monitor"') == "false"


def test_a_bookmarked_monitor_address_renders_in_that_shape_first(client=None):
    """A second laptop propped up beside the rig bookmarks its own screen,
    and the server paints that shape rather than flashing the other one
    (queezz, 2026-09-07: "Monitor: plots only, even hide the rails")."""
    page = _client().get("/?mode=monitor").get_data(as_text=True)
    assert '<body data-mode="monitor">' in page
    assert _pressed(page, 'class="choice" data-mode="monitor"') == "true"


def test_a_mistyped_mode_is_the_ordinary_page_and_never_an_error():
    response = _client().get("/?mode=cockpit")
    assert response.status_code == 200
    assert '<body data-mode="operate">' in response.get_data(as_text=True)


def test_every_tab_carries_a_mode_and_only_live_offers_the_switch():
    """The body attribute is never absent, so nothing renders half-shaped;
    the mode itself belongs to the tab that has charts to give the window."""
    client = _client()
    for path in ("/", "/control", "/log", "/lab"):
        page = client.get(path).get_data(as_text=True)
        assert "<body data-mode=" in page
    for path in ("/log", "/lab"):
        page = client.get(path).get_data(as_text=True)
        assert 'data-mode="monitor"' not in page


def test_monitor_keeps_the_two_pills_and_hides_the_rest():
    """Only the rails and the tab bar step aside: what the rig is doing is
    the one thing that screen exists to say."""
    page = _client().get("/?mode=monitor").get_data(as_text=True)
    pills = page[page.index('class="pills"'):]
    pills = pills[:pills.index("</div>")]
    assert 'data-role="operating"' in pills
    assert 'data-role="data-state"' in pills
    toolbar = page[page.index('class="view-toolbar"'):page.index('class="readout-toolbar"')]
    assert 'data-drawer="live-controls"' not in toolbar
    assert 'data-drawer="live-context"' in page
    assert 'data-mode="observe"' in toolbar
    assert 'data-mode="operate"' in toolbar
    assert 'data-role="fullscreen"' in page


def test_the_rails_are_the_same_rails_summoned_from_their_own_edge():
    """The drawer is the diagram's own shape and the same DOM: nothing is
    duplicated for the mode, so no control can drift from its twin."""
    page = _client().get("/").get_data(as_text=True)
    assert 'class="rail rail-left operation-rail" id="live-controls"' in page
    assert 'class="rail rail-right operation-rail" id="live-context"' in page
    assert page.count('class="drawer-close"') == 1
    assert page.count('class="drawer-backdrop"') == 1
    css = _client().get("/static/css/controlunit.css").get_data(as_text=True)
    assert 'body[data-mode="monitor"] .tabbar { display: none; }' in css
    assert 'body[data-mode="monitor"] .rail.drawer-open' in css


def test_the_view_card_teaches_the_one_thing_its_rows_cannot_say():
    """A data surface states and one line teaches, once for the whole
    surface: that a mode is in the address is what a reader cannot see from
    the buttons, and it is said nowhere else on this page."""
    page = _client().get("/").get_data(as_text=True)
    assert page.count("a mode stays in the address, so a screen can be bookmarked") == 1
    # And nothing here explains a second time what the zero card already
    # teaches about the page and the file.
    assert page.count("the data file keeps the signal as measured") == 1


def test_the_mode_lives_in_the_address_so_back_and_reload_keep_it():
    source = _live_js()
    assert "window.history.pushState" in source
    assert 'url.searchParams.set("mode", next)' in source
    assert 'window.addEventListener("popstate"' in source


def test_escape_leaves_the_drawer_first_and_then_the_mode():
    """A mode is never a room without a door."""
    source = _live_js()
    escape = source[source.index('if (event.key !== "Escape") return;'):]
    escape = escape[:escape.index("});")]
    assert escape.index("closeDrawers(); return;") < escape.index('setMode("observe")')


def test_the_two_presets_are_the_curves_the_work_needs():
    """A preset is a named set of the per-curve switches and nothing else.
    Vacuum is pumping and leak hunting; Plasma is a discharge running, where
    the Baratrons read the pressure and the ion gauges are off scale."""
    page = _client().get("/").get_data(as_text=True)
    for name, channels in (
        ("all", "Ip,Pu,Pd,Bu,Bd"),
        ("vacuum", "Pu,Pd,Bu,Bd"),
        ("plasma", "Ip,Bu,Bd"),
    ):
        button = page[page.index('data-preset="{}"'.format(name)):]
        button = button[:button.index("</button>")]
        assert 'data-channels="{}"'.format(channels) in button


def test_a_preset_changes_what_is_drawn_and_nothing_the_rig_records():
    """It writes the same browser-local choice the legend switches write,
    and posts nothing at all."""
    source = _live_js()
    applied = source[source.index("function applyPreset"):]
    applied = applied[:applied.index("function reflectChannels")]
    assert "view.channels[name]" in applied
    assert "remember()" in applied
    assert "fetch(" not in applied and "post(" not in applied


def test_which_preset_is_pressed_is_derived_from_the_switches():
    """Turn one curve off by hand and the page stops claiming a preset,
    rather than keeping a second stored value that could drift."""
    source = _live_js()
    assert "function matchesPreset" in source
    assert "view.preset" not in source


def test_a_panel_with_every_curve_off_keeps_its_legend():
    """The switches that bring the curves back stay where the reader left
    them; only the drawing area is given up."""
    source = _live_js()
    assert "function collapsedLegend" in source
    assert 'section.classList.toggle("chart--collapsed", !shown)' in source
    assert 'if (!drawn) return "Click a pill to show a curve";' in source
    css = _client().get("/static/css/controlunit.css").get_data(as_text=True)
    assert ".chart--collapsed canvas { display: none; }" in css


def test_unified_modes_and_legacy_control_links():
    client = _client()
    for asked, expected in (("operate", "operate"), ("observe", "observe"),
                            ("monitor", "monitor"), ("normal", "observe")):
        page = client.get("/?mode=" + asked).get_data(as_text=True)
        assert '<body data-mode="{}">'.format(expected) in page
        assert page.count('data-role="acq-start"') == 1
    page = client.get("/control?mode=monitor").get_data(as_text=True)
    assert '<body data-mode="operate">' in page
    assert 'aria-current="page">ControlUnit ' in page

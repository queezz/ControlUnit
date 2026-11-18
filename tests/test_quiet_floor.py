"""Ip's quiet floor: settings `Quiet Within`, carried to the Live tab's charts.

queezz, 2026-09-07: the current plot with no plasma is "a noisy waste of
space"; 2026-11-18, on the floor measured from the quiet record of 11-16:
"build it. Number, you now know better".
"""

import os
import types
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit._version import __version__  # noqa: E402
from controlunit.devices.adc_channels import AdcChannelProps  # noqa: E402
from controlunit.web.status import RigStatus, state_body  # noqa: E402

SETTINGS = Path(__file__).resolve().parents[1] / "controlunit" / "settings.yml"


def props(**extra):
    base = {"Channel": 0, "Gain": 5, "Description": "Plasma Current",
            "Conversion Function": "Hall Sensor"}
    base.update(extra)
    return AdcChannelProps("Ip", **base)


def test_the_settings_give_ip_its_measured_floor_and_no_one_else_one():
    config = yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
    floors = {name: spec.get("Quiet Within")
              for name, spec in config["ADC Channels"].items()}
    assert floors["Ip"] == 0.06
    assert [name for name, floor in floors.items() if floor is not None] == ["Ip"]


def test_a_channel_reads_its_floor_and_ignores_what_is_not_one():
    assert props(**{"Quiet Within": 0.06}).quiet_within == 0.06
    assert props().quiet_within is None
    for bad in (0, -0.1, "none", None):
        assert props(**{"Quiet Within": bad}).quiet_within is None


def test_the_state_carries_each_channel_floor_or_none():
    status = RigStatus(names=["Ip", "Bu"], units={"Ip": "A", "Bu": "Torr"},
                       quiet={"Ip": 0.06, "Bu": None})
    channels = {c["name"]: c for c in state_body(status, __version__)["channels"]}
    assert channels["Ip"]["quiet_within"] == 0.06
    assert channels["Bu"]["quiet_within"] is None


def test_a_status_without_floors_still_answers():
    body = state_body(RigStatus(names=["Ip"]), __version__)
    assert body["channels"][0]["quiet_within"] is None


def test_the_main_thread_hands_over_only_the_floors_it_has():
    main = pytest.importorskip("controlunit.main")
    owner = types.SimpleNamespace(config={"Adc Channel Properties": {
        "Ip": props(**{"Quiet Within": 0.06}), "Bu": props()}})
    assert main.MainApp._web_quiet(owner) == {"Ip": 0.06}


STATIC = Path(__file__).resolve().parents[1] / "controlunit" / "web" / "static"


def test_the_fold_memory_never_keeps_a_fold_the_page_made():
    # A quiet chart folds itself (live.js marks it `foldAuto`); remembering
    # that fold would leave the chart shut after a reload with a discharge on.
    control = (STATIC / "js" / "control.js").read_text(encoding="utf-8")
    listener = control[control.index('fold.addEventListener("toggle"'):]
    guard = listener.index('fold.dataset.foldAuto === (fold.open ? "1" : "0")) return;')
    assert guard < listener.index("localStorage.setItem")


def test_a_folded_chart_leaves_the_column_for_a_chip():
    # queezz, 2026-11-18: "the collapsed bar still eats space"; he chose chips.
    css = (STATIC / "css" / "controlunit.css").read_text(encoding="utf-8")
    assert ".chart-head.fold-head { min-height: 28px; padding: 2px 0; }" in css
    assert ".chart.fold:not([open]) { display: none; }" in css
    page = (STATIC.parent / "templates" / "_live_readings.html").read_text(encoding="utf-8")
    row = page[page.index('<div class="pressure-grouping">'):]
    row = row[:row.index("</div>")]
    assert '<span class="muted">Charts</span>' in row
    assert 'data-role="chart-chips"' in row and 'aria-label="Charts shown"' in row
    # The grouping switch keeps its own group, so a screen reader still hears
    # what By gauge and By vessel group.
    assert 'aria-label="Pressure plot grouping"' in row


def test_operate_and_observe_keep_the_declared_chart_size():
    # queezz: "The plot view size was correct before your last commits".
    live = (STATIC / "js" / "live.js").read_text(encoding="utf-8")
    assert 'return (mode === "monitor" && plotHeight !== null) ? plotHeight : declared;' in live
    fit = live[live.index("function fitHeight() {"):]
    assert fit.index('if (mode !== "monitor") return null;') < fit.index("getBoundingClientRect")


def test_the_charts_row_heads_every_chart(tmp_path):
    # It stood between the plasma chart and the pressure charts and moved
    # with the first whenever it folded (queezz, 2026-11-18: "No JUMPING UI
    # is my old and strong rule in the fleet!"). Above all of them, nothing
    # a chart does can move it.
    from controlunit.web.neighbours import NeighbourBoard
    from controlunit.web.server import create_app

    status = RigStatus(names=["Ip", "Pu", "Pd", "Bu", "Bd"])
    app = create_app(status=status, board=NeighbourBoard(home=tmp_path / "nowhere"))
    page = app.test_client().get("/").get_data(as_text=True)
    row = page.index('<div class="pressure-grouping">')
    charts = [page.index('id="%s"' % chart) for chart in ("chart-plasma", "chart-ig", "chart-bar")]
    assert row < min(charts)
    assert page.count('<div class="pressure-grouping">') == 1


def test_the_chart_switches_are_built_once_and_only_repainted():
    # Chips that came and went made their neighbours slide; a switch per
    # chart that only changes its own state moves nothing.
    live = (STATIC / "js" / "live.js").read_text(encoding="utf-8")
    paint = live[live.index("function paintChartChips() {"):]
    paint = paint[:paint.index("\n    }\n")]
    assert "if (names !== switchNames)" in paint
    assert 'button.setAttribute("aria-pressed", section.open ? "true" : "false");' in paint

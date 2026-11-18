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

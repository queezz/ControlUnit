"""The Lab page renders, names the three services, and keeps its assets local."""

import re

import pytest

from controlunit._version import __version__
from controlunit.web.neighbours import NeighbourBoard
from controlunit.web.server import create_app


@pytest.fixture
def page(tmp_path):
    client = create_app(board=NeighbourBoard(home=tmp_path / "nowhere")).test_client()
    response = client.get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_the_page_names_the_three_services(page):
    for name in ("ControlUnit", "PIHTI Log", "PIHTI diagram"):
        assert name in page


def test_the_page_asks_the_neighbours_route_for_its_refresh():
    client = create_app().test_client()
    script = client.get("/static/js/lab.js").get_data(as_text=True)
    assert "/api/neighbours" in script


def test_the_page_carries_the_three_lab_start_lines(page):
    for command in ("lab controlunit --web", "lab pihti-log", "lab pihti-diagram"):
        assert command in page


def test_assets_are_keyed_to_the_version(page):
    for asset in ("css/controlunit.css", "js/lab.js"):
        assert re.search(re.escape(asset) + r"\?v=" + re.escape(__version__), page)


def test_the_page_fetches_nothing_from_the_internet(page):
    assert "//" not in page.replace("http://", "").replace("https://", "")
    assert "cdn" not in page.lower()


def test_the_page_uses_the_three_track_grid_with_both_rails(page):
    assert 'class="page"' in page
    assert "rail-left" in page
    assert "rail-right" in page


def test_the_states_are_explained_in_exactly_one_place(page):
    """The rail legend teaches once; every chip elsewhere only states."""
    for meaning in (
        "nothing answered from this machine",
        "answered, and said it is not working",
    ):
        assert page.count(meaning) == 1

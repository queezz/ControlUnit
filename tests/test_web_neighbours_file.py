"""Neighbours come from their own small file, with how each is started.

`~/.controlunit/settings.yml` is a complete replacement for the packaged
settings when it exists, so a file holding only neighbours would stop the
rig from starting. The addresses therefore live in `neighbours.yml`; the
older block in `settings.yml` is still honoured when the new file is absent.
"""

import io
import json

from controlunit.web import neighbours as neighbourhood
from controlunit.web.neighbours import NeighbourBoard, read_neighbours
from controlunit.web.server import create_app

NEIGHBOURS = """\
pihti-diagram:
  url: http://rig.example:5000/
  where: on this Pi, as a system service
  start_how: on the Pi itself, as a system service
  start: sudo systemctl start pihti.service
pihti-log:
  url: http://vault.example:4310
"""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_the_neighbours_file_carries_where_and_start(tmp_path):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "neighbours.yml").write_text(NEIGHBOURS, encoding="utf-8")
    entries = read_neighbours(home)
    assert entries["pihti-diagram"] == {
        "url": "http://rig.example:5000",
        # No `open_url` in this file, so a browser opens the same address
        # the rig probed.
        "open_url": "http://rig.example:5000",
        "where": "on this Pi, as a system service",
        "start_how": "on the Pi itself, as a system service",
        "start": "sudo systemctl start pihti.service",
    }
    assert entries["pihti-log"] == {
        "url": "http://vault.example:4310",
        "open_url": "http://vault.example:4310",
        "where": "",
        "start_how": "",
        "start": "",
    }


def test_the_old_settings_block_is_used_only_when_the_file_is_absent(tmp_path):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "settings.yml").write_text(
        "Settings Version: 1.3\nNeighbours:\n  pihti-log: http://old.example:4310\n",
        encoding="utf-8",
    )
    assert read_neighbours(home)["pihti-log"]["url"] == "http://old.example:4310"
    (home / "neighbours.yml").write_text(NEIGHBOURS, encoding="utf-8")
    assert read_neighbours(home)["pihti-log"]["url"] == "http://vault.example:4310"


def test_the_card_says_how_that_service_starts_or_nothing(tmp_path, monkeypatch):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "neighbours.yml").write_text(NEIGHBOURS, encoding="utf-8")

    def opener(url, timeout=None):
        return FakeResponse(json.dumps({"status": "ok", "version": "0.7.0", "detail": ""}).encode())

    monkeypatch.setattr(neighbourhood.urllib.request, "urlopen", opener)
    client = create_app(board=NeighbourBoard(home=home)).test_client()
    rows = {row["alias"]: row for row in client.get("/api/neighbours").get_json()["services"]}
    assert rows["pihti-diagram"]["start"] == "sudo systemctl start pihti.service"
    assert rows["pihti-diagram"]["start_how"] == "on the Pi itself, as a system service"
    assert rows["pihti-diagram"]["where"] == "on this Pi, as a system service"
    assert rows["pihti-log"]["start"] == ""
    assert rows["pihti-log"]["start_how"] == ""
    assert rows["pihti-log"]["where"] == ""

    page = client.get("/lab").get_data(as_text=True)
    diagram = page[page.index('data-alias="pihti-diagram"'):]
    diagram = diagram[:diagram.index("</article>")]
    # The words lead the row; the command is there, behind the toggle.
    assert 'data-role="start-how">on the Pi itself, as a system service<' in diagram
    assert 'data-role="start" hidden>sudo systemctl start pihti.service</code>' in diagram

    # The other entry gives neither, so its card says neither. A start line
    # is copied from this file or the row ends at an em dash; it is never
    # invented from the service's own name.
    journal = page[page.index('data-alias="pihti-log"'):]
    journal = journal[:journal.index("</article>")]
    assert 'data-role="start-how">—<' in journal
    assert "lab pihti-log" not in page


def test_a_command_without_words_still_leads_with_words(tmp_path, monkeypatch):
    """An older file gives `start` and nothing else. Meaning still leads:
    the card says so in words of its own and keeps the line behind the
    toggle, rather than putting a command where the meaning belongs."""
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "neighbours.yml").write_text(
        "pihti-log:\n"
        "  url: http://vault.example:4310\n"
        "  start: lab pihti-log\n",
        encoding="utf-8",
    )

    def opener(url, timeout=None):
        return FakeResponse(json.dumps({"status": "ok", "version": "0.8.0"}).encode())

    monkeypatch.setattr(neighbourhood.urllib.request, "urlopen", opener)
    client = create_app(board=NeighbourBoard(home=home)).test_client()
    page = client.get("/lab").get_data(as_text=True)
    journal = page[page.index('data-alias="pihti-log"'):]
    journal = journal[:journal.index("</article>")]
    assert 'data-role="start-how">Started by a command on its own machine.<' in journal
    assert 'data-role="start" hidden>lab pihti-log</code>' in journal


# -- the address the rig asks, and the address a browser opens ----------------

TWO_ADDRESSES = """\
pihti-diagram:
  url: http://rig.example:5000
  open_url: http://rig.local.example:5000
pihti-log:
  url: http://vault.example:4310
"""


def _home_with(tmp_path, text):
    home = tmp_path / ".controlunit"
    home.mkdir()
    (home / "neighbours.yml").write_text(text, encoding="utf-8")
    return home


def test_a_browser_may_be_sent_to_a_different_name_than_the_rig_probes(
    tmp_path, monkeypatch
):
    """Two machines follow that link and they do not resolve the same names.

    On 2026-09-07 the diagram's card read `ok` — the Pi resolves the bare
    name `pihti` on its own network — and its Open link did nothing on the
    owner's Mac, which knows `pihti.local` and the numeric address but not
    the bare name (PIHTI Log's audit, letter `20260907-023785d0`). A green
    chip is this rig's measurement and was never a promise about the laptop
    reading the page, so where the two names differ the file says both.
    """
    home = _home_with(tmp_path, TWO_ADDRESSES)

    def opener(url, timeout=None):
        # The probe goes to the rig's own name, never to the browser's.
        assert url.startswith("http://rig.example:5000"), url
        return FakeResponse(
            json.dumps({"status": "ok", "version": "0.8.0", "detail": ""}).encode()
        )

    monkeypatch.setattr(neighbourhood.urllib.request, "urlopen", opener)
    board = NeighbourBoard(home=home)
    board.neighbours()
    assert board.wait(timeout=10)
    rows = {row["alias"]: row for row in board.neighbours()}

    diagram = rows["pihti-diagram"]
    assert diagram["state"] == "ok"
    assert diagram["url"] == "http://rig.local.example:5000"
    assert diagram["probe_url"] == "http://rig.example:5000"
    assert diagram["opens_at"] == "rig.local.example:5000"


def test_one_address_serves_both_when_the_file_gives_only_one(tmp_path):
    """The usual case, and the field is usually absent."""
    home = _home_with(tmp_path, TWO_ADDRESSES)
    entry = read_neighbours(home)["pihti-log"]
    assert entry["url"] == entry["open_url"] == "http://vault.example:4310"


def test_the_card_shows_the_address_the_reader_will_open(tmp_path, monkeypatch):
    home = _home_with(tmp_path, TWO_ADDRESSES)
    monkeypatch.setattr(
        neighbourhood.urllib.request,
        "urlopen",
        lambda url, timeout=None: FakeResponse(
            json.dumps({"status": "ok", "version": "0.8.0", "detail": ""}).encode()
        ),
    )
    client = create_app(board=NeighbourBoard(home=home)).test_client()
    client.get("/lab")
    page = client.get("/lab").get_data(as_text=True)
    card = page[page.index('data-alias="pihti-diagram"'):]
    card = card[:card.index("</article>")]
    assert 'href="http://rig.local.example:5000"' in card
    assert "rig.local.example:5000</span>" in card

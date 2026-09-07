"""The lab's roster, as this machine happens to hold a copy of it.

Every way of not having one — no file, a folder, bytes that are not JSON, a
schema from some other program — is the same answer here: no names, and the
Acting-as field stays the free-text box it has always been. Nothing in this
module may raise into a request.
"""

import os

import pytest

from controlunit.web import roster as roster_module
from controlunit.web.roster import Roster, read_roster

GOOD = """\
{"schema": "pihti-operators/v1",
 "operators": [
   {"username": "hashizuka", "display_name": "Hashizuka Takuma"},
   {"username": "queezz", "display_name": "Arseniy Kuzmin"},
   {"username": "sasaki", "display_name": "Sasaki Rei"}
 ]}
"""


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / ".controlunit"
    folder.mkdir()
    return folder


def write(home, text):
    (home / "operators.json").write_text(text, encoding="utf-8")
    return home / "operators.json"


def test_no_file_means_no_names(tmp_path):
    assert read_roster(tmp_path / "nowhere") == []


def test_a_file_that_is_not_json_means_no_names(home):
    write(home, "not json at all")
    assert read_roster(home) == []


def test_json_that_is_not_an_object_means_no_names(home):
    write(home, '["hashizuka", "queezz"]')
    assert read_roster(home) == []


def test_another_programs_schema_means_no_names(home):
    write(home, '{"schema": "some-other/v3", "operators": [{"display_name": "X"}]}')
    assert read_roster(home) == []


def test_a_missing_schema_means_no_names(home):
    write(home, '{"operators": [{"display_name": "Hashizuka Takuma"}]}')
    assert read_roster(home) == []


def test_operators_that_are_not_a_list_means_no_names(home):
    write(home, '{"schema": "pihti-operators/v1", "operators": {"a": "b"}}')
    assert read_roster(home) == []


def test_an_entry_with_no_display_name_is_skipped(home):
    write(
        home,
        '{"schema": "pihti-operators/v1", "operators": ['
        '{"username": "ghost"}, "not an entry",'
        '{"username": "queezz", "display_name": "Arseniy Kuzmin"}]}',
    )
    assert read_roster(home) == [
        {"username": "queezz", "display_name": "Arseniy Kuzmin"}
    ]


def test_a_good_file_gives_its_names_in_file_order(home):
    write(home, GOOD)
    assert read_roster(home) == [
        {"username": "hashizuka", "display_name": "Hashizuka Takuma"},
        {"username": "queezz", "display_name": "Arseniy Kuzmin"},
        {"username": "sasaki", "display_name": "Sasaki Rei"},
    ]


def test_a_folder_where_the_file_should_be_means_no_names(home):
    (home / "operators.json").mkdir()
    assert read_roster(home) == []


def test_the_settings_home_override_is_honoured(home, monkeypatch):
    write(home, GOOD)
    monkeypatch.setenv("CONTROLUNIT_SETTINGS_HOME", str(home))
    assert [person["display_name"] for person in read_roster()][0] == "Hashizuka Takuma"


# -- the cached reread --------------------------------------------------------


def test_the_names_are_the_display_names(home):
    write(home, GOOD)
    assert Roster(home=home).names() == [
        "Hashizuka Takuma",
        "Arseniy Kuzmin",
        "Sasaki Rei",
    ]


def test_an_unchanged_file_is_not_read_twice(home, monkeypatch):
    write(home, GOOD)
    now = [0.0]
    people = Roster(home=home, clock=lambda: now[0])
    assert len(people.names()) == 3

    reads = []
    monkeypatch.setattr(
        roster_module, "read_roster", lambda home=None: reads.append(1) or []
    )
    # Past the once-a-second bound, so it looks — and finds the same
    # (mtime, size) it had, which is the whole point of comparing them.
    now[0] = 60.0
    assert len(people.names()) == 3
    assert reads == []


def test_a_changed_file_is_read_again(home):
    write(home, GOOD)
    now = [0.0]
    people = Roster(home=home, clock=lambda: now[0])
    assert len(people.names()) == 3

    path = write(
        home,
        '{"schema": "pihti-operators/v1", "operators": ['
        '{"username": "queezz", "display_name": "Arseniy Kuzmin"}]}',
    )
    # A copy made twice in the same second still has to be noticed, so the
    # timestamp is moved deliberately rather than left to the clock.
    os.utime(path, ns=(10**9, 5 * 10**9))
    now[0] = 60.0
    assert people.names() == ["Arseniy Kuzmin"]


def test_the_file_is_not_looked_at_more_than_once_a_second(home):
    write(home, GOOD)
    now = [0.0]
    people = Roster(home=home, clock=lambda: now[0])
    assert len(people.names()) == 3

    (home / "operators.json").unlink()
    now[0] = 0.4  # inside the bound: the last answer stands
    assert len(people.names()) == 3
    now[0] = 2.0
    assert people.names() == []


def test_a_roster_that_appears_later_is_picked_up(home):
    now = [0.0]
    people = Roster(home=home, clock=lambda: now[0])
    assert people.names() == []

    write(home, GOOD)
    now[0] = 2.0
    assert len(people.names()) == 3


# -- two colleagues spelled the same way --------------------------------------

TWINS = """\
{"schema": "pihti-operators/v1",
 "operators": [
   {"username": "tanaka.h", "display_name": "Tanaka Haruki"},
   {"username": "queezz", "display_name": "Arseniy Kuzmin"},
   {"username": "tanaka.k", "display_name": "Tanaka Haruki"}
 ]}
"""

NAMELESS_TWINS = """\
{"schema": "pihti-operators/v1",
 "operators": [
   {"username": "", "display_name": "Tanaka Haruki"},
   {"username": "tanaka.k", "display_name": "Tanaka Haruki"}
 ]}
"""


def test_a_name_two_people_share_carries_the_username_that_tells_them_apart(home):
    """The Acting-as list offered one word twice, and choosing the second one
    told you nothing about which colleague the log would name (PIHTI Log's Mac
    audit 2026-09-07, the same defect in the journal). A colliding name is
    written with its username; a name nobody shares is untouched."""
    from controlunit.web.roster import labels

    (home / "operators.json").write_text(TWINS, encoding="utf-8")
    names = Roster(home=home).names()
    assert names == [
        "Tanaka Haruki (tanaka.h)",
        "Arseniy Kuzmin",
        "Tanaka Haruki (tanaka.k)",
    ]
    assert len(set(names)) == len(names)
    # Nothing merged: the roster still holds both people, with their own ids.
    assert [person["username"] for person in Roster(home=home).entries()] == [
        "tanaka.h",
        "queezz",
        "tanaka.k",
    ]
    assert labels(read_roster(home)) == names


def test_a_colliding_entry_with_no_username_is_left_as_it_stands(home):
    """There is nothing to tell them apart with, and an invented id would be
    worse than a repeated name. Neither entry is dropped or merged."""
    (home / "operators.json").write_text(NAMELESS_TWINS, encoding="utf-8")
    assert Roster(home=home).names() == [
        "Tanaka Haruki",
        "Tanaka Haruki (tanaka.k)",
    ]


def test_names_nobody_shares_are_never_decorated(home):
    (home / "operators.json").write_text(GOOD, encoding="utf-8")
    assert Roster(home=home).names() == [
        "Hashizuka Takuma",
        "Arseniy Kuzmin",
        "Sasaki Rei",
    ]


# -- the copy refreshes itself over the LAN -----------------------------------
#
# PIHTI Log 0.38.0 serves the vault's roster at GET /api/roster on the same
# origin this rig already asks /api/health of (letter
# `20260907-2e0205ef-f3c730`). The rig reads it behind its own neighbour
# probe, so nobody runs the push script again after the first time.


class FakeAnswer:
    """What `urlopen` hands back: a context manager with `read`."""

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size=None):
        return self._payload


def opener_for(payload, seen=None):
    def opener(url, timeout=None):
        if seen is not None:
            seen.append((url, timeout))
        if isinstance(payload, Exception):
            raise payload
        return FakeAnswer(payload)

    return opener


SERVED = (
    b'{"schema": "pihti-operators/v1", "operators": ['
    b'{"username": "hashizuka", "display_name": "Hashizuka Takuma"},'
    b'{"username": "queezz", "display_name": "Arseniy Kuzmin"}]}'
)


def test_the_roster_is_asked_of_the_neighbours_own_origin():
    seen = []
    people = roster_module.fetch_roster(
        "http://ak-office.local:4310/", opener=opener_for(SERVED, seen)
    )
    assert [person["display_name"] for person in people] == [
        "Hashizuka Takuma",
        "Arseniy Kuzmin",
    ]
    assert seen == [("http://ak-office.local:4310/api/roster", 2.0)]


@pytest.mark.parametrize(
    "payload",
    [
        b"not json at all",
        b'{"schema": "some-other-thing/v1", "operators": []}',
        b'{"schema": "pihti-operators/v1", "operators": "everyone"}',
        OSError("the office PC is off"),
    ],
)
def test_every_kind_of_no_answer_is_one_answer(payload):
    """A 404 from a vault with no roster, silence, and a body that is not a
    roster all mean the same thing to the caller: nothing new to write."""
    assert roster_module.fetch_roster("http://host", opener=opener_for(payload)) is None


def test_a_refresh_writes_the_copy_this_machine_reads(home):
    mirror = roster_module.RosterMirror(
        home=home,
        fetch=lambda url: [{"username": "sasaki", "display_name": "Sasaki Rei"}],
        stamp=lambda: "14:02:57",
    )
    assert mirror.refresh("http://host") is True
    # The very file `Roster` already reads, in the shape it already parses.
    assert read_roster(home) == [{"username": "sasaki", "display_name": "Sasaki Rei"}]
    assert mirror.report() == {"source": "PIHTI Log", "at": "14:02:57", "names": 1}


def test_the_last_copy_survives_a_neighbour_that_does_not_answer(home):
    write(home, GOOD)
    before = (home / "operators.json").read_bytes()
    mirror = roster_module.RosterMirror(home=home, fetch=lambda url: None)
    assert mirror.refresh("http://host") is False
    assert (home / "operators.json").read_bytes() == before
    # Never asked and asked-and-nothing-came-back are not the same fact, and
    # neither of them is a time this copy was confirmed.
    assert mirror.report() is None


def test_an_empty_roster_never_erases_the_names_this_machine_has(home):
    """A vault answering with nobody in it is not a reason to forget the
    people this rig has been spelling correctly for a month."""
    write(home, GOOD)
    mirror = roster_module.RosterMirror(home=home, fetch=lambda url: [])
    assert mirror.refresh("http://host") is False
    assert len(read_roster(home)) == 3


def test_the_copy_is_never_written_in_halves(home, monkeypatch):
    """The file is written beside itself and moved over in one step, so a
    write that falls over leaves the old roster whole."""
    write(home, GOOD)

    def explode(*args, **kwargs):
        raise OSError("the card filled up")

    monkeypatch.setattr(roster_module.os, "replace", explode)
    assert roster_module.write_copy(
        [{"username": "x", "display_name": "Somebody Else"}], home
    ) is False
    assert len(read_roster(home)) == 3
    # And the half-written file it was going to move is not left lying about.
    assert [p.name for p in home.iterdir()] == ["operators.json"]


def test_a_copy_that_already_says_this_is_not_rewritten(home):
    people = [{"username": "sasaki", "display_name": "Sasaki Rei"}]
    assert roster_module.write_copy(people, home) is True
    stamp = (home / "operators.json").stat().st_mtime_ns
    assert roster_module.write_copy(people, home) is True
    assert (home / "operators.json").stat().st_mtime_ns == stamp


def test_only_the_neighbour_that_keeps_the_roster_is_asked_for_it(tmp_path):
    """The mirror rides on the neighbour probe: one ask per probe at most,
    for the one service that serves a roster, and none of its own."""
    from controlunit.web.server import ROSTER_SOURCE, _roster_follower

    asked = []

    class Counter:
        def refresh(self, url):
            asked.append(url)

    follow = _roster_follower(Counter())
    follow("pihti-diagram", "http://pihti:5000")
    assert asked == []
    follow(ROSTER_SOURCE, "http://ak-office.local:4310")
    assert asked == ["http://ak-office.local:4310"]


def test_the_probe_asks_for_names_only_when_a_neighbour_answered(tmp_path):
    from controlunit.web.neighbours import NeighbourBoard

    (tmp_path / "neighbours.yml").write_text(
        "pihti-log:\n  url: http://ak-office.local:4310\n"
        "pihti-diagram:\n  url: http://pihti:5000\n",
        encoding="utf-8",
    )
    asked = []
    answers = {
        "http://ak-office.local:4310": ("ok", "0.38.0", "idle"),
        "http://pihti:5000": ("unreachable", "", "no answer within two seconds"),
    }
    import controlunit.web.neighbours as neighbours_module

    original = neighbours_module._read_health
    neighbours_module._read_health = lambda url, timeout=None: answers[url]
    try:
        board = NeighbourBoard(
            home=tmp_path, after_health=lambda alias, url: asked.append(alias)
        )
        board.neighbours()
        board.wait(5)
    finally:
        neighbours_module._read_health = original
    # The diagram was unreachable, so nothing was asked of it.
    assert asked == ["pihti-log"]


def test_the_state_route_says_when_the_names_last_refreshed(tmp_path):
    from controlunit.web.server import create_app

    mirror = roster_module.RosterMirror(
        home=tmp_path,
        fetch=lambda url: [{"username": "sasaki", "display_name": "Sasaki Rei"}],
        stamp=lambda: "14:02:57",
    )
    client = create_app(mirror=mirror).test_client()
    assert client.get("/api/state").get_json()["roster"] is None
    mirror.refresh("http://host")
    body = client.get("/api/state").get_json()["roster"]
    assert body == {"source": "PIHTI Log", "at": "14:02:57", "names": 1}
    # A count and a time. No address, and no names.
    assert "ak-office" not in repr(body) and "Sasaki" not in repr(body)

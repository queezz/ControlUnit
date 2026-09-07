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

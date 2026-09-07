"""The lab's word, as this machine happens to hold it.

The important half of this file is the absences. A machine with no
`~/.controlunit/fence.txt` has no fence, so every off-rig dummy run and
every other test in this suite behaves exactly as it did before; only a
machine that holds a word asks anybody for one. Nothing in this module may
raise into a request.
"""

import os

import pytest

from controlunit.web import fence as fence_module
from controlunit.web.fence import Fence, read_fence

WORD = "plasmabox"


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / ".controlunit"
    folder.mkdir()
    return folder


def write(home, text):
    (home / "fence.txt").write_text(text, encoding="utf-8")
    return home / "fence.txt"


# -- what counts as no fence at all -------------------------------------------


def test_no_file_means_no_fence(tmp_path):
    assert read_fence(tmp_path / "nowhere") == ""


def test_an_empty_file_means_no_fence(home):
    write(home, "")
    assert read_fence(home) == ""


def test_a_file_of_blank_lines_means_no_fence(home):
    write(home, "\n  \n\t\n")
    assert read_fence(home) == ""


def test_a_folder_where_the_file_should_be_means_no_fence(home):
    (home / "fence.txt").mkdir()
    assert read_fence(home) == ""


def test_a_machine_with_no_fence_needs_nothing(home):
    barrier = Fence(home=home)
    assert barrier.word() == ""
    assert barrier.needed() is False
    # And nothing opens it, not even the empty string it holds.
    assert barrier.opens("") is False
    assert barrier.opens("plasmabox") is False


# -- the word itself ----------------------------------------------------------


def test_the_word_is_read_and_stripped(home):
    write(home, "  plasmabox \n")
    assert read_fence(home) == WORD


def test_only_the_first_line_is_the_word(home):
    """One line, the word. A second line is a note somebody left, not part
    of what has to be typed."""
    write(home, "plasmabox\nchanged 2026-09-07\n")
    assert read_fence(home) == WORD


def test_the_settings_home_override_is_honoured(home, monkeypatch):
    write(home, WORD)
    monkeypatch.setenv("CONTROLUNIT_SETTINGS_HOME", str(home))
    assert read_fence() == WORD


def test_a_machine_with_a_word_asks_for_it(home):
    write(home, WORD)
    barrier = Fence(home=home)
    assert barrier.needed() is True
    assert barrier.opens(WORD) is True
    assert barrier.opens("  plasmabox  ") is True
    assert barrier.opens("Plasmabox") is False
    assert barrier.opens("") is False
    assert barrier.opens(None) is False


# -- the cached reread --------------------------------------------------------


def test_an_unchanged_file_is_not_read_twice(home, monkeypatch):
    write(home, WORD)
    now = [0.0]
    barrier = Fence(home=home, clock=lambda: now[0])
    assert barrier.word() == WORD

    reads = []
    monkeypatch.setattr(
        fence_module, "read_fence", lambda home=None: reads.append(1) or ""
    )
    # Past the once-a-second bound, so it looks — and finds the same
    # (mtime, size) it had, which is the whole point of comparing them.
    now[0] = 60.0
    assert barrier.word() == WORD
    assert reads == []


def test_a_changed_file_is_read_again(home):
    write(home, WORD)
    now = [0.0]
    barrier = Fence(home=home, clock=lambda: now[0])
    assert barrier.word() == WORD

    path = write(home, "sputterhut")
    # A word changed twice in the same second still has to be noticed, so
    # the timestamp is moved deliberately rather than left to the clock.
    os.utime(path, ns=(10**9, 5 * 10**9))
    now[0] = 60.0
    assert barrier.word() == "sputterhut"


def test_the_file_is_not_looked_at_more_than_once_a_second(home):
    write(home, WORD)
    now = [0.0]
    barrier = Fence(home=home, clock=lambda: now[0])
    assert barrier.word() == WORD

    (home / "fence.txt").unlink()
    now[0] = 0.4  # inside the bound: the last answer stands
    assert barrier.word() == WORD
    now[0] = 2.0
    assert barrier.word() == ""
    assert barrier.needed() is False


def test_a_fence_put_up_later_is_picked_up(home):
    now = [0.0]
    barrier = Fence(home=home, clock=lambda: now[0])
    assert barrier.needed() is False

    write(home, WORD)
    now[0] = 2.0
    assert barrier.word() == WORD

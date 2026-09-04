"""One version number, in two places, held equal.

`controlunit/_version.py` is what the program shows in its tab bar and its
health report; `pyproject.toml` is what the fleet and a packaging tool read.
They move together or this fails.
"""

import re
from pathlib import Path

from controlunit._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_the_same_version_as_the_package():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml declares no version"
    assert match.group(1) == __version__


def test_the_major_number_names_the_lan_era():
    """Era 4 is the rig on the lab network (owner decision 2026-09-04)."""
    assert int(__version__.split(".")[0]) >= 4

"""What the rig's screen was set to, kept across a program restart.

A program restart on 2026-11-11 at 16:47:15 brought both ion gauges back at
Torr and 1e-3, settings.yml's defaults, and forgot that Pu2 had been
declared off: for 18 s Pd_c read 1.5e-3 Torr when the vessel was at about
1.5e-7. A fresh program also started at settings.yml's 0.1 s sampling
whatever the run before it had used (the 4.29.1 deployment, 2026-10-21:
"Started with sampling 0.1 s", then set to 10 s a second later). queezz,
2026-10-21: "it should remember settings, not run with whatever is default
and invisible." `_apply_screen_settings` already carries the screen into
every Start; this carries the screen across the restart itself.

Three things are kept, and nothing else: each ion gauge's mode and range,
and the sampling time the run used. Outputs are never kept here: gas, the
cathode drive, the PID and the supply's output start at zero and off after
a restart, as they always have.

Two more for each gauge, both optional, since the review of 2026-11-13:
`reading`, the mode a gauge declared off read in before (Torr or Pa), so
the Diagram turning it back on after a restart finds Pa where Pa was; and
`diagram`, the PIHTI Diagram's word the program last applied to it
(`active` or `inactive`). Without that the first answer after every launch
was a change from not knowing, and undid a gauge declared off by hand while
the Diagram still said on. A file without them is read as before, and a
program before them reads a file with them, passing the two over.

The file is this machine's, beside the roster and the lab's word, and never
in git: `~/.controlunit/screen.json` (or `$CONTROLUNIT_SETTINGS_HOME`)::

    {
      "schema": "controlunit-screen/v1",
      "sampling_s": 10.0,
      "gauges": {
        "Pd": {"mode": "Torr", "range": -7, "diagram": "active"},
        "Pu2": {"mode": "Off", "range": -3, "reading": "Pa",
                "diagram": "inactive"}
      }
    }

A missing file, an unreadable one, one that is not this schema's JSON, and
a value outside what the dock offers are all read as "nothing remembered"
for that value, so the program starts with settings.yml as it did before.
Nothing here raises: a remembered setting is a convenience, and a broken
one must never keep the window from opening.

Plain standard library, and nothing here imports PyQt.
"""

import json
import os
import tempfile
from pathlib import Path

from controlunit.web.commands import (
    GAUGE_MODES,
    GAUGE_OFF,
    GAUGE_RANGE_HIGH,
    GAUGE_RANGE_LOW,
    SAMPLING_CHOICES,
)
from controlunit.web.neighbours import settings_home

SCREEN_FILE = "screen.json"
SCHEMA = "controlunit-screen/v1"

#: The PIHTI Diagram's two words for an element, as `diagram_follower`
#: reads them (`ACTIVE`, `INACTIVE`; a test holds them equal). Written out
#: here so this module stays plain standard library.
DIAGRAM_WORDS = ("active", "inactive")


def screen_path(home=None):
    """Where this machine keeps what its screen was last set to."""
    return (settings_home() if home is None else Path(home)) / SCREEN_FILE


def _gauge_entry(entry):
    """One gauge's `{"mode", "range"}` as the dock offers it, or None, with
    `reading` and `diagram` beside them where the file has usable ones; an
    unusable one of those two is passed over alone."""
    if not isinstance(entry, dict):
        return None
    mode, decade = entry.get("mode"), entry.get("range")
    if mode not in GAUGE_MODES:
        return None
    # A JSON `true` is an int to Python; a range is a whole decade, not a flag.
    if isinstance(decade, bool) or not isinstance(decade, int):
        return None
    if not GAUGE_RANGE_LOW <= decade <= GAUGE_RANGE_HIGH:
        return None
    kept = {"mode": mode, "range": decade}
    reading = entry.get("reading")
    if reading in GAUGE_MODES and reading != GAUGE_OFF:
        kept["reading"] = reading
    if entry.get("diagram") in DIAGRAM_WORDS:
        kept["diagram"] = entry["diagram"]
    return kept


def _sampling(value):
    """One of the dock's own sampling times, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    for choice in SAMPLING_CHOICES:
        if abs(float(value) - choice) < 1e-9:
            return choice
    return None


def read_screen(home=None):
    """What the file remembers, as `(state, notes)`.

    `state` is None when nothing at all can be used, and `notes` then holds
    the one reason why. Otherwise `state` is `{"gauges": {name: {"mode",
    "range"[, "reading"][, "diagram"]}}, "sampling_s": seconds}` holding
    only the values the dock offers, `sampling_s` absent when it was not
    usable, and `notes` names
    whatever was passed over. Which gauges this rig has is the caller's to
    judge: the file may name one the settings no longer list.
    """
    path = screen_path(home)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, ["no file yet"]
    except (OSError, ValueError) as error:
        return None, ["unreadable: {}".format(type(error).__name__)]
    try:
        body = json.loads(text)
    except ValueError:
        return None, ["not JSON"]
    if not isinstance(body, dict) or body.get("schema") != SCHEMA:
        return None, ["not a {} file".format(SCHEMA)]

    notes = []
    state = {"gauges": {}}
    gauges = body.get("gauges")
    if not isinstance(gauges, dict):
        gauges = {}
        notes.append("gauges")
    for name, entry in gauges.items():
        kept = _gauge_entry(entry)
        if kept is None:
            notes.append(str(name))
        else:
            state["gauges"][str(name)] = kept
    if "sampling_s" in body:
        seconds = _sampling(body.get("sampling_s"))
        if seconds is None:
            notes.append("sampling")
        else:
            state["sampling_s"] = seconds
    return state, notes


def _document(state):
    """The bytes the file holds for `state`: the schema, then the values."""
    body = {"schema": SCHEMA}
    body.update(state)
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def write_screen(state, home=None):
    """Replace the file with `state`, in one step or not at all.

    Written to a temporary file in the same folder and moved over the old
    one with `os.replace`, as the roster's copy is: a program killed in the
    middle of a write leaves the whole old file or the whole new one, never
    half of either, so the next start reads one or the other. A file that
    already says exactly this is left alone.

    Returns True when the file on disk now holds `state`; never raises.
    """
    path = screen_path(home)
    wanted = _document(state)
    try:
        if path.read_text(encoding="utf-8") == wanted:
            return True
    except (OSError, ValueError):
        pass
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=".screen-", suffix=".json"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(wanted)
            os.replace(temporary, str(path))
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except Exception:
        return False
    return True


def describe(state):
    """The Log's words for what was restored: `Pd Torr 1e-7, Pu2 off,
    sampling 10 s`. A gauge declared off is just off; its range is kept and
    restored all the same, for when it is switched back on."""
    parts = []
    for name, entry in state.get("gauges", {}).items():
        if entry["mode"] == GAUGE_OFF:
            parts.append("{} off".format(name))
        else:
            parts.append("{} {} 1e{}".format(name, entry["mode"], entry["range"]))
    if "sampling_s" in state:
        parts.append("sampling {:g} s".format(state["sampling_s"]))
    return ", ".join(parts)

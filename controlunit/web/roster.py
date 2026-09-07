"""The lab's list of operator names, as this machine happens to hold it.

Asking each person to invent a name spells one person three ways across the
lab's logs. PIHTI Log already solved that: it reads a names-only roster kept
in the Obsidian vault on the office PC, `<vault>/People/operators.json`, and
mirrors it whenever the file changes. The Pi that serves this view has no
Dropbox and no vault, so it cannot read that file where it lives; it reads a
copy of the very same file from its own settings folder instead,
`~/.controlunit/operators.json`::

    {"schema": "pihti-operators/v1",
     "operators": [{"username": "hashizuka",
                    "display_name": "Hashizuka Takuma"}]}

The copy is made by hand — one `scp` from the office PC, written down in
`docs/architecture/web-ui.md`. That is on purpose for now: the roster is a
courtesy list so the log spells a colleague's name the same way twice, never
a credential and never a list of who may drive the rig.

Every failure means one thing here — this machine has no roster — and the
page falls back to the free-text field it has always had. A missing file, a
folder in its place, an unreadable one, bytes that are not JSON, JSON that is
not an object, a `schema` that is not `pihti-operators/v1`, an `operators`
that is not a list, and an entry with no `display_name` are all read as
nothing rather than as an error: nothing here may raise into a request.
"""

import json
import time
from pathlib import Path

from controlunit.web.neighbours import settings_home

ROSTER_FILE = "operators.json"
SCHEMA = "pihti-operators/v1"

#: How often the file on disk may be looked at. A page asking a stat call per
#: request is fine; a poll asking one per hundred milliseconds is not.
REREAD_SECONDS = 1.0


def roster_path(home=None):
    """Where this machine keeps its copy of the lab's roster."""
    return (settings_home() if home is None else Path(home)) / ROSTER_FILE


def read_roster(home=None):
    """The roster's entries, in file order, as `{username, display_name}`.

    An empty list is the answer to every kind of absence; see the module
    docstring for the list of them. This never raises.
    """
    try:
        text = roster_path(home).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    try:
        document = json.loads(text)
    except ValueError:
        return []
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        return []
    operators = document.get("operators")
    if not isinstance(operators, list):
        return []

    people = []
    for entry in operators:
        if not isinstance(entry, dict):
            continue
        display = str(entry.get("display_name") or "").strip()
        if not display:
            continue
        people.append(
            {
                "username": str(entry.get("username") or "").strip(),
                "display_name": display,
            }
        )
    return people


class Roster:
    """The names this machine knows, reread when the file underneath changes.

    The file is compared by `(mtime_ns, size)` rather than by its contents,
    so a roster that has not been recopied costs one `stat` and no parse;
    and it is not looked at more than once a second, so a page polling hard
    does not turn into a stat call per request.
    """

    def __init__(self, home=None, clock=time.monotonic):
        self._home = home
        self._clock = clock
        self._names = []
        self._stamp = None
        self._looked_at = None

    def _fingerprint(self):
        """What says the file has changed, or None when there is no file."""
        try:
            status = roster_path(self._home).stat()
        except OSError:
            return None
        return (status.st_mtime_ns, status.st_size)

    def names(self):
        """The display names, in file order; empty when there is no roster."""
        now = self._clock()
        if self._looked_at is not None and (now - self._looked_at) < REREAD_SECONDS:
            return list(self._names)
        self._looked_at = now
        stamp = self._fingerprint()
        if stamp != self._stamp:
            self._stamp = stamp
            self._names = [person["display_name"] for person in read_roster(self._home)]
        return list(self._names)

    def entries(self):
        """Every field the roster carries, read fresh. For a caller that
        wants the usernames; the page only ever needs the display names."""
        return read_roster(self._home)

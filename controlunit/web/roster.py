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

The copy refreshes itself over the LAN. PIHTI Log answers `GET /api/roster`
on the same origin this rig already asks `/api/health` of (its 0.38.0,
letter `20260907-2e0205ef-f3c730`), so whenever the neighbour probe finds
that service answering, `RosterMirror` fetches the roster behind it and
rewrites this machine's copy. `scripts/push_roster.ps1` stays as the
fallback for a machine that cannot reach the office PC, and is still what a
brand-new Pi needs once.

Three rules the mirror holds to. It never asks more often than the health
probe does, because it rides on that probe and starts nothing of its own.
It never writes a partial file: the copy is written beside itself and moved
into place in one step, so a reader either sees the old roster or the new
one. And it keeps the last copy whenever the answer is anything but a
complete roster — no answer, a 404 from a vault with no roster, a body that
is not a roster, an empty list — because a name the log has been spelling
correctly for a month should not disappear because the office PC is off.

The roster is a courtesy list so the log spells a colleague's name the same
way twice, never a credential and never a list of who may drive the rig.

Every failure means one thing here — this machine has no roster — and the
page falls back to the free-text field it has always had. A missing file, a
folder in its place, an unreadable one, bytes that are not JSON, JSON that is
not an object, a `schema` that is not `pihti-operators/v1`, an `operators`
that is not a list, and an entry with no `display_name` are all read as
nothing rather than as an error: nothing here may raise into a request.
"""

import json
import os
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from controlunit.web.neighbours import settings_home

ROSTER_FILE = "operators.json"
SCHEMA = "pihti-operators/v1"

#: How often the file on disk may be looked at. A page asking a stat call per
#: request is fine; a poll asking one per hundred milliseconds is not.
REREAD_SECONDS = 1.0

#: Where the lab's roster is served, on the neighbour that keeps it, and how
#: long this rig waits for it — the same path shape and the same patience the
#: health probe already uses, because it is the same service on the same LAN.
ROSTER_PATH = "/api/roster"
FETCH_TIMEOUT = 2.0

#: A roster of the whole lab is a few hundred bytes. Anything past this is
#: not the file this rig asked for and is not read.
MAX_BYTES = 256 * 1024


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


def labels(people):
    """One readable label per person, with no two the same.

    The lab has two colleagues whose display names are spelled identically,
    and the Acting-as list offered the same word twice: a person choosing
    the second one had no way to know which of them the log would name
    (PIHTI Log's Mac audit 2026-09-07, the same defect in the journal). A
    name that collides is written "Display Name (username)" — the username
    is the roster's own identity for that person and is exactly what tells
    them apart.

    Nothing is merged and nothing is renamed: a name nobody shares is
    untouched, the roster's entries keep their own fields, and where a
    colliding entry carries no username there is nothing to disambiguate
    with, so it is left as it stands rather than given an invented one.
    """
    seen = {}
    for person in people:
        display = person.get("display_name", "")
        seen[display] = seen.get(display, 0) + 1
    out = []
    for person in people:
        display = person.get("display_name", "")
        username = person.get("username", "")
        if seen.get(display, 0) > 1 and username:
            out.append("{} ({})".format(display, username))
        else:
            out.append(display)
    return out


def _people_from(document):
    """The entries a parsed roster document holds, or None if it holds none.

    `None` is "this is not a roster", and an empty list is "this document is
    a roster of nobody" — which the mirror treats the same way, because
    neither is a reason to throw away a copy that works.
    """
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        return None
    operators = document.get("operators")
    if not isinstance(operators, list):
        return None
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


def fetch_roster(url, timeout=FETCH_TIMEOUT, opener=None):
    """The roster one neighbour serves, or None for every kind of no answer.

    Every failure means the same thing to the caller — there is nothing new
    to write — so a 404 from a vault with no roster, a 503 from one that
    could not be read, a name that does not resolve, a two-second silence,
    bytes that are not JSON and a body that is not a roster all come back as
    `None`. Nothing here raises: this runs on the neighbour probe's own
    thread, behind a page that has already been answered.
    """
    target = str(url or "").rstrip("/") + ROSTER_PATH
    open_url = opener if opener is not None else urllib.request.urlopen
    try:
        with open_url(target, timeout=timeout) as response:
            payload = response.read(MAX_BYTES)
    except Exception:
        return None
    try:
        document = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    return _people_from(document)


def _document(people):
    """The bytes a copy of the roster is: the file this rig already reads."""
    body = {"schema": SCHEMA, "operators": list(people)}
    return json.dumps(body, ensure_ascii=False, indent=2) + "\n"


def write_copy(people, home=None):
    """Replace this machine's copy of the roster, in one step or not at all.

    The copy is written to a temporary file in the same folder and moved
    over the old one with `os.replace`, which is atomic on both platforms
    this program runs on: a reader — this program's own `Roster`, or a
    person with the file open — sees the whole old roster or the whole new
    one, never half of either. A copy that already says exactly this is left
    alone, so an unchanged roster costs no write and does not disturb the
    `(mtime, size)` fingerprint `Roster` watches.

    Returns True when the file on disk now holds this roster.
    """
    path = roster_path(home)
    wanted = _document(people)
    try:
        if path.read_text(encoding="utf-8") == wanted:
            return True
    except (OSError, ValueError):
        pass
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=".operators-", suffix=".json"
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


class RosterMirror:
    """This machine's copy of the lab's roster, kept up over the LAN.

    It owns no clock of its own and asks nobody on a timer: `refresh` is
    called by the neighbour probe, once per probe at most, for the one
    neighbour that serves a roster. So the rig asks the office PC for names
    exactly as often as it already asks it how it is, and not once more.

    What it reports afterwards is one line for the Control tab: when this
    copy was last confirmed against the service, and how many names it
    holds. `refreshed_at` stays `None` until the first successful fetch —
    "never asked" and "asked and nobody answered" are not the same fact, and
    neither is "the file on this machine is old".
    """

    def __init__(self, home=None, fetch=None, stamp=None, source="PIHTI Log"):
        self._home = home
        self._fetch = fetch if fetch is not None else fetch_roster
        self._stamp = stamp if stamp is not None else (lambda: time.strftime("%H:%M:%S"))
        self._source = source
        self._lock = threading.RLock()
        self._refreshed_at = None
        self._count = None

    def refresh(self, url):
        """Ask one neighbour for the roster and keep the answer, or keep what
        this machine already has. True when a fresh roster is on disk."""
        people = self._fetch(url)
        if not people:
            return False
        if not write_copy(people, self._home):
            return False
        with self._lock:
            self._refreshed_at = self._stamp()
            self._count = len(people)
        return True

    def report(self):
        """What the Control tab says in one line, or `None` for never."""
        with self._lock:
            if self._refreshed_at is None:
                return None
            return {
                "source": self._source,
                "at": self._refreshed_at,
                "names": self._count,
            }


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
        """The labels to offer, in file order; empty when there is no roster.

        A label is the display name, or the display name with the person's
        username beside it where two people in this roster are spelled the
        same; see `labels`.
        """
        now = self._clock()
        if self._looked_at is not None and (now - self._looked_at) < REREAD_SECONDS:
            return list(self._names)
        self._looked_at = now
        stamp = self._fingerprint()
        if stamp != self._stamp:
            self._stamp = stamp
            self._names = labels(read_roster(self._home))
        return list(self._names)

    def entries(self):
        """Every field the roster carries, read fresh. For a caller that
        wants the usernames; the page only ever needs the display names."""
        return read_roster(self._home)

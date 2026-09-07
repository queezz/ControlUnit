"""Ask the other two services how they are, from this machine's own side.

The browser never talks to a neighbour: it would have to open cross-origin
reads on all three services, and a neighbour's address would have to travel
into the page. Instead this server asks each neighbour itself, over a two
second timeout, and remembers the answer for ten seconds.

Asking happens beside the page, never in front of it. A request that had to
wait for the LAN waited two seconds per silent neighbour, plus however long a
`.local` name takes to fail to resolve, before the Lab tab appeared at all —
the page paying for a question the reader had not asked yet. So the board
answers from what it already knows and refreshes behind that answer: the
cached rows when there are any, however old, and otherwise rows in the state
`checking`, which says this machine is asking right now and has not heard
back. One probe runs at a time; a second caller arriving mid-probe is handed
the same rows and starts nothing. `checking` is a sixth state and not a
sixth kind of failure: a neighbour this machine has no address for is `not
configured` from the first paint, because that answer needs no one.

"Ask again now" on the page is `invalidate()` and nothing more: the cached
answer is dropped and the next read starts a probe behind `checking` rows,
so the press is answered in the same breath as any other read.

Addresses come only from a machine-local file the repository never carries,
`~/.controlunit/neighbours.yml`::

    pihti-diagram:
      url: http://pihti:5000
      open_url: http://pihti.local:5000
      where: on this Pi, as a system service
      start_how: on the Pi itself, as a system service
      start: sudo systemctl start pihti.service
    pihti-log:
      url: http://ak-office.local:4310
      where: on the office Windows PC
      start_how: from the office PC, as lab pihti-log
      start: lab pihti-log

`url` is required for a neighbour to be asked at all. `where`, `start_how`
and `start` are optional and say how *that* service is started on *the
machine it runs on*; a card with none of them says nothing about starting,
rather than guessing.

`open_url` is optional and exists because two different machines follow that
link. **`url` is the address this rig asks from; `open_url` is the address
the reader's browser opens.** They are usually the same and the field is
usually absent. They were not the same on 2026-09-07: the diagram's card said
`ok`, because the Pi resolves the bare name `pihti` on its own network, and
the Open link did nothing on the owner's Mac, which resolves `pihti.local`
and the numeric address but not the bare name (PIHTI Log's audit, letter
`20260907-023785d0`). A green chip is this machine's measurement and was
never a promise about the laptop reading the page, so where the two names
differ the file says both and the card opens the one a browser can use.

Starting is two facts and not one (owner decision 2026-09-07, relayed from
the diagram's 0.8.0): `start_how` is the plain words a reader understands
without a shell — "from the office PC, as lab pihti-log" — and `start` is
the literal line, which the card keeps behind a show/hide toggle. A file
that gives only `start` leaves `start_how` empty, and the card says so in
plain words of its own rather than putting a command where the meaning
belongs.

Why its own file, and not a block in `~/.controlunit/settings.yml`: the
program treats a local `settings.yml` as a complete replacement for the
packaged one, so a file holding only a neighbours block would stop the rig
from starting. The older `Neighbours:` block in `settings.yml` is still read
when `neighbours.yml` is absent, for a machine that already has one.
"""

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_SECONDS = 2.0
CACHE_SECONDS = 10.0
HEALTH_PATH = "/api/health"
NEIGHBOURS_FILE = "neighbours.yml"

#: The two neighbours, in the order the board shows them.
#:
#: The whole ensemble reads Diagram, PIHTI Log, ControlUnit on every one of
#: the three surfaces, so a person who learns the board on one machine knows
#: where to look on the next (owner direction 2026-09-07, from three
#: side-by-side screenshots: "they should be identical"). That order is not
#: "this service first": ControlUnit's own card stands third here, where it
#: stands on the other two.
NEIGHBOUR_ALIASES = ("pihti-diagram", "pihti-log")

DISPLAY_NAMES = {
    "controlunit": "ControlUnit",
    "pihti-log": "PIHTI Log",
    "pihti-diagram": "PIHTI diagram",
}

#: Six states, never conflated, and worded the same way in all three
#: surfaces of the ensemble (owner decision 2026-09-07, after the three had
#: drifted). `down` means something answered and the answer was bad — an
#: error status, or a refused connection, which is a machine that is there
#: with nothing listening on the port. `unreachable` means nothing answered
#: this machine at all: the wait ran out, or the name did not resolve.
#: `degraded` means the answer arrived and was not a health report. `not
#: configured` means this machine was never told where the service lives;
#: `checking` means this machine is asking now and has not heard back.
STATE_OK = "ok"
STATE_DEGRADED = "degraded"
STATE_DOWN = "down"
STATE_UNREACHABLE = "unreachable"
STATE_NOT_CONFIGURED = "not configured"
STATE_CHECKING = "checking"


def settings_home():
    """The directory holding this machine's own ControlUnit settings."""
    override = os.environ.get("CONTROLUNIT_SETTINGS_HOME")
    if override:
        return Path(override)
    return Path.home() / ".controlunit"


def _load_yaml(path):
    """The mapping a YAML file holds, or an empty one for any failure."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    try:
        data = yaml.safe_load(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _entries(block):
    """Normalise a neighbours mapping: alias -> {url, where, start_how, start}."""
    entries = {}
    if not isinstance(block, dict):
        return entries
    for alias, value in block.items():
        if isinstance(value, dict):
            url = value.get("url") or value.get("URL")
            open_url = value.get("open_url") or ""
            where = value.get("where") or ""
            start_how = value.get("start_how") or ""
            start = value.get("start") or ""
        else:
            url, open_url, where, start_how, start = value, "", "", "", ""
        if isinstance(url, str) and url.strip():
            probe = url.strip().rstrip("/")
            opens = str(open_url).strip().rstrip("/") or probe
            entries[str(alias).strip()] = {
                "url": probe,
                # Where a browser goes. The same address as the probe's
                # unless this machine was told they differ.
                "open_url": opens,
                "where": str(where).strip(),
                "start_how": str(start_how).strip(),
                "start": str(start).strip(),
            }
    return entries


def read_neighbours(home=None):
    """Map each neighbour alias to its entry, from local files only.

    A missing file, an unreadable one, or one with nothing usable all mean
    the same thing here: this machine has not been told, which the page shows
    as "not configured" rather than guessing.
    """
    path = Path(home) if home is not None else settings_home()
    entries = _entries(_load_yaml(path / NEIGHBOURS_FILE))
    if entries:
        return entries
    return _entries(_load_yaml(path / "settings.yml").get("Neighbours"))


def read_addresses(home=None):
    """Alias -> URL only; kept for callers that want nothing else."""
    return {alias: entry["url"] for alias, entry in read_neighbours(home).items()}


def _failure(error):
    """What a failed request means: (state, detail), told apart by why.

    A refused connection is not silence. Something on the other end answered
    the knock — the host is up, the port is closed — so it is `down`, beside
    an HTTP error status, and never `unreachable`. Nothing answering at all,
    whether because the wait ran out or because the name never resolved to an
    address to wait on, is `unreachable`.

    `urlopen` wraps most of these in a `URLError` carrying the real one as
    its `reason`, so the wrapper is unwrapped before it is read; a `URLError`
    whose reason is a plain string is nothing more specific than silence.

    The chip names the state and the rail explains it once, so each sentence
    here adds only the fact neither carries: which failure this was.
    """
    reason = getattr(error, "reason", None)
    if isinstance(reason, BaseException):
        error = reason
    if isinstance(error, ConnectionRefusedError):
        return STATE_DOWN, "refused the connection"
    if isinstance(error, socket.gaierror):
        return STATE_UNREACHABLE, "the name did not resolve"
    # A timeout — `socket.timeout`, which is `TimeoutError` — and anything
    # else that left this machine with nothing: it waited its two seconds.
    return STATE_UNREACHABLE, "no answer within two seconds"


def _read_health(url, timeout=TIMEOUT_SECONDS):
    """Fetch one neighbour's health report. Returns (state, version, detail)."""
    target = url.rstrip("/") + HEALTH_PATH
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            payload = response.read(64 * 1024)
    except urllib.error.HTTPError as error:
        # It answered; it just answered badly. That is not unreachable.
        return (
            STATE_DOWN,
            "",
            "answered with an error, code {}".format(getattr(error, "code", "?")),
        )
    except Exception as error:
        state, detail = _failure(error)
        return state, "", detail

    try:
        report = json.loads(payload.decode("utf-8"))
    except Exception:
        report = None
    if not isinstance(report, dict):
        return STATE_DEGRADED, "", "answered, but not with a health report"

    reported = str(report.get("status") or "").strip().lower()
    version = str(report.get("version") or "")
    detail = str(report.get("detail") or "")
    if reported in (STATE_OK, STATE_DEGRADED, STATE_DOWN):
        return reported, version, detail
    return STATE_DEGRADED, version, detail or "answered, but not with a health report"


def open_label(url):
    """The host and port an Open link goes to, without the scheme.

    The card shows it because a state chip and a link answer for two
    different machines: the chip is what this rig reached, the link is what
    the reader's browser will try. When those are different names — the rig
    knows `pihti`, a Mac knows `pihti.local` — the reader can see which one
    is about to be opened instead of finding out by a page that never loads.
    """
    text = str(url or "").strip()
    if not text:
        return ""
    without_scheme = text.split("://", 1)[-1]
    return without_scheme.rstrip("/")


def _row(alias, entry, state, version="", detail=""):
    """One card's worth of facts. The local file's part of it is known
    without asking anyone, so it is filled in whatever the state."""
    return {
        "alias": alias,
        "name": DISPLAY_NAMES.get(alias, alias),
        # What the Open link points at, which is the reader's browser's
        # business and not this machine's. `probe_url` is what the chip's
        # state was measured against.
        "url": entry.get("open_url") or entry.get("url", ""),
        "probe_url": entry.get("url", ""),
        "opens_at": open_label(entry.get("open_url") or entry.get("url", "")),
        "state": state,
        "version": version,
        "detail": detail,
        "where": entry.get("where", ""),
        # Two facts about starting, never one: the plain words, and the
        # literal line the card keeps behind its toggle. Both keys are on
        # every row, whatever the local file happened to say.
        "start_how": entry.get("start_how", ""),
        "start": entry.get("start", ""),
    }


def _wall_stamp():
    """This machine's own clock, to the second. The rig's clock, on the rig.

    The cache is timed on a monotonic clock, which is the right one for
    "how old is this" and the wrong one for "when was that": a reader wants
    the time their own watch would have shown.
    """
    return time.strftime("%H:%M:%S")


class NeighbourBoard:
    """The two neighbours' states, answered now and refreshed behind the answer.

    `neighbours()` never waits on the network. It hands back the rows it has
    — the cache when it is warm, the cache when it is stale, `checking` rows
    when there is no cache at all — and starts one background probe whenever
    what it handed back was not fresh. `wait()` is the seam a test or a
    script uses to stand still until that probe has finished.
    """

    def __init__(
        self,
        cache_seconds=CACHE_SECONDS,
        home=None,
        clock=time.monotonic,
        prober=None,
        stamp=None,
    ):
        self._cache_seconds = cache_seconds
        self._home = home
        self._clock = clock
        #: What a reader's watch says, for the one line that reports a time
        #: rather than an age. Injectable for the same reason `clock` is.
        self._stamp = stamp if stamp is not None else _wall_stamp
        #: What one refresh does. Injectable so a test can make it slow, or
        #: count it, without a real neighbour and without a real wait.
        self._prober = prober if prober is not None else self._probe_all
        self._lock = threading.RLock()
        self._cached = None
        self._cached_at = None
        self._checked_at = None
        self._probing = False
        self._thread = None

    def addresses(self):
        return read_addresses(self._home)

    def entries(self):
        return read_neighbours(self._home)

    def _probe_all(self):
        entries = self.entries()
        rows = []
        for alias in NEIGHBOUR_ALIASES:
            entry = entries.get(alias) or {}
            if not entry.get("url"):
                # The chip states it and the rail legend explains it once;
                # there is nothing further to say here.
                rows.append(_row(alias, entry, STATE_NOT_CONFIGURED))
                continue
            state, version, detail = _read_health(entry["url"])
            rows.append(_row(alias, entry, state, version, detail))
        return rows

    def _checking_rows(self):
        """What to show while the first answer is still on its way.

        A neighbour with an address is `checking`, because this machine is
        asking it right now. A neighbour with no address is `not configured`
        from the first paint: nobody is being asked about it, and saying
        `checking` would promise an answer that is never coming.
        """
        entries = self.entries()
        rows = []
        for alias in NEIGHBOUR_ALIASES:
            entry = entries.get(alias) or {}
            state = STATE_CHECKING if entry.get("url") else STATE_NOT_CONFIGURED
            rows.append(_row(alias, entry, state))
        return rows

    def _start_probe(self):
        """Begin one refresh, unless one is already running. Lock held."""
        if self._probing:
            return
        self._probing = True
        self._thread = threading.Thread(
            target=self._run_probe, name="neighbour-probe", daemon=True
        )
        self._thread.start()

    def _run_probe(self):
        try:
            rows = self._prober()
        except Exception:
            # A probe that fell over leaves the last answer standing: the
            # reader is told nothing new rather than told something false.
            rows = None
        with self._lock:
            if rows is not None:
                self._cached = rows
                self._cached_at = self._clock()
                self._checked_at = self._stamp()
            self._probing = False

    def wait(self, timeout=None):
        """Block until the probe in flight has finished; True if none is left.

        The page never calls this. It exists so a test can drive the refresh
        deterministically instead of sleeping, and so a script can ask for
        one settled answer.
        """
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
        with self._lock:
            return not self._probing

    def checked_at(self):
        """When the last probe finished, on this machine's clock, or None.

        `None` means no probe has ever finished here — nothing has been
        checked yet — and is not the same as an old time.
        """
        with self._lock:
            return self._checked_at

    def invalidate(self):
        """Throw the cached answer away, so the next read asks the LAN again.

        What is dropped is the answer, not the record of when the last one
        landed: `checked_at()` still says when this machine last heard back
        while every row says `checking`. Two facts about two different
        things, and neither is allowed to stand in for the other.

        Nothing is started here. The probe begins on the next `neighbours()`,
        which is the same call the page makes anyway, so a reader pressing
        "Ask again now" is answered at once with `checking` rather than held
        while the LAN is asked.
        """
        with self._lock:
            self._cached = None
            self._cached_at = None

    def neighbours(self):
        """The two neighbours, answered from what this machine already knows."""
        now = self._clock()
        with self._lock:
            cached = self._cached
            fresh = (
                cached is not None
                and self._cached_at is not None
                and (now - self._cached_at) < self._cache_seconds
            )
            if not fresh:
                self._start_probe()
            if cached is not None:
                return [dict(row) for row in cached]
        return self._checking_rows()

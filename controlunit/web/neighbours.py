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

Addresses come only from a machine-local file the repository never carries,
`~/.controlunit/neighbours.yml`::

    pihti-diagram:
      url: http://pihti:5000
      where: on this Pi, as a system service
      start: sudo systemctl start pihti.service
    pihti-log:
      url: http://ak-office.local:4310
      where: on the office Windows PC
      start: lab pihti-log

`url` is required for a neighbour to be asked at all. `where` and `start`
are optional and say how *that* service is started on *the machine it runs
on*; a card with neither says nothing about starting, rather than guessing.

Why its own file, and not a block in `~/.controlunit/settings.yml`: the
program treats a local `settings.yml` as a complete replacement for the
packaged one, so a file holding only a neighbours block would stop the rig
from starting. The older `Neighbours:` block in `settings.yml` is still read
when `neighbours.yml` is absent, for a machine that already has one.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_SECONDS = 2.0
CACHE_SECONDS = 10.0
HEALTH_PATH = "/api/health"
NEIGHBOURS_FILE = "neighbours.yml"

#: The ensemble, in the order the page shows it: this service, then the two
#: it stands beside.
NEIGHBOUR_ALIASES = ("pihti-log", "pihti-diagram")

DISPLAY_NAMES = {
    "controlunit": "ControlUnit",
    "pihti-log": "PIHTI Log",
    "pihti-diagram": "PIHTI diagram",
}

#: Six states, never conflated. `down` means a service answered and said so;
#: `unreachable` means nothing answered from this machine at all; `not
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
    """Normalise a neighbours mapping: alias -> {url, where, start}."""
    entries = {}
    if not isinstance(block, dict):
        return entries
    for alias, value in block.items():
        if isinstance(value, dict):
            url = value.get("url") or value.get("URL")
            where = value.get("where") or ""
            start = value.get("start") or ""
        else:
            url, where, start = value, "", ""
        if isinstance(url, str) and url.strip():
            entries[str(alias).strip()] = {
                "url": url.strip().rstrip("/"),
                "where": str(where).strip(),
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
    except Exception:
        # The chip already names the state and the rail legend explains it
        # once; this sentence only adds the fact neither carries — how long
        # this machine waited.
        return STATE_UNREACHABLE, "", "no answer within two seconds"

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


def _row(alias, entry, state, version="", detail=""):
    """One card's worth of facts. The local file's part of it is known
    without asking anyone, so it is filled in whatever the state."""
    return {
        "alias": alias,
        "name": DISPLAY_NAMES.get(alias, alias),
        "url": entry.get("url", ""),
        "state": state,
        "version": version,
        "detail": detail,
        "where": entry.get("where", ""),
        "start": entry.get("start", ""),
    }


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
    ):
        self._cache_seconds = cache_seconds
        self._home = home
        self._clock = clock
        #: What one refresh does. Injectable so a test can make it slow, or
        #: count it, without a real neighbour and without a real wait.
        self._prober = prober if prober is not None else self._probe_all
        self._lock = threading.RLock()
        self._cached = None
        self._cached_at = None
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

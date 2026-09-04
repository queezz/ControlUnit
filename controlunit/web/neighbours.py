"""Ask the other two services how they are, from this machine's own side.

The browser never talks to a neighbour: it would have to open cross-origin
reads on all three services, and a neighbour's address would have to travel
into the page. Instead this server asks each neighbour itself, over a two
second timeout, and remembers the answer for ten seconds.

Addresses come only from the machine-local file `~/.controlunit/settings.yml`,
which the repository never carries. Nothing about the lab's topology lives in
the portable source.
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

#: The ensemble, in the order the page shows it: this service, then the two
#: it stands beside. The alias is also the `lab` name used to start each one.
NEIGHBOUR_ALIASES = ("pihti-log", "pihti-diagram")

DISPLAY_NAMES = {
    "controlunit": "ControlUnit",
    "pihti-log": "PIHTI Log",
    "pihti-diagram": "PIHTI diagram",
}

#: Five states, never conflated. `down` means a service answered and said so;
#: `unreachable` means nothing answered from this machine at all; `not
#: configured` means this machine was never told where the service lives.
STATE_OK = "ok"
STATE_DEGRADED = "degraded"
STATE_DOWN = "down"
STATE_UNREACHABLE = "unreachable"
STATE_NOT_CONFIGURED = "not configured"


def settings_home():
    """The directory holding this machine's own ControlUnit settings."""
    override = os.environ.get("CONTROLUNIT_SETTINGS_HOME")
    if override:
        return Path(override)
    return Path.home() / ".controlunit"


def read_addresses(home=None):
    """Map each neighbour alias to its address, from local settings only.

    A missing file, an unreadable one, or a file with no `Neighbours:` block
    all mean the same thing here: this machine has not been told, which the
    page shows as "not configured" rather than guessing.
    """
    path = Path(home) if home is not None else settings_home()
    try:
        text = (path / "settings.yml").read_text(encoding="utf-8")
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
    if not isinstance(data, dict):
        return {}
    block = data.get("Neighbours")
    if not isinstance(block, dict):
        return {}

    addresses = {}
    for alias, value in block.items():
        if isinstance(value, dict):
            url = value.get("url") or value.get("URL")
        else:
            url = value
        if isinstance(url, str) and url.strip():
            addresses[str(alias).strip()] = url.strip().rstrip("/")
    return addresses


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


class NeighbourBoard:
    """The three services' states, refreshed no more than once every ten seconds."""

    def __init__(self, cache_seconds=CACHE_SECONDS, home=None, clock=time.monotonic):
        self._cache_seconds = cache_seconds
        self._home = home
        self._clock = clock
        self._lock = threading.RLock()
        self._cached = None
        self._cached_at = None

    def addresses(self):
        return read_addresses(self._home)

    def _probe_all(self):
        addresses = self.addresses()
        rows = []
        for alias in NEIGHBOUR_ALIASES:
            url = addresses.get(alias, "")
            if not url:
                rows.append(
                    {
                        "alias": alias,
                        "name": DISPLAY_NAMES.get(alias, alias),
                        "url": "",
                        "state": STATE_NOT_CONFIGURED,
                        "version": "",
                        # The chip states it and the rail legend explains it
                        # once; there is nothing further to say here.
                        "detail": "",
                    }
                )
                continue
            state, version, detail = _read_health(url)
            rows.append(
                {
                    "alias": alias,
                    "name": DISPLAY_NAMES.get(alias, alias),
                    "url": url,
                    "state": state,
                    "version": version,
                    "detail": detail,
                }
            )
        return rows

    def neighbours(self):
        """The two neighbours, from the cache when it is still warm."""
        now = self._clock()
        with self._lock:
            fresh = (
                self._cached is not None
                and self._cached_at is not None
                and (now - self._cached_at) < self._cache_seconds
            )
            if fresh:
                return [dict(row) for row in self._cached]
        rows = self._probe_all()
        with self._lock:
            self._cached = rows
            self._cached_at = self._clock()
        return [dict(row) for row in rows]

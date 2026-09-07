"""What the web thread is allowed to know about the running rig.

The Qt main thread owns every worker; this module owns nothing but a few
plain values behind a lock. Nothing here imports PyQt, and nothing here
reaches for a worker, a device or a file. The main thread writes; the web
thread reads a copy.

Slice two adds three things the Live and Log tabs read: the latest converted
value of every channel, a bounded ring of recent samples for the strip
charts, and the tail of the message log. All three are written from the
main thread's existing step and log methods and cost a few list appends per
call, so the acquisition loop is not slowed by a browser being open.

Slice three adds three more, for the Control tab: whether the Remote switch
on the rig's own screen is on, the baseline zeros the display subtracts, and
what became of the last command a browser sent. The browser learns what
happened from the next reading of this record, never by assuming its own
request succeeded.
"""

import collections
import sys
import threading
import time

from controlunit.web.commands import NOBODY

# The dummy stubs are imported under either name depending on how the
# package was entered, so both spellings count as "the stubs are loaded".
_DUMMY_MODULES = ("devices.dummy", "controlunit.devices.dummy")

SERVICE = "controlunit"

#: How much of the run the browser can look back over. The CSV on disk is
#: the record; this ring only feeds the live window.
KEEP_SECONDS = 2 * 60 * 60

#: A hard cap on the ring however fast the rig samples, so a mis-set sampling
#: time cannot grow memory without bound. Two hours at 10 Hz is 72 000.
MAX_SAMPLES = 200_000

#: How many message-log lines the Log tab can read back.
LOG_LINES = 1000

#: The most points a series answer carries per channel. The Live tab fills
#: its own history from the ring once, when the page opens, and asks only
#: for what is newer after that; three thousand carries the whole ring at
#: full resolution in that one fill, because two hours at the rig's 0.1 Hz
#: is 720 samples. A larger cap costs nothing on the poll that follows,
#: which asks `since` and is answered with the handful of new rows.
MAX_POINTS = 3000

#: The channels whose baseline the screen, the plots and the web subtract.
#: The CSV on disk is never adjusted; a zero is a way of reading, not data.
ZERO_CHANNELS = ("Ip", "Bu", "Bd")

DATA_LIVE = "live"
DATA_STALE = "stale"
DATA_IDLE = "idle"


def dummy_hardware_loaded():
    """True when the off-rig stubs stand in for the real boards."""
    return any(name in sys.modules for name in _DUMMY_MODULES)


class RigStatus:
    """A small locked record of what the rig is doing right now."""

    def __init__(
        self,
        channels=0,
        sampling=None,
        names=(),
        units=None,
        keep_seconds=KEEP_SECONDS,
        clock=time.time,
    ):
        self._lock = threading.RLock()
        self._clock = clock
        self._acquiring = False
        self._channels = int(channels or 0)
        self._sampling = sampling
        self._names = list(names)
        self._units = dict(units or {})
        self._keep_seconds = float(keep_seconds)

        self._latest = {}
        self._last_sample_at = None
        self._samples = 0
        self._file = ""
        self._started_at = None

        # The ring: parallel deques so a window can be cut by time by walking
        # the times alone, backwards from the newest.
        self._times = collections.deque(maxlen=MAX_SAMPLES)
        self._rows = collections.deque(maxlen=MAX_SAMPLES)

        self._setpoints = {
            "mfc1_v": 0.0,
            "mfc2_v": 0.0,
            "plasma_a": 0.0,
            "ig_mode": None,
            "ig_range": None,
            "sync": False,
        }

        self._log = collections.deque(maxlen=LOG_LINES)
        self._log_seq = 0

        # Browser control: the switch on the rig's screen, the baselines the
        # display subtracts, and the fate of the last command sent.
        self._remote = False
        self._zeros = {name: 0.0 for name in ZERO_CHANNELS}
        self._last_command = None

    # -- what the main thread writes -----------------------------------------

    def describe_run(self, channels, sampling, names=None, units=None):
        """Record the channel count and sampling time the config declares."""
        with self._lock:
            self._channels = int(channels or 0)
            self._sampling = sampling
            if names is not None:
                self._names = list(names)
            if units is not None:
                self._units = dict(units)

    def set_acquiring(self, running):
        """Record whether the acquisition threads are running."""
        with self._lock:
            self._acquiring = bool(running)
            if not self._acquiring:
                self._last_sample_at = None

    def start_run(self, file_name):
        """A new data file has been opened: a new run starts, the ring empties."""
        with self._lock:
            self._file = str(file_name or "")
            self._started_at = self._clock()
            self._samples = 0
            self._times.clear()
            self._rows.clear()
            self._latest = {}
            self._last_sample_at = None

    def record_samples(self, times, values):
        """Append samples the ADC step delivered.

        `times` is a sequence of epoch seconds; `values` maps a channel name
        to a sequence of the same length holding converted values, already
        adjusted the way the rig's own screen shows them.
        """
        times = [float(t) for t in times]
        if not times:
            return
        columns = {name: list(column) for name, column in values.items()}
        with self._lock:
            for index, stamp in enumerate(times):
                row = {}
                for name, column in columns.items():
                    try:
                        row[name] = float(column[index])
                    except (TypeError, ValueError, IndexError):
                        row[name] = None
                self._times.append(stamp)
                self._rows.append(row)
            self._samples += len(times)
            self._latest = dict(self._rows[-1])
            self._last_sample_at = self._clock()
            self._trim()

    def _trim(self):
        """Drop what is older than the window the ring promises to keep."""
        if not self._times:
            return
        oldest_kept = self._times[-1] - self._keep_seconds
        while self._times and self._times[0] < oldest_kept:
            self._times.popleft()
            self._rows.popleft()

    def record_setpoints(self, **setpoints):
        """Record the setpoints the rig currently holds, by name."""
        with self._lock:
            for key, value in setpoints.items():
                if key in self._setpoints:
                    self._setpoints[key] = value

    def set_remote(self, on):
        """Record the Remote switch on the rig's own screen."""
        with self._lock:
            self._remote = bool(on)

    def record_zeros(self, zeros):
        """Record the baselines the display and the web view subtract."""
        with self._lock:
            for name in ZERO_CHANNELS:
                if name in (zeros or {}):
                    try:
                        self._zeros[name] = float(zeros[name])
                    except (TypeError, ValueError):
                        self._zeros[name] = 0.0

    def record_command(self, record):
        """Keep what became of the last command a browser sent."""
        with self._lock:
            self._last_command = dict(record or {})

    def log(self, text, stamp=None):
        """Keep one message-log line, tags already stripped."""
        with self._lock:
            self._log_seq += 1
            self._log.append(
                {
                    "seq": self._log_seq,
                    "time": str(stamp or ""),
                    "text": str(text or ""),
                }
            )

    # -- what the web thread reads -------------------------------------------

    def read(self):
        """A snapshot the web thread may keep and use without the lock."""
        with self._lock:
            now = self._clock()
            age = None
            if self._last_sample_at is not None:
                age = max(0.0, now - self._last_sample_at)
            return {
                "acquiring": self._acquiring,
                "channels": self._channels,
                "sampling": self._sampling,
                "dummy": dummy_hardware_loaded(),
                "names": list(self._names),
                "units": dict(self._units),
                "values": dict(self._latest),
                "setpoints": dict(self._setpoints),
                "remote": self._remote,
                "zeros": dict(self._zeros),
                "last_command": dict(self._last_command) if self._last_command else None,
                "file": self._file,
                "started_at": self._started_at,
                "samples": self._samples,
                "held_seconds": self._keep_seconds,
                "age": age,
                "now": now,
            }

    def series(
        self, window_seconds=0, max_points=MAX_POINTS, names=None, since=None
    ):
        """Thinned `[t, v]` pairs per channel, by window or by `since`.

        A window of zero or less means everything the ring holds. Thinning
        keeps every `skip`-th point plus the last one, the same arithmetic the
        Qt graph uses, so a two hour window costs the same as a short one.

        A real window is cut by walking the ring backwards from the newest
        sample and stopping at the first one that falls outside it, so twenty
        seconds costs two hundred rows however long the ring has grown. The
        Live tab may ask four times a second while someone zeroes a gauge at
        the rig, and the Pi should not pay for two hours of samples to answer
        a question about the last twenty. `Full` still copies everything,
        because everything is what it asked for.

        `since` is the same walk against a stamp rather than a span: only
        samples strictly newer than it come back, the walk stopping at the
        first stamp that is not. It is what the Live tab asks on every poll
        once it holds a history of its own, so a browser that has been open
        an hour costs the Pi the few rows that arrived since it last asked
        rather than the hour it already has. Nothing newer is an empty
        answer, not an error. `since` wins over `window_seconds`.
        """
        with self._lock:
            if not self._times:
                return {"from": None, "to": None, "count": 0, "channels": {}}
            if since is not None:
                mark = float(since)
                times = []
                rows = []
                walk = zip(reversed(self._times), reversed(self._rows))
                for stamp, row in walk:
                    if stamp <= mark:
                        break
                    times.append(stamp)
                    rows.append(row)
                times.reverse()
                rows.reverse()
                if not times:
                    return {
                        "from": None,
                        "to": None,
                        "count": 0,
                        "channels": {},
                    }
            elif window_seconds and window_seconds > 0:
                cutoff = self._times[-1] - float(window_seconds)
                times = []
                rows = []
                for stamp, row in zip(reversed(self._times), reversed(self._rows)):
                    if stamp < cutoff:
                        break
                    times.append(stamp)
                    rows.append(row)
                times.reverse()
                rows.reverse()
            else:
                times = list(self._times)
                rows = list(self._rows)
            # A row is never written again once it is in the ring, so the rest
            # of this can be done without holding the lock.
            wanted = list(names) if names else list(self._names or rows[-1].keys())
        count = len(times)
        skip = 1
        if max_points and count > max_points:
            skip = -(-count // int(max_points))
        picked = list(range(0, count, skip))
        if picked and picked[-1] != count - 1:
            picked.append(count - 1)
        channels = {}
        for name in wanted:
            channels[name] = [
                [times[i], rows[i].get(name)] for i in picked if name in rows[i]
            ]
        return {"from": times[0], "to": times[-1], "count": count, "channels": channels}

    def log_since(self, seq=0):
        """Every kept log line after sequence number `seq`, oldest first."""
        with self._lock:
            lines = [dict(line) for line in self._log if line["seq"] > int(seq or 0)]
            last = self._log_seq
            held = len(self._log)
        return {"lines": lines, "last": last, "held": held}


# -- derived facts ------------------------------------------------------------


def _rate_phrase(sampling):
    """'10 Hz' from a 0.1 s sampling time; empty when nothing is known."""
    try:
        seconds = float(sampling)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    hertz = 1.0 / seconds
    if abs(hertz - round(hertz)) < 1e-9:
        return "{:d} Hz".format(int(round(hertz)))
    return "{:.3g} Hz".format(hertz)


def stale_after(sampling):
    """Seconds without a sample after which live data is called stale.

    The ADC hands the main thread a few samples at a time, so a single
    sampling period is too tight a bound; five periods, and never less than
    two seconds, is the line between a hiccup and a stall.
    """
    try:
        seconds = float(sampling)
    except (TypeError, ValueError):
        seconds = 0.0
    return max(2.0, 5.0 * seconds) if seconds > 0 else 2.0


def data_state(snapshot):
    """One of `live`, `stale`, `idle` for the snapshot's freshness."""
    if not snapshot.get("acquiring"):
        return DATA_IDLE
    age = snapshot.get("age")
    if age is None:
        return DATA_STALE
    if age > stale_after(snapshot.get("sampling")):
        return DATA_STALE
    return DATA_LIVE


def health_detail(snapshot):
    """One short sentence a lab person can read, or an empty string."""
    channels = snapshot.get("channels") or 0
    rate = _rate_phrase(snapshot.get("sampling"))
    hardware = "dummy hardware" if snapshot.get("dummy") else "real hardware"
    if not snapshot.get("acquiring"):
        return "idle, {}".format(hardware)
    if channels and rate:
        acquiring = "acquiring {:d} channels at {}".format(channels, rate)
    elif channels:
        acquiring = "acquiring {:d} channels".format(channels)
    else:
        acquiring = "acquiring"
    parts = [acquiring]
    setpoints = snapshot.get("setpoints") or {}
    if setpoints.get("plasma_a"):
        parts.append("plasma PID on")
    if snapshot.get("dummy"):
        parts.append("dummy hardware")
    return ", ".join(parts)


def health_body(status, version):
    """The health report, exactly the shape the ensemble agreed on."""
    snapshot = status.read()
    healthy = bool(snapshot.get("acquiring")) and not snapshot.get("dummy")
    return {
        "service": SERVICE,
        "version": version,
        "status": "ok" if healthy else "degraded",
        "detail": health_detail(snapshot),
    }


#: What `/api/state` carries when nobody has taken control, and what it
#: carries for a run with no command queue at all. The sentence comes from
#: the command desk so that the page and a refusal cannot word it differently.
NO_CONTROL = {
    "holder": "",
    "origin": "",
    "since": None,
    "mine": False,
    "line": NOBODY,
}


def state_body(status, version, control=None):
    """What every tab polls once a second: values, run facts, freshness.

    `control` is who holds the operator lock, read from the command queue by
    the caller rather than kept here: the lock is decided in the web thread,
    and a second copy in this record could only ever go stale.
    """
    snapshot = status.read()
    units = snapshot.get("units") or {}
    values = snapshot.get("values") or {}
    channels = []
    for name in snapshot.get("names") or sorted(values):
        channels.append(
            {
                "name": name,
                "value": values.get(name),
                "unit": units.get(name, ""),
            }
        )
    started = snapshot.get("started_at")
    elapsed = None
    if started is not None:
        elapsed = max(0.0, snapshot["now"] - started)
    return {
        "service": SERVICE,
        "version": version,
        "acquiring": bool(snapshot.get("acquiring")),
        "dummy": bool(snapshot.get("dummy")),
        "data": {
            "state": data_state(snapshot),
            "age": snapshot.get("age"),
            "stale_after": stale_after(snapshot.get("sampling")),
        },
        "run": {
            "file": snapshot.get("file") or "",
            "started_at": started,
            "elapsed": elapsed,
            "samples": snapshot.get("samples") or 0,
            "rate": _rate_phrase(snapshot.get("sampling")),
            "sampling": snapshot.get("sampling"),
            "held_seconds": snapshot.get("held_seconds"),
        },
        "setpoints": snapshot.get("setpoints") or {},
        # Browser control: whether the rig's own switch allows it, the
        # baselines the readings above already have subtracted, and what
        # became of the last command sent. The page reads its answer here.
        "remote": bool(snapshot.get("remote")),
        "zeros": snapshot.get("zeros") or {},
        "last_command": snapshot.get("last_command"),
        # Who holds control of the rig from a browser, whether that is the
        # browser asking, and the one sentence both the page and a refusal
        # say it in. The holder's address is the deliberate exception to "no
        # response carries an address": naming the other person is the point.
        "control": dict(control) if control else dict(NO_CONTROL),
        "channels": channels,
    }

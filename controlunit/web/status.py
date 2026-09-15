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
import datetime
import math
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

#: Series this rig does not sample itself. The cathode supply is read over
#: the LAN by a sidecar recorder on its own clock, at about 2 Hz, and its
#: rows are stamped by that recorder — so these live beside the ADC ring in
#: their own time base rather than being squeezed into the ADC's one time
#: list. `Ic` is the filament current the Plasma current panel draws beside
#: `Ip` (owner ask 2026-09-15: "so it'll be obvious when plasma is on… is it
#: the Hall sensor drifting or the plasma died"); `Uc` is recorded beside it
#: and drawn nowhere yet.
#:
#: They are never counted as ADC samples: the run's sample count, its
#: cadence and the freshness clock are all written by `record_samples` and
#: nothing here touches them.
SIDECAR_SERIES = ("Ic", "Uc")

#: The cathode supply's own colour, written once for every surface that
#: wears it: the two readout cards and their folded entries, the Cathode
#: control card's edge, the `Ic` curve and its own right-hand axis, and the
#: Qt window's value browser (queezz, 2026-09-15: "cathode display digits,
#: cathode curves, and cathode control card should share the color").
#:
#: It lives here because this is the one module the Qt main thread and the
#: Flask thread both import and which imports neither PyQt nor Flask. The
#: stylesheet carries the same value once, as `--cathode-pen`; a test holds
#: the two equal.
CATHODE_PEN = "#ff6b35"


def sidecar_epoch(text):
    """Epoch seconds from a sidecar row's own ISO timestamp, or `None`.

    The Kikusui recorder stamps every row with its local receipt time and a
    UTC offset (`datetime.now().astimezone().isoformat()`), so the stamp a
    point is plotted at is the moment the supply answered rather than the
    moment the GUI happened to look at the snapshot 500 ms later.
    """
    if isinstance(text, (int, float)):
        return float(text) if math.isfinite(float(text)) else None
    try:
        moment = datetime.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.timestamp()


def _cut(times, values, newest, window_seconds, since):
    """One time base's tail: by `since` if given, else by a window.

    The walk is backwards from the newest entry and stops at the first one
    outside the question, so twenty seconds costs twenty seconds' worth of
    rows however long the ring has grown. `newest` is the reference the
    window is measured back from — shared between the time bases, so one
    window means one span of wall clock on all of them.
    """
    if not times:
        return [], []
    if since is not None:
        mark = float(since)
        kept = 0
        for stamp in reversed(times):
            if stamp <= mark:
                break
            kept += 1
    elif window_seconds and window_seconds > 0:
        cutoff = float(newest) - float(window_seconds)
        kept = 0
        for stamp in reversed(times):
            if stamp < cutoff:
                break
            kept += 1
    else:
        return list(times), list(values)
    if not kept:
        return [], []
    return list(times[len(times) - kept:]), list(values[len(values) - kept:])


def _thin(count, max_points):
    """Which indices of a `count`-long run to answer with: every `skip`-th
    one plus the last, the same arithmetic the Qt graph uses."""
    skip = 1
    if max_points and count > max_points:
        skip = -(-count // int(max_points))
    picked = list(range(0, count, skip))
    if picked and picked[-1] != count - 1:
        picked.append(count - 1)
    return picked

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
        gauges=(),
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
        self._gauges = list(gauges)
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

        # A second, smaller ring for the series the rig does not sample
        # itself. Each carries its own times, because the sidecar recorder
        # keeps its own clock and its own cadence: one time list for every
        # channel was only ever true while every channel came from one ADC
        # step. `series()` answers these by name like any other.
        self._side = {
            name: (
                collections.deque(maxlen=MAX_SAMPLES),
                collections.deque(maxlen=MAX_SAMPLES),
            )
            for name in SIDECAR_SERIES
        }

        self._setpoints = {
            "mfc1_v": 0.0,
            "mfc2_v": 0.0,
            "plasma_a": 0.0,
            # What the cathode DAC is holding, in millivolts, whether the
            # PID put it there or the rig's own output-voltage box did. It
            # is a separate fact from `plasma_a` on purpose: setting the DAC
            # directly turns the PID off and leaves the cathode driven, and
            # a record that carried only the PID setpoint called that
            # combination "nothing running" (see `live_outputs`).
            "cathode_mv": 0.0,
            # The first ionization gauge's mode and exponent, under the two
            # names every reader has known; `gauges` carries the same pair
            # for every gauge by channel name, the first one included.
            "ig_mode": None,
            "ig_range": None,
            "gauges": {name: {"mode": None, "range": None} for name in self._gauges},
            "sync": False,
        }

        self._log = collections.deque(maxlen=LOG_LINES)
        self._log_seq = 0

        # Browser control: the switch on the rig's screen, the baselines the
        # display subtracts, and the fate of the last command sent.
        self._remote = False
        self._zeros = {name: 0.0 for name in ZERO_CHANNELS}
        self._last_command = None
        self._kikusui = {"status": "idle"}
        self._kikusui_at = self._clock()

    # -- what the main thread writes -----------------------------------------

    def record_kikusui(self, snapshot):
        """Copy the GUI's telemetry record; no web request reaches the recorder."""
        with self._lock:
            self._kikusui = dict(snapshot)
            self._kikusui_at = self._clock()

    def _read_kikusui(self, now):
        result = self._kikusui.copy()
        if result.get("age_s") is not None:
            result["age_s"] += max(0, now - self._kikusui_at)
        if result.get("status") in ("ok", "dummy") and (
            result.get("age_s") is None
            or result["age_s"] > result.get("stale_after_s", 0)
        ):
            result["status"] = "stale"
        if result.get("status") not in ("ok", "dummy"):
            for key in ("voltage_v", "current_a", "output_on"):
                result.pop(key, None)
        # The browser needs the run filename, not the host's home directory.
        result["file"] = result.get("file", "").replace("\\", "/").rsplit("/", 1)[-1]
        return result

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
            for times, column in self._side.values():
                times.clear()
                column.clear()
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

    def record_sidecar(self, stamp, values):
        """Append one reading of a series the rig does not sample itself.

        `stamp` is that reading's *own* epoch seconds — the sidecar row's
        timestamp, not the moment the main thread looked at it — and
        `values` maps a name in `SIDECAR_SERIES` to its number.

        A stamp that is not newer than the last one held for that series is
        dropped, so a snapshot republished unchanged (the GUI reads the
        recorder's snapshot every 500 ms and the recorder writes a row every
        500 ms on its own clock) never lays down the same point twice.

        Returns whether anything was written, so a caller can say so.
        Nothing here touches the sample count, the latest values or the
        freshness clock: those are the ADC's facts and a LAN reading is not
        an ADC sample.
        """
        try:
            moment = float(stamp)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(moment):
            return False
        wrote = False
        with self._lock:
            for name, value in (values or {}).items():
                if name not in self._side:
                    continue
                times, column = self._side[name]
                if times and moment <= times[-1]:
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(number):
                    continue
                times.append(moment)
                column.append(number)
                wrote = True
            if wrote:
                self._trim_sidecar()
        return wrote

    def _trim(self):
        """Drop what is older than the window the ring promises to keep."""
        if not self._times:
            return
        oldest_kept = self._times[-1] - self._keep_seconds
        while self._times and self._times[0] < oldest_kept:
            self._times.popleft()
            self._rows.popleft()

    def _trim_sidecar(self):
        """The same promise for the sidecar series, each against its own
        newest: a supply that stops answering keeps the history it has
        rather than having it cut back by an ADC that is still running."""
        for times, column in self._side.values():
            if not times:
                continue
            oldest_kept = times[-1] - self._keep_seconds
            while times and times[0] < oldest_kept:
                times.popleft()
                column.popleft()

    def record_setpoints(self, **setpoints):
        """Record the setpoints the rig currently holds, by name."""
        with self._lock:
            for key, value in setpoints.items():
                if key in self._setpoints:
                    self._setpoints[key] = value

    def record_gauge(self, gauge, mode=None, range=None):
        """Record one ionization gauge's mode and/or exponent, by channel name.

        The first gauge declared is also written under `ig_mode` and
        `ig_range`, the names the record carried before there were two.
        """
        with self._lock:
            entry = self._setpoints["gauges"].setdefault(
                gauge, {"mode": None, "range": None}
            )
            if mode is not None:
                entry["mode"] = mode
            if range is not None:
                entry["range"] = range
            # Undeclared gauges: the first one ever recorded is the first.
            first = self._gauges[0] if self._gauges else next(iter(self._setpoints["gauges"]))
            if gauge == first:
                if mode is not None:
                    self._setpoints["ig_mode"] = mode
                if range is not None:
                    self._setpoints["ig_range"] = range

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

    def _copy_setpoints(self):
        """The setpoints with the per-gauge pairs copied too, so a reader
        holding a snapshot never shares a dict with the main thread."""
        setpoints = dict(self._setpoints)
        setpoints["gauges"] = {
            name: dict(pair) for name, pair in self._setpoints["gauges"].items()
        }
        return setpoints

    def read(self):
        """A snapshot the web thread may keep and use without the lock."""
        with self._lock:
            now = self._clock()
            age = None
            if self._last_sample_at is not None:
                age = max(0.0, now - self._last_sample_at)
            return {
                "acquiring": self._acquiring,
                "kikusui": self._read_kikusui(now),
                "channels": self._channels,
                "sampling": self._sampling,
                "dummy": dummy_hardware_loaded(),
                "names": list(self._names),
                "units": dict(self._units),
                "values": dict(self._latest),
                "setpoints": self._copy_setpoints(),
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

        A sidecar series (`SIDECAR_SERIES`) is answered by name exactly like
        an ADC channel, cut by the same walk and thinned by the same
        arithmetic — but against its own times, because the recorder that
        writes it keeps its own clock. `count` stays the ADC sample count:
        a LAN reading is not a sample, and the span line that says how many
        samples a window holds must not be inflated by one.
        """
        with self._lock:
            side_names = [name for name in SIDECAR_SERIES if self._side[name][0]]
            if not self._times and not side_names:
                return {"from": None, "to": None, "count": 0, "channels": {}}
            # One reference for every window cut, so a 20 s window means the
            # same twenty seconds on both time bases.
            newest = self._times[-1] if self._times else None
            for name in side_names:
                last = self._side[name][0][-1]
                if newest is None or last > newest:
                    newest = last
            times, rows = _cut(
                list(self._times), list(self._rows), newest, window_seconds, since
            )
            side = {}
            for name in side_names:
                side_times, side_values = self._side[name]
                side[name] = _cut(
                    list(side_times), list(side_values), newest, window_seconds, since
                )
            # Nothing above is written again once it is in the ring, so the
            # rest of this can be done without holding the lock.
            if names:
                wanted = list(names)
            else:
                wanted = list(self._names)
                if not wanted and rows:
                    wanted = list(rows[-1].keys())
                wanted += [name for name in side_names if name not in wanted]
        count = len(times)
        picked = _thin(count, max_points)
        channels = {}
        for name in wanted:
            if name in side:
                side_times, side_values = side[name]
                chosen = _thin(len(side_times), max_points)
                channels[name] = [[side_times[i], side_values[i]] for i in chosen]
                continue
            channels[name] = [
                [times[i], rows[i].get(name)] for i in picked if name in rows[i]
            ]
        first, last = None, None
        for stamps in [times] + [pair[0] for pair in side.values()]:
            if not stamps:
                continue
            if first is None or stamps[0] < first:
                first = stamps[0]
            if last is None or stamps[-1] > last:
                last = stamps[-1]
        if first is None:
            return {"from": None, "to": None, "count": 0, "channels": {}}
        return {"from": first, "to": last, "count": count, "channels": channels}

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


#: The outputs the rig can be holding, in the order a person would say
#: them, each with the plain words that name it. Every one of them is a
#: setpoint the main thread already records; nothing here reaches for a
#: worker or a device.
#:
#: `cathode_mv` is beside `plasma_a` and not folded into it because they are
#: two different ways for the cathode to be driven: the PID holds a current,
#: and the output-voltage box on the rig's own screen holds a voltage with
#: the PID off. On 2026-08-19 the second one is what kept Mizuno-kun's
#: plasma running after the reader died.
LIVE_OUTPUTS = (
    ("mfc1_v", "gas flow H₂"),
    ("mfc2_v", "gas flow O₂"),
    ("cathode_mv", "cathode drive"),
    ("plasma_a", "plasma current PID"),
)

#: What the rig is doing, in three words a person can act on. `stopped` is
#: nothing running and nothing driven; `measuring` is recording with every
#: output at zero; `outputs live` is at least one output holding something,
#: whether or not anything is being recorded.
OPERATING_STOPPED = "stopped"
OPERATING_MEASURING = "measuring"
OPERATING_LIVE = "outputs live"


def live_outputs(snapshot):
    """Which of the rig's outputs are holding something other than zero.

    Plain words, in a fixed order, and never a value: this answer travels
    into the health report the other two surfaces read, and what a reader
    needs there is which output is live, not what it is set to.
    """
    setpoints = snapshot.get("setpoints") or {}
    live = []
    for key, words in LIVE_OUTPUTS:
        try:
            value = float(setpoints.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
        if value:
            live.append(words)
    return live


def operating_state(snapshot):
    """`stopped`, `measuring` or `outputs live`, and outputs win.

    "Not acquiring" was never "safe to restart" (owner direction 2026-09-07:
    "If the rig is running. And if it's measuring only or have some
    gas/plasma on"). The rig can hold gas open and the cathode driven with
    nothing recording at all — that is exactly what the 2026-08-19 reader
    death left behind — so a live output outranks the acquisition flag here
    rather than being mentioned after it.
    """
    if live_outputs(snapshot):
        return OPERATING_LIVE
    if snapshot.get("acquiring"):
        return OPERATING_MEASURING
    return OPERATING_STOPPED


def health_detail(snapshot):
    """One short sentence a lab person can read, or an empty string."""
    channels = snapshot.get("channels") or 0
    rate = _rate_phrase(snapshot.get("sampling"))
    outputs = live_outputs(snapshot)
    if not snapshot.get("acquiring"):
        # Idle says what the rig is doing — nothing — rather than what it
        # is not doing wrong (owner correction 2026-09-07: "It's up and not
        # doing a thing"). The hardware standing in is the second fact and
        # only when it is standing in.
        if not outputs:
            if snapshot.get("dummy"):
                return "idle, dummy hardware"
            return "idle, not recording"
        # Recording nothing while the apparatus is driven. It is not a
        # fault of this program's — nobody has pressed Start — and it is the
        # one thing a person about to restart the rig must see.
        parts = ["not recording", "outputs live: " + ", ".join(outputs)]
        if snapshot.get("dummy"):
            parts.append("dummy hardware")
        return ", ".join(parts)
    if channels and rate:
        acquiring = "acquiring {:d} channels at {}".format(channels, rate)
    elif channels:
        acquiring = "acquiring {:d} channels".format(channels)
    else:
        acquiring = "acquiring"
    parts = [acquiring]
    if outputs:
        parts.append("outputs live: " + ", ".join(outputs))
    if snapshot.get("dummy"):
        parts.append("dummy hardware")
    stalled = stalled_for(snapshot)
    if stalled is not None:
        parts.append("no new reading for {:d} s".format(int(stalled)))
    return ", ".join(parts)


def stalled_for(snapshot):
    """How long a running acquisition has delivered nothing, or None.

    None is "nothing measured", and it covers two different innocent
    facts: the rig is not acquiring at all, and a run whose first sample
    has not landed yet — at ten seconds a sample, that gap is ordinary and
    saying `degraded` through it would cry wolf every time somebody presses
    Start. A stall is only ever claimed from a sample that did arrive and
    then stopped being followed.
    """
    if not snapshot.get("acquiring"):
        return None
    age = snapshot.get("age")
    if age is None:
        return None
    return age if age > stale_after(snapshot.get("sampling")) else None


def health_status(snapshot):
    """`ok`, `degraded` or `down` for the shared board of three.

    Idle is `ok`. The rig sitting up and recording nothing is the rig
    waiting for somebody to press Start, and calling that degraded made the
    lab's board amber all night for no reason (owner correction 2026-09-07,
    relayed as letter `20260907-86d2c305-2815fa`: "It's up and not doing a
    thing, not degraded"). `degraded` is kept for a capability that is
    actually impaired, and there are two of those this record can see:

    * a run that has stopped delivering samples — the reader died between
      two of them, which is exactly what happened to Mizuno-kun's
      depositions on 2026-08-19, and the one failure this report can name
      today without the watchdog that is still to be built;
    * a process standing dummy devices in for the instruments, which is
      honest about what it cannot do rather than an invented failure: the
      web server is fine and there is nothing attached to it. That is an
      off-rig run or a test, never the Pi.

    `down` is not returned from here. A service that is down does not
    answer, and the reader asking is the one who finds that out.
    """
    if stalled_for(snapshot) is not None:
        return "degraded"
    if snapshot.get("dummy"):
        return "degraded"
    return "ok"


def health_body(status, version):
    """The health report, exactly the shape the ensemble agreed on."""
    snapshot = status.read()
    return {
        "service": SERVICE,
        "version": version,
        "status": health_status(snapshot),
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

#: What `/api/state` carries on a machine that holds no word of its own,
#: which is every off-rig run and every test that does not write one.
NO_FENCE = {"needed": False, "passed": False}


def state_body(status, version, control=None, fence=None, roster=None):
    """What every tab polls once a second: values, run facts, freshness.

    `control` is who holds the operator lock, read from the command queue by
    the caller rather than kept here: the lock is decided in the web thread,
    and a second copy in this record could only ever go stale. `fence` is the
    same kind of thing for the lab's word — whether this machine asks for one
    and whether this browser has typed it — and is worked out per request for
    the same reason `control.mine` is: a page cannot see its own cookies.
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
        # What the rig is doing, for the reader and for a session about to
        # pull a new version onto the Pi: stopped, measuring only, or
        # outputs live and which. Names only — a setpoint's value belongs to
        # the row that sets it, on Control.
        "operating": {
            "state": operating_state(snapshot),
            "outputs": live_outputs(snapshot),
        },
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
        # Whether this machine asks for the lab's word, and whether the
        # browser reading this has already typed it. The word itself is
        # never carried: the page needs to know where it stands, not what
        # the fence is made of.
        "fence": dict(fence) if fence else dict(NO_FENCE),
        # When this machine's copy of the lab's names was last confirmed
        # against the service that keeps them, or `None` for never. A count
        # and a time; no address, and no names — the names are the roster's
        # own route and the Acting-as field's business.
        "roster": dict(roster) if roster else None,
        "channels": channels,
        "kikusui": snapshot["kikusui"],
    }

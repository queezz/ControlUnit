"""The ion gauges follow the PIHTI Diagram's on and off.

queezz, 2026-11-13, live: "Gauge left off, maybe we sync from the journal?
Why should we turn that off twice??" The audit of the student runs of
2026-10-22 to 11-13 found the ion gauges switched off at their controllers
for days without being declared off here, Pd for 224 h and Pu2 for 132 h,
so the file recorded noise at the gauge's floor as pressure. The operators
had recorded every one of those switches in the PIHTI Diagram, the vacuum
diagram on the same Pi (`downstream-ionization-gauge` inactive at
2026-11-13 14:43:20, for one). So the Diagram's word is taken here, and a
gauge is turned off once, where people already turn it off.

Three parts, each on the thread it belongs to:

- `DiagramFollower` asks the Diagram for `/elements-state` every
  `POLL_SECONDS` on a daemon thread of its own, with a `TIMEOUT_SECONDS`
  wait, and keeps only the newest answer. It never touches Qt, a worker or
  the ADC; nothing waits on it, and it holds nothing a shutdown must close.
- `GaugeFollowing` is the main thread's memory of what the Diagram last
  said for each mapped gauge. It turns an answer into the gauges whose word
  *changed*, and into at most one Log sentence when following stops working
  and one when it works again. Edges only: a press on the dock or in a
  browser holds until the Diagram itself changes again, so the two never
  fight and nothing is re-applied at every poll.
- `SwitchCheck` holds one recorded switch against the gauge's own raw
  volts. queezz, the same day: "When the diagram says the gauge is off, but
  the signal doesn't change, we should warn. And we can detect on/off, I
  guess. Not automatically, but when the switch is recorded somewhere." The
  Diagram's edge is the trigger and the signal is only the check; nothing
  here ever infers on or off from the signal alone.

Which gauge is which element is `Diagram Element` in settings.yml, the
channel map (`readsettings.gauge_diagram_elements`); a gauge without one is
not followed. Where the Diagram answers is the `pihti-diagram` entry of this
machine's neighbours file (`web.neighbours.read_neighbours`), the address
the Lab board already probes.

The Diagram's `/elements-state` is a flat JSON object, element id to
`"active"` or `"inactive"`, unauthenticated and read-only (its
`src/pihti/server.py`). The Diagram itself reads an element missing from it
as inactive; this does not. A mapped element absent from an answer is not
followed, with one Log line, so a renamed id on the Diagram's side can never
declare a working gauge off.

Plain standard library and numpy; nothing here imports PyQt.
"""

import collections
import datetime
import ipaddress
import json
import math
import threading
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from controlunit.web import neighbours

#: The neighbours file's name for the Diagram.
DIAGRAM_ALIAS = "pihti-diagram"

#: The Diagram's own record of what operators entered: `{id: "active" |
#: "inactive"}`. Its `/state` answers the same object; this is the name its
#: own pages read.
STATE_PATH = "/elements-state"

#: The Diagram's history of every recorded switch, with its time and the
#: operator's initials: `[{"ts": "YYYY-MM-DD HH:MM:SS", "user", "changes":
#: [{"id", "state": bool}]}, ...]`. `/elements-state` carries no time, and
#: the time a person recorded the switch is the one the signal check should
#: count from, not the moment this program noticed it (queezz, 2026-11-13:
#: "The diagram has no timestamp? But it has history. So it has time...").
#: Asked only when the states changed: it is the whole history.
HISTORY_PATH = "/history/events"
#: The most of the history that is read; months of presses are well under.
MAX_HISTORY_BYTES = 16 * 1024 * 1024
#: The Diagram's own stamp format, local time on the machine it runs on: on
#: the rig the same Pi, so the same clock as the ADC's rows.
HISTORY_STAMP = "%Y-%m-%d %H:%M:%S"

#: How often the Diagram is asked. A person flips a gauge and records it
#: within about a minute either way (below), so ten seconds is quick enough
#: to matter and slow enough to be nothing to a Pi serving both programs.
POLL_SECONDS = 10.0

#: How long one ask may wait: the Lab board's own two seconds.
TIMEOUT_SECONDS = neighbours.TIMEOUT_SECONDS

#: How long a stop waits for the thread. The thread holds no file, socket
#: or device past one request, and is a daemon, so a stop that does not
#: finish in this time is left to the interpreter rather than waited on.
STOP_WAIT_SECONDS = 0.5

#: The most of an answer that is read. The whole diagram is a few kilobytes.
MAX_ANSWER_BYTES = 256 * 1024

ACTIVE = "active"
INACTIVE = "inactive"

#: Why an answer that arrived was not used.
NOT_STATES = "answered, but not with the elements' states"

# -- what a recorded switch looks like on the gauge's own wire ---------------
#
# The audit of 2026-10-22 to 11-13: a gauge switched off at its controller
# reads its raw volts within 3 mV of zero, and a live one reads far above
# that. Ten millivolts is the floor, with room for the ADC's own noise.
FLOOR_VOLTS = 0.01
# On 2026-10-07 the upstream controller's output swung to -1.56 V as it lost
# power and decayed to zero over about 15 s, so a single sample at either
# side of the floor proves nothing: the signal must stay there this long.
HOLD_SECONDS = 5.0
# Operators record a switch in the Diagram up to about a minute before or
# after they flip it (queezz: "Sometimes I log first, sometimes I open
# first"). The window reaches a minute back from the edge, and ninety
# seconds on, to leave the decay above time to settle.
BEFORE_SECONDS = 60.0
AFTER_SECONDS = 90.0

#: A check's verdicts. `UNCHECKED` is a window with no sample in it at all:
#: nothing to hold the Diagram's word against, and so nothing to say.
PENDING = "pending"
CONFIRMED = "confirmed"
UNCONFIRMED = "unconfirmed"
UNCHECKED = "unchecked"


class DiagramUnanswered(Exception):
    """The Diagram could not be asked, or its answer was not usable."""


Answer = collections.namedtuple("Answer", "states reason at recorded", defaults=(None,))
Answer.__doc__ = """One ask's outcome: the states, or None and why not, and
when it was asked, on this machine's wall clock (the clock the ADC's rows
are stamped with). `recorded`, when the states had changed, is what the
Diagram's history says of each element's latest switch (`recorded_switches`),
or None."""


def diagram_url(home=None):
    """The Diagram's address from this machine's neighbours file, or None."""
    entry = neighbours.read_neighbours(home).get(DIAGRAM_ALIAS) or {}
    return entry.get("url") or None


def is_loopback(url):
    """True when `url` names this machine itself.

    The dummy hardware asks only such a Diagram: a laptop checking this
    feature runs a Diagram of its own, and never reads the rig's.
    """
    host = urllib.parse.urlsplit(str(url or "")).hostname or ""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def fetch_elements_state(url, timeout=TIMEOUT_SECONDS):
    """Ask the Diagram at `url` for its elements' states.

    Returns the answer, a dict. Raises `DiagramUnanswered` with the reason,
    in the Lab board's own words for the same failures, when nothing usable
    came back.
    """
    target = url.rstrip("/") + STATE_PATH
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            payload = response.read(MAX_ANSWER_BYTES)
    except urllib.error.HTTPError as error:
        raise DiagramUnanswered(
            "answered with an error, code {}".format(getattr(error, "code", "?"))
        )
    except Exception as error:  # noqa: BLE001 -- every silence is one reason
        # The board's private sentence, reused so a refused port, a name
        # that did not resolve and a wait that ran out read the same here as
        # on the Lab tab.
        raise DiagramUnanswered(neighbours._failure(error)[1])
    try:
        body = json.loads(payload.decode("utf-8"))
    except Exception:  # noqa: BLE001 -- not JSON, not UTF-8: one reason
        raise DiagramUnanswered(NOT_STATES)
    if not isinstance(body, dict):
        raise DiagramUnanswered(NOT_STATES)
    return body


def recorded_switches(events):
    """Each element's latest recorded switch to each state, from the
    Diagram's history: `{element: {"active" | "inactive": (time, user)}}`.

    Anything in the history that is not a well-formed press is skipped; a
    history that is not a list is no history.
    """
    found = {}
    if not isinstance(events, list):
        return found
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            moment = datetime.datetime.strptime(str(event.get("ts")), HISTORY_STAMP)
        except ValueError:
            continue
        user = str(event.get("user") or "").strip()
        for change in event.get("changes") or []:
            if not isinstance(change, dict) or not isinstance(change.get("state"), bool):
                continue
            status = ACTIVE if change["state"] else INACTIVE
            slot = found.setdefault(str(change.get("id")), {})
            if status not in slot or moment >= slot[status][0]:
                slot[status] = (moment, user)
    return found


def fetch_recorded(url, timeout=TIMEOUT_SECONDS):
    """The Diagram's history as `recorded_switches` reads it; {} when it
    cannot be had. The states are followed either way: a missing time only
    means the check counts from when the change was noticed."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + HISTORY_PATH, timeout=timeout) as response:
            payload = response.read(MAX_HISTORY_BYTES)
        return recorded_switches(json.loads(payload.decode("utf-8")))
    except Exception:  # noqa: BLE001 -- a time is a refinement, never a stop
        return {}


class DiagramFollower:
    """Ask the Diagram on a thread of its own and keep the newest answer.

    `take()` is the main thread's half: it hands over the newest answer
    once, or None when nothing new has come. Only the newest is kept, so a
    main thread that falls behind reads the Diagram as it is now, never a
    queue of what it was.
    """

    def __init__(self, url, fetch=None, interval=None, clock=None, history=None):
        self.url = url
        #: One ask: returns the states or raises. Injectable so a test can
        #: answer without a network.
        self._fetch = fetch if fetch is not None else (
            lambda: fetch_elements_state(url)
        )
        #: The history, asked only when the states changed; injectable too.
        self._history = history if history is not None else (
            lambda: fetch_recorded(url)
        )
        self._last_states = None
        self._interval = POLL_SECONDS if interval is None else float(interval)
        self._clock = clock if clock is not None else datetime.datetime.now
        self._lock = threading.Lock()
        self._latest = None
        self._stop = threading.Event()
        self._thread = None

    @property
    def thread(self):
        return self._thread

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="diagram-follower", daemon=True
        )
        self._thread.start()

    def _ask(self):
        at = self._clock()
        try:
            states = self._fetch()
        except DiagramUnanswered as error:
            return Answer(None, str(error), at)
        except Exception as error:  # noqa: BLE001 -- the thread outlives any ask
            return Answer(None, "the ask failed: {}".format(error), at)
        recorded = None
        if states != self._last_states:
            try:
                recorded = self._history()
            except Exception:  # noqa: BLE001 -- a time is a refinement
                recorded = None
        self._last_states = states
        return Answer(states, "", at, recorded)

    def _run(self):
        while not self._stop.is_set():
            answer = self._ask()
            if self._stop.is_set():
                break
            with self._lock:
                self._latest = answer
            self._stop.wait(self._interval)

    def take(self):
        """The newest answer, once; None when nothing new has arrived."""
        with self._lock:
            answer, self._latest = self._latest, None
        return answer

    def stop(self, timeout=STOP_WAIT_SECONDS):
        """Ask the thread to end and wait a moment; True once it has."""
        self._stop.set()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()


def gauge_words(place):
    """How a Log line names a gauge: "the downstream ion gauge"."""
    return "{} ion gauge".format(place).strip() if place else "ion gauge"


class GaugeFollowing:
    """What the Diagram last said for each mapped gauge, on the main thread.

    `read()` takes one answer and returns `(changes, notes)`: the gauges
    whose word changed since the last answer, as `(gauge, status)`, and the
    sentences the Log should carry about following itself. The first answer
    is a change from not knowing, so at launch the gauges take the
    Diagram's current word.
    """

    def __init__(self, elements):
        #: gauge -> the Diagram's element id.
        self.elements = dict(elements)
        self._seen = {}
        #: None before any answer, then whether the last ask was answered.
        self._answering = None
        self._unnamed = set()

    def read(self, states, reason=""):
        notes = []
        if not isinstance(states, dict):
            # Said when following stops working, not at every poll after.
            if self._answering is not False:
                notes.append(
                    "Gauges not following the Diagram: {}; gauge modes left"
                    " as they are".format(reason or NOT_STATES)
                )
            self._answering = False
            return [], notes
        if self._answering is False:
            notes.append("Gauges following the Diagram again")
        self._answering = True
        changes = []
        for gauge, element in self.elements.items():
            status = states.get(element)
            if status not in (ACTIVE, INACTIVE):
                if gauge not in self._unnamed:
                    self._unnamed.add(gauge)
                    notes.append(
                        "{} not following the Diagram: its answer has no"
                        " active or inactive for {}".format(gauge, element)
                    )
                continue
            self._unnamed.discard(gauge)
            if self._seen.get(gauge) == status:
                continue
            self._seen[gauge] = status
            changes.append((gauge, status))
        return changes, notes


def _stamp(moment):
    return np.datetime64(moment, "ns")


def _held(times, volts, at_floor, start, end):
    """Whether the raw volts stayed on one side of the floor for
    `HOLD_SECONDS` somewhere between `start` and `end`.

    `times` is ascending (the run history keeps its rows in order), so the
    window is found by bisection. A sample that is not a number breaks a
    stretch, as one on the other side of the floor does.
    """
    first = int(np.searchsorted(times, start, side="left"))
    last = int(np.searchsorted(times, end, side="right"))
    hold = np.timedelta64(int(HOLD_SECONDS * 1e9), "ns")
    since = None
    for stamp, value in zip(times[first:last], volts[first:last]):
        value = float(value)
        if not math.isfinite(value) or (abs(value) < FLOOR_VOLTS) != at_floor:
            since = None
            continue
        if since is None:
            since = stamp
        if stamp - since >= hold:
            return True
    return False


def _last_reading(times, volts, start, end):
    """The newest finite raw value between `start` and `end`, or None."""
    first = int(np.searchsorted(times, start, side="left"))
    last = int(np.searchsorted(times, end, side="right"))
    for value in volts[first:last][::-1]:
        value = float(value)
        if math.isfinite(value):
            return value
    return None


class SwitchCheck:
    """One switch the Diagram recorded, awaiting the gauge's own signal.

    Off is confirmed when the raw volts sit at the floor for `HOLD_SECONDS`
    at any point from `BEFORE_SECONDS` before the edge to `AFTER_SECONDS`
    after it; on is confirmed when they leave it as long. Confirmed early
    when the signal has already said so; unconfirmed only once the whole
    window has passed, so a slow decay is never warned about.
    """

    def __init__(self, gauge, status, at, words):
        self.gauge = gauge
        self.status = status
        self.words = words
        self.start = _stamp(at - datetime.timedelta(seconds=BEFORE_SECONDS))
        self.end = _stamp(at + datetime.timedelta(seconds=AFTER_SECONDS))

    def verdict(self, times, volts, now):
        """`(verdict, Log line or "")` as of `now`, from the run's raw column."""
        if times is not None and volts is not None and len(times):
            if _held(times, volts, self.status == INACTIVE, self.start, self.end):
                return CONFIRMED, ""
        if _stamp(now) < self.end:
            return PENDING, ""
        reading = None
        if times is not None and volts is not None and len(times):
            reading = _last_reading(times, volts, self.start, self.end)
        if reading is None:
            return UNCHECKED, ""
        return UNCONFIRMED, self.warning(reading)

    def warning(self, reading):
        """The one red line for a switch the signal does not show. ASCII,
        like every line the Log file carries."""
        if self.status == INACTIVE:
            return (
                "<font color='red'>{g}: the Diagram shows the {w} off</font>,"
                " but {g} still reads {v:.3g} V, a live gauge's signal; is its"
                " controller still on, or was another gauge recorded?".format(
                    g=self.gauge, w=self.words, v=reading
                )
            )
        return (
            "<font color='red'>{g}: the Diagram shows the {w} on</font>, but"
            " {g} still reads {v:.3g} V, its floor; is its controller"
            " on?".format(g=self.gauge, w=self.words, v=reading)
        )

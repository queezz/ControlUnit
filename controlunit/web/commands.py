"""What a browser may ask the rig to do, and how the rig gets to hear it.

Thread ownership is the whole design. The Qt main thread owns every worker
and is the only caller of a worker slot; the web thread must therefore never
call one. So a browser's request becomes a small record on a plain
`queue.Queue`, and the main thread drains that queue on a timer and calls the
very methods its own buttons call. A setpoint has one code path whether it
came from the rig's touchscreen or from a laptop, and so does a run: `start`
and `stop` reach the same two methods the on/off switch on the rig's own
screen reaches, and set that switch to match on the way through.

Who may send one is a second question, and the operator lock below answers
it: the first browser to send a setter holds control, everyone else sees by
name and address who that is, and takes it over deliberately. The lock is
decided here, in the web thread where the commands arrive, and let go from
the main thread when the rig stops listening.

Nothing here imports PyQt, and nothing here touches a device. `drain` is
handed the running `MainApp` and only ever calls methods that already exist
on it; every value is checked in the web thread before it is queued, so the
main thread is never asked to run a command it should have refused.
"""

import queue
import re
import threading
import time

#: Every kind of command a browser may send, in operating order.
KINDS = (
    "stop_all",
    "take_over",
    "start",
    "stop",
    "sampling",
    "mfc",
    "plasma",
    "gauge",
    "sync",
    "zero",
)

#: Stopping the outputs is always allowed: it only ever drives the hardware
#: to zero, and a person who can see the rig must be able to do it whether
#: or not they typed a name and whether or not the switch on the rig is on.
#: Starting and stopping a run is not in here: a run is the whole point of
#: the switch on the rig, so it is gated like every other setter.
ALWAYS_ALLOWED = ("stop_all",)

#: Everything else needs workers running to mean anything. Taking control is
#: not one of them: it moves a lock, it does not touch the hardware. Nor is
#: `start`, which is the one command that means something only while idle.
NEEDS_ACQUISITION = ("stop", "sampling", "mfc", "plasma", "gauge", "sync", "zero")

#: The commands that mean something only while nothing is running. Just the
#: one, and it is refused with its own reason rather than the idle one, so a
#: person who pressed Start twice is told which of the two facts is in the
#: way.
NEEDS_IDLE = ("start",)

#: The setters the operator lock is about — everything that starts, stops or
#: moves gas, cathode current, the gauge or the sync line. Stopping the
#: outputs is never gated by it, and taking control is how the lock is moved,
#: not something the lock may refuse.
LOCKED = ("start", "stop", "sampling", "mfc", "plasma", "gauge", "sync", "zero")

#: The sampling times the rig offers, in seconds, exactly the choices the Qt
#: Settings dock's combo carries (`ui/docks/settings.py`). A test builds that
#: dock and holds the two lists equal, so a browser can never ask for a
#: sampling time the rig's own screen does not offer.
SAMPLING_CHOICES = (10.0, 1.0, 0.1, 0.01)

#: The channels whose baseline can be zeroed from the browser.
ZERO_CHANNELS = ("Ip", "Bu", "Bd")

#: The gas flow setpoint's own bounds, in millivolts, as the Qt dock's.
MFC_MAX_MV = 5000

#: The plasma current setpoint's bounds, in amperes, as the Qt spinbox's.
PLASMA_MAX_A = 3.0

#: The ionization gauge's two modes and its decade range.
GAUGE_MODES = ("Torr", "Pa")
GAUGE_RANGE_LOW = -8
GAUGE_RANGE_HIGH = -3

#: A name is a label a person chose, not an identity: it is kept short and
#: reduced to characters that cannot disturb the log, the page or the file.
ACTOR_MAX = 24
_ACTOR_ALLOWED = re.compile(r"[^0-9A-Za-z .,'_-]+")

#: More waiting commands than this and the rig is not keeping up; refusing is
#: honest, and a queue that cannot grow without bound cannot starve the loop.
MAX_QUEUED = 32

APPLIED = "applied"
REFUSED = "refused"

#: The reasons a command is refused, in the words the reader is shown.
NO_REMOTE = "the Remote switch on the rig's screen is off"
NO_ACQUISITION = "no acquisition running"
ALREADY_ACQUIRING = "acquisition is already running"
NO_SAMPLES = "no samples to take a baseline from yet"
TOO_MANY = "too many commands are already waiting"

#: What the holder line says when the lock is free.
NOBODY = "Nobody has control"


class Invalid(ValueError):
    """A body the web thread refuses to queue, with the reason to show."""


class Command(object):
    """One queued instruction, and everything the log needs to name it."""

    __slots__ = ("id", "kind", "value", "actor", "origin", "at")

    def __init__(self, ident, kind, value, actor="", origin="", at=None):
        self.id = ident
        self.kind = kind
        self.value = dict(value or {})
        self.actor = actor or ""
        self.origin = origin or ""
        self.at = time.time() if at is None else at

    def summary(self):
        """What was asked for, in a few plain ASCII words."""
        return summarise(self.kind, self.value)

    def as_record(self, outcome, reason=""):
        """The shape `/api/state` carries as `last_command`."""
        return {
            "id": self.id,
            "kind": self.kind,
            "value": self.summary(),
            "actor": self.actor,
            "at": self.at,
            "outcome": outcome,
            "reason": reason,
        }


class OperatorLock(object):
    """Who is allowed to set what the rig holds from a browser, and since when.

    Two people at one plasma is what this exists for. It is not a permission
    system — a name is a label a person typed, not a credential — it is a way
    of making the other person visible: the first browser to send a setter
    holds control, everyone else is told who that is by name, address and
    time, and takes it over deliberately rather than by accident.

    Control is an actor *and* an origin together, because one shared name on
    two laptops is still two people at one plasma. The rig's own screen is
    never gated by any of this: a person standing at the machine always wins,
    and the main thread lets go of the lock when acquisition stops or the
    Remote switch goes off.
    """

    def __init__(self, clock=time.time):
        self._lock = threading.Lock()
        self._clock = clock
        self._holder = ""
        self._origin = ""
        self._since = None

    def _record(self):
        return {"holder": self._holder, "origin": self._origin, "since": self._since}

    def read(self):
        """Who holds control right now, as `/api/state` carries it."""
        with self._lock:
            return self._record()

    def held_by(self, actor, origin):
        """True when this very browser is the one holding control."""
        with self._lock:
            return bool(self._holder) and self._is_holder(actor, origin)

    def _is_holder(self, actor, origin):
        # One browser, one address: control is held by where a person is
        # sitting, and the name is only what the log calls them. So saving a
        # name after taking control does not lock anybody out of their own
        # session, and two laptops are two people however they sign.
        return self._origin == (origin or "")

    def blocks(self, actor, origin):
        """Whoever else holds control, or `None` when this browser may set.

        One reading under one lock, so the sentence a refusal shows names the
        person who actually held it at the moment the answer was decided.
        """
        with self._lock:
            if not self._holder or self._is_holder(actor, origin):
                return None
            return self._record()

    def claim(self, actor, origin):
        """Take control if it is free; the first setter is what claims it."""
        identity = _identity(actor, origin)
        if not identity:
            return False
        with self._lock:
            if self._holder and self._is_holder(actor, origin):
                # The same browser, perhaps with a name saved since it took
                # control: keep the lock and call this person what they now
                # call themselves.
                self._holder = identity
                return False
            if self._holder:
                return False
            self._holder = identity
            self._origin = origin or ""
            self._since = self._clock()
            return True

    def take_over(self, actor, origin):  # noqa: D401
        """Move control here. Returns (whether it moved, who held it before).

        Taking over when nobody holds control simply takes it; taking over
        when you already hold it changes nothing, so the caller can answer
        without pretending anything happened.
        """
        identity = _identity(actor, origin)
        origin = origin or ""
        with self._lock:
            if self._holder and self._is_holder(actor, origin):
                self._holder = identity
                return False, self._holder
            previous = self._holder
            self._holder = identity
            self._origin = origin
            self._since = self._clock()
            return True, previous

    def release(self):
        """Let go, and say who was holding it. Empty when nobody was."""
        with self._lock:
            previous = self._holder
            self._holder = ""
            self._origin = ""
            self._since = None
            return previous


def _identity(actor, origin):
    """What the holder line calls a person: the name they typed, or, while
    they have typed none, the address their browser is at. A name is a label
    and never a credential, so the rig asks for one but never waits for it.
    """
    return clean_actor(actor) or (origin or "")


def holder_sentence(control):
    """The one sentence that says who has control, in the reader's words.

    Built here and nowhere else: the page prints it, a refusal gives it as
    its reason, and neither can drift from the other. The clock is the rig's,
    which is the clock everyone in the room is standing next to.
    """
    control = control or {}
    holder = control.get("holder") or ""
    if not holder:
        return NOBODY
    parts = ["{} has control".format(holder)]
    since = control.get("since")
    if since:
        parts.append("since {}".format(time.strftime("%H:%M", time.localtime(since))))
    # Somebody who has typed no name is already named by their address;
    # saying it twice reads as two facts about two people.
    if control.get("origin") and control["origin"] != holder:
        parts.append("from {}".format(control["origin"]))
    return " ".join(parts)


class CommandQueue(object):
    """The one crossing between the web thread and the Qt main thread."""

    def __init__(self, maxsize=MAX_QUEUED):
        self._queue = queue.Queue(maxsize=maxsize)
        self._next = 0
        #: Who may set anything from a browser. It is decided in the web
        #: thread, where the commands arrive, and read from both threads.
        self.control = OperatorLock()

    def submit(self, kind, value, actor="", origin=""):
        """Queue a checked command and return it, or raise `Invalid`."""
        self._next += 1
        command = Command(self._next, kind, value, actor=actor, origin=origin)
        try:
            self._queue.put_nowait(command)
        except queue.Full:
            raise Invalid(TOO_MANY)
        # A setter that made it onto the queue is what takes control: from
        # here on the next person sees this one's name rather than quietly
        # setting the same gas line.
        if kind in LOCKED:
            self.control.claim(actor, origin)
        return command

    def take_all(self):
        """Everything waiting, oldest first. Only the main thread calls this."""
        taken = []
        while True:
            try:
                taken.append(self._queue.get_nowait())
            except queue.Empty:
                return taken

    def waiting(self):
        return self._queue.qsize()


# -- what a browser is allowed to say ----------------------------------------


def clean_actor(text):
    """The name a browser carries, reduced to something safe to print."""
    name = _ACTOR_ALLOWED.sub("", str(text or "")).strip()
    return name[:ACTOR_MAX]


def _body(body):
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise Invalid("the request body must be a set of named values")
    return body


def _whole_number(value, low, high, what):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise Invalid(what)
    if number != int(number) or not (low <= number <= high):
        raise Invalid(what)
    return int(number)


def validate_mfc(number, body):
    """`{"mv": 0..5000}` for MFC 1 or 2; zero is the Zero button."""
    which = _whole_number(number, 1, 2, "there are two gas lines, 1 and 2")
    body = _body(body)
    if "mv" not in body:
        raise Invalid("a flow setpoint needs a value in millivolts")
    millivolts = _whole_number(
        body["mv"],
        0,
        MFC_MAX_MV,
        "a flow setpoint is a whole number of millivolts from 0 to {}".format(
            MFC_MAX_MV
        ),
    )
    return {"n": which, "mv": millivolts}


def validate_plasma(body):
    """`{"a": 0..3}` sets the PID setpoint; `{"off": true}` turns it off."""
    body = _body(body)
    if body.get("off"):
        return {"off": True}
    if "a" not in body:
        raise Invalid("a plasma setpoint needs a value in amperes")
    try:
        amperes = float(body["a"])
    except (TypeError, ValueError):
        raise Invalid(
            "a plasma setpoint is a number of amperes from 0 to {:g}".format(
                PLASMA_MAX_A
            )
        )
    if not (0.0 <= amperes <= PLASMA_MAX_A) or amperes != amperes:
        raise Invalid(
            "a plasma setpoint is a number of amperes from 0 to {:g}".format(
                PLASMA_MAX_A
            )
        )
    return {"a": round(amperes, 3)}


def validate_gauge(body):
    """`{"mode": "Torr"|"Pa"}` and/or `{"range": -8..-3}`; at least one."""
    body = _body(body)
    value = {}
    if body.get("mode") is not None:
        mode = str(body["mode"])
        if mode not in GAUGE_MODES:
            raise Invalid("the gauge reads in Torr or in Pa")
        value["mode"] = mode
    if body.get("range") is not None:
        value["range"] = _whole_number(
            body["range"],
            GAUGE_RANGE_LOW,
            GAUGE_RANGE_HIGH,
            "the gauge range is a whole decade from {} to {}".format(
                GAUGE_RANGE_LOW, GAUGE_RANGE_HIGH
            ),
        )
    if not value:
        raise Invalid("say a gauge mode, a range, or both")
    return value


def validate_sync(body):
    """`{"on": bool}` for the QMS sync line."""
    body = _body(body)
    if "on" not in body or not isinstance(body["on"], bool):
        raise Invalid("the sync line is either on or off")
    return {"on": body["on"]}


def validate_zero(body):
    """`{"channel": "Ip"|"Bu"|"Bd"}`: take the present reading as the zero."""
    body = _body(body)
    channel = str(body.get("channel") or "")
    if channel not in ZERO_CHANNELS:
        raise Invalid(
            "a baseline is taken for {}".format(", ".join(ZERO_CHANNELS))
        )
    return {"channel": channel}


def validate_stop_all(body):
    """Nothing to say: the one meaning is every output to zero."""
    _body(body)
    return {}


def validate_start(body):
    """Nothing to say: the one meaning is start acquiring."""
    _body(body)
    return {}


def validate_stop(body):
    """Nothing to say: the one meaning is stop acquiring."""
    _body(body)
    return {}


def sampling_label(seconds):
    """How the rig writes one sampling time: `10 s`, `0.1 s`, `0.01 s`."""
    return "{:g} s".format(float(seconds))


def sampling_choices():
    """The sampling times on offer, as (value, label) pairs for the page."""
    return [("{:g}".format(s), sampling_label(s)) for s in SAMPLING_CHOICES]


def validate_sampling(body):
    """`{"seconds": 10|1|0.1|0.01}`: one of the rig's own sampling times."""
    body = _body(body)
    if "seconds" not in body:
        raise Invalid("a sampling time needs a value in seconds")
    try:
        seconds = float(body["seconds"])
    except (TypeError, ValueError):
        seconds = None
    # The rig's ADC batches its rows by sampling time, so only the four the
    # Settings dock offers are known to behave; anything else is refused in
    # the words of the four on offer.
    if seconds is None or not any(
        abs(seconds - choice) < 1e-9 for choice in SAMPLING_CHOICES
    ):
        raise Invalid(
            "the sampling time is one of {}".format(
                ", ".join(sampling_label(s) for s in SAMPLING_CHOICES)
            )
        )
    return {"seconds": float(seconds)}


def validate(kind, body, number=None):
    """Check one body by kind. Raises `Invalid` with the reason to show."""
    if kind == "stop_all":
        return validate_stop_all(body)
    if kind == "start":
        return validate_start(body)
    if kind == "stop":
        return validate_stop(body)
    if kind == "sampling":
        return validate_sampling(body)
    if kind == "mfc":
        return validate_mfc(number, body)
    if kind == "plasma":
        return validate_plasma(body)
    if kind == "gauge":
        return validate_gauge(body)
    if kind == "sync":
        return validate_sync(body)
    if kind == "zero":
        return validate_zero(body)
    raise Invalid("that is not something this rig accepts")


# -- who may press what -------------------------------------------------------


def refusal(kind, remote, actor, origin="", control=None):
    """Why this command may not be queued, or an empty string if it may.

    Reading is open to anyone on the lab network. Setting needs two things:
    the Remote switch turned on beside the rig's own screen, so nobody moves
    gas or cathode current past a person who is not there, and control of
    the rig, so two people do not drive one plasma without seeing each
    other. A name is asked for and never waited for (owner report
    2026-09-05, "I toggled it on, but the browser doesn't allow my
    control"): the switch is what authorises, and an unnamed person is
    logged by the address they are sitting at.

    The second is answered by `control`, an `OperatorLock`; without one the
    switch is the whole gate, which is what a read-only run wants.
    """
    if kind in ALWAYS_ALLOWED:
        return ""
    if not remote:
        return NO_REMOTE
    if kind in LOCKED and control is not None:
        blocker = control.blocks(actor, origin)
        if blocker:
            return holder_sentence(blocker)
    return ""


def needs_acquisition(kind):
    """True when the command has no meaning without the workers running."""
    return kind in NEEDS_ACQUISITION


def needs_idle(kind):
    """True when the command has no meaning while the workers are running."""
    return kind in NEEDS_IDLE


# -- what the reader is told a command was ------------------------------------

_GAS = {1: "H2", 2: "O2"}


def summarise(kind, value):
    """One short ASCII phrase naming what was asked for.

    ASCII on purpose: this phrase goes into the message log, which is
    appended to a text file with the platform's own encoding.
    """
    value = value or {}
    if kind == "stop_all":
        return "all outputs to zero"
    if kind == "take_over":
        previous = value.get("from")
        if previous:
            return "took control from {}".format(previous)
        return "took control"
    if kind == "start":
        return "acquisition started"
    if kind == "stop":
        return "acquisition stopped"
    if kind == "sampling":
        return "sampling {}".format(sampling_label(value.get("seconds", 0)))
    if kind == "mfc":
        return "{} flow {} mV".format(_GAS.get(value.get("n"), "gas"), value.get("mv"))
    if kind == "plasma":
        if value.get("off"):
            return "plasma current PID off"
        return "plasma current {:.2f} A".format(float(value.get("a", 0.0)))
    if kind == "gauge":
        parts = []
        if value.get("mode"):
            parts.append("gauge in {}".format(value["mode"]))
        if value.get("range") is not None:
            parts.append("gauge range {}".format(value["range"]))
        return ", ".join(parts)
    if kind == "sync":
        return "QMS sync {}".format("on" if value.get("on") else "off")
    if kind == "zero":
        return "baseline of {} taken".format(value.get("channel"))
    return kind


# -- the main thread's half ---------------------------------------------------


def _mfc_digits(millivolts):
    """The four digit spinboxes of the gas flow dock, most significant first."""
    millivolts = int(millivolts)
    return [
        millivolts // 1000,
        (millivolts // 100) % 10,
        (millivolts // 10) % 10,
        millivolts % 10,
    ]


def _apply_stop_all(app):
    """The same call the shutdown path makes, plus the screen agreeing."""
    running = bool(getattr(app, "workers", None))
    app.turn_off_voltages()
    # The rig's own screen must not keep showing a setpoint the hardware no
    # longer holds, so the spinboxes this drove go to zero as well.
    app.plasma_control_dock.ampere_spin_box.setValue(0.0)
    app.gasflow_dock.resetSpinBoxes(1)
    app.gasflow_dock.resetSpinBoxes(2)
    if not running:
        return APPLIED, "nothing was running; the outputs are off"
    return APPLIED, ""


def _apply_start(app, value):
    """Start a run the way the switch on the rig's own screen starts one.

    That the rig is not already running was decided twice by the time this
    runs — once in the web thread against the status record, once in `apply`
    against the workers themselves — because the two are one poll apart and a
    person who pressed Start twice must not be handed a second set of workers
    over the first.

    `setChecked` emits no `clicked`, so the switch agreeing with what a
    browser did cannot re-enter the switch's own handler.
    """
    app.control_dock.OnOffSW.setChecked(True)
    app.start_acquisition()
    return APPLIED, ""


def _apply_stop(app, value):
    """Stop a run, and leave the Remote switch exactly as it was.

    Stopping used to force the switch back to LOCAL. It no longer does: the
    browser that just pressed Stop would have been stranded by a switch that
    turned itself off, and the switch belongs to the person at the rig. The
    operator lock is still let go of, in `abort_all_threads`, so nobody is
    left silently holding a rig that is not running.
    """
    app.control_dock.OnOffSW.setChecked(False)
    app.stop_acquisition()
    return APPLIED, ""


def _apply_sampling(app, value):
    """One sampling time, through the one method the Set button calls."""
    app.set_sampling(value["seconds"])
    return APPLIED, ""


def _apply_mfc(app, value):
    for digit, box in zip(_mfc_digits(value["mv"]), app.gasflow_dock.mfc_spinboxes[value["n"]]):
        box.setValue(digit)
    app.set_mfc_goal(value["n"])
    return APPLIED, ""


def _apply_plasma(app, value):
    if value.get("off"):
        app.turn_off_currentcontrol_voltage()
        return APPLIED, ""
    app.plasma_control_dock.ampere_spin_box.setValue(float(value["a"]))
    app.set_currentcontrol_voltage()
    return APPLIED, ""


def _apply_gauge(app, value):
    if value.get("mode"):
        app.control_dock.IGmode.setCurrentIndex(GAUGE_MODES.index(value["mode"]))
        # Setting a combo box to the value it already holds emits nothing, so
        # the updater is called outright; it is the same idempotent emit.
        app.update_ig_mode()
    if value.get("range") is not None:
        app.control_dock.IGrange.setValue(int(value["range"]))
        app.update_ig_range()
    return APPLIED, ""


def _apply_sync(app, value):
    app.control_dock.qmsSigSw.setChecked(bool(value["on"]))
    app._toggle_led_status()
    return APPLIED, ""


def _apply_zero(app, value):
    # The main thread says whether it had samples to average; a zero that
    # was not taken is never reported as one that was.
    if app.set_zero_baseline(value["channel"]):
        return APPLIED, ""
    return REFUSED, NO_SAMPLES


def _apply_take_over(app, value):
    """Nothing to drive: the lock moved in the web thread, where it was asked
    for, so the browser's answer was true the moment it was given. This runs
    here only so a take-over is logged and reported like any other command."""
    return APPLIED, ""


_APPLIERS = {
    "take_over": _apply_take_over,
    "start": _apply_start,
    "stop": _apply_stop,
    "sampling": _apply_sampling,
    "mfc": _apply_mfc,
    "plasma": _apply_plasma,
    "gauge": _apply_gauge,
    "sync": _apply_sync,
    "zero": _apply_zero,
}


def apply(app, command):
    """Run one command on the Qt main thread. Returns (outcome, reason)."""
    if needs_acquisition(command.kind) and not getattr(app, "workers", None):
        return REFUSED, NO_ACQUISITION
    if needs_idle(command.kind) and getattr(app, "workers", None):
        return REFUSED, ALREADY_ACQUIRING
    if command.kind == "stop_all":
        return _apply_stop_all(app)
    worker = _APPLIERS.get(command.kind)
    if worker is None:
        return REFUSED, "that is not something this rig accepts"
    return worker(app, command.value)


def describe(command, outcome, reason):
    """The message-log line one command leaves behind, in plain ASCII."""
    # Whoever typed no name is already named by their address; saying it
    # twice would read as two people.
    who = _identity(command.actor, command.origin)
    where = ""
    if command.origin and command.origin != who:
        where = " from {}".format(command.origin)
    # The summary is a whole clause ("H2 flow 1234 mV", "baseline of Bu
    # taken"), so nothing is prefixed to it that only fits a setpoint.
    if outcome == APPLIED:
        tail = " ({})".format(reason) if reason else ""
        return "Remote: {}{}: {}{}".format(who, where, command.summary(), tail)
    return "Remote: {}{}: {} - refused, {}".format(
        who, where, command.summary(), reason
    )


def release(app, reason):
    """Let go of browser control from the main thread, and say so in the log.

    The rig's own screen always wins: when acquisition stops, or when the
    Remote switch goes off, nobody is left holding a lock over a rig that is
    no longer listening. There is no idle timeout — a lock held quietly
    through a long overnight run is the normal case, not a fault.
    """
    waiting = getattr(app, "web_commands", None)
    if waiting is None:
        return ""
    previous = waiting.control.release()
    if previous:
        try:
            app.log_message("Control released ({})".format(reason))
        except Exception as error:  # losing a log line never stops a shutdown
            print("web control release: {}".format(error))
    return previous


def drain(app):
    """Run everything a browser queued. The main thread's timer calls this.

    One command failing is not allowed to stop the timer or the acquisition
    loop, so a failure is recorded as a refusal and the next command runs.
    """
    waiting = getattr(app, "web_commands", None)
    if waiting is None:
        return 0
    done = 0
    for command in waiting.take_all():
        try:
            outcome, reason = apply(app, command)
        except Exception as error:  # a bad command never stops the rig
            outcome, reason = REFUSED, "the rig could not carry that out"
            print("web command {}: {}".format(command.kind, error))
        done += 1
        try:
            app.web_status.record_command(command.as_record(outcome, reason))
            app.log_message(describe(command, outcome, reason))
        except Exception as error:
            print("web command log: {}".format(error))
    return done

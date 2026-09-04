"""What a browser may ask the rig to do, and how the rig gets to hear it.

Thread ownership is the whole design. The Qt main thread owns every worker
and is the only caller of a worker slot; the web thread must therefore never
call one. So a browser's request becomes a small record on a plain
`queue.Queue`, and the main thread drains that queue on a timer and calls the
very methods its own buttons call. A setpoint has one code path whether it
came from the rig's touchscreen or from a laptop.

Nothing here imports PyQt, and nothing here touches a device. `drain` is
handed the running `MainApp` and only ever calls methods that already exist
on it; every value is checked in the web thread before it is queued, so the
main thread is never asked to run a command it should have refused.
"""

import queue
import re
import time

#: Every kind of command a browser may send, in operating order.
KINDS = ("stop_all", "mfc", "plasma", "gauge", "sync", "zero")

#: Stopping the outputs is always allowed: it only ever drives the hardware
#: to zero, and a person who can see the rig must be able to do it whether
#: or not they typed a name and whether or not the switch on the rig is on.
ALWAYS_ALLOWED = ("stop_all",)

#: Everything else needs workers running to mean anything.
NEEDS_ACQUISITION = ("mfc", "plasma", "gauge", "sync", "zero")

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
NO_ACTOR = "no name is set in this browser"
NO_ACQUISITION = "no acquisition running"
NO_SAMPLES = "no samples to take a baseline from yet"
TOO_MANY = "too many commands are already waiting"


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


class CommandQueue(object):
    """The one crossing between the web thread and the Qt main thread."""

    def __init__(self, maxsize=MAX_QUEUED):
        self._queue = queue.Queue(maxsize=maxsize)
        self._next = 0

    def submit(self, kind, value, actor="", origin=""):
        """Queue a checked command and return it, or raise `Invalid`."""
        self._next += 1
        command = Command(self._next, kind, value, actor=actor, origin=origin)
        try:
            self._queue.put_nowait(command)
        except queue.Full:
            raise Invalid(TOO_MANY)
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


def validate(kind, body, number=None):
    """Check one body by kind. Raises `Invalid` with the reason to show."""
    if kind == "stop_all":
        return validate_stop_all(body)
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


def refusal(kind, remote, actor):
    """Why this command may not be queued, or an empty string if it may.

    Reading is open to anyone on the lab network. Setting needs two things
    at once: a name chosen in the browser, so the log says who, and the
    Remote switch turned on beside the rig's own screen, so nobody moves gas
    or cathode current past a person who is not there.
    """
    if kind in ALWAYS_ALLOWED:
        return ""
    if not remote:
        return NO_REMOTE
    if not clean_actor(actor):
        return NO_ACTOR
    return ""


def needs_acquisition(kind):
    """True when the command has no meaning without the workers running."""
    return kind in NEEDS_ACQUISITION


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


_APPLIERS = {
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
    if command.kind == "stop_all":
        return _apply_stop_all(app)
    worker = _APPLIERS.get(command.kind)
    if worker is None:
        return REFUSED, "that is not something this rig accepts"
    return worker(app, command.value)


def describe(command, outcome, reason):
    """The message-log line one command leaves behind, in plain ASCII."""
    who = command.actor or "someone"
    where = " from {}".format(command.origin) if command.origin else ""
    # The summary is a whole clause ("H2 flow 1234 mV", "baseline of Bu
    # taken"), so nothing is prefixed to it that only fits a setpoint.
    if outcome == APPLIED:
        tail = " ({})".format(reason) if reason else ""
        return "Remote: {}{}: {}{}".format(who, where, command.summary(), tail)
    return "Remote: {}{}: {} - refused, {}".format(
        who, where, command.summary(), reason
    )


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

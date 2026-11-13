"""Plasma current read with the filament off, said once in the Log.

queezz, 2026-11-13: "if we see the current with the filament power off, it's
a SUS. So we should warn, really. Sometimes the current sensor gets a wrong
zero".

What the files say. Across the runs of 2026-10-22 to 11-13, with the cathode
drive at 0 mV, `Ip_c` sat at -0.005 to -0.016 A and drifted slowly: that is
the Hall sensor's zero, and it is under any threshold. Exactly one stretch of
more than three seconds had the drive at 0 and `Ip_c` above 0.1 A: at
15:25 on 2026-11-13, 27 s at a flat 2.38 A after a discharge had been put
out, then -0.02 A (`cu_20261111_164721.csv`). Its cause is not known: a
sensor whose zero has moved, or current through the preanode circuit with
no filament to make a plasma. Either way it is not plasma current, and a
person reading the plot as if it were is misled.

A discharge outlives its drive by a second or two at most, so a reading has
to stay up for `HOLD_SECONDS` before it counts. "Up" is the PID's own
"lit", `Lit Above A` in settings.yml (0.1 A), on Ip as the PID sees it,
after the Ip zero. "Filament off" is the Kikusui's telemetry, while it is
fresh, measuring under `SUPPLY_OFF_BELOW_A` or its output off; without
fresh telemetry, the row's own cathode drive at 0 mV.

Nothing is zeroed or driven from here, and nothing is inferred: the Log says
what is seen and where to look, once when it starts and once when it ends.

Plain standard library; nothing here imports PyQt.
"""

import math

#: How long Ip must read above the lit threshold, with the filament off,
#: before it is said. A discharge whose drive went to zero has gone in under
#: this; the 2026-11-13 reading stayed for 27 s. Counted on the rows' own
#: times, so at 10 s sampling two rows in a row are enough.
HOLD_SECONDS = 3.0

#: The supply's measured current below which the filament is not heated.
#: A lit filament on this rig draws 15 to 20 A (17:50 on 2026-09-30: 15.5 A
#: at an 1800 mV drive).
SUPPLY_OFF_BELOW_A = 1.0

#: What a person should look at, in the order they can look at it.
ADVICE = (
    ": not plasma current. If the preanode supply's panel shows no current,"
    " the sensor's zero is off (Zero Ip with everything off); if it shows"
    " current, something conducts with the filament off."
)


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def filament_off(drive_mv, supply=None):
    """Whether the filament is off for one row, and the words that say how
    that is known; `(False, "")` when it is on or not known to be off.

    `supply` is the Kikusui telemetry snapshot the main thread holds. While
    it is fresh (`ok` or `dummy`) it decides: the supply's own measurement
    is the filament's power, which is what the warning is about. A drive of
    0 mV with the supply measuring 18 A is the filament run on the supply's
    own knob (CF10 off, `docs/hardware/cathode-control.md`), and its plasma
    current is plasma current. Without fresh telemetry, the row's own
    `PresetV_cathode` at 0 mV is the filament off; a stale or lost link
    never says off by itself.
    """
    supply = supply or {}
    if supply.get("status") in ("ok", "dummy"):
        if supply.get("output_on") == 0:
            return True, "the supply's output off"
        current = _number(supply.get("current_a"))
        if current is not None:
            if current < SUPPLY_OFF_BELOW_A:
                return True, "the supply at {:.2f} A".format(current)
            return False, ""
    if _number(drive_mv) == 0:
        return True, "cathode drive 0 mV"
    return False, ""


class FilamentOffCurrent:
    """Ip read above the lit threshold while the filament is off.

    `observe(at, ip, off, why)` takes one row at a time, in order: its time
    in seconds, Ip as the PID sees it (zero subtracted), and what
    `filament_off` said. It returns `(head, rest, alarm)` when the Log
    should say something, the head being the words a red line colours, and
    None otherwise. A NaN never counts as current.
    """

    def __init__(self, lit_above, hold_seconds=HOLD_SECONDS):
        self.lit_above = float(lit_above)
        self.hold_seconds = float(hold_seconds)
        self._since = None
        self._peak = None
        self._warned = False

    @property
    def warning(self):
        """True between the warning line and its end."""
        return self._warned

    def observe(self, at, ip, off, why=""):
        current = _number(ip)
        if not (off and current is not None and current > self.lit_above):
            return self._end(at)
        if self._since is None:
            self._since, self._peak = at, current
        else:
            self._peak = max(self._peak, current)
        if self._warned or at - self._since < self.hold_seconds:
            return None
        self._warned = True
        head = "Ip reads {:.2f} A with the filament off".format(current)
        if why:
            head += " ({})".format(why)
        return head, ADVICE, True

    def _end(self, at):
        since, peak, warned = self._since, self._peak, self._warned
        self._since = self._peak = None
        self._warned = False
        if not warned:
            return None
        return (
            "Ip no longer reads current with the filament off",
            ", after {:.0f} s at up to {:.2f} A".format(max(0.0, at - since), peak),
            False,
        )

    def close(self, at):
        """The run stopped. Its end line if a warning was standing, else None."""
        said = self._end(at)
        if said is None:
            return None
        head, rest, alarm = said
        return "Acquisition stopped while Ip still read current with the filament off", rest, alarm

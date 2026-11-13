"""The Raspberry Pi's own health, read on a thread of its own.

The I²C reads fail during plasma, and both deaths of 2026-09-09 (18:20:36
and 18:27:27) came while the preanode was dumping current to ground. That
evening `vcgencmd get_throttled` read `0x0` twelve days after boot, so the
supply was clean then (`.agents/directions.md`); but a Pi whose supply sags
under load would fail the same reads in the same way, and once read by hand
is not a record. So the program reads it, with the core temperature and the
free space under the data folder, every `INTERVAL_SECONDS`, and the Log
carries one line at start and a line only when something changes enough to
matter.

Three parts, each on the thread it belongs to:

- the readers (`read_throttled`, `read_temperature`, `read_free_bytes`)
  ask the Pi and answer None where there is nothing to ask: off the Pi
  there is no `vcgencmd` and no thermal zone, and that is not a failure;
- `PiHealthJudge` turns one reading after another into Log sentences;
- `PiHealthMonitor` does both on a daemon thread, `pi-health`, and hands
  each report to a callable it was given. `MainApp` gives it a queued Qt
  signal's `emit`, as the Kikusui recorder's messages cross, so the Log and
  the web record are written on the main thread. It never touches Qt, a
  worker or the ADC, and nothing waits on it.

The `get_throttled` word (Raspberry Pi documentation, `vcgencmd`): bit 0
under-voltage now, bit 1 ARM frequency capped now, bit 2 throttled now,
bit 3 soft temperature limit now; bits 16 to 19 the same four "has occurred
since boot". A "now" bit is only true at the moment of asking, and five
minutes is long enough for a sag to come and go between two asks, so a
since-boot bit that newly sets while its "now" bit is clear is said too:
that is the one record of a sag during a discharge.

Plain standard library; nothing here imports PyQt.
"""

import collections
import re
import shutil
import subprocess
import threading
import time

#: How often the Pi is read. Slow enough to be nothing to the Pi, quick
#: enough that a sag or a filling disk is in the Log the same quarter hour.
INTERVAL_SECONDS = 300.0

#: How long a stop waits for the thread. It holds no file or device past
#: one reading and is a daemon, so a reading still in `vcgencmd` then is
#: left to the interpreter.
STOP_WAIT_SECONDS = 0.5

#: How long one `vcgencmd` may take before the reading goes without it.
VCGENCMD_TIMEOUT_SECONDS = 5.0

#: Where the Pi's kernel keeps the core temperature, in millidegrees.
THERMAL_ZONE = "/sys/class/thermal/thermal_zone0/temp"

#: The core is said to run hot at this and cool again under the second;
#: the gap keeps a core sitting at the line from writing a line a reading.
#: The Pi's own soft limit is 80 °C (that is bit 3 above), so 70 °C is a
#: warning with room left before it throttles.
HOT_C = 70.0
COOL_C = 65.0

#: Free space under the data folder below which the Log says so. A day at
#: 0.1 s sampling is about a hundred megabytes; two gigabytes is weeks of
#: that, and enough warning to move files off before a write fails.
LOW_DISK_BYTES = 2e9

#: The four conditions of `get_throttled`, by bit, in the Pi's own words.
FLAGS = (
    (0, "under-voltage"),
    (1, "ARM frequency capped"),
    (2, "throttled"),
    (3, "soft temperature limit"),
)

#: How far the "has occurred since boot" half is shifted from "now".
SINCE_BOOT_SHIFT = 16

#: What `/api/health` carries as `pi` before the first reading, and the
#: keys of every reading after it.
UNREAD = {
    "temperature_c": None,
    "throttled": None,
    "now": [],
    "since_boot": [],
    "free_gb": None,
    "checked_at": None,
}

#: One reading: the `get_throttled` word, the core in °C, the free bytes
#: under the data folder (each None where it could not be read), and when.
Reading = collections.namedtuple(
    "Reading", ("throttled", "temperature_c", "free_bytes", "at")
)

#: What the monitor hands over: the reading, and the Log sentences it made,
#: each as `(text, alarm)`; an alarm is written red.
Report = collections.namedtuple("Report", ("reading", "lines"))


# -- asking the Pi -------------------------------------------------------------


def parse_throttled(text):
    """The word in `throttled=0x50000`, as an integer; None if absent."""
    match = re.search(r"throttled=(0x[0-9a-fA-F]+)", str(text or ""))
    return int(match.group(1), 16) if match else None


def read_throttled(run=subprocess.run, which=shutil.which):
    """`vcgencmd get_throttled`, or None off a Pi or when it cannot be run.

    `which` is asked first, so a machine without `vcgencmd` never starts a
    process at all.
    """
    if which("vcgencmd") is None:
        return None
    try:
        done = run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=VCGENCMD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_throttled(getattr(done, "stdout", ""))


def read_temperature(path=THERMAL_ZONE):
    """The core temperature in °C, or None where there is no thermal zone."""
    try:
        with open(path, "r") as zone:
            return int(zone.read().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def read_free_bytes(folder):
    """Free bytes on the filesystem that holds `folder`, or None."""
    try:
        return shutil.disk_usage(folder).free
    except (OSError, TypeError, ValueError):
        return None


def read_pi(folder, throttled=None, temperature=None, free=None, clock=time.time):
    """One reading of all three. A reader that raises reads as None: a
    reading is a convenience and nothing about it may stop the thread."""

    def ask(reader, *args):
        try:
            return reader(*args)
        except Exception:  # noqa: BLE001 -- not available, never a failure
            return None

    return Reading(
        throttled=ask(throttled or read_throttled),
        temperature_c=ask(temperature or read_temperature),
        free_bytes=ask(free or read_free_bytes, folder),
        at=clock(),
    )


# -- what a reading says -------------------------------------------------------


def flags(word, shift=0):
    """The names of the conditions set in `word`, in the Pi's order."""
    if word is None:
        return []
    return [name for bit, name in FLAGS if word & (1 << (bit + shift))]


def gigabytes(free_bytes):
    """Free space as a person reads it: `41 GB`, `1.8 GB`."""
    value = free_bytes / 1e9
    return "{:.0f} GB".format(value) if value >= 10 else "{:.1f} GB".format(value)


def as_json(reading):
    """A reading in the shape `/api/health` carries as `pi`."""
    if reading is None:
        return dict(UNREAD)
    word = reading.throttled
    return {
        "temperature_c": None
        if reading.temperature_c is None
        else round(float(reading.temperature_c), 1),
        "throttled": None if word is None else "0x{:x}".format(word),
        "now": flags(word),
        "since_boot": flags(word, SINCE_BOOT_SHIFT),
        "free_gb": None
        if reading.free_bytes is None
        else round(reading.free_bytes / 1e9, 1),
        "checked_at": reading.at,
    }


def _power_words(word):
    if word is None:
        return "power flags not available"
    now = flags(word)
    if now:
        return ", ".join(name + " now" for name in now)
    since = flags(word, SINCE_BOOT_SHIFT)
    if since:
        return "power fine now ({} since boot)".format(", ".join(since))
    return "power fine"


def describe(reading):
    """The start line's words: `52.1 °C, power fine, 41 GB free`."""
    temperature = (
        "temperature not available"
        if reading.temperature_c is None
        else "{:.1f} °C".format(reading.temperature_c)
    )
    disk = (
        "free disk not available"
        if reading.free_bytes is None
        else "{} free".format(gigabytes(reading.free_bytes))
    )
    return "{}, {}, {}".format(temperature, _power_words(reading.throttled), disk)


class PiHealthJudge:
    """One reading after another, into the Log's sentences.

    `see(reading)` returns `[(text, alarm), ...]`: the start line for the
    first reading, then only what changed. Something not available stays
    quiet; it says nothing new, and a Pi that cannot be read for a moment is
    not a Pi in trouble.
    """

    def __init__(self, hot_c=HOT_C, cool_c=COOL_C, low_bytes=LOW_DISK_BYTES):
        self._hot_c = hot_c
        self._cool_c = cool_c
        self._low_bytes = low_bytes
        self._started = False
        self._word = None
        self._hot = False
        self._low = False

    def see(self, reading):
        if not self._started:
            return [self._start(reading)]
        lines = []
        lines.extend(self._power(reading.throttled))
        lines.extend(self._temperature(reading.temperature_c))
        lines.extend(self._disk(reading.free_bytes))
        return lines

    def _start(self, reading):
        self._started = True
        self._word = reading.throttled
        self._hot = reading.temperature_c is not None and reading.temperature_c >= self._hot_c
        self._low = reading.free_bytes is not None and reading.free_bytes < self._low_bytes
        alarm = bool(flags(reading.throttled)) or self._hot or self._low
        return "Pi health: " + describe(reading), alarm

    def _power(self, word):
        if word is None:
            return []
        before, self._word = self._word, word
        if before is None:
            return []
        now, was = set(flags(word)), set(flags(before))
        since = set(flags(word, SINCE_BOOT_SHIFT)) - set(flags(before, SINCE_BOOT_SHIFT))
        named = "get_throttled 0x{:x}".format(word)
        lines = []
        began = [name for _, name in FLAGS if name in now - was]
        ended = [name for _, name in FLAGS if name in was - now]
        # Set and cleared again between two asks: only the since-boot bit
        # remembers it, and this is the line that would have been missed.
        between = [name for _, name in FLAGS if name in since - now - was]
        if began:
            lines.append(("Pi: {} now ({})".format(", ".join(began), named), True))
        if between:
            lines.append((
                "Pi: {} came and went since the last check ({})".format(
                    ", ".join(between), named),
                True,
            ))
        if ended:
            lines.append(("Pi: {} over ({})".format(", ".join(ended), named), False))
        return lines

    def _temperature(self, celsius):
        if celsius is None:
            return []
        if not self._hot and celsius >= self._hot_c:
            self._hot = True
            return [("Pi at {:.1f} °C, above {:.0f} °C".format(celsius, self._hot_c), True)]
        if self._hot and celsius < self._cool_c:
            self._hot = False
            return [("Pi back to {:.1f} °C, under {:.0f} °C".format(celsius, self._cool_c), False)]
        return []

    def _disk(self, free_bytes):
        if free_bytes is None:
            return []
        limit = gigabytes(self._low_bytes)
        if not self._low and free_bytes < self._low_bytes:
            self._low = True
            return [("Pi: {} free under the data folder, less than {}".format(
                gigabytes(free_bytes), limit), True)]
        if self._low and free_bytes >= self._low_bytes:
            self._low = False
            return [("Pi: {} free under the data folder again".format(
                gigabytes(free_bytes)), False)]
        return []


# -- the thread ----------------------------------------------------------------


def _say(text):
    """Print, if there is still somewhere to print to. A program whose
    terminal was closed under it (SIGHUP) has a stdout that raises."""
    try:
        print(text)
    except Exception:  # noqa: BLE001
        pass


class PiHealthMonitor:
    """Read the Pi on a thread of its own and hand each report over.

    `report(Report)` is called on this thread; the caller makes it safe to
    call from here (MainApp passes a queued Qt signal's `emit`). `read` is
    one reading, injectable so a test answers without a Pi.
    """

    def __init__(self, folder, report, interval=None, read=None, judge=None):
        self._folder = folder
        self._report = report
        self._interval = INTERVAL_SECONDS if interval is None else float(interval)
        self._read = read if read is not None else (lambda: read_pi(folder))
        self._judge = judge if judge is not None else PiHealthJudge()
        self._stop = threading.Event()
        self._thread = None

    @property
    def thread(self):
        return self._thread

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="pi-health", daemon=True)
        self._thread.start()

    def check_once(self):
        """One reading, judged and handed over. Never raises."""
        try:
            reading = self._read()
            lines = self._judge.see(reading)
        except Exception as error:  # noqa: BLE001 -- the thread outlives any reading
            _say("pi health: {}".format(error))
            return None
        report = Report(reading, lines)
        if self._stop.is_set():
            return report
        try:
            self._report(report)
        except Exception as error:  # noqa: BLE001 -- a receiver gone at shutdown
            _say("pi health report: {}".format(error))
        return report

    def _run(self):
        while not self._stop.is_set():
            self.check_once()
            self._stop.wait(self._interval)

    def stop(self, timeout=STOP_WAIT_SECONDS):
        """Ask the thread to end and wait a moment; True once it has."""
        self._stop.set()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

"""What the web thread is allowed to know about the running rig.

The Qt main thread owns every worker; this module owns nothing but a few
plain values behind a lock. Nothing here imports PyQt, and nothing here
reaches for a worker, a device or a file. The main thread writes; the web
thread reads a copy.
"""

import sys
import threading

# The dummy stubs are imported under either name depending on how the
# package was entered, so both spellings count as "the stubs are loaded".
_DUMMY_MODULES = ("devices.dummy", "controlunit.devices.dummy")

SERVICE = "controlunit"


def dummy_hardware_loaded():
    """True when the off-rig stubs stand in for the real boards."""
    return any(name in sys.modules for name in _DUMMY_MODULES)


class RigStatus:
    """A small locked record of what the rig is doing right now."""

    def __init__(self, channels=0, sampling=None):
        self._lock = threading.RLock()
        self._acquiring = False
        self._channels = int(channels or 0)
        self._sampling = sampling

    def describe_run(self, channels, sampling):
        """Record the channel count and sampling time the config declares."""
        with self._lock:
            self._channels = int(channels or 0)
            self._sampling = sampling

    def set_acquiring(self, running):
        """Record whether the acquisition threads are running."""
        with self._lock:
            self._acquiring = bool(running)

    def read(self):
        """A snapshot the web thread may keep and use without the lock."""
        with self._lock:
            return {
                "acquiring": self._acquiring,
                "channels": self._channels,
                "sampling": self._sampling,
                "dummy": dummy_hardware_loaded(),
            }


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
    if snapshot.get("dummy"):
        return "{}, dummy hardware".format(acquiring)
    return acquiring


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

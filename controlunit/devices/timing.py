"""Monotonic scheduling and bounded-cost acquisition diagnostics."""

import math
import time


class SampleClock:
    """Keep scheduled periods; after an overrun wait a fresh period.

    Late slots are counted, never replayed as a burst of catch-up samples.
    The same deadline is a fast scan's start or an averaged window's end.
    """

    def __init__(self, period, now):
        self.period = period
        self.due = now + period

    def remaining(self, now):
        return max(0.0, self.due - now)

    def advance(self, now):
        self.due += self.period
        if now < self.due:
            return 0
        missed = math.floor((now - self.due) / self.period) + 1
        self.due = now + self.period
        return missed


class TimingDiagnostics:
    """Aggregate stage durations; report every 30 s and the first slowdown.

    No per-sample I/O or retained sample arrays. Durations are monotonic
    seconds; counts (such as missed slots) are reported separately.
    """

    def __init__(self, label, emit, clock=time.monotonic):
        self.label, self.emit, self.clock = label, emit, clock
        self.started = clock()
        self.last_warning = float('-inf')
        self.count = 0
        self.durations = {}
        self.missed = 0
        self.slowest_channel = ('none', 0.0)

    def observe(self, durations, *, missed=0, slow=False, channel=None):
        now = self.clock()
        self.count += 1
        self.missed += missed
        for name, value in durations.items():
            if value is None:
                continue
            total, maximum, count = self.durations.get(name, (0.0, 0.0, 0))
            self.durations[name] = (total + value, max(maximum, value), count + 1)
        if channel and channel[1] > self.slowest_channel[1]:
            self.slowest_channel = channel
        warning = slow and now - self.last_warning >= 30.0
        if warning or now - self.started >= 30.0:
            if warning:
                self.last_warning = now
            self.report(now, warning)

    def report(self, now=None, warning=False):
        if not self.count:
            return
        if now is None:
            now = self.clock()
        parts = [
            f"{name} mean/max {total / count * 1000:.1f}/{maximum * 1000:.1f} ms"
            for name, (total, maximum, count) in self.durations.items()
        ]
        channel, duration = self.slowest_channel
        if duration:
            parts.append(f"slowest channel {channel} {duration * 1000:.1f} ms")
        self.emit(
            f"{self.label}{' overrun' if warning else ''}: {self.count} observations"
            f" in {now - self.started:.1f} s; " + '; '.join(parts)
            + f"; missed slots {self.missed}"
        )
        self.started = now
        self.count = 0
        self.durations.clear()
        self.missed = 0
        self.slowest_channel = ('none', 0.0)

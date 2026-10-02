"""The plasma-current loop: a PI controller on the cathode drive.

It replaces the `simple_pid` object the reader used to hold, for one
reason: what happens at the moment the loop takes over. The old loop's
clock ran from the last time anything touched it, so its first step
integrated the error over the whole manual stretch before, on top of a
fixed 1000 mV: on 2026-10-02 three engagements started at 1728, 1759 and
1000 mV, none of them the drive already held, and the third put the plasma
out. On 2026-09-14 the same arithmetic produced 5500 mV.

`engage` is the takeover written down: the clock starts now, and the
integral is set so that the first command is the drive the cathode already
holds. From there the loop moves at the integral's own pace and no faster.

`ramp` is what the loop does while there is no discharge to regulate. A PI
loop facing an unlit source integrates an error that is not telling it
anything: how fast it walks the filament up depends on the setpoint asked
for, and nothing stops the walk. So without a discharge the drive goes up
at a fixed rate to a ceiling and waits there, and the integral is kept
where a PI step would carry on from that drive, so the moment the plasma
lights the loop takes over without a step.
"""

import time


def _clamp(value, limits):
    low, high = limits
    if value < low:
        return low
    if value > high:
        return high
    return value


class CathodeLoop:
    """Proportional and integral on `setpoint - measured`; output in mV."""

    def __init__(self, kp, ki, kd=0.0, setpoint=0.0, limits=(0.0, 5000.0),
                 sample_time=0.3, clock=time.monotonic):
        self.kp, self.ki, self.kd = float(kp), float(ki), float(kd)
        self.setpoint = float(setpoint)
        self.limits = (float(limits[0]), float(limits[1]))
        self.sample_time = float(sample_time)
        self._clock = clock
        self._integral = 0.0
        self._drive = 0.0
        self._last_time = clock()
        self._last_output = None
        self._last_measured = None

    @property
    def tunings(self):
        return self.kp, self.ki, self.kd

    @tunings.setter
    def tunings(self, values):
        self.kp, self.ki, self.kd = (float(value) for value in values)

    def engage(self, drive, measured=None):
        """Take over from `drive` mV: the first command will be that value.

        `measured` is the current the loop is about to see. Without it the
        proportional term is taken as zero, which is exact whenever the
        current already sits at the setpoint.
        """
        drive = _clamp(float(drive), self.limits)
        error = 0.0 if measured is None else self.setpoint - float(measured)
        self._integral = _clamp(drive - self.kp * error, self.limits)
        self._drive = drive
        self._last_time = self._clock()
        self._last_output = None
        self._last_measured = None if measured is None else float(measured)
        return drive

    def ramp(self, measured, rate, ceiling):
        """One step with no discharge: up at `rate` mV/s, never past `ceiling`.

        A drive already above the ceiling comes down to it at once: the
        ceiling is what an unlit filament may be given, however the loop
        got here. Between sample times the last command is repeated, as in
        a regulating step.
        """
        now = self._clock()
        elapsed = now - self._last_time
        if self._last_output is not None and elapsed < self.sample_time:
            return self._last_output
        measured = float(measured)
        drive = min(self._drive + float(rate) * max(elapsed, 0.0), float(ceiling))
        drive = _clamp(drive, self.limits)
        # Where a regulating step would have to stand to give this drive.
        self._integral = _clamp(drive - self.kp * (self.setpoint - measured), self.limits)
        self._drive = drive
        self._last_time = now
        self._last_output = drive
        self._last_measured = measured
        return drive

    def __call__(self, measured):
        """One step. Between sample times the last command is repeated."""
        now = self._clock()
        elapsed = now - self._last_time
        if self._last_output is not None and elapsed < self.sample_time:
            return self._last_output
        elapsed = max(elapsed, 0.0)
        measured = float(measured)
        error = self.setpoint - measured
        # The integral stops at the limits, so a command pinned at one of
        # them leaves as soon as the error changes sign.
        self._integral = _clamp(self._integral + self.ki * error * elapsed, self.limits)
        derivative = 0.0
        if self.kd and elapsed > 0 and self._last_measured is not None:
            derivative = -self.kd * (measured - self._last_measured) / elapsed
        output = _clamp(self.kp * error + self._integral + derivative, self.limits)
        self._drive = output
        self._last_time = now
        self._last_output = output
        self._last_measured = measured
        return output

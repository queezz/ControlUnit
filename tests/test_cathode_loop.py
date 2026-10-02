"""The plasma-current loop takes over from the drive the cathode holds.

The three engagements of 2026-10-02 are the cases. The old loop started
each one at 1000 mV plus forty times the error times the seconds since
anybody last touched it: 1728, 1759 and 1000 mV, none of them the 1790 mV
or the nothing the cathode actually held, and the third put the plasma out.
The same arithmetic gave 5500 mV on 2026-09-14 after a long manual stretch.
"""

import pytest

from controlunit.devices import adc as adc_module
from controlunit.devices.cathode_loop import CathodeLoop
from test_adc_average import qt_app, home, worker  # noqa: F401 -- shared fixtures


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def loop(clock, setpoint):
    return CathodeLoop(30, 40, 0, setpoint=setpoint, sample_time=0.3, clock=clock)


# MARK: the loop alone


@pytest.mark.parametrize(
    "held, measured, setpoint",
    [
        (1790.0, 0.53, 0.70),   # 17:26:02: started at 1728 mV, sag to 0.30 A
        (1790.0, 0.71, 0.50),   # 17:47:58: started at 1000 mV, plasma out
        (1800.0, 0.50, 0.50),   # already where it is asked to be
    ],
)
def test_the_first_command_is_the_drive_already_held(held, measured, setpoint):
    clock = Clock()
    pid = loop(clock, setpoint)
    clock.advance(600)                      # ten manual minutes before engaging
    pid.engage(held, measured)
    clock.advance(0.1)                      # the next sample
    first = pid(measured)
    assert first == pytest.approx(held, abs=1.0)


def test_the_loop_moves_at_the_integrals_pace_after_taking_over():
    clock = Clock()
    pid = loop(clock, 0.70)
    pid.engage(1790.0, 0.53)
    commands = []
    for _ in range(10):                     # ten steps, a little over 0.3 s each
        clock.advance(0.31)
        commands.append(pid(0.53))
    # 40 mV per ampere-second on 0.17 A of error: 6.8 mV a second, no jump.
    assert commands[0] == pytest.approx(1790.0 + 40 * 0.17 * 0.31, abs=0.01)
    assert commands[-1] == pytest.approx(1790.0 + 40 * 0.17 * 3.1, abs=0.01)
    steps = [b - a for a, b in zip(commands, commands[1:])]
    assert max(steps) < 2.5


def test_between_sample_times_the_last_command_is_repeated():
    clock = Clock()
    pid = loop(clock, 0.5)
    pid.engage(1700.0, 0.4)
    clock.advance(0.3)
    first = pid(0.4)
    clock.advance(0.1)
    assert pid(0.1) == first                # too soon: not a new step


def test_the_integral_stops_at_the_limits_and_comes_back_at_once():
    clock = Clock()
    pid = loop(clock, 0.5)
    pid.engage(4990.0, -0.1)
    for _ in range(100):                    # thirty seconds of unreachable setpoint
        clock.advance(0.3)
        assert pid(-0.1) <= 5000.0
    clock.advance(0.3)
    assert pid(1.0) < 5000.0                # the first step with the error reversed


# MARK: the reader that holds it


def hold(worker, current, supply=5.0):
    """Give the reader one scan in which the Hall sensor reads `current`."""
    ratio = worker.adc_channels["Ip"].zero_ratio
    values = dict.fromkeys(worker.adc_signals_columns, 0.1)
    values.update(Ip=supply * (ratio + current / 25), Vhall=supply)
    worker.hold_voltages(values)


@pytest.fixture
def driven(worker):
    clock = Clock()
    worker._pid_clock = clock
    worker.prep_pid()
    worker.commands = []
    worker.messages = []
    worker.send_control_voltage.connect(worker.commands.append)
    worker.send_message.connect(worker.messages.append)
    return worker, clock


def test_engaging_from_a_manual_drive_starts_from_that_drive(driven):
    worker, clock = driven
    worker.set_manual_drive.emit(1790.0)
    assert worker.commands == []            # telling the reader moves no DAC
    clock.advance(105)                      # the manual stretch of 17:24 to 17:26
    hold(worker, 0.53)
    worker.set_plasma_current.emit(0.70)
    clock.advance(0.1)
    worker.plasma_current_control()
    assert worker.commands[-1] == pytest.approx(1790.0, abs=1.0)
    assert "engaged at 1790 mV (the drive already held)" in worker.messages[-1]


def test_engaging_above_the_setpoint_does_not_drop_the_drive(driven):
    """17:47:58: 0.71 A held by hand, 0.50 A asked for, 1000 mV sent."""
    worker, clock = driven
    worker.set_manual_drive.emit(1790.0)
    clock.advance(20)
    hold(worker, 0.71)
    worker.set_plasma_current.emit(0.50)
    seen = []
    for _ in range(10):
        clock.advance(0.3)
        worker.plasma_current_control()
        seen.append(worker.commands[-1])
    assert seen[0] == pytest.approx(1790.0, abs=3.0)
    assert min(seen) > 1760.0               # down at 8 mV a second, not to 1000


def test_engaging_with_the_cathode_off_is_a_cold_start(driven):
    worker, clock = driven
    worker.set_plasma_current.emit(0)       # PID off: the drive goes to zero
    assert worker.commands == [0]
    clock.advance(31)
    hold(worker, 0.0)
    worker.set_plasma_current.emit(0.50)
    clock.advance(0.1)
    worker.plasma_current_control()
    assert worker.commands[-1] == pytest.approx(adc_module.COLD_START_MV, abs=3.0)
    assert any("a cold start" in line for line in worker.messages)


def test_changing_the_setpoint_of_a_running_loop_does_not_restart_it(driven):
    worker, clock = driven
    worker.set_manual_drive.emit(1800.0)
    hold(worker, 0.70)
    worker.set_plasma_current.emit(0.70)
    engaged = worker.pid
    for _ in range(5):
        clock.advance(0.3)
        worker.plasma_current_control()
    worker.set_plasma_current.emit(0.60)
    assert worker.pid is engaged
    assert worker.pid.setpoint == pytest.approx(0.60)
    assert sum("engaged" in line for line in worker.messages) == 1


def test_the_row_records_the_manual_drive(driven):
    worker, _ = driven
    hold(worker, 0.5)
    worker.set_manual_drive.emit(1800.0)
    worker.put_new_data_in_dataframe()
    assert worker.adc_values.iloc[-1]["PresetV_cathode"] == 1800.0
    worker.set_plasma_current.emit(0)       # drive off
    worker.put_new_data_in_dataframe()
    assert worker.adc_values.iloc[-1]["PresetV_cathode"] == 0


def test_the_zero_is_subtracted_before_the_loop_sees_the_current(driven):
    worker, clock = driven
    worker.set_zero("Ip", -0.1)
    worker.set_manual_drive.emit(1790.0)
    hold(worker, 0.40)                      # reads 0.40, is 0.50 above its zero
    worker.set_plasma_current.emit(0.50)
    for _ in range(10):
        clock.advance(0.3)
        worker.plasma_current_control()
    assert worker.commands[-1] == pytest.approx(1790.0, abs=0.5)   # no error to chase


def test_the_loop_follows_a_sampling_change(driven):
    worker, _ = driven
    worker.set_sampling_time(1.0)
    assert worker.pid.sample_time == pytest.approx(1.0 * worker.STEP)
    worker.set_sampling_time(0.1)
    assert worker.pid.sample_time == pytest.approx(0.1 * worker.STEP)



# MARK: with no discharge to regulate
#
# queezz, 2026-10-02, on whether the loop should light a cold plasma at all:
# "Since PID could light a cold plasma, that means we should try and improve
# it." The one clean cold start of that day walked up from 1000 mV at
# 24 mV/s and lit without overshoot, but only because the setpoint happened
# to be 0.5 A: the walk's pace was the integral of an error that says
# nothing while the source is unlit, and nothing stopped it.


def cold(worker, clock, setpoint):
    worker.set_plasma_current.emit(0)
    hold(worker, 0.0)
    worker.set_plasma_current.emit(setpoint)


def run(worker, clock, seconds, current):
    for _ in range(int(round(seconds / 0.31))):
        clock.advance(0.31)
        hold(worker, current)
        worker.plasma_current_control()
    return worker.commands[-1]


@pytest.mark.parametrize("setpoint", [0.3, 0.5, 1.5])
def test_an_unlit_loop_walks_up_at_one_pace_whatever_the_setpoint(driven, setpoint):
    worker, clock = driven
    cold(worker, clock, setpoint)
    after = run(worker, clock, 10.0, 0.0)
    walked = 0.31 * int(round(10.0 / 0.31))
    assert after == pytest.approx(adc_module.COLD_START_MV + 25.0 * walked, abs=1.0)
    assert sum("walking the drive up at 25 mV/s" in line for line in worker.messages) == 1


def test_an_unlit_loop_stops_at_the_ceiling_and_says_so_once(driven):
    worker, clock = driven
    cold(worker, clock, 0.5)
    run(worker, clock, 120.0, 0.0)             # far longer than the walk takes
    assert max(worker.commands) == adc_module.UNLIT_CEILING_MV
    assert worker.commands[-1] == adc_module.UNLIT_CEILING_MV
    assert sum("no discharge at the 1900 mV ceiling" in line for line in worker.messages) == 1


def test_when_the_plasma_lights_the_loop_carries_on_from_where_the_walk_was(driven):
    worker, clock = driven
    cold(worker, clock, 0.5)
    walked_to = run(worker, clock, 26.0, 0.0)  # 2026-10-02: lit near 1650 mV
    assert 1600 < walked_to < 1700
    clock.advance(0.31)
    hold(worker, 0.20)                         # the discharge appears
    worker.plasma_current_control()
    assert worker.commands[-1] == pytest.approx(walked_to, abs=6.0)
    assert "discharge lit at" in worker.messages[-1]
    # And from there it regulates: 0.3 A of error is 12 mV a second.
    before = worker.commands[-1]
    after = run(worker, clock, 3.1, 0.20)
    assert after - before == pytest.approx(40 * 0.3 * 3.1, abs=1.0)


def test_an_arc_is_not_the_plasma_going_out(driven):
    """An arc takes the current to zero for 0.2 to 0.3 s; the loop regulates
    straight through it and nothing is said."""
    worker, clock = driven
    worker.set_manual_drive.emit(2000.0)        # lit, and above the ceiling
    hold(worker, 0.50)
    worker.set_plasma_current.emit(0.50)
    run(worker, clock, 3.0, 0.50)
    said = len(worker.messages)
    run(worker, clock, 0.62, 0.0)              # two samples of nothing
    run(worker, clock, 3.0, 0.50)
    assert len(worker.messages) == said
    assert min(worker.commands[-25:]) > 1990.0


def test_a_plasma_that_goes_out_brings_the_drive_down_to_the_ceiling(driven):
    worker, clock = driven
    worker.set_manual_drive.emit(2000.0)
    hold(worker, 0.50)
    worker.set_plasma_current.emit(0.50)
    run(worker, clock, 3.0, 0.50)
    run(worker, clock, 5.0, 0.0)               # gone for good
    assert worker.commands[-1] == adc_module.UNLIT_CEILING_MV
    assert "no discharge at the 1900 mV ceiling" in worker.messages[-1]
    # It comes back: the loop lights it from the ceiling and regulates again.
    # (The proportional term answers the current appearing: 30 mV/A of it.)
    run(worker, clock, 0.31, 0.45)
    assert "discharge lit at" in worker.messages[-1]
    assert worker.commands[-1] == pytest.approx(adc_module.UNLIT_CEILING_MV - 30 * 0.45, abs=2.0)


def test_engaging_unlit_from_a_drive_above_the_ceiling_starts_at_the_ceiling(driven):
    worker, clock = driven
    worker.set_manual_drive.emit(2300.0)        # held by hand, nothing lit
    hold(worker, 0.0)
    worker.set_plasma_current.emit(0.50)
    clock.advance(0.31)
    worker.plasma_current_control()
    assert worker.commands[-1] == adc_module.UNLIT_CEILING_MV


def test_the_walk_is_set_in_the_settings_file(worker):
    assert worker.cold_start_mv == 1000.0
    assert worker.unlit_ramp == 25.0
    assert worker.unlit_ceiling == 1900.0
    assert worker.lit_above == pytest.approx(0.1)
    assert worker.unlit_after == pytest.approx(2.0)


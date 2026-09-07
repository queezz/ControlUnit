"""A worker's sleep between steps ends the moment it is told to abort.

The rig samples every ten seconds on long runs, and its workers used to
sleep a whole period before looking at the abort flag, so the Qt window's
quit button came back ten seconds after Stop (owner report 2026-09-07).
"""

import threading
import time

from controlunit.devices.device import sleep_unless_aborted


def test_a_sleep_runs_its_course_when_nobody_aborts():
    started = time.monotonic()
    assert sleep_unless_aborted(0.25, lambda: False, slice_seconds=0.05) is True
    assert time.monotonic() - started >= 0.24


def test_a_sleep_ends_within_a_slice_of_the_abort():
    flag = {"abort": False}

    def abort_soon():
        time.sleep(0.15)
        flag["abort"] = True

    threading.Thread(target=abort_soon, daemon=True).start()
    started = time.monotonic()
    assert sleep_unless_aborted(10.0, lambda: flag["abort"], slice_seconds=0.05) is False
    assert time.monotonic() - started < 1.0


def test_an_abort_already_set_costs_no_sleep_at_all():
    started = time.monotonic()
    assert sleep_unless_aborted(10.0, lambda: True) is False
    assert time.monotonic() - started < 0.05

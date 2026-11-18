import argparse
import contextlib
import html
import signal
import sys, datetime, os
import threading
import time
import traceback
import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets, QtGui

from mainView import UIWindow
from controlunit.devices.adc import ADC, LIT_ABOVE_A
from controlunit.history import RunHistory
from controlunit.devices.timing import TimingDiagnostics
from controlunit.devices.dac8532 import DAC8532
from controlunit.devices.mcp4725 import MCP4725
from controlunit.devices.kikusui import (
    KikusuiLogger,
    is_output_failure,
    load_config as load_kikusui_config,
    set_output as set_supply_output,
)

import readsettings
from striphtmltags import strip_tags
from controlunit.trigger_signal import IndicatorLED

from controlunit.ui.text_shortcuts import RED, BLUE, RESET
from controlunit.ui.widgets.graph import Graph

# Plain standard library: a few locked values the optional web view reads,
# and the queue it puts commands on. Nothing here imports Flask, so a machine
# without it starts as it always did.
from controlunit.web.status import (
    BEHIND_SECONDS,
    CATHODE_PEN,
    RigStatus,
    sidecar_epoch,
    stale_after,
    dummy_hardware_loaded,
)
from controlunit.web import commands as web_commands
# The gauges and the sampling time, as the screen last showed them; the
# same plain standard library, kept in this machine's settings folder.
from controlunit import screen_memory
# The ion gauges' on and off, as operators record it in the PIHTI Diagram.
from controlunit import diagram_follower
# The Raspberry Pi's own supply flags, temperature and free disk, read on a
# thread of its own; and Ip read with the filament off. Both plain library.
from controlunit import pi_health
from controlunit import filament_off

#: How often the main thread looks at when the last sample arrived.
READER_CHECK_MS = 2000

#: How often the main thread takes the Diagram's newest answer and looks at
#: the switches it is checking. The Diagram is asked every ten seconds on a
#: thread of its own (`diagram_follower.POLL_SECONDS`); this only picks up.
DIAGRAM_CHECK_MS = 3000

#: The signals that end the program through Stop's own path, and what each
#: one means for a person reading why it ended. SIGHUP is what closing the
#: terminal it runs from sends; SIGTERM is `kill`, a service manager or a
#: shutdown; SIGINT is Ctrl+C. Windows has no SIGHUP and is passed over.
STOP_SIGNALS = (
    ("SIGTERM", "asked to stop by another program (kill, a service manager or a shutdown)"),
    ("SIGHUP", "the terminal it ran from was closed, or its session ended"),
    ("SIGINT", "Ctrl+C in the terminal it ran from"),
)

#: How often the main thread looks for a signal that has arrived. Python
#: runs its own signal handlers only between its own bytecodes, and Qt's
#: event loop is C++, so without this a SIGTERM to an idle window would wait
#: for the next Python slot to run at all. The handler only notes the
#: signal; this timer's slot acts on it, inside the event loop.
SIGNAL_CHECK_MS = 250

#: How long the same uncaught error waits before the Log carries it again.
#: An error no code catches no longer ends the program, so one raised by a
#: timer's slot would otherwise be a line every tick for as long as it runs;
#: the next line after the minute says how many were held back meanwhile,
#: as a refused press's does (`web.commands.REFUSAL_REPEAT_SECONDS`).
UNCAUGHT_REPEAT_SECONDS = 60.0


def signal_reason(signum):
    """How a Log line names the signal that ended the program."""
    for name, words in STOP_SIGNALS:
        if getattr(signal, name, None) == signum:
            return "{}, {}".format(name, words)
    return "signal {}".format(signum)


def describe_exception(kind, error, trace):
    """The traceback's last line, and where it was raised: `ZeroDivisionError:
    division by zero (in _adc_step, main.py line 1340)`. The whole traceback
    goes to stderr, which the launcher keeps in a file beside the data."""
    words = traceback.format_exception_only(kind, error)[-1].strip()
    frames = traceback.extract_tb(trace) if trace is not None else []
    if frames:
        last = frames[-1]
        words += " (in {}, {} line {})".format(
            last.name, os.path.basename(last.filename), last.lineno
        )
    return words


def _quiet_print(text):
    """Print, if there is still somewhere to print to: a program whose
    terminal was closed under it (SIGHUP) has a stdout that raises."""
    try:
        print(text)
    except Exception:  # noqa: BLE001
        pass


def _epoch(stamp):
    """Seconds since the epoch for a delivered row's `date`.

    The rows are stamped with the naive local `datetime.now()`, and pandas
    hands them back as `Timestamp`s, whose own `.timestamp()` reads a naive
    stamp as UTC: nine hours out on the rig's JST clock. Through the plain
    `datetime` it is read as local time, as it was written.
    """
    return getattr(stamp, "to_pydatetime", lambda: stamp)().timestamp()


def _thread_name():
    """What a Log line calls the thread it is on: the worker's own name for
    a hardware thread (`ADC`, `MFCs`, `PlasmaCurrent`, set in `prep_worker`),
    else Python's name for it."""
    try:
        name = QtCore.QThread.currentThread().objectName()
    except Exception:  # noqa: BLE001 -- a name is never worth an error
        name = ""
    return name or threading.current_thread().name


class _Repeats:
    """The same thing said once a `seconds`, from any thread.

    `note(key)` answers `(say, tail)`: whether to say it now, and the words
    to end the line with when earlier repeats were held back.
    """

    #: Kept keys past which the expired ones are forgotten.
    KEEP = 64

    def __init__(self, seconds, clock=time.monotonic, wall=time.time):
        self._seconds = float(seconds)
        self._clock = clock
        self._wall = wall
        self._lock = threading.Lock()
        self._last = {}

    def note(self, key):
        now = self._clock()
        with self._lock:
            last = self._last.get(key)
            if last is not None and now - last["at"] < self._seconds:
                last["held"] += 1
                return False, ""
            tail = ""
            if last is not None and last["held"]:
                tail = "; {} more like it since {}".format(
                    last["held"], time.strftime("%H:%M:%S", time.localtime(last["wall"]))
                )
            self._last[key] = {"at": now, "wall": self._wall(), "held": 0}
            if len(self._last) > self.KEEP:
                for old in [k for k, v in self._last.items() if now - v["at"] >= self._seconds]:
                    del self._last[old]
            return True, tail


class _LosingStream:
    """A stdout or stderr that loses what it cannot write instead of raising.

    Closing the terminal the program runs from sends SIGHUP, and from then
    on every write to that terminal raises. The DAC8532 worker prints each
    voltage it sets, after setting it, so a shutdown on SIGHUP would stop at
    its first line: gas line 1 at zero, gas line 2 never reached. The
    program's streams are wrapped in this as soon as it starts to end.
    """

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        try:
            return self._stream.write(text)
        except Exception:  # noqa: BLE001
            return len(text)

    def flush(self):
        try:
            self._stream.flush()
        except Exception:  # noqa: BLE001
            pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _keep_streams_writable():
    """Wrap stdout and stderr once (`_LosingStream`); a stream that is not
    there (pythonw, a test's capture swapped out) is left alone."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and not isinstance(stream, _LosingStream):
            setattr(sys, name, _LosingStream(stream))


def reader_lost_after(sampling):
    """Seconds without a sample after which the reader is called lost.

    Twice the web view's own stale line, and never under five seconds: the
    web view says `stale` first, and this is the sentence in the log when
    stale has gone on long enough to mean the reader, not a hiccup.
    """
    return max(5.0, 2.0 * stale_after(sampling))

try:
    import pigpio
    from start_gpio import start_pigpiod

    start_pigpiod()
except ImportError as e:
    print(RED + "main.py Error: " + RESET + f"{e}")
    TEST = True
    from devices.dummy import pigpio

    txt = f"{BLUE}main.py WARNING:{RESET} importing {BLUE} DUMMY{RESET} sensors.dummy.pigpio"
    print(txt)


class MainApp(QtCore.QObject, UIWindow):
    # DEFAULT_TEMPERATURE = 0
    DEFAULT_VOLTAGE = 0
    STEP = 3
    # Baselines exist before the first run does, so nothing has to ask
    # whether the dict is there yet.
    zero_adjustment = {"Ip": 0, "Bu": 0, "Bd": 0}
    # Who is moving the screen's selectors when it is not a person: None
    # for a hand on the dock, "restore" while the last run's settings are
    # put back at launch, "web" while a browser's command is carried out,
    # "diagram" while a gauge follows the PIHTI Diagram's on or off.
    # Class-level, because the selectors are connected before `__init__`
    # gets this far.
    _selector_mover = None
    # Each gauge's last mode that read pressure (Torr or Pa), so a gauge the
    # Diagram turns back on reads as it did before it was off. Built on the
    # first move, for the same reason as the mover.
    _reading_modes = None
    # The Diagram's follower and the main thread's memory of its word; both
    # stay None on a machine that does not follow it. And the words the last
    # run had applied, from `screen.json`, until the memory takes them over.
    _diagram_follower = None
    _gauge_following = None
    _remembered_diagram = None
    # What `screen_memory` last wrote, or found on disk at launch, so an
    # unchanged screen costs no write.
    _remembered = None
    _remember_failed = False
    # The longest sampling time since the last sample taken at the current
    # one; None when no change is pending (see `_check_reader`).
    _sampling_before_change = None
    # Ip read with the filament off, watched over one run's rows; None while
    # nothing runs (`filament_off.FilamentOffCurrent`).
    _filament_watch = None
    # The Pi's own health monitor; None until `start_pi_health`.
    _pi_health = None
    # Why the program is ending, for its last Log line, and the status it
    # exits with; a signal waiting for the event loop (`_take_pending_stop`);
    # and whether the end has begun, and stopped a run on its way.
    _stop_reason = None
    _exit_status = 0
    _stop_pending = None
    _shutting_down = False
    _stopped_run_to_close = False

    sigAbortWorkers = QtCore.pyqtSignal()
    kikusui_message = QtCore.pyqtSignal(str)
    # An uncaught error's Log line, from a worker thread: queued, so the Log
    # is written here, on the thread it belongs to (`note_uncaught`).
    uncaught_elsewhere = QtCore.pyqtSignal(str)
    # A `pi_health.Report`, from the monitor's own thread: queued, as the
    # Kikusui recorder's messages are, so the Log is written here.
    pi_health_report = QtCore.pyqtSignal(object)

    # MARK: init
    def __init__(self, app: QtWidgets.QApplication):
        super(self.__class__, self).__init__()
        self.__app = app
        self.connections()
        # self.tempcontrolDock.set_heating_goal(self.DEFAULT_TEMPERATURE, "---")
        self.gasflow_dock.update_display(self.DEFAULT_VOLTAGE, "NaN", 1)
        self.gasflow_dock.update_display(self.DEFAULT_VOLTAGE, "NaN", 2)

        QtCore.QThread.currentThread().setObjectName("main")

        self.__workers_done = 0
        self.workers = {}
        self._kikusui_logger = None
        # When the last recorder saw the supply's LAN go, kept past that
        # recorder's end so a press with none running can still say it.
        self._kikusui_lost_since = None
        self.kikusui_message.connect(self._kikusui_said)
        self.pi_health_report.connect(self._pi_health_reported)
        self._uncaught_repeats = _Repeats(UNCAUGHT_REPEAT_SECONDS)
        self.uncaught_elsewhere.connect(self._uncaught_said)
        self.kikusui_display_timer = QtCore.QTimer(self)
        self.kikusui_display_timer.timeout.connect(self._refresh_kikusui_display)
        self.kikusui_display_timer.start(500)
        # Define presets
        # self.__temp = self.DEFAULT_TEMPERATURE
        self._mfc_presets = {1: self.DEFAULT_VOLTAGE, 2: self.DEFAULT_VOLTAGE}

        self.config = readsettings.init_configuration(verbose=True)
        self.datapath = self.config["Data Folder"]
        # The dock's combo is where the sampling time lives from here on:
        # it starts at settings.yml's value, then at what the last run used
        # once `_restore_screen` has run, and every Start runs with what it
        # shows (`_apply_screen_settings`), so the two never disagree.
        index = self.settings_dock.samplingCb.findText(
            f"{float(self.config['Sampling Time']):g} s"
        )
        if index >= 0:
            self.settings_dock.samplingCb.setCurrentIndex(index)
        self.sampling = self._screen_sampling()

        # What the web view is allowed to know: how many channels, how fast,
        # and whether acquisition is running. It reads a copy, never a worker.
        self.web_status = RigStatus(
            channels=len(self.config["ADC Signal Names"]),
            sampling=self.sampling,
            names=self.config["ADC Signal Names"],
            gauges=self.config["Ion Gauges"],
            units=self._web_units(),
            quiet=self._web_quiet(),
        )
        # Where a browser's instruction waits for this thread. The web thread
        # only ever appends to it; every worker call still happens here.
        self.web_commands = web_commands.CommandQueue()
        self.web_status.set_remote(self.control_dock.remoteSW.isChecked())

        # The reader watchdog. The ADC worker used to die between two
        # samples with nothing on the screen saying so (Mizuno-kun's
        # "logging interrupted", 2026-08-19; queezz's "logging dead",
        # 2026-09-09): the window kept looking alive while the file stopped.
        # The worker now retries instead of dying, and this timer says so
        # here, on the main thread, if samples stop arriving anyway.
        self._last_sample_at = None
        self._reader_lost_since = None
        self.reader_watchdog = QtCore.QTimer(self)
        self.reader_watchdog.timeout.connect(self._check_reader)
        self.reader_watchdog.start(READER_CHECK_MS)

        # MARK: Current Values
        # To display in text browser
        self.currentvalues = {i: 0 for i in self.config["ADC Signal Names"]}
        self.baratronsignal1 = 0
        self.baratronsignal2 = 0

        self.update_plot_timewindow()
        self.set_scales_switches()

        self.showMain()
        self.log_to_file(f"App started: {os.path.abspath(__file__)}")
        # Before anybody can press Start: the selectors and the combo show
        # what they showed when the program last ran, and the first Start's
        # `_apply_screen_settings` carries that into the new workers.
        self._restore_screen()
        # The Diagram's recorded switches still being held against each
        # gauge's own volts: gauge -> `diagram_follower.SwitchCheck`.
        self._switch_checks = {}
        # Then the Diagram's word, which outranks the remembered screen where
        # it changed: a gauge an operator switched off in the Diagram while
        # the program was down comes back declared off, and a word the last
        # run already applied (kept in screen.json) is not applied again, so
        # a press on the dock since then stands.
        self._start_diagram_follower()
        # The follower is the program's, not a run's: it lives across Stop
        # and Start, and ends with the program, after the hardware: `_closing`
        # stops a run still going first, then the helpers, then says why.
        self.__app.aboutToQuit.connect(self._closing)
        # A person closing the window ends the program (Qt quits on the last
        # window), and the last Log line should say that is what happened.
        self.__app.lastWindowClosed.connect(self._window_closed)

    # MARK: Remembered screen
    def _restore_screen(self):
        """Put the gauges and the sampling time back as the last run had them.

        A restart on 2026-11-11 at 16:47:15 brought both ion gauges back at
        Torr and 1e-3 and forgot that Pu2 was declared off: for 18 s Pd_c
        read 1.5e-3 Torr when the vessel was at about 1.5e-7, and the two
        ranges were then set from a browser the wrong way round and put
        right a minute later. The sampling time came back at settings.yml's
        0.1 s the same way (the 4.29.1 deployment, 2026-10-21).

        Selectors only: nothing is sent to a worker from here, and there is
        none yet. A file that is missing, unreadable or not what this writes
        leaves settings.yml's values, with one line in the Log saying so;
        nothing about it may keep the window from opening.
        """
        applied = {"gauges": {}}
        notes = []
        try:
            state, notes = screen_memory.read_screen()
            if state is None:
                self.log_message(
                    "Gauges and sampling from settings.yml: nothing remembered"
                    " from a last run ({})".format(notes[0])
                )
                return
            with self._moving_selectors("restore"):
                for gauge, entry in state["gauges"].items():
                    if gauge not in self.control_dock.gauges:
                        notes.append(gauge)
                        continue
                    mode_box, range_box = self.control_dock.gauges[gauge]
                    index = mode_box.findText(entry["mode"])
                    if index < 0:  # -1 would blank the box, not restore it
                        notes.append(gauge)
                        continue
                    mode_box.setCurrentIndex(index)
                    range_box.setValue(entry["range"])
                    applied["gauges"][gauge] = entry
                    # What it read in before it was declared off, so the
                    # Diagram turning it back on finds Pa where Pa was; and
                    # the Diagram's word this program last applied, so the
                    # first answer after the launch changes only what
                    # changed while the program was down.
                    if entry.get("reading"):
                        if self._reading_modes is None:
                            self._reading_modes = {}
                        self._reading_modes[gauge] = entry["reading"]
                    if entry.get("diagram"):
                        if self._remembered_diagram is None:
                            self._remembered_diagram = {}
                        self._remembered_diagram[gauge] = entry["diagram"]
                if "sampling_s" in state:
                    combo = self.settings_dock.samplingCb
                    index = combo.findText(
                        web_commands.sampling_label(state["sampling_s"])
                    )
                    if index >= 0:
                        combo.setCurrentIndex(index)
                        applied["sampling_s"] = state["sampling_s"]
                    else:
                        notes.append("sampling")
            self._remembered = state
        except Exception as error:  # noqa: BLE001 -- a convenience never stops a start
            self.log_message(
                "Gauges and sampling from settings.yml: the last run's could"
                " not be restored ({})".format(error)
            )
            return
        finally:
            # Whatever the combo shows now is the sampling, everywhere.
            self.sampling = self._screen_sampling()
            self.web_status.describe_run(
                len(self.config["ADC Signal Names"]), self.sampling
            )
        said = screen_memory.describe(applied)
        passed = "; passed over: " + ", ".join(notes) if notes else ""
        if said:
            self.log_message("Restored from the last run: " + said + passed)
        else:
            self.log_message(
                "Gauges and sampling from settings.yml: nothing usable"
                " remembered from a last run" + passed
            )

    def _screen_state(self):
        """The gauges and the sampling time, as `screen_memory` keeps them.

        The sampling is the one the program runs with, not whatever the
        combo shows: a choice in the combo that was never Set is not what
        the run used.

        Beside a gauge's mode and range: for one declared off, the mode it
        read in before (`reading`), so Pa survives a restart while it is
        off; and the Diagram's word last applied to it (`diagram`), so the
        next launch's first answer is not a change from not knowing.
        """
        words = (
            self._gauge_following.words()
            if self._gauge_following is not None
            else dict(self._remembered_diagram or {})
        )
        state = {"gauges": {}}
        for gauge, (mode_box, range_box) in self.control_dock.gauges.items():
            entry = {"mode": mode_box.currentText(), "range": range_box.value()}
            reading = (self._reading_modes or {}).get(gauge)
            if entry["mode"] == web_commands.GAUGE_OFF and reading:
                entry["reading"] = reading
            if words.get(gauge):
                entry["diagram"] = words[gauge]
            state["gauges"][gauge] = entry
        sampling = getattr(self, "sampling", None)
        if sampling is not None:
            state["sampling_s"] = float(sampling)
        return state

    def _remember_screen(self):
        """Write the screen's gauges and sampling for the next start, when
        they changed. Never while the last ones are being put back: a start
        writes nothing until something is set."""
        if self._selector_mover == "restore":
            return
        state = self._screen_state()
        if state == self._remembered:
            return
        if screen_memory.write_screen(state):
            self._remembered = state
            self._remember_failed = False
        elif not self._remember_failed:
            # Said once, not at every press, until a write succeeds again.
            self._remember_failed = True
            self.log_message(
                "Gauges and sampling not saved for the next start: the"
                " settings folder could not be written"
            )

    @contextlib.contextmanager
    def _moving_selectors(self, who):
        """The program, not a person, moves the screen's selectors inside."""
        previous = self._selector_mover
        self._selector_mover = who
        try:
            yield
        finally:
            self._selector_mover = previous

    # MARK: The Diagram's gauges
    def _start_diagram_follower(self):
        """Follow the PIHTI Diagram's on and off for the mapped gauges.

        The audit of the student runs of 2026-10-22 to 11-13 found Pd off
        at its controller for 224 h and Pu2 for 132 h without being declared
        off here, so the file kept the floor's noise as pressure, while
        every one of those switches was recorded in the Diagram. queezz,
        2026-11-13: "Why should we turn that off twice??"

        Which gauge is which element is settings.yml's `Diagram Element`;
        where the Diagram answers is this machine's neighbours file, the
        address the Lab board already asks. The asking happens on the
        follower's own daemon thread (`diagram_follower`), never here and
        never in the reader; this thread picks the newest answer up on a
        timer. One line says whether the gauges follow, and why not.

        Dummy hardware asks only a Diagram on this machine itself: a laptop
        checking the view must never read, and so never act on, the rig's.
        """
        elements = {
            gauge: element
            for gauge, element in readsettings.gauge_diagram_elements(self.config).items()
            if gauge in self.control_dock.gauges
        }
        # Seeded with the words the last run applied: only a word that
        # changed while the program was down is a change.
        self._gauge_following = diagram_follower.GaugeFollowing(
            elements, seen=self._remembered_diagram
        )
        if not elements:
            return
        url = diagram_follower.diagram_url()
        if url is None:
            self.log_message(
                "Gauges do not follow the Diagram: this machine has no address"
                " for {} in its neighbours file".format(diagram_follower.DIAGRAM_ALIAS)
            )
            return
        if dummy_hardware_loaded() and not diagram_follower.is_loopback(url):
            self.log_message(
                "Gauges do not follow the Diagram: dummy hardware never asks"
                " a Diagram on another machine ({})".format(url)
            )
            return
        follower = diagram_follower.DiagramFollower(url)
        follower.start()
        self._diagram_follower = follower
        self.diagram_timer = QtCore.QTimer(self)
        self.diagram_timer.timeout.connect(self._check_diagram)
        self.diagram_timer.start(DIAGRAM_CHECK_MS)
        self.log_message(
            "Gauges follow the Diagram's on and off at {}: {}".format(
                url,
                ", ".join(
                    "{} ({})".format(gauge, element) for gauge, element in elements.items()
                ),
            )
        )

    def _stop_diagram_follower(self):
        """End the follower with the program; True once its thread is gone.

        It holds no device and no file, so nothing about the hardware-first
        order waits on it: by the time the program quits, a Stop has already
        zeroed the outputs (Quit is disabled while acquiring). Its stop waits
        at most `diagram_follower.STOP_WAIT_SECONDS`, and a thread still in
        its one request then is a daemon the interpreter ends.
        """
        timer = getattr(self, "diagram_timer", None)
        if timer is not None:
            timer.stop()
        follower = self._diagram_follower
        if follower is None:
            return True
        return follower.stop()

    # MARK: The Pi's own health
    def start_pi_health(self, read=None, interval=None):
        """Read the Pi's supply flags, temperature and free disk every five
        minutes, on a thread of its own (`pi_health`).

        The I²C reads have failed during plasma, and a sagging Pi supply
        would fail them the same way; the one look at it, on 2026-09-09,
        was by hand. The thread never touches Qt, a worker or the ADC: it
        hands each report to `pi_health_report`, queued to this thread, and
        stops with the program in `_closing`. Started from `main` beside
        the web view rather than here, so a test that builds a window starts
        no thread it did not ask for. `read` and `interval` are a test's.
        """
        if self._pi_health is not None:
            return
        monitor = pi_health.PiHealthMonitor(
            self.datapath, self.pi_health_report.emit, interval=interval, read=read
        )
        monitor.start()
        self._pi_health = monitor

    def _stop_pi_health(self):
        """End the monitor with the program; True once its thread is gone.
        It holds nothing a shutdown waits on, and a thread still inside its
        one `vcgencmd` is a daemon the interpreter ends."""
        monitor = self._pi_health
        if monitor is None:
            return True
        return monitor.stop()

    @QtCore.pyqtSlot(object)
    def _pi_health_reported(self, report):
        """One reading, on the main thread: into `/api/health`'s `pi`, and
        its sentences into the Log, red when something went wrong."""
        try:
            self.web_status.record_pi(pi_health.as_json(report.reading))
            for text, alarm in report.lines:
                if alarm:
                    self.log_message(f"<font color='red'>{text}</font>", htmltag="div")
                else:
                    self.log_message(text)
        except Exception as error:  # noqa: BLE001 -- a convenience never stops the rig
            _quiet_print(f"pi health: {error}")

    def _check_diagram(self):
        """The timer's slot: the Diagram's newest answer, then the checks.

        Nothing raised here may reach Qt, which would end the program.
        """
        try:
            follower = self._diagram_follower
            answer = follower.take() if follower is not None else None
            if answer is not None:
                self._follow_diagram(
                    answer.states, answer.reason, answer.at, answer.recorded
                )
            self._check_gauge_switches()
        except Exception as error:  # noqa: BLE001 -- a convenience never stops the rig
            _quiet_print(f"diagram: {error}")

    def _follow_diagram(self, states, reason="", at=None, recorded=None):
        """Take one answer the follower already fetched: the Diagram's
        `{element: "active" | "inactive"}`, or None and why there was none.

        Only a gauge whose word differs from the one last applied is touched
        (`GaugeFollowing`); an answer that is not usable changes nothing,
        and says so once. Each gauge is applied on its own, and marked as
        applied only once it was, so one that fails (its Log line raising,
        say) neither keeps the others in the same answer from theirs nor is
        forgotten: it is a change again at the next answer. Before, the
        whole answer was marked seen first, and a failure on the first gauge
        left the second never applied (the review of 2026-11-13). The word
        applied is remembered in `screen.json`, so the next launch takes
        only what changed while the program was down.

        `recorded` is the Diagram's history of each element's latest switch
        (`diagram_follower.recorded_switches`). Where it has this switch, the
        signal check counts from the time the operator recorded it and the
        Log line says when and who; otherwise from when it was noticed here.
        A recorded time later than the notice is not believed, nor one
        earlier than the last answer that still carried the word before:
        that is an older switch (`diagram_follower.recorded_time_believed`).
        """
        at = at if at is not None else datetime.datetime.now()
        following = self._gauge_following
        changes, notes = following.read(states, reason, at)
        for note in notes:
            try:
                self.log_message(note)
            except Exception as error:  # noqa: BLE001 -- the gauges still follow
                _quiet_print(f"diagram: {error}")
        for gauge, status in changes:
            try:
                element = following.elements.get(gauge)
                entry = ((recorded or {}).get(element) or {}).get(status)
                if entry is not None and not diagram_follower.recorded_time_believed(
                    entry[0], at, following.last_seen(gauge)
                ):
                    entry = None
                self._apply_diagram_word(gauge, status, entry)
                following.applied(gauge, status, at)
                self._remember_screen()
                self._await_switch(gauge, status, entry[0] if entry else at)
            except Exception as error:  # noqa: BLE001 -- one gauge never stops the rest
                _quiet_print(f"diagram: {gauge}: {error}")

    def _gauge_words(self, gauge):
        place = readsettings.ion_gauge_places(self.config).get(gauge)
        return diagram_follower.gauge_words(place if place != gauge else "")

    def _reading_mode(self, gauge):
        """The mode a gauge read pressure in before it was off; Torr when
        this program never saw it read."""
        return (self._reading_modes or {}).get(gauge, "Torr")

    def _note_reading_mode(self, gauge):
        mode = self.control_dock.gauges[gauge][0].currentText()
        if mode != web_commands.GAUGE_OFF:
            if self._reading_modes is None:
                self._reading_modes = {}
            self._reading_modes[gauge] = mode

    def _apply_diagram_word(self, gauge, status, recorded=None):
        """Move one gauge's mode selector to the Diagram's new word.

        Off declares it off. On puts back the mode it read in before it was
        off, and leaves a gauge already in Torr or Pa as it is. The move goes
        through the selector, as a browser's command does: the selector's
        own signal tells the worker, the web status and the remembered
        screen. The mover is "diagram", so the dock-press line is not
        written; this line says what moved it instead.
        """
        mode_box, _ = self.control_dock.gauges[gauge]
        shown = mode_box.currentText()
        if status == diagram_follower.INACTIVE:
            if shown == web_commands.GAUGE_OFF:
                return
            self._note_reading_mode(gauge)
            target = web_commands.GAUGE_OFF
        else:
            if shown != web_commands.GAUGE_OFF:
                return
            target = self._reading_mode(gauge)
        with self._moving_selectors("diagram"):
            mode_box.setCurrentIndex(web_commands.GAUGE_MODES.index(target))
        when = ""
        if recorded is not None:
            moment, user = recorded
            stamp = "%H:%M:%S" if moment.date() == datetime.date.today() else "%Y-%m-%d %H:%M:%S"
            # The initials are typed into the Diagram by whoever records the
            # switch, and the Log panel renders HTML.
            when = " (recorded {}{})".format(
                moment.strftime(stamp), " by " + html.escape(user) if user else ""
            )
        self.log_message(
            "{}: the Diagram shows the {} {}{}".format(
                web_commands.summarise("gauge", {"gauge": gauge, "mode": target}),
                self._gauge_words(gauge),
                "off" if status == diagram_follower.INACTIVE else "on",
                when,
            )
        )

    def _await_switch(self, gauge, status, at):
        """Hold a switch the Diagram recorded against the gauge's own volts.

        queezz, 2026-11-13: "When the diagram says the gauge is off, but
        the signal doesn't change, we should warn." Only while a run is
        recording: with no samples there is nothing to check. A newer
        switch of the same gauge replaces the one before it.
        """
        if not self.workers:
            return
        # The check waits for its window's rows to be delivered, and for a
        # reader that delivers none no longer than it takes to call it lost.
        sampling = float(getattr(self, "sampling", 0.0) or 0.0)
        self._switch_checks[gauge] = diagram_follower.SwitchCheck(
            gauge, status, at, self._gauge_words(gauge),
            period=sampling, patience=reader_lost_after(sampling),
        )

    def _check_gauge_switches(self, now=None):
        """Settle the switches whose gauge's signal has had its say.

        Reads the raw column the window already keeps (`self.datadict`),
        never the ADC. A confirmed switch is dropped in silence; one the
        signal does not show by the end of its window leaves one red line,
        and the gauge keeps the Diagram's word: the raw volts are in the
        file either way. Checks end with the run that would have answered
        them.
        """
        checks = self._switch_checks
        if not checks:
            return
        if not self.workers:
            checks.clear()
            return
        now = now if now is not None else datetime.datetime.now()
        history = getattr(self, "datadict", {}).get("ADC")
        for gauge, check in list(checks.items()):
            try:
                times, volts = history.column("date"), history.column(gauge)
            except (AttributeError, KeyError):
                times = volts = None
            verdict, line = check.verdict(times, volts, now)
            if verdict == diagram_follower.PENDING:
                continue
            del checks[gauge]
            if line:
                self.log_message(line)

    # MARK: Web status
    # Unit per conversion function, for the web view's readouts. A channel
    # whose conversion returns the ADC voltage unchanged stays in volts.
    _WEB_UNITS = {
        "Hall Sensor": "A",
        "Ionization Gauge": "Torr",
        "Pfeiffer Single Gauge": "Torr",
        "Pfeiffer IKR251": "Torr",
        "Baratron": "Torr",
        "cathode volt": "V",
    }

    def _web_units(self):
        """Map each channel name to the unit its converted value carries."""
        props = self.config["Adc Channel Properties"]
        return {
            name: self._WEB_UNITS.get(props[name].conversion_id, "V")
            for name in props
        }

    def _web_quiet(self):
        """Each channel's quiet floor (settings `Quiet Within`), for the
        web view's charts; channels without one are left out."""
        props = self.config["Adc Channel Properties"]
        return {
            name: props[name].quiet_within
            for name in props
            if getattr(props[name], "quiet_within", None)
        }

    def _for_web(self, text):
        """
        The same message the Log dock shows, minus this machine's paths:
        a browser is told the data file's name, never where it lives.
        """
        folder = getattr(self, "datapath", "")
        if not folder:
            return text
        for spelling in (os.path.abspath(folder), folder, folder.replace("\\", "/")):
            if spelling:
                text = text.replace(spelling + os.sep, "").replace(spelling + "/", "")
        return text

    def _publish_step(self, newdata):
        """
        Hand the web view the samples this step delivered, in the same
        units and with the same zero adjustment the rig's own screen shows.
        The web view must never stop the acquisition loop, so any failure
        here is printed and swallowed.
        """
        try:
            times = [_epoch(stamp) for stamp in newdata["date"]]
            values = {}
            zeros = getattr(self, "zero_adjustment", {})
            for name, column in zip(
                self.config["ADC Signal Names"], self.config["ADC Converted Names"]
            ):
                series = newdata[column].astype(float).tolist()
                zero = zeros.get(name, 0)
                if zero:
                    series = [value - zero for value in series]
                values[name] = series
            self.web_status.record_samples(times, values)
        except Exception as error:
            print(f"{RED}web status:{RESET} {error}")

    def update_plot_timewindow(self):
        """
        adjust time window for data plots
        """
        txt = self.control_dock.scaleBtn.currentText()
        val = self.control_dock.sampling_windows[txt]
        self.time_window = val
        try:
            [self.update_plots(device) for device in self.device_name]
        except AttributeError:
            pass

    def update_baratron_gain(self):
        """"""
        txt = self.adcgain_dock.gain_box.currentText()
        val = self.adcgain_dock.gains[txt]
        self.baratrongain = val

    # MARK: connections
    def connections(self):
        self._init_controldock_connections()
        self._init_adcgain_connections()
        self._init_mfc_connections()
        self._init_cocnnections()
        self._init_plot_controls()
        self._init_calibration_connections()
        self._init_plasmacontrol_connections()

        # self.tempcontrolDock.registerBtn.clicked.connect(self.set_heater_goal)

    def _init_plasmacontrol_connections(self):
        self.plasma_control_dock.set_dac_voltage.clicked.connect(
            self.set_currentcontrol_voltage
        )
        self.plasma_control_dock.turn_off_pid_btn.clicked.connect(
            self.turn_off_currentcontrol_voltage
        )
        self.plasma_control_dock.cathode_set_btn.clicked.connect(
            self.set_cathode_drive
        )
        self.plasma_control_dock.cathode_off_btn.clicked.connect(
            self.turn_off_cathode_drive
        )
        # The supply's own output switch, beside the drive that feeds it.
        self.plasma_control_dock.output_on_btn.clicked.connect(
            self.turn_on_cathode_output
        )
        self.plasma_control_dock.output_off_btn.clicked.connect(
            self.turn_off_cathode_output
        )

    def _init_calibration_connections(self):
        self.calibration_dock.calibrationBtn.clicked.connect(self.calibration)
        self.calibration_dock.stopBtn.clicked.connect(self.stop_mfc)

    def _init_mfc_connections(self):
        self.gasflow_dock.registerBtn1.clicked.connect(lambda: self.set_mfc_goal(1))
        self.gasflow_dock.registerBtn2.clicked.connect(lambda: self.set_mfc_goal(2))

    def _init_controldock_connections(self):
        # One pair of selectors per ionization gauge; each carries its own
        # channel name to the updater, so the worker hears which gauge moved.
        for gauge, (mode_box, range_box) in self.control_dock.gauges.items():
            mode_box.currentIndexChanged.connect(
                lambda _index, gauge=gauge: self._gauge_selector_moved(gauge, "mode")
            )
            range_box.valueChanged.connect(
                lambda _value, gauge=gauge: self._gauge_selector_moved(gauge, "range")
            )
        self.control_dock.FullNormSW.clicked.connect(self.fulltonormal)
        self.control_dock.OnOffSW.clicked.connect(self.__onoff)
        self.control_dock.remoteSW.clicked.connect(self._toggle_remote)
        self.control_dock.quitBtn.clicked.connect(self.__quit)
        self.control_dock.qmsSigSw.clicked.connect(self._toggle_led_status)
        self.control_dock.scaleBtn.currentIndexChanged.connect(
            self.update_plot_timewindow
        )

    def _init_adcgain_connections(self):
        self.adcgain_dock.gain_box.currentIndexChanged.connect(
            self.update_baratron_gain
        )
        self.adcgain_dock.set_gain_btn.clicked.connect(self.__set_gain)

    def _init_cocnnections(self):
        """Toggle plots for Current, Temperature, and Pressure"""
        self.settings_dock.setSamplingBtn.clicked.connect(self.__set_sampling)
        self.scale_dock.subzero_ip.clicked.connect(self._set_zero_ip)
        # The Bu button existed and was never wired; Bd is new beside it.
        self.scale_dock.subzero_baratron.clicked.connect(
            lambda: self._zero_from_dock("Bu")
        )
        self.scale_dock.subzero_baratron_down.clicked.connect(
            lambda: self._zero_from_dock("Bd")
        )

    # MARK: GUI setup

    def __quit(self):
        """terminate app"""
        self._note_stop_reason("the Quit button was pressed")
        self.__app.quit()

    # MARK: Ending
    # 2026-11-11 16:47 the program restarted with nothing anywhere saying
    # why: not the Log, not the stderr file. Every way it ends now leaves its
    # reason as the Log's last line ("Program closing: ..."), and the
    # launcher adds the exit status to the stderr file.

    def _note_stop_reason(self, reason, status=0):
        """Keep the first reason the program was given to end."""
        if self._stop_reason is None:
            self._stop_reason = reason
            self._exit_status = status

    def _window_closed(self):
        """The last window closed; Qt quits after this."""
        self._note_stop_reason("the window was closed")

    def _signal_received(self, signum, frame):
        """The Python handler for SIGTERM, SIGHUP and SIGINT: note it, and
        nothing else. It runs between two bytecodes of whatever Python was
        running, perhaps halfway through a slot, so the stopping itself is
        left to `_take_pending_stop`, which the event loop calls whole."""
        if self._stop_pending is None:
            self._stop_pending = (signal_reason(signum), 128 + int(signum))

    def _take_pending_stop(self):
        """The signal timer's slot: end the program if something asked."""
        pending, self._stop_pending = self._stop_pending, None
        if pending is not None:
            self.shut_down(*pending)

    def note_uncaught(self, kind, error, trace):
        """An exception nothing caught (`sys.excepthook`): one red Log line,
        and the program carries on with the outputs where they were.

        PyQt5 ends the process (`qFatal`, an abort) on an exception that
        escapes a slot, unless a hook is installed, in which case it carries
        on. An abort leaves the DACs holding what they held with nothing
        recording, the 2026-08-19 plasma. Ending through Stop instead, as
        4.30.0 did, zeroes a discharge somebody is running because a
        convenience broke. queezz's standing ruling for a dead reader is
        "Hold and alarm!" (owner decision 2026-09-07: the outputs stay where
        they were and the Log says so), and an uncaught error is held the
        same way: the slot that raised has ended, the program goes on, and
        the line says what broke and where.

        On the main thread the line is written here. A hardware worker's
        slot (the ADC reader, a DAC worker) is a `QThread` of its own, and
        PyQt calls the hook on that thread, where the Log must not be
        written: its line crosses on `uncaught_elsewhere`, a queued signal,
        as the Kikusui recorder's do. A plain Python thread's exception is
        `threading.excepthook`'s, and never reaches here.

        The same error from the same place is said once a minute
        (`UNCAUGHT_REPEAT_SECONDS`). Returns whether this one was said, so
        the hook prints the traceback only then. Never raises.
        """
        words = describe_exception(kind, error, trace)
        on_main = threading.current_thread() is threading.main_thread()
        where = "" if on_main else _thread_name()
        repeats = getattr(self, "_uncaught_repeats", None)
        said, tail = repeats.note((where, words)) if repeats is not None else (True, "")
        if not said:
            return False
        if on_main:
            self._uncaught_said(
                "<font color='red'>Uncaught error</font>: " + html.escape(words)
                + "; outputs held, the program carries on" + tail
            )
        else:
            try:
                self.uncaught_elsewhere.emit(
                    "<font color='red'>Uncaught error on {}</font>: {}; outputs"
                    " held".format(html.escape(where), html.escape(words)) + tail
                )
            except Exception:  # noqa: BLE001 -- the traceback must still print
                _quiet_print("Uncaught error on {}: {}".format(where, words))
        return True

    @QtCore.pyqtSlot(str)
    def _uncaught_said(self, text):
        """An uncaught error's line, in the Log, on the main thread."""
        try:
            self.log_message(text, htmltag="div")
        except Exception:  # noqa: BLE001 -- the log itself may be what failed
            _quiet_print(strip_tags(text))

    def shut_down(self, reason, status=0):
        """End the program as Stop and then Quit would: a run still going
        is stopped first, outputs to zero and workers joined, hardware first
        (`docs/architecture/qt-threading.md`), and then the event loop ends
        with `status`. A second call while ending changes nothing."""
        self._note_stop_reason(reason, status)
        if self._shutting_down:
            return
        self._shutting_down = True
        _keep_streams_writable()
        self._let_a_signal_end_it()
        try:
            self._stop_run_to_close()
        finally:
            self._exit_program(self._exit_status)

    def _let_a_signal_end_it(self):
        """Once the program has begun to end, SIGTERM and SIGINT end it at
        once again, the way they would end any program.

        Their handler only notes a signal for the event loop, and an ending
        that hangs, a worker's `thread.wait()` behind an I²C call that never
        returns, runs no event loop: a second Ctrl+C or `kill` would be
        noted and nothing more, and only SIGKILL would end it. SIGHUP keeps
        its handler: a terminal that closes sends it, and may send it again,
        while the shutdown that the first one started is still zeroing the
        outputs. Only where `install_stop_handlers` installed them.
        """
        setter = getattr(self, "_set_signal_handler", None)
        if setter is None:
            return
        for name in ("SIGTERM", "SIGINT"):
            number = getattr(signal, name, None)
            if number is None:
                continue
            try:
                setter(number, signal.SIG_DFL)
            except (OSError, RuntimeError, ValueError):
                continue

    def _exit_program(self, status):
        """End the event loop; `app.exec_()` returns `status`."""
        self.__app.exit(status)

    def _stop_run_to_close(self):
        """Stop a run the program is ending under, exactly as Stop does;
        True if there was one. The switch on the rig's screen is set to
        match, as a browser's Stop sets it."""
        if not self.workers:
            return False
        self.control_dock.OnOffSW.setChecked(False)
        self.stop_acquisition()
        self._stopped_run_to_close = True
        return True

    def _closing(self):
        """`QApplication.aboutToQuit`: whatever ended the event loop.

        The Quit button is disabled while a run records, but the window's
        own close is not, and it used to end the program with the workers
        running and the DACs holding. A run still going is stopped here
        first, hardware first; then the program's helpers, which hold no
        device; and last the line that says why, so it is the last line.
        """
        _keep_streams_writable()
        # Each step guarded: whatever fails, the next still runs and the
        # last line is still written.
        for step in (self._stop_run_to_close, self._stop_diagram_follower, self._stop_pi_health):
            try:
                step()
            except Exception as error:  # noqa: BLE001 -- the rest must still run
                _quiet_print("closing: {}".format(error))
        reason = self._stop_reason or (
            "no reason recorded; the event loop was ended from elsewhere"
        )
        if self._stopped_run_to_close:
            reason += "; the run was stopped first, outputs to zero"
        try:
            self.log_message("Program closing: " + html.escape(reason))
        except Exception:  # noqa: BLE001
            _quiet_print("Program closing: " + reason)

    def __onoff(self):
        """
        The on/off switch on the rig's own screen. It asks before stopping,
        and then takes the same two paths a browser takes, so a run begins
        and ends the same way whoever asked for it.
        """
        if self.control_dock.OnOffSW.isChecked():
            self.start_acquisition()
            return

        question = "Are you sure you want to stop data acquisition?"
        if self.popup_confirmation_window(question):
            self.stop_acquisition()
        else:
            self.control_dock.OnOffSW.setChecked(True)

    def start_acquisition(self):
        """
        Start the worker threads and say so, whoever asked.

        The switch on the rig's screen calls this, and so does a browser's
        Start through the command queue; the browser's half sets the switch
        to match first, so the rig's own screen agrees with what was done.
        """
        self.prep_threads()
        self.web_status.set_acquiring(True)
        self.control_dock.quitBtn.setEnabled(False)

    def stop_acquisition(self):
        """
        Stop the worker threads and say so, whoever asked.

        The Remote switch is deliberately left exactly as the person at the
        rig set it. It used to be forced off here, so that a laptop could not
        hold a gate over a rig that is not running; a browser that can now
        press Stop would be stranded by a switch that turned itself off
        behind it. The switch is still the only way in, and still only
        turnable on at the rig. The operator lock is let go of instead, in
        `abort_all_threads`, so nobody silently holds an idle rig.
        """
        self.abort_all_threads()
        self.web_status.set_acquiring(False)
        self.control_dock.quitBtn.setEnabled(True)

    # MARK: Remote control
    def _toggle_remote(self):
        """Record the Remote switch, and say so in the log.

        The switch is the whole gate on a browser changing anything: with it
        off the web view reads and nothing more. It cannot be turned on from
        a browser, only here, and it stays exactly where this person put it:
        stopping acquisition no longer takes it down, because a browser may
        now stop a run and would otherwise lock itself out of restarting it.
        """
        on = self.control_dock.remoteSW.isChecked()
        self.web_status.set_remote(on)
        self.log_message("Remote control {}".format("on" if on else "off"))
        if not on:
            web_commands.release(self, "Remote switch off")

    def _drain_web_commands(self):
        """Run what a browser queued, here on the thread that owns the workers.

        A browser's gauge command moves the dock's selector to match, and its
        own "Remote: …" line already says what was set and by whom; the line
        `_gauge_selector_moved` writes is for a hand on the dock alone.
        """
        try:
            with self._moving_selectors("web"):
                web_commands.drain(self)
        except Exception as error:  # noqa: BLE001 -- a browser never stops the rig
            _quiet_print(f"web command: {error}")

    def _toggle_led_status(self):
        if not self.control_dock.OnOffSW.isChecked():
            return
        self.web_status.record_setpoints(sync=self.control_dock.qmsSigSw.isChecked())
        if self.control_dock.qmsSigSw.isChecked():
            self.indicator_led.on()
        else:
            self.indicator_led.off()

    def fulltonormal(self):
        """Change from full screen to normal view on click"""
        if self.control_dock.FullNormSW.isChecked():
            self.MainWindow.showFullScreen()
            self.control_dock.setStretch(*(10, 300))  # minimize control dock width
        else:
            self.MainWindow.showNormal()
            self.control_dock.setStretch(*(10, 300))  # minimize control dock width

    # MARK: Devices
    def define_devices(self):
        """
        Define devices, data structure, and step methods
        """
        devices = {
            "MFCs": DAC8532,
            "PlasmaCurrent": MCP4725,
            "ADC": ADC,
        }
        # devices['MembraneTemperature'] = MAX6675
        self.step_methods = {
            "MembraneTemperature": self._membrane_heater_step,
            "ADC": self._adc_step,
        }

        self.devices = devices

        self.savepaths = {}
        # What the window draws from, bounded: the file is the record.
        self.datadict = {"ADC": RunHistory()}
        self._behind_since = None
        self.newdata = {
            # "MembraneTemperature": pd.DataFrame(columns=self.config["Temperature Columns"]),
            "ADC": pd.DataFrame(columns=self.config["ADC Column Names"]),
        }

        self.create_file("ADC")

        self.plot_methods = {
            "MAX6675": self.update_plots_max6675,
            "ADC": self.update_plots_adc,
        }

        # Plasma current and both Baratrons can be read from a baseline. A
        # zero changes the display, the plots and the web view; the CSV on
        # disk keeps the converted signal exactly as measured.
        self.zero_adjustment = {"Ip": 0, "Bu": 0, "Bd": 0}
        self.web_status.record_zeros(self.zero_adjustment)

    # MARK: Prep Threads
    def prep_threads(self):
        """
        Define Workers for Devices to run in separate threads.
        """
        self.log_message(
            "<font color='#1cad47'>Starting</font> acquisition", htmltag="h2"
        )
        self.__workers_done = 0
        self.terminate_existing_threads()
        # The first sample is awaited from now; a fresh reader is never
        # "lost" on the strength of the previous run's last sample.
        self._last_sample_at = time.monotonic()
        self._reader_lost_since = None
        self._sampling_before_change = None
        self.pi = pigpio.pi()
        self.define_devices()
        now = datetime.datetime.now()

        self.workers = {
            device_name: self.prep_worker(worker_class, device_name, now)
            for device_name, worker_class in self.devices.items()
        }

        self.start_all_threads()
        self.start_cross_connections()
        # Each run watches its own rows for Ip with the filament off, at the
        # threshold its own reader calls a discharge lit.
        self._filament_watch = filament_off.FilamentOffCurrent(self._lit_above())
        self.indicator_led = IndicatorLED(
            self.__app, self.pi, self.workers["ADC"]["worker"]
        )
        self._start_kikusui_logging()

    def _refresh_kikusui_display(self):
        if self._kikusui_logger is not None:
            self._publish_kikusui(self._kikusui_logger.snapshot())
            self._remember_lost_since()

    def _remember_lost_since(self):
        """Copy the recorder's last LOST time; None once the LAN came BACK."""
        logger = getattr(self, "_kikusui_logger", None)
        if logger is not None:
            self._kikusui_lost_since = logger.lost_since()
        return getattr(self, "_kikusui_lost_since", None)

    @QtCore.pyqtSlot(str)
    def _kikusui_said(self, text):
        """A line from the supply's link, on the main thread: into the Log,
        and, when it is a press that failed, onto the browser's own answer
        too. The press was answered `done` when it was handed over, before
        the LAN had a chance to stay silent (queezz, 2026-10-07: "Kikusui
        output button in WebUI not working")."""
        self.log_message(text)
        if is_output_failure(text):
            self.web_status.fail_command(("cathode_output", "stop_all"), text)

    def _publish_kikusui(self, snapshot):
        self._kikusui_snapshot = snapshot
        self.web_status.record_kikusui(snapshot)
        self._record_cathode_curve(snapshot)
        self._render_value_browser()

    def _record_cathode_curve(self, snapshot):
        """Put the supply's measured current and voltage in the web ring, so
        the Plasma current panel can draw `Ic` beside `Ip` and a reader can
        tell a dead discharge from a drifting Hall sensor (owner ask
        2026-09-15: "we need to add cathode current to the current plot").

        Two rules, both because this is a LAN reading and not an ADC sample.
        Only a fresh snapshot is recorded — `ok` or `dummy`, the two states
        that carry measurements at all — so nothing stale or refused is ever
        laid down as a point. And the point is stamped with the sidecar
        row's *own* time, not this moment: the recorder samples on its own
        clock at about 2 Hz while this runs on a 500 ms display timer, so a
        snapshot republished unchanged must not repeat a point, and the ring
        drops one whose stamp is not newer than the last.
        """
        if (snapshot or {}).get("status") not in ("ok", "dummy"):
            return
        stamp = sidecar_epoch(snapshot.get("date"))
        if stamp is None:
            return
        self.web_status.record_sidecar(
            stamp,
            {"Ic": snapshot.get("current_a"), "Uc": snapshot.get("voltage_v")},
        )

    def _cathode_readouts(self):
        """The supply's volts and amperes for the value browser: numbers
        while the telemetry is fresh, dashes otherwise, and a SIM mark on
        dummy data so a simulated reading is never taken for a measured one."""
        snapshot = getattr(self, "_kikusui_snapshot", None) or {"status": "idle"}
        fresh = snapshot.get("status") in ("ok", "dummy")
        mark = "·SIM" if snapshot.get("status") == "dummy" else ""
        volts = snapshot.get("voltage_v") if fresh else None
        amps = snapshot.get("current_a") if fresh else None
        return [
            [CATHODE_PEN, "Uc" + mark, volts, False, ".3f"],
            [CATHODE_PEN, "Ic" + mark, amps, False, ".3f"],
        ]

    def _render_value_browser(self):
        """The Control dock's numbers: the ADC signals the screen keeps,
        the three with no other display large, then the cathode supply."""
        values = []
        gauges = getattr(self.control_dock, "gauges", {})
        for label in Graph.SCREEN_READOUTS:
            v = self.currentvalues[label] - self.zero_adjustment.get(label, 0)
            # A gauge declared off at its controller reads the word, not the
            # NaN its row records (queezz, 2026-10-07).
            if label in gauges and gauges[label][0].currentText() == "Off":
                v = "off"
            values.append([self.graph.pens[label]["color"], label, v,
                           label in Graph.SCREEN_PROMINENT])
        values.extend(self._cathode_readouts())
        self.control_dock.update_current_values(values)

    def _start_kikusui_logging(self):
        """Optional telemetry; a missing/broken LAN must not stop manual acquisition."""
        previous = self._kikusui_logger
        if previous is not None:
            if previous.thread.is_alive():
                self.log_message("Kikusui recording unavailable: previous logger is still stopping")
                return
            # A stop that outlived its wait has since finished on its own; the
            # stale reference must not block every later run of this session.
            self._kikusui_logger = None
        try:
            config = load_kikusui_config()
            if config is None:
                self._publish_kikusui({"status": "disabled"})
                self.log_message("Kikusui telemetry disabled: no kikusui.yml configured")
                return
            if dummy_hardware_loaded() and not config.dummy:
                self._publish_kikusui({"status": "error"})
                self.log_message("Kikusui telemetry disabled: dummy hardware never contacts the supply")
                return
            logger = KikusuiLogger(
                config, self.savepaths["ADC"], self.kikusui_message.emit,
                context=lambda: self.web_status.read()["setpoints"],
            )
            logger.start()
            self._kikusui_logger = logger
            self._refresh_kikusui_display()
        except Exception as error:  # noqa: BLE001 -- Optional telemetry cannot prevent acquisition.
            self._publish_kikusui({"status": "error"})
            self.log_message(f"Kikusui telemetry unavailable: {error}; manual drive unchanged")

    def prep_worker(self, device_class, device_name, start_time):
        """
        Generalized worker preparation method for different device types.
        """
        thread = QtCore.QThread()
        thread.setObjectName(f"{device_name}")

        worker = device_class(device_name, self.__app, start_time, self.config, self.pi)

        return {"worker": worker, "thread": thread}

    def start_all_threads(self):
        """
        Start all threads by assigning workers to threads and initiating them.

        The screen's settings reach the new workers first, so the first row
        is already taken with them.
        """
        self._apply_screen_settings()
        for device_name, worthre in self.workers.items():
            self.start_thread(worthre)

    def _apply_screen_settings(self):
        """
        Give fresh workers what the screen shows, never what settings.yml
        or a constant says.

        Every Start builds new workers, and a new worker begins from its
        defaults. Settings are pushed here; outputs are not. Gas flows, the
        cathode drive, the PID and the supply's output start at zero and off,
        as they always have: a restart never drives anything.
        """
        # A fresh worker rests at Torr and 1e-3 for every gauge; what the
        # selectors show is what it must run with, so every gauge's pair is
        # pushed, not only the first (4.18.0 pushed Pd's alone, and Pu2 read
        # a thousand times high until its range was pressed again: queezz,
        # 2026-09-15, "it was already selected. So it's a UI lie").
        for gauge in self.control_dock.gauges:
            self.update_ig_range(gauge)
            self.update_ig_mode(gauge)
        # The same lie, for the sampling time. On 2026-10-19 the run was set
        # to 10 s from a browser, then stopped and started: the new reader
        # took settings.yml's 0.1 s while the dock, the watchdog and the web
        # view all still said 10 s, and it recorded at 0.1 s for two days.
        # queezz: "it should remember settings, not run with whatever is
        # default and invisible."
        seconds = self._screen_sampling()
        self.sampling = seconds
        self.workers["ADC"]["worker"].set_sampling_time(seconds)
        self.web_status.describe_run(len(self.config["ADC Signal Names"]), seconds)
        self.log_message(f"Started with sampling {seconds:g} s")
        # What this run uses is what the next program start puts back.
        self._remember_screen()

    def _screen_sampling(self):
        """The sampling time the Settings dock's combo shows, in seconds."""
        return float(self.settings_dock.samplingCb.currentText().split(" ")[0])

    def start_thread(self, worthre):
        """
        Starts Device Worker thread
        """
        worthre["worker"].moveToThread(worthre["thread"])
        self.connect_worker_signals(worthre["worker"])
        worthre["thread"].started.connect(worthre["worker"].start)
        worthre["thread"].start()

    def connect_worker_signals(self, worker):
        """
        Connects worker signals to the main thread
        """
        worker.data_ready.connect(self.on_worker_step)
        worker.sigDone.connect(self.on_worker_done)
        worker.send_message.connect(self.log_message)
        worker.send_routine.connect(self.log_routine)

        if worker.device_name == "ADC":
            worker.send_control_voltage.connect(self._set_cathode_current)
            worker.send_zero_adjustment.connect(self._adjust_zeros)

    def start_cross_connections(self):
        """Connect workers signals directly"""
        mfcs_worker = self.workers["MFCs"]["worker"]
        adc_worker = self.workers["ADC"]["worker"]
        mfcs_worker.send_presets_to_adc.connect(
            adc_worker.update_mfcs, type=QtCore.Qt.DirectConnection
        )

    # MARK: Abort
    def terminate_existing_threads(self):
        """
        Gracefully quits and waits for all currently running threads.
        """
        for device_name, worthre in self.workers.items():
            worthre["worker"].abort()
            worthre["thread"].quit()
            worthre["thread"].wait()

        self.workers = {}
        self.terminate_indicator_thread()
        if hasattr(self, "pi"):
            self.pi.stop()
        # All hardware shutdown work precedes the optional LAN recorder's wait.
        logger = getattr(self, "_kikusui_logger", None)
        if logger is not None:
            if logger.stop():
                self._remember_lost_since()
                self._kikusui_logger = None
                self._publish_kikusui({"status": "idle"})
            else:
                self.log_message("Kikusui recorder is still stopping; new telemetry start blocked")

    def terminate_indicator_thread(self):
        if hasattr(self, "indicator_led"):
            self.indicator_led.quit()
            self.indicator_led.wait()

    def turn_off_voltages(self):
        """Safely turn off any DAC voltages"""
        if not self.workers:
            return

        self.workers["ADC"]["worker"].set_plasma_current.emit(0)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=0.0)

        self._mfc_presets = {1: 0, 2: 0}
        self.update_current_values()
        self.workers["MFCs"]["worker"].output_voltage_signal.emit(1, 0)
        self.workers["MFCs"]["worker"].output_voltage_signal.emit(2, 0)

    @QtCore.pyqtSlot()
    def abort_all_threads(self):
        """
        Do we need two terminators?
        This one signals to workers to stop.
        """
        self.turn_off_voltages()
        self.terminate_existing_threads()
        self._last_sample_at = None
        self._reader_lost_since = None
        self._sampling_before_change = None
        # A warning about Ip with the filament off ends with the run.
        watch, self._filament_watch = self._filament_watch, None
        # A recorded switch still being checked ends with the run whose
        # samples would have answered it; the next Start begins a new
        # history, and no check is carried into it.
        self._switch_checks.clear()
        self.web_status.set_acquiring(False)
        # Nobody is left holding control of a rig that is not listening. The
        # Remote switch itself stays as the person at the rig set it: it is
        # theirs, and a browser that has just stopped a run must still be
        # able to start one.
        web_commands.release(self, "acquisition stopped")
        # Last, and guarded: the warning's end line, if one was standing. A
        # Log line that fails must not leave the run's state behind it.
        if watch is not None:
            try:
                self._say_filament(watch.close(time.time()))
            except Exception as error:  # noqa: BLE001 -- a warning never holds a stop
                _quiet_print(f"filament-off watch: {error}")

    # MARK: logging
    def generate_time_stamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_to_file(self, message):
        filepath = self.config["Log File Path"]
        time_stamp = self.generate_time_stamp()
        new_line = f"{time_stamp}, {message}\n"
        with open(filepath, "a") as f:
            f.write(new_line)

    #: How many lines the Log panel keeps; the oldest go first. The web
    #: view's Log is where the log is read now, and `controlunit.log` is the
    #: record; the panel is a fallback on the rig's own screen (queezz,
    #: 2026-10-21: "100 or 200 is more than enough. The qt side is there for
    #: redundancy and history, not for current use. We switched to the
    #: Webui."). Few enough lines that the panel never grows into a cost.
    LOG_PANEL_LINES = 200

    def log_message(self, message, htmltag="p", panel=True):
        """
        Append a message to the log file, the web view's Log and, unless
        `panel` is False, the Log panel on the rig's screen, with a timestamp.

        The panel used to be appended to by reading its whole document back
        as HTML and setting it again with one more line. That costs as much
        as the panel is long, and PyQt holds the interpreter while Qt does
        it, so the reader thread waited too: two days into a run the reader
        stood still for a minute and a half at every message, and a row was
        recorded every three minutes (the rig's logs, 2026-10-21). A line is
        now added at the end, and the panel is capped at `LOG_PANEL_LINES`.
        """
        time_stamp = self.generate_time_stamp()
        self.log_to_file(strip_tags(message))
        self.web_status.log(self._for_web(strip_tags(message)), time_stamp)
        if panel:
            self._show_in_log_panel(f"<{htmltag}>{time_stamp}: {message}</{htmltag}>")

    def log_routine(self, message):
        """A routine report: kept in the file and the web view's Log, and
        left off the panel.

        The 30-second timing summaries are about six thousand lines a day.
        They are the record of how the reader kept time and belong in the
        file; on the panel they would push out, within hours, every line a
        person needs to see. A timing overrun is not routine and still goes
        through `log_message` to the panel.
        """
        self.log_message(message, panel=False)

    def _show_in_log_panel(self, new_line):
        """Add one line of HTML at the end of the Log panel, and scroll to it.

        Only the new line is parsed. Its paragraph shape (a `p`'s spacing, an
        `h2`'s size) is read from the line itself and given to a fresh block,
        so it neither inherits the previous line's shape nor lends its own
        to the next one, which is what `QTextEdit.append` would do.
        """
        log = self.logDock.log
        document = log.document()
        if document.maximumBlockCount() != self.LOG_PANEL_LINES:
            document.setMaximumBlockCount(self.LOG_PANEL_LINES)
        shape = QtGui.QTextDocument()
        shape.setHtml(new_line)
        first = shape.begin()
        cursor = QtGui.QTextCursor(document)
        cursor.movePosition(QtGui.QTextCursor.End)
        if document.isEmpty():
            cursor.setBlockFormat(first.blockFormat())
            cursor.setBlockCharFormat(first.charFormat())
        else:
            cursor.insertBlock(first.blockFormat(), first.charFormat())
        cursor.insertHtml(new_line)
        log.moveCursor(QtGui.QTextCursor.End)

    # MARK: Data - handling
    def create_file(self, device_name):
        """
        Create file for saving sensor data
        """
        # if device_name == "MAX6675":
        #     self.savepaths[device_name] = os.path.join(
        #         os.path.abspath(self.datapath),
        #         f"cu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_temp.csv",
        #     )
        #     with open(self.savepaths[device_name], "w") as f:
        #         f.writelines(self.generate_header_temperature())
        if device_name == "ADC":
            self.savepaths[device_name] = os.path.join(
                os.path.abspath(self.datapath),
                f"cu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            with open(self.savepaths[device_name], "w") as f:
                f.writelines(self.generate_header_adc())
            # A new file is a new run for the web view: its ring empties and
            # its run facts start again. The name only, never the path.
            self.web_status.start_run(os.path.basename(self.savepaths[device_name]))
            self._note_file_size(device_name)

        self.log_datafile_name(device_name)

    def log_datafile_name(self, device_name):
        """Log filename of a datafile created"""
        message = (
            f"<font size=4 color='blue'>{device_name}</font>"
            f" savepath:<br> {self.savepaths[device_name]}"
        )
        self.log_message(message)

    def generate_header_adc(self):
        """
        Generage ADC header
        """
        hall_metadata = []
        for name, channel in self.config["Adc Channel Properties"].items():
            if channel.conversion_id == "Hall Sensor" and channel.supply_channel:
                hall_metadata.append(
                    f"# {name}_c [A] = {channel.amperes_per_volt:g} * "
                    f"{channel.nominal_supply:g} * ({name}/{channel.supply_channel}"
                    f" - {channel.zero_ratio:g}); valid supply "
                    f"{channel.supply_minimum:g}..{channel.supply_maximum:g} V; "
                    "invalid = NaN; raw voltages retained\n"
                )
        # Each gauge's mode column, and what its codes mean.
        gauge_metadata = []
        for name in self.config.get("Ion Gauges", []):
            channel = self.config["Adc Channel Properties"][name]
            gauge_metadata.append(
                f"# {name}_c: mode in {channel.mode_column} (0 = Torr linear, "
                f"1 = Pa log, 2 = off, converted value NaN), exponent in "
                f"{channel.scale_column}; raw voltages retained\n"
            )
        return [
            "# Title , Control Unit ADC signals\n",
            f"# Date , {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"# Columns , {', '.join(self.config['ADC Column Names'])}\n",
            f"# Signals , {', '.join(self.config['ADC Signal Names'])}\n",
            f"# Channels , {', '.join([str(i) for i in self.config['ADC Channel Numbers']])}\n",
            "# For converted signals '_c' is added\n",
            *hall_metadata,
            *gauge_metadata,
            "#\n",
            "# [Data]\n",
        ]

    def generate_header_temperature(self):
        """
        Generage Teperature header
        """
        return [
            "# Control Unit Temperature Control signals\n",
            f"# Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"# Columns: {', '.join(self.config['Temperature Columns'])}\n",
            f"# Heater GPIO: {self.config['Heater GPIO']}\n",
            f"# LED GPIO: {self.config['LED GPIO']}\n",
            "#\n",
            "# [Data]\n",
        ]

    # MARK: Data - append
    def append_data(self, device_name):
        """
        Add the delivered rows to what the window remembers of the run.

        This used to concatenate the whole run into a new frame at every
        delivery, which cost as much as the run was long and, two days into
        a 0.1 s run, more than the time between deliveries (2026-10-02).
        The history is a bounded store filled in place: see `history.py`.
        """
        self.datadict[device_name].append(self.newdata[device_name])

    #: How many points a curve is drawn with at most.
    PLOT_POINTS = 3000

    def select_data_to_plot(self, device_name):
        """
        The stretch `self.time_window` asks for, thinned for the screen:
        a dict of column arrays.
        """
        return self.datadict[device_name].view(self.time_window, self.PLOT_POINTS)

    def calculate_skip_points(self, l, noskip=5000):
        return 1 if l < noskip else l // noskip + 1

    def _recent_mean(self, device_name, column, rows=3):
        """The mean of a column's last rows, as the readouts show it; NaN
        while there is nothing to average."""
        try:
            tail = self.datadict[device_name].tail(column, rows)
        except KeyError:
            return float("nan")
        tail = tail[np.isfinite(tail)]
        return float(tail.mean()) if tail.size else float("nan")

    def save_data(self, device_name):
        """
        Save sensor data
        """
        savepath = self.savepaths[device_name]
        data = self.newdata[device_name]
        data.to_csv(savepath, mode="a", header=False, index=False)
        self._note_file_size(device_name)

    def _note_file_size(self, device_name):
        """Tell the web view how big the run file now is. One stat on the
        main thread, just after its own append, so the size never runs ahead
        of what is written; a failure leaves the size unknown and never stops
        the record."""
        if device_name != "ADC":
            return
        try:
            size = os.path.getsize(self.savepaths[device_name])
        except (OSError, KeyError):
            size = None
        self.web_status.record_file_size(size)

    # MARK: Worker Step
    @QtCore.pyqtSlot(list)
    def on_worker_step(self, result):
        """
        Collect data from worker
        - Recives data from worker(s)
        - Updates text indicators in GUI
        - Appends recived data to dataframes (call to self.__setStepData)
        - Updates data in plots (skips points if data is too big)
        """
        device_name = result[-1]
        self.step_methods[device_name](result)
        self.update_current_values()

    #: How late a delivery may arrive before the window stops redrawing to
    #: catch up. The reader stamps each batch as it hands it over; the gap
    #: to its arrival here is how far this thread is behind.
    BEHIND_SECONDS = BEHIND_SECONDS

    def _adc_step(self, result):
        received = time.monotonic()
        device_name = result[-1]
        #  self.data_ready.emit([newdata, self.device_name])
        batch = result[0]
        self._note_sample_arrived(batch.attrs.get('adc_period'))
        self.newdata[device_name] = batch
        emitted = batch.attrs.get('adc_emitted_at', received)
        period = batch.attrs.get('adc_period', 0.1)
        lag = max(0.0, received - emitted)
        # The record first. Nothing the screen does may stand between a
        # delivered row and the file.
        self.save_data(device_name)
        saved = time.monotonic()
        self.append_data(device_name)
        appended = time.monotonic()
        for plotname, name in zip(
            self.config["ADC Signal Names"], self.config["ADC Converted Names"]
        ):
            self.currentvalues[plotname] = self._recent_mean("ADC", name)
        # to debug mV signal from Baratron, ouptut it directly.
        self.baratronsignal1 = self._recent_mean("ADC", "Bu")
        self.baratronsignal2 = self._recent_mean("ADC", "Bd")
        if not self._note_backlog(lag):
            self.update_plots(device_name)
        self._publish_step(batch)
        self._watch_filament_off_current(batch)
        finished = time.monotonic()
        if not hasattr(self, '_adc_delivery_timing'):
            self._adc_delivery_timing = TimingDiagnostics(
                'ADC delivery', self.log_message, routine=self.log_routine)
        self._adc_delivery_timing.observe(
            {'queue': lag, 'save': saved - received, 'append': appended - saved,
             'display': finished - appended, 'total': finished - received},
            slow=lag > max(0.1, 3 * period) or finished - received > max(0.1, period),
        )

    def _note_backlog(self, lag):
        """Whether this thread is behind the reader, said once each way.

        Behind, the charts are not redrawn: redrawing is the one cost here
        that can be skipped, and skipping it is how the thread catches up.
        The file, the readouts and the web view are still served from every
        delivery. The web record carries the lag, so the health report and
        a browser can say it too.
        """
        behind = lag > self.BEHIND_SECONDS
        self.web_status.record_backlog(lag)
        if behind and self._behind_since is None:
            self._behind_since = time.monotonic()
            self.log_message(
                f"<font color='red'>Screen behind the reader</font> by {lag:.0f} s:"
                " chart redraws are paused until it catches up. Rows are still"
                " written as they are delivered",
                htmltag="div",
            )
        elif not behind and self._behind_since is not None:
            lasted = time.monotonic() - self._behind_since
            self._behind_since = None
            self.log_message(
                f"<font color='#1cad47'>Screen caught up</font> with the reader"
                f" after {lasted:.0f} s; charts are redrawn again",
                htmltag="div",
            )
        return behind

    # MARK: Ip with the filament off
    def _lit_above(self):
        """The current above which the reader calls a discharge lit: its own
        `lit_above` while one runs, else settings.yml's `Lit Above A`."""
        worker = (self.workers.get("ADC") or {}).get("worker") if self.workers else None
        value = getattr(worker, "lit_above", None)
        if value is None:
            tuning = self.config.get("Plasma Current PID") or {}
            value = tuning.get("Lit Above A", LIT_ABOVE_A)
        return float(value)

    def _watch_filament_off_current(self, batch):
        """Say when Ip reads current with the filament off (`filament_off`).

        queezz, 2026-11-13: "if we see the current with the filament power
        off, it's a SUS. So we should warn, really. Sometimes the current
        sensor gets a wrong zero". Each delivered row is judged on its own
        cathode drive and time, and on the supply's telemetry as this thread
        last had it; Ip is taken as the PID sees it, after the Ip zero. One
        red line when it has lasted three seconds, one plain line when it
        ends. Nothing is zeroed or driven, and nothing here may keep a row
        from the file, which is already written.
        """
        watch = self._filament_watch
        if watch is None:
            return
        try:
            zero = float(self.zero_adjustment.get("Ip", 0) or 0)
            supply = getattr(self, "_kikusui_snapshot", None) or {}
            rows = zip(batch["date"], batch["PresetV_cathode"], batch["Ip_c"])
            for stamp, drive, current in rows:
                off, why = filament_off.filament_off(drive, supply)
                try:
                    ip = float(current) - zero
                except (TypeError, ValueError):
                    ip = float("nan")
                # The rows' own clock, read as the local time it was
                # written in: `close` compares it with `time.time()`.
                self._say_filament(watch.observe(_epoch(stamp), ip, off, why))
        except Exception as error:  # noqa: BLE001 -- a warning never stops a run
            _quiet_print(f"filament-off watch: {error}")

    def _say_filament(self, said):
        """One of `FilamentOffCurrent`'s lines, the head red when it warns."""
        if said is None:
            return
        head, rest, alarm = said
        if alarm:
            self.log_message(f"<font color='red'>{head}</font>{rest}", htmltag="div")
        else:
            self.log_message(head + rest)

    def _membrane_heater_step(self, result):
        device_name = result[-1]
        # [self.data, self.device_name]
        self.newdata[device_name] = result[0]
        self.append_data(device_name)
        self.save_data(device_name)
        # here 3 is number of data points recieved from worker.
        # TODO: update to self.newdata[device_name]['T'].mean()
        self.currentvalues["T"] = self._recent_mean(device_name, "T")
        self.update_plots(device_name)

    # MARK: reader watchdog
    def _note_sample_arrived(self, period=None):
        """A sample landed: the reader is alive, and if it had been given up
        on, say it is back and how long the gap in the file is.

        `period` is the sampling time the reader took the delivery at (the
        batch's `adc_period`). The allowance a sampling change bought ends
        with the first delivery taken at the new time, not merely the first
        to arrive: one the reader handed over just before the change, and
        this thread reads just after it, says nothing about how long the
        reader will now take. Unknown counts as the new time.
        """
        try:
            taken_at_new = period is None or abs(float(period) - float(self.sampling)) < 1e-9
        except (TypeError, ValueError):  # nothing here may keep a row from the file
            taken_at_new = True
        if taken_at_new:
            self._sampling_before_change = None
        now = time.monotonic()
        if self._reader_lost_since is not None:
            gap = now - self._reader_lost_since
            self.log_message(
                f"<font color='#1cad47'>Reader back</font> after {gap:.0f} s"
                " without a sample; the file has a gap of that length",
                htmltag="div",
            )
            self._reader_lost_since = None
        self._last_sample_at = now

    def _check_reader(self):
        """Say so, once, when the reader has stopped delivering samples.

        Nothing is driven from here: the outputs stay exactly where they
        were (owner decision 2026-09-07, "Hold and alarm!"), because the
        cathode holding is what saved Mizuno-kun's depositions. What this
        adds is the sentence the screen never had: that the file stopped,
        and what to press.
        """
        if not self.workers or self._last_sample_at is None:
            return
        if self._reader_lost_since is not None:
            return
        age = time.monotonic() - self._last_sample_at
        # Judged by the longer of the old and the new sampling time until a
        # sample taken at the new one arrives. The reader takes a new time
        # only when the period it is in has ended, and an averaged period
        # runs to its end, so from 10 s to 0.1 s the next row can still be
        # ten seconds away. Judged at once by the new, short line, a reader
        # sleeping out its old period was called lost: 2026-10-23 15:48:51,
        # "Reader lost: no sample for 7 s", while cu_20261023_154824.csv
        # went from 15:48:44.31 to 15:48:54.31 without a gap. Resetting the
        # clock at the change would not do: a change made just after a
        # sample still leaves ten seconds to the next one, twice the short
        # line, and a reader that had already stopped would be given a
        # fresh start it never earned. Counted from the last sample, a
        # reader silent through the change is still called lost, by the
        # longer line.
        judged_by = self.sampling
        if self._sampling_before_change is not None:
            judged_by = max(judged_by, self._sampling_before_change)
        if age <= reader_lost_after(judged_by):
            return
        self._reader_lost_since = self._last_sample_at
        self.log_message(
            f"<font color='red'>Reader lost</font>: no sample for {age:.0f} s."
            " Outputs are held where they were. Stop and Start restarts the"
            " reader; the manual cathode drive still works meanwhile",
            htmltag="div",
        )

    # MARK: worker done
    @QtCore.pyqtSlot(str)
    def on_worker_done(self, device_name):
        if device_name == "ADC" and hasattr(self, "_adc_delivery_timing"):
            self._adc_delivery_timing.report()
            del self._adc_delivery_timing
        self.log_message(
            f"Sensor thread <font size=4 color='blue'> {device_name}</font> <font size=4 color={'red'}>stopped</font>",
            htmltag="div",
        )
        self.__workers_done += 1
        self.reset_data(device_name)

        if self.__workers_done == 2:
            self.abort_all_threads()

    def reset_data(self, device_name):
        self.datadict[device_name].clear()
        self.newdata[device_name] = self.newdata[device_name].iloc[0:0]

    # MARK: update values
    def update_current_values(self):
        """
        update current values when new signal comes
        """
        # self.tempcontrolDock.update_current_values(self.__temp, f"{self.currentvalues['T']:.0f}")
        self.web_status.record_setpoints(
            mfc1_v=self._mfc_presets[1], mfc2_v=self._mfc_presets[2]
        )
        self.gasflow_dock.update_display(
            self._mfc_presets[1], f"{self.currentvalues['MFC1']*1000:.0f}", 1
        )
        self.gasflow_dock.update_display(
            self._mfc_presets[2], f"{self.currentvalues['MFC2']*1000:.0f}", 2
        )
        # self.control_dock.gaugeT.update_value(self.currentvalues["T"])

        self._render_value_browser()

    @QtCore.pyqtSlot(dict)
    def _adjust_zeros(self, zero_adjustment):
        """Set zero adjustment dict"""
        self.zero_adjustment = zero_adjustment
        self.web_status.record_zeros(zero_adjustment)

    # MARK: Update Plots
    def update_plots(self, device_name):
        """plot updater abstraction"""
        self.plot_methods[device_name]()

    def update_plots_max6675(self):
        """
        MAX6675 data: update plots
        """
        df = self.select_data_to_plot("MAX6675")
        time = df["time"].astype(float)
        temperature = df["T"].astype(float)
        skip = self.calculate_skip_points(time.shape[0])
        self.graph.valueTPlot.setData(time[::skip], temperature[::skip])

    def update_plots_adc(self):
        """
        Update plots for ADC dataframe
        """
        df = self.select_data_to_plot("ADC")
        # time = df["time"].values.astype(float)
        utc_offset = 9
        # Vectorize the same naive timestamp arithmetic. Explicit nanoseconds
        # keep this correct across pandas versions with different resolutions.
        if "date" not in df:
            return  # nothing delivered yet
        time = (np.asarray(df["date"], dtype='datetime64[ns]').astype('int64') / 1e9
                - utc_offset * 3600)
        skip = self.calculate_skip_points(time.shape[0])

        what_to_plot = ["Ip", *Graph.PRESSURE_CURVES]
        for name in what_to_plot:
            values = np.asarray(df[name + "_c"], dtype=float) - self.zero_adjustment.get(
                name, 0
            )
            self.graph.plot_lines[name].setData(time[::skip], values[::skip])

    @QtCore.pyqtSlot()
    def set_heater_goal(self):
        if not self.workers:
            return
        value = self.tempcontrolDock.temperatureSB.value()
        self.__temp = value
        temp_now = self.currentvalues["T"]
        self.tempcontrolDock.set_heating_goal(self.__temp, f"{temp_now:.0f}")
        self.workers["MembraneTemperature"]["worker"].setPresetTemp(self.__temp)

    def get_calibration_time(self):
        txt = self.calibration_dock.scaleBtn.currentText()
        return self.calibration_dock.calibration_durations[txt]

    # MARK: QMS Calibration
    def calibration(self):
        """
        Start and stop calibration
        """
        if not self.workers:
            return
        mfc = self.workers["MFCs"]["worker"]
        if mfc.calibrating:
            question = "STOP calibration?"
            if self.popup_confirmation_window(question):
                mfc.calibrating = False
            return

        question = "START calibration?"
        if self.popup_confirmation_window(question):
            self.indicator_led.qms_calibration_indicator()
            mfc.start_calibration_signal.emit(
                self._mfc_presets[1], 10, self.get_calibration_time()
            )

    # MARK: MFC signal
    def stop_mfc(self):
        """
        Sets 0V output for both Flow Controllers.
        """
        if not self.workers:
            return
        self._mfc_presets = {1: 0, 2: 0}
        self.update_current_values()
        self.workers["MFCs"]["worker"].stop_signal.emit()

    def set_mfc_goal(self, mfc_num):
        if not self.workers:
            return
        value = self.gasflow_dock.get_massflow_from_gui(mfc_num)
        self._mfc_presets[mfc_num] = value
        voltage_now = self.currentvalues[f"MFC{mfc_num}"]
        self.update_current_values()
        self.workers["MFCs"]["worker"].output_voltage_signal.emit(
            mfc_num, self._mfc_presets[mfc_num]
        )

    # MARK: Plasma Control
    def set_currentcontrol_voltage(self):
        """
        Send control voltage to ADCs plasma current PID
        """
        if not self.workers:
            return
        ampere = self.plasma_control_dock.ampere_spin_box.value()
        # The PID owns the DAC from here on, so the manual box says so.
        self.plasma_control_dock.cathode_spin_box.setValue(0)
        self.workers["ADC"]["worker"].set_plasma_current.emit(ampere)
        self.web_status.record_setpoints(plasma_a=float(ampere))

    @QtCore.pyqtSlot()
    def turn_off_currentcontrol_voltage(self):
        """Stop plasma current PID and force the DAC output to 0 V."""
        if not self.workers:
            return
        self.plasma_control_dock.ampere_spin_box.setValue(0.0)
        self.plasma_control_dock.cathode_spin_box.setValue(0)
        self.workers["ADC"]["worker"].set_plasma_current.emit(0)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=0.0)
        self.log_message("Plasma current PID turned off")

    def hold_currentcontrol_voltage(self):
        """Turn the PID off and keep the cathode at the drive it gives now.

        The other way off. "PID off" drops the drive to zero, and on
        2026-11-13 it put out two discharges the loop had just brought to
        1.5 A (16:20:03, 16:38:45), under a button that said nothing about
        the drive. This hands the cathode back to the hand, Manual, at the
        loop's own last command, as the manual mode's Set would with that
        number typed in.
        """
        if not self.workers:
            return
        drive = float(getattr(self.workers["ADC"]["worker"], "control_voltage", 0.0) or 0.0)
        self.plasma_control_dock.cathode_spin_box.setValue(int(round(drive)))
        self.set_cathode_drive()

    @QtCore.pyqtSlot(float)
    def _set_cathode_current(self, control_voltage):
        """
        Set voltage, recived from ADC worker in PlasmaCurrent worker
        For PID control

        The web record follows the DAC rather than the PID's setpoint: this
        is the only place that knows what the cathode is actually being
        driven with while the loop is closed, and "is anything driven" is
        the question the rig's operating state answers.

        A command the loop sent before it was turned off is dropped. The
        reader steps the loop on its own thread and the command crosses here
        queued, so one decided just before a press arrives just after it:
        the review of 2026-11-13 had PID off end with the DAC at 2200 mV, and
        Hold at 2240 mV where it held 2211. The loop's setpoint is written
        only here, on the main thread (`set_plasma_current` and
        `set_manual_drive` are direct connections), so a setpoint of zero
        when the command lands means Off, Hold, a manual Set or Stop all
        outputs came first, and the hand, not the loop, owns the DAC. A zero
        still passes: it is what turning the loop off sends.
        """
        if not self.workers:
            return
        reader = self.workers["ADC"]["worker"]
        if control_voltage and not getattr(reader, "plasma_current_setpopint", 0):
            return
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(
            control_voltage
        )
        self.web_status.record_setpoints(cathode_mv=float(control_voltage))

    # MARK: ADC controls
    def _set_zero_ip(self):
        """set current ip as 0"""
        self._zero_from_dock("Ip")

    def _zero_from_dock(self, channel):
        """A Scales dock button: take the baseline, and say so in the log.

        A browser's Zero now takes the same baseline but writes its own log
        line, naming who asked, so a zero is never logged twice.
        """
        if not self.workers:
            return
        if self.set_zero_baseline(channel):
            self.log_message(f"Baseline of {channel} taken")
        else:
            self.log_message(f"Baseline of {channel} not taken: no samples yet")

    #: How much of the run a baseline averages over. Two seconds is twenty
    #: samples at the usual rate: enough to sit above the Hall sensor's noise,
    #: short enough that the reading is still "now".
    BASELINE_SECONDS = 2.0

    def baseline_of(self, channel):
        """
        The mean of the last two seconds of `channel`, as converted and
        never zero-adjusted, or None while there is not a sample yet.
        """
        try:
            rows = max(1, int(round(self.BASELINE_SECONDS / float(self.sampling))))
        except (TypeError, ValueError, ZeroDivisionError):
            rows = 20
        try:
            mean = self._recent_mean("ADC", channel + "_c", rows)
        except (KeyError, AttributeError, TypeError, ValueError):
            return None
        if mean != mean:
            return None
        return mean

    def set_zero_baseline(self, channel):
        """
        Take what `channel` has read over the last seconds as its zero.
        True when a baseline was taken; False when nothing is running or no
        sample has arrived yet, so a caller can say so instead of claiming
        a zero it did not take.

        One path for all three channels and for both origins: the buttons in
        the Scales dock and a browser's Zero now both arrive here, and the
        worker answers with every zero at once through `send_zero_adjustment`.
        """
        if not self.workers:
            return False
        value = self.baseline_of(channel)
        if value is None:
            return False
        self.workers["ADC"]["worker"].set_zero_signal.emit(channel, value)
        return True

    def _gauge_selectors(self, gauge):
        """One gauge's mode box and range box; the first gauge when unnamed."""
        if gauge is None:
            gauge = next(iter(self.control_dock.gauges))
        return gauge, self.control_dock.gauges[gauge]

    def update_ig_mode(self, gauge=None):
        """
        Update mode of one IG controller:
        Torr and linear
        or
        Pa and log
        """
        gauge, (mode_box, _) = self._gauge_selectors(gauge)
        self.web_status.record_gauge(gauge, mode=mode_box.currentText())
        if not self.workers:
            return
        value = mode_box.currentIndex()
        self.workers["ADC"]["worker"].set_ig_mode_signal.emit(gauge, value)

    def update_ig_range(self, gauge=None):
        """
        Update range of one IG controller:
        10^{-3} - 10^{-8} multiplier when in linear mode (Torr)
        """
        gauge, (_, range_box) = self._gauge_selectors(gauge)
        value = range_box.value()
        self.web_status.record_gauge(gauge, range=value)
        if not self.workers:
            return
        self.workers["ADC"]["worker"].set_ig_range_signal.emit(gauge, value)

    def _gauge_selector_moved(self, gauge, what):
        """One of the dock's gauge selectors moved: tell the worker and, when
        it was a person's hand on the dock, say so in the Log.

        A press on the rig's own screen used to leave no line at all; only a
        browser's did ("Remote: … Pd range -7"). The presses of 2026-11-02
        16:36:44 and 16:37:04, and of 2026-11-11 16:44:19, 16:45:59, 16:46:09
        and 16:49:09, are seen only in the file's IGmode and IGscale columns.
        The line uses the browser's own words for the same setting, without
        its "Remote: who:", as the dock's other lines do.

        Not when the program moved the selector itself: putting the last
        run's settings back at launch, carrying out a browser's command, or
        following the Diagram, each of which logs its own line. Start's push
        into fresh workers (`_apply_screen_settings`) calls the updaters
        directly and never comes through here.

        Whoever moved it, the screen is remembered for the next start
        (`_remember_screen`), except while it is being put back, and a mode
        that reads pressure is kept as the one a gauge the Diagram turns
        back on returns to.
        """
        if what == "mode":
            self._note_reading_mode(gauge)
            self.update_ig_mode(gauge)
        else:
            self.update_ig_range(gauge)
        # A browser's command moves the selector too, so this one write
        # covers both; a value set to what it already was moves nothing.
        self._remember_screen()
        if self._selector_mover is not None:
            return
        mode_box, range_box = self.control_dock.gauges[gauge]
        value = {"gauge": gauge}
        if what == "mode":
            value["mode"] = mode_box.currentText()
        else:
            value["range"] = range_box.value()
        self.log_message(web_commands.summarise("gauge", value))

    @QtCore.pyqtSlot()
    def __set_gain(self):
        """
        Set gain for Baratron channel on ADC
        Parameters
        ----------
        value: int
            gain, values [1,2,5,10] (in V)
        """
        if not self.workers:
            return
        txt = self.adcgain_dock.gain_box.currentText()
        gain = self.adcgain_dock.gains[txt]
        self.workers["ADC"]["worker"].set_adc_gain_signal.emit(gain)

    @QtCore.pyqtSlot()
    def __set_sampling(self):
        """
        The Settings dock's Set button: read the combo, then the one path.
        """
        if not self.workers:
            return
        txt = self.settings_dock.samplingCb.currentText()
        self.set_sampling(float(txt.split(" ")[0]))

    def set_sampling(self, seconds):
        """
        Set sampling time for all threads, whoever asked.

        The dock's combo is set to the matching item first, so the rig's own
        screen agrees with what a browser did; the choices a browser may send
        are the combo's own (`web.commands.SAMPLING_CHOICES`, held equal to
        the dock by a test).
        """
        if not self.workers:
            return
        value = float(seconds)
        index = self.settings_dock.samplingCb.findText(f"{value:g} s")
        if index >= 0:
            self.settings_dock.samplingCb.setCurrentIndex(index)
        previous = float(self.sampling)
        self.sampling = value
        if value != previous:
            # The watchdog keeps the longest time in force since the last
            # sample taken at the current one (`_check_reader`).
            self._sampling_before_change = max(
                previous, self._sampling_before_change or 0.0
            )
        self.update_plot_timewindow()
        self.workers["ADC"]["worker"].set_sampling_time(value)
        self.web_status.describe_run(len(self.config["ADC Signal Names"]), value)
        self.log_message(f"ADC sampling set to {value}")
        self._remember_screen()

    @QtCore.pyqtSlot()
    def set_cathode_drive(self):
        """
        The manual mode: hold the cathode DAC at the Cathode dock's
        millivolts with the plasma current PID off, whoever asked.

        The PID is turned off first and its box zeroed, so the rig's own
        screen says which of the two is driving. The DAC is written from
        here, on the main thread, straight to the DAC worker: nothing about
        this passes through the reader, so it works while the reader is
        dead, which is what a person flying blind on 2026-09-09 needed.
        The PID is off and the cathode is driven: the exact pair that read
        as "nothing running" until the record carried the DAC as its own
        fact, and the pair that kept a plasma on after the reader died on
        2026-08-19.
        """
        if not self.workers:
            return
        value = float(self.plasma_control_dock.cathode_spin_box.value())
        self.plasma_control_dock.ampere_spin_box.setValue(0.0)
        # The reader is told the held value and turns its loop off. It used
        # to be told "PID off", which zeroed the DAC for an instant before
        # the line below set it, and left the file's PresetV_cathode at 0.
        self.workers["ADC"]["worker"].set_manual_drive.emit(value)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(value)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=value)
        self.log_message(f"Cathode drive set to {value:.0f} mV, PID off")

    # MARK: the supply's own output
    #: Why a press could not even be attempted, in the words the browser and
    #: the rig's own Log both use. `web.commands.NO_SUPPLY_ANSWER` is held
    #: equal to the first by a test, so a refusal reads the same everywhere.
    NO_SUPPLY_ANSWER = "the supply is not answering; turn it on at the supply"
    NO_SUPPLY_LINK = "the supply's LAN link is not configured here"

    def _cathode_output_state(self):
        """What the telemetry last said the supply's output was, or `None`.

        `None` is every kind of not-knowing at once — no recorder, LAN lost,
        stale, never configured — and they are one fact for this purpose:
        nothing may be switched *on* by somebody who cannot see it. Off is
        not asked this question; zeroing something is safe from blind.
        """
        snapshot = getattr(self, "_kikusui_snapshot", None) or {}
        if snapshot.get("status") not in ("ok", "dummy"):
            return None
        state = snapshot.get("output_on")
        return state if state in (0, 1) else None

    def set_cathode_output(self, on):
        """The supply's output switch, the only thing this program writes.

        Owner decision 2026-09-15, live: "Kikusui has LAN now, I want the
        one-off signal button in our control. Then we turn that one off no
        matter the dac voltage", and, the same day, "Off and on. Why not?
        Then we have full cathode control when powered".

        Nothing here waits on a network. While a run records, the request is
        handed to the recorder's own thread, which owns the socket; with no
        recorder a short daemon thread opens a connection of its own and
        says how it went through `kikusui_message`, the queued signal that
        already carries this recorder's words to the Log. Either way this
        method returns at once, and the Log carries the outcome.

        Returns `(whether the write is on its way, why not)`.
        """
        if on and self._cathode_output_state() is None:
            return False, self.NO_SUPPLY_ANSWER
        logger = getattr(self, "_kikusui_logger", None)
        if logger is not None and logger.request_output(on):
            return True, ""
        try:
            config = load_kikusui_config()
        except Exception as error:  # noqa: BLE001 -- a broken file is a reason, not a crash
            return False, str(error)
        if config is None:
            return False, self.NO_SUPPLY_LINK
        if dummy_hardware_loaded() and not config.dummy:
            return False, "dummy hardware never contacts the supply"
        threading.Thread(
            target=set_supply_output,
            args=(config, on, self.kikusui_message.emit, self._remember_lost_since()),
            name="Kikusui output switch",
            daemon=True,
        ).start()
        return True, ""

    def turn_on_cathode_output(self):
        """Switch the supply's output on, if the telemetry can see it."""
        return self._press_cathode_output(True)

    def turn_off_cathode_output(self):
        """Switch the supply's output off, whatever the DAC is holding.

        This is the press queezz asked for: the drive and the output are two
        different wires, and dropping the drive to zero is not the same as
        opening the output. It is always allowed, from the dock and from a
        browser, like Stop all outputs.
        """
        return self._press_cathode_output(False)

    def _press_cathode_output(self, on):
        """One press, and the Log line when it could not even be attempted."""
        sent, reason = self.set_cathode_output(on)
        if not sent:
            self.log_message(
                "Kikusui output {} not sent: {}; manual drive unchanged".format(
                    "ON" if on else "OFF", reason
                )
            )
        return sent, reason

    @QtCore.pyqtSlot()
    def turn_off_cathode_drive(self):
        """Drop the manual cathode drive to zero; the PID stays off."""
        if not self.workers:
            return
        self.plasma_control_dock.cathode_spin_box.setValue(0)
        self.workers["ADC"]["worker"].set_plasma_current.emit(0)
        self.workers["PlasmaCurrent"]["worker"].output_voltage_signal.emit(0)
        self.web_status.record_setpoints(plasma_a=0.0, cathode_mv=0.0)
        self.log_message("Cathode drive turned off")


# MARK: Web view
def parse_arguments(argv=None):
    """
    Read the command line. Without --web nothing about the program changes.
    """
    parser = argparse.ArgumentParser(
        prog="controlunit",
        description="Plasma-lab control and data acquisition.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="also serve the read-only web view in this process",
    )
    parser.add_argument(
        "--host",
        # Answers on the lab network by default (owner decision 2026-09-04,
        # "the whole point is LAN"): the rig is one machine in the lab and the
        # view is read from a laptop or a phone. Pass --host 127.0.0.1 to
        # narrow a run to the Pi itself. The view stays read-only either way.
        default="0.0.0.0",
        help="address the web view listens on (default: the lab network)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4187,
        help="port the web view listens on (default: 4187)",
    )
    return parser.parse_args(argv)


#: How often the main thread looks for what a browser asked for. Fast enough
#: that a press feels answered within one poll of the page, slow enough that
#: it costs the acquisition loop nothing.
WEB_COMMAND_MS = 200


def start_web_view(widget, arguments):
    """
    Start the web view on a daemon thread, if it was asked for.

    The thread reads the status record the main thread writes and appends to
    the command queue the main thread drains; it never calls a worker slot,
    so worker ownership and the hardware-first shutdown order are untouched.
    The timer belongs to the main thread and exists only under --web.
    """
    if not arguments.web:
        return None
    from controlunit.web.server import serve_in_thread

    timer = QtCore.QTimer(widget)
    timer.timeout.connect(widget._drain_web_commands)
    timer.start(WEB_COMMAND_MS)
    widget.web_command_timer = timer

    serve_in_thread(
        widget.web_status,
        commands=widget.web_commands,
        host=arguments.host,
        port=arguments.port,
    )
    print(f" Web view: http://{arguments.host}:{arguments.port}/")
    return True


def install_stop_handlers(widget, set_handler=signal.signal):
    """End on a signal the way Stop and Quit end, and say why
    (`MainApp.shut_down`); and hold on an uncaught error, and say what it
    was (`MainApp.note_uncaught`).

    SIGTERM, SIGHUP and SIGINT each get a handler that only notes the
    signal; `SIGNAL_CHECK_MS`'s timer acts on it inside the event loop, so a
    signal never runs the shutdown halfway through some other slot. Before
    this a SIGTERM killed the process where it stood, with the DACs holding
    whatever they held, and a SIGHUP from a closed terminal did the same.
    Once the shutdown has begun, SIGTERM and SIGINT are given back their
    default (`MainApp._let_a_signal_end_it`), so a shutdown that hangs can
    still be ended.

    `sys.excepthook` writes the error's last line to the Log, then hands the
    error to the hook that was there before, which prints the traceback to
    stderr; a repeat the Log holds back is not printed again either. The
    program carries on. Installed from `main` only, after the window
    exists, and never by a test unless it asks: `set_handler` is a test's.
    """
    for name, _words in STOP_SIGNALS:
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            set_handler(number, widget._signal_received)
        except (OSError, RuntimeError, ValueError):
            continue
    widget._set_signal_handler = set_handler
    timer = QtCore.QTimer(widget)
    timer.timeout.connect(widget._take_pending_stop)
    timer.start(SIGNAL_CHECK_MS)
    widget.stop_signal_timer = timer

    before = sys.excepthook

    def hook(kind, error, trace):
        said = True
        try:
            said = widget.note_uncaught(kind, error, trace) is not False
        except Exception:  # noqa: BLE001 -- the traceback must still print
            pass
        if said:
            before(kind, error, trace)

    sys.excepthook = hook
    return hook


def start_beside(widget, arguments):
    """What runs beside the window in a real start, and never in a test that
    builds one: the web view, the Pi's health, and the ways to end."""
    start_web_view(widget, arguments)
    widget.start_pi_health()
    install_stop_handlers(widget)


# MARK: End
def main():
    """
    for command line script using entrypoint
    """
    arguments = parse_arguments()
    app = QtWidgets.QApplication([])
    widget = MainApp(app)
    start_beside(widget, arguments)
    sys.exit(app.exec_())


if __name__ == "__main__":
    from __init__ import _echelle_base

    arguments = parse_arguments()
    pth = str(_echelle_base / "icons/controlunit.png")
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(pth))
    widget = MainApp(app)
    start_beside(widget, arguments)

    sys.exit(app.exec_())

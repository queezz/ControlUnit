"""PWR401L telemetry in a separately timestamped CSV, and the two writes.

The link is a measurement link with exactly two exceptions. Its wire
commands are the four queries below plus `OUTP 0` and `OUTP 1` — the
supply's output off and on (owner decision 2026-09-15, live: "Kikusui has
LAN now, I want the one-off signal button in our control. Then we turn that
one off no matter the dac voltage", and, the same day, "Off and on. Why not?
Then we have full cathode control when powered"). There is no third write:
no setpoint, no reset, no clear-status, nothing that could hand the supply a
voltage or a current. The recorder still never drives the supply of its own
accord; both writes happen only because a person pressed something.

Off is a safety press and is never gated. On is gated like any other setter,
and refused unless the telemetry is fresh, so nothing is ever switched on
blind.

The logger owns its socket and file; it never calls a Qt widget, the ADC
reader or a DAC worker. A press from any thread is handed to the logger's
own thread, which is the only thread that ever touches the socket.
"""

import csv
import datetime
import ipaddress
import math
import queue
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from controlunit._version import __version__


@dataclass(frozen=True)
class KikusuiConfig:
    host: str = ""
    port: int = 5025
    interval_s: float = 0.5
    timeout_s: float = 1.0
    retry_s: float = 5.0
    dummy: bool = False

    def __post_init__(self):
        if type(self.dummy) is not bool:
            raise TypeError("dummy must be true or false")
        if not self.dummy:
            # No DNS resolver can hold up shutdown beyond the socket timeout.
            if not isinstance(self.host, str):
                raise TypeError("host must be a numeric IP address string")
            ipaddress.ip_address(self.host)
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be an integer from 1 to 65535")
        for name, low, high in (
            ("interval_s", 0.1, 60), ("timeout_s", 0.1, 5), ("retry_s", 1, 60)
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high} seconds")


def load_config(path=None):
    """Absent configuration disables telemetry; invalid configuration is explicit."""
    path = Path(path) if path is not None else Path.home() / ".controlunit/kikusui.yml"
    try:
        with path.open(encoding="utf-8") as source:
            values = yaml.safe_load(source)
    except FileNotFoundError:
        return None
    if not isinstance(values, dict):
        raise TypeError("Kikusui configuration must be a mapping")
    if any(key not in KikusuiConfig.__dataclass_fields__ for key in values):
        raise ValueError("Unknown Kikusui configuration field")
    return KikusuiConfig(**values)


#: The whole of what this program may ever put on the wire, and the sentence
#: it refuses everything else in. Four queries and two writes; `VOLT`, `CURR`,
#: `*RST`, `OUTP ON` and every other SCPI word are refused before a byte is
#: sent, because a client that can only say these six cannot set a supply.
PERMITTED = "Only the four telemetry queries and OUTP 0 / OUTP 1 are permitted"


class ReadOnlyClient:
    """Read-only but for the output switch: it cannot set a voltage or current."""

    QUERIES = ("*IDN?", "MEAS:VOLT?", "MEAS:CURR?", "OUTP?")
    #: The two writes, in the words the supply reads them in.
    WRITES = ("OUTP 0", "OUTP 1")
    ALLOWED = QUERIES + WRITES

    def __init__(self, config):
        self.config = config
        self.sock = None
        self.identity = ""
        self.expected_identity = None

    def close(self):
        sock, self.sock = self.sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def _deadline(self, sock, deadline):
        """Arm the socket for whatever is left of this transaction's budget."""
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("Telemetry query deadline exceeded")
        sock.settimeout(value)

    def _send(self, command, deadline):
        """The one place a byte reaches the supply, and the allowlist gate.

        Every command, query or write, passes through here, so the allowlist
        is a property of the transport rather than of each caller: an
        unpermitted word raises before `sendall`, with nothing on the wire.
        """
        if command not in self.ALLOWED:
            raise ValueError(PERMITTED)
        sock = self.sock
        if sock is None:
            raise OSError("Telemetry connection closed")
        self._deadline(sock, deadline)
        sock.sendall((command + "\n").encode("ascii"))
        return sock

    def _query(self, command, deadline):
        # A write answers nothing, so reading one back would only wait for a
        # reply the supply will never send.
        if command not in self.QUERIES:
            raise ValueError(PERMITTED)
        sock = self._send(command, deadline)

        def remaining():
            self._deadline(sock, deadline)

        reply = bytearray()
        while b"\n" not in reply:
            remaining()
            chunk = sock.recv(257 - len(reply))
            if not chunk:
                raise OSError("Supply closed the telemetry connection")
            reply.extend(chunk)
            if len(reply) > 256:
                raise ValueError("Oversized SCPI reply")
        line, extra = bytes(reply).split(b"\n", 1)
        if extra.strip():
            raise ValueError("Unexpected extra SCPI reply")
        return line.decode("ascii").strip()

    def _connect(self, deadline):
        """Open the socket if it is shut, and prove what answered on it."""
        if self.sock is not None:
            return
        address = ipaddress.ip_address(self.config.host)
        sock = socket.socket(socket.AF_INET6 if address.version == 6 else socket.AF_INET)
        self.sock = sock
        sock.settimeout(self.config.timeout_s)
        sock.connect((self.config.host, self.config.port))
        identity = self._query("*IDN?", deadline)
        parts = identity.split(",")
        if len(parts) != 4 or parts[:2] != ["KIKUSUI", "PWR401L"]:
            raise ValueError("Expected a KIKUSUI PWR401L")
        # A reconnection to another serial number must not silently splice runs.
        key = tuple(parts[:3])
        if self.expected_identity is not None and key != self.expected_identity:
            raise ValueError("Supply identity changed during this run")
        self.expected_identity = key
        self.identity = identity

    def set_output(self, on):
        """The one write, in its two directions, with the supply's own answer.

        Identity is verified before anything is written, so `OUTP 0` can only
        reach a PWR401L this client has identified — never whatever else
        happens to be answering on that address. The readback is queried back
        on the same socket and returned, so a press that did not take is
        reported as one that did not take rather than assumed.
        """
        deadline = time.monotonic() + self.config.timeout_s
        self._connect(deadline)
        self._send("OUTP 1" if on else "OUTP 0", deadline)
        state = self._query("OUTP?", deadline)
        if state not in ("0", "1"):
            raise ValueError("Invalid SCPI output state")
        return int(state)

    def sample(self):
        # One deadline for the entire transaction, even on a slow trickle of bytes.
        deadline = time.monotonic() + self.config.timeout_s
        self._connect(deadline)
        voltage = float(self._query("MEAS:VOLT?", deadline))
        current = float(self._query("MEAS:CURR?", deadline))
        output = self._query("OUTP?", deadline)
        if not all(math.isfinite(v) and abs(v) < 1e30 for v in (voltage, current)):
            raise ValueError("Invalid SCPI measurement")
        if output not in ("0", "1"):
            raise ValueError("Invalid SCPI output state")
        return voltage, current, int(output)


class DummyClient:
    """Off-rig stand-in. It holds an output flag so a press has something to
    move, and it is never mistaken for a supply: every message it produces
    says SIMULATED and every row it writes says `dummy`."""

    identity = "DUMMY,PWR401L,SIMULATED,0"

    def __init__(self):
        self.output_on = 0

    def sample(self):
        return 0.0, 0.0, self.output_on

    def set_output(self, on):
        self.output_on = 1 if on else 0
        return self.output_on

    def close(self):
        pass


def _report_output(message, on, state, dummy):
    """The one sentence a press leaves in the Log, and whether it stuck.

    Said in one place because the recorder's thread and the one-shot helper
    must not word the same event two ways. A readback that does not match
    what was asked for is reported as exactly that — the write went out, the
    supply says otherwise — and never as a confirmation.
    """
    word = "ON" if on else "OFF"
    if dummy:
        message(
            "Kikusui output {} SIMULATED: no supply is connected; "
            "manual drive unchanged".format(word)
        )
        return False
    if state == (1 if on else 0):
        message("Kikusui output {} (confirmed)".format(word))
        return True
    message("Kikusui output {} sent, readback {}".format(word, state))
    return False


def set_output(config, on, message):
    """The same write with no recorder running: connect, write, read back, close.

    Called on a short daemon thread so the GUI thread never waits on a LAN,
    and it therefore swallows nothing: every ending leaves a line in the Log.
    """
    client = DummyClient() if config.dummy else ReadOnlyClient(config)
    try:
        state = client.set_output(on)
    except Exception as error:  # noqa: BLE001 -- a press must never end silently.
        message(
            "Kikusui output {} FAILED: {}; manual drive unchanged".format(
                "ON" if on else "OFF", error
            )
        )
        return False
    finally:
        client.close()
    return _report_output(message, on, state, config.dummy)


class KikusuiLogger:
    """A run-scoped recorder. Loss of LAN never changes an apparatus output.

    It also carries the two presses, because it owns the socket: a request
    from the main thread waits on `_presses` until this thread is between
    polls, and the write and its readback then go out on the connection the
    recorder already has. Nothing here presses anything on its own.
    """

    COLUMNS = (
        "date", "logger_elapsed_s", "query_ms", "voltage_v", "current_a",
        "output_on", "commanded_cathode_mv", "plasma_target_a", "status",
        "error", "identity",
    )

    def __init__(self, config, adc_path, message, context=dict, client=None):
        self.config = config
        adc_path = Path(adc_path)
        self.adc_name = adc_path.name
        self.path = adc_path.with_name("kikusui_" + adc_path.stem.removeprefix("cu_") + ".csv")
        self.message = message
        self.context = context
        self.client = client or (DummyClient() if config.dummy else ReadOnlyClient(config))
        self.stopping = threading.Event()
        #: Presses waiting for this recorder's own thread, oldest first. Any
        #: thread may put one here; only this recorder's thread takes them,
        #: which is what keeps two threads off one socket. A request that
        #: arrives mid-poll simply waits for the poll to finish.
        self._presses = queue.Queue()
        #: One wait to interrupt, for both a stop and a press: without it a
        #: press during an outage would sit through the whole retry delay.
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._latest = {"status": "connecting"}
        self._received_at = None
        self.thread = threading.Thread(target=self._run, name="Kikusui telemetry", daemon=True)

    def snapshot(self):
        """Copy recorded telemetry, withholding measurements once they are stale."""
        with self._lock:
            result = self._latest.copy()
            received = self._received_at
        age = None if received is None else max(0, time.monotonic() - received)
        expires = self.config.interval_s + self.config.timeout_s + 0.5
        if result["status"] in ("ok", "dummy") and age > expires:
            result = {"status": "stale"}
        result.update(age_s=age, stale_after_s=expires, file=str(self.path))
        return result

    def _publish(self, row, received=None):
        with self._lock:
            self._latest = row.copy()
            self._received_at = received

    def start(self):
        self.thread.start()

    def request_output(self, on):
        """Ask this recorder's thread for the one write. Any thread may call.

        Returns whether there is a live thread to carry it, so a caller whose
        press has nowhere to go can open its own short-lived connection
        rather than believe a press nothing will ever send. A request that
        makes it onto the queue is always answered in the Log: if the thread
        ends first, its own shutdown says the press was not sent.
        """
        if self.stopping.is_set() or not self.thread.is_alive():
            return False
        self._presses.put(bool(on))
        self._wake.set()
        return True

    def _drop_pending(self, why):
        """No press is ever lost in silence, not even to a shutdown."""
        while True:
            try:
                on = self._presses.get_nowait()
            except queue.Empty:
                return
            self.message(
                "Kikusui output {} FAILED: {}; manual drive unchanged".format(
                    "ON" if on else "OFF", why
                )
            )

    def _wait(self, seconds):
        """Sleep between polls, and wake at once for a stop or a press."""
        self._wake.wait(max(0.01, seconds))
        self._wake.clear()

    def stop(self):
        self.stopping.set()
        self._wake.set()
        self.client.close()  # Interrupt a connected recv; connect has a bounded timeout.
        self.thread.join(self.config.timeout_s + 0.5)
        return not self.thread.is_alive()

    def _stamp(self, row, before, started):
        """The three time columns every row carries, written in one place."""
        now = time.monotonic()
        row.update(
            date=datetime.datetime.now().astimezone().isoformat(timespec="microseconds"),
            logger_elapsed_s=round(now - started, 6),
            query_ms=round((now - before) * 1000, 3),
        )
        return now

    def _write_press(self, on, started):
        """Carry out one press here, on the socket this thread already owns.

        It is a row of its own in the sidecar, with the readback in
        `output_on` and no voltage or current: the supply was switched, not
        measured, and an event row must never look like a measurement. A
        failure leaves manual drive exactly as it was — the DAC is a
        different wire — and says so.
        """
        before = time.monotonic()
        context = self.context()
        word = "on" if on else "off"
        row = {
            "commanded_cathode_mv": context.get("cathode_mv", ""),
            "plasma_target_a": context.get("plasma_a", ""),
        }
        try:
            answered = self.client.set_output(on)
            row.update(
                output_on=answered,
                status="output_" + word,
                identity=self.client.identity,
            )
            _report_output(self.message, on, answered, self.config.dummy)
        except (OSError, ValueError, UnicodeError) as error:
            self.client.close()
            row.update(status="output_{}_failed".format(word), error=str(error)[:240])
            self.message(
                "Kikusui output {} FAILED: {}; manual drive unchanged".format(
                    word.upper(), error
                )
            )
        return row, self._stamp(row, before, started)

    def _run(self):
        started = time.monotonic()
        state = None
        try:
            # Never overwrite a previous telemetry file, even for a same-second restart.
            with self.path.open("x", newline="", encoding="utf-8") as target:
                target.write("# schema: controlunit-kikusui/v1\n")
                target.write(f"# software: ControlUnit {__version__}\n")
                target.write(f"# adc_file: {self.adc_name}\n")
                target.write(f"# interval_s: {self.config.interval_s}\n")
                target.write(f"# timeout_s: {self.config.timeout_s}\n")
                target.write(f"# retry_s: {self.config.retry_s}\n")
                target.write("# date: local receipt time with UTC offset; queries are sequential\n")
                writer = csv.DictWriter(target, fieldnames=self.COLUMNS)
                writer.writeheader()
                target.flush()
                self.message(f"Kikusui telemetry file: {self.path.name}")
                while not self.stopping.is_set():
                    # A press first, between polls: one thread, one socket,
                    # and a request that arrived mid-poll has waited for it.
                    while not self.stopping.is_set():
                        try:
                            pressed = self._presses.get_nowait()
                        except queue.Empty:
                            break
                        press, at = self._write_press(pressed, started)
                        writer.writerow(press)
                        target.flush()
                        self._publish(press, at)
                    if self.stopping.is_set():
                        break
                    before = time.monotonic()
                    context = self.context()
                    row = {
                        "commanded_cathode_mv": context.get("cathode_mv", ""),
                        "plasma_target_a": context.get("plasma_a", ""),
                    }
                    try:
                        voltage, current, output = self.client.sample()
                        row.update(voltage_v=voltage, current_a=current, output_on=output)
                        status = "dummy" if self.config.dummy else "ok"
                        row.update(status=status, identity=self.client.identity)
                    except (OSError, ValueError, UnicodeError) as error:
                        self.client.close()
                        status = "unavailable"
                        # No retained voltage/current/output flag is ever reused here.
                        row.update(status=status, error=str(error)[:240])
                    if self.stopping.is_set():
                        break
                    now = self._stamp(row, before, started)
                    writer.writerow(row)
                    target.flush()
                    self._publish(row, now)
                    if status != state:
                        if status == "unavailable":
                            self.message(
                                "Kikusui telemetry LOST: measurements unavailable; "
                                "manual drive unchanged; retrying in background"
                            )
                        elif state == "unavailable":
                            self.message("Kikusui telemetry BACK: recording fresh measurements")
                        else:
                            self.message(f"Kikusui telemetry connected ({status})")
                        state = status
                    delay = self.config.retry_s if status == "unavailable" else self.config.interval_s
                    # No catch-up bursts; a slow poll reduces only this recorder's cadence.
                    self._wait(delay - (time.monotonic() - before))
        except Exception as error:  # noqa: BLE001 -- Report any recorder failure, never lose it silently.
            self.message(f"Kikusui recording STOPPED: {error}; manual drive unchanged")
        finally:
            self.client.close()
            self._publish({"status": "stopped"})
            # A press queued in the instant this thread was ending is told so,
            # rather than disappearing with the thread that was to send it.
            self._drop_pending("the telemetry recorder stopped first")

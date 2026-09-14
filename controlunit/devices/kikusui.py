"""Optional, read-only PWR401L telemetry in a separately timestamped CSV.

This module cannot drive the supply. Its only wire commands are the four
queries below. The logger owns its socket and file; it never calls a Qt
widget, the ADC reader or a DAC worker.
"""

import csv
import datetime
import ipaddress
import math
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


class ReadOnlyClient:
    QUERIES = ("*IDN?", "MEAS:VOLT?", "MEAS:CURR?", "OUTP?")

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

    def _query(self, command, deadline):
        if command not in self.QUERIES:
            raise ValueError("Only telemetry queries are permitted")
        sock = self.sock
        if sock is None:
            raise OSError("Telemetry connection closed")

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError("Telemetry query deadline exceeded")
            sock.settimeout(value)

        remaining()
        sock.sendall((command + "\n").encode("ascii"))
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

    def sample(self):
        # One deadline for the entire transaction, even on a slow trickle of bytes.
        deadline = time.monotonic() + self.config.timeout_s
        if self.sock is None:
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
        voltage = float(self._query("MEAS:VOLT?", deadline))
        current = float(self._query("MEAS:CURR?", deadline))
        output = self._query("OUTP?", deadline)
        if not all(math.isfinite(v) and abs(v) < 1e30 for v in (voltage, current)):
            raise ValueError("Invalid SCPI measurement")
        if output not in ("0", "1"):
            raise ValueError("Invalid SCPI output state")
        return voltage, current, int(output)


class DummyClient:
    identity = "DUMMY,PWR401L,SIMULATED,0"

    def sample(self):
        return 0.0, 0.0, 0

    def close(self):
        pass


class KikusuiLogger:
    """A run-scoped recorder. Loss of LAN never changes an apparatus output."""

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
        self.thread = threading.Thread(target=self._run, name="Kikusui telemetry", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.client.close()  # Interrupt a connected recv; connect has a bounded timeout.
        self.thread.join(self.config.timeout_s + 0.5)
        return not self.thread.is_alive()

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
                    now = time.monotonic()
                    row.update(
                        date=datetime.datetime.now().astimezone().isoformat(timespec="microseconds"),
                        logger_elapsed_s=round(now - started, 6),
                        query_ms=round((now - before) * 1000, 3),
                    )
                    writer.writerow(row)
                    target.flush()
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
                    self.stopping.wait(max(0.01, delay - (time.monotonic() - before)))
        except Exception as error:  # noqa: BLE001 -- Report any recorder failure, never lose it silently.
            self.message(f"Kikusui recording STOPPED: {error}; manual drive unchanged")
        finally:
            self.client.close()

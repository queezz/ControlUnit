"""Transport, the two writes, data-loss semantics and bounded shutdown."""

import csv
import socket
import threading
import time

import pytest

from controlunit.devices.kikusui import (
    DummyClient,
    KikusuiConfig,
    KikusuiLogger,
    ReadOnlyClient,
    load_config,
    set_output,
)


class ScriptedSocket:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.sent = []
        self.closed = False

    def settimeout(self, value):
        assert 0 < value <= 5

    def connect(self, address):
        self.address = address

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, count):
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def shutdown(self, how):
        pass

    def close(self):
        self.closed = True


def client_with(monkeypatch, replies):
    sock = ScriptedSocket(replies)
    monkeypatch.setattr(socket, "socket", lambda *args: sock)
    return ReadOnlyClient(KikusuiConfig(host="127.0.0.1")), sock


def test_fragmented_replies_and_only_read_queries(monkeypatch):
    client, sock = client_with(monkeypatch, [
        b"KIKUSUI,PWR401L,TEST,1\r", b"\n", b"+2.4", b"E+00\n", b"12.0\n", b"1\n",
        b"-.0045\n", b".0075\n", b"0\n",
    ])
    assert client.sample() == (2.4, 12.0, 1)
    assert client.sample() == (-0.0045, 0.0075, 0)
    assert sock.sent == [
        b"*IDN?\n", b"MEAS:VOLT?\n", b"MEAS:CURR?\n", b"OUTP?\n",
        b"MEAS:VOLT?\n", b"MEAS:CURR?\n", b"OUTP?\n",
    ]
    with pytest.raises(ValueError, match="Only the four telemetry queries"):
        client._query("OUTP ON", time.monotonic() + 1)
    client.close()
    assert sock.closed


def test_the_allowlist_is_six_words_and_nothing_else_reaches_the_wire(monkeypatch):
    """The whole safety argument, in one assertion.

    Six commands may be written: the four queries and the two output writes
    the owner decided on 2026-09-15. Every other SCPI word — the one that
    differs by a character, the one that sets a voltage, the one that resets
    the instrument — raises in `_send`, which is the only place a byte
    reaches the supply, and the socket is left with nothing sent.
    """
    assert ReadOnlyClient.QUERIES == ("*IDN?", "MEAS:VOLT?", "MEAS:CURR?", "OUTP?")
    assert ReadOnlyClient.WRITES == ("OUTP 0", "OUTP 1")
    assert ReadOnlyClient.ALLOWED == (
        "*IDN?", "MEAS:VOLT?", "MEAS:CURR?", "OUTP?", "OUTP 0", "OUTP 1",
    )

    client, sock = client_with(monkeypatch, [])
    client.sock = sock
    deadline = time.monotonic() + 1
    for command in (
        "OUTP ON", "OUTP OFF", "OUTP 2", "outp 0", "OUTP 0;OUTP 1",
        "VOLT 10", "CURR 1", "*RST", "*CLS", "SYST:COMM:RLST REM", "",
    ):
        with pytest.raises(ValueError, match="Only the four telemetry queries"):
            client._send(command, deadline)
        with pytest.raises(ValueError, match="Only the four telemetry queries"):
            client._query(command, deadline)
    # A write is never read back as a query either: it answers nothing.
    for write in ReadOnlyClient.WRITES:
        with pytest.raises(ValueError, match="Only the four telemetry queries"):
            client._query(write, deadline)
    assert sock.sent == [], "nothing refused may reach the wire"


@pytest.mark.parametrize("on, expected", [(False, b"OUTP 0\n"), (True, b"OUTP 1\n")])
def test_a_write_identifies_the_supply_first_and_reads_the_output_back(
    monkeypatch, on, expected
):
    client, sock = client_with(
        monkeypatch, [b"KIKUSUI,PWR401L,TEST,1\n", b"1\n" if on else b"0\n"]
    )
    assert client.set_output(on) == (1 if on else 0)
    assert sock.sent == [b"*IDN?\n", expected, b"OUTP?\n"]
    client.close()


def test_a_write_to_something_that_is_not_the_supply_is_refused(monkeypatch):
    """`OUTP 0` may only reach a PWR401L this client has identified."""
    client, sock = client_with(monkeypatch, [b"RIGOL,DP832,X,1\n"])
    with pytest.raises(ValueError, match="Expected a KIKUSUI"):
        client.set_output(False)
    assert sock.sent == [b"*IDN?\n"], "the write never went out"
    client.close()


@pytest.mark.parametrize("reply", [b"NaN\n", b"inf\n", b"9.9E37\n", b"broken\n"])
def test_invalid_measurement_never_becomes_a_sample(monkeypatch, reply):
    client, _ = client_with(monkeypatch, [b"KIKUSUI,PWR401L,TEST,1\n", reply, b"1\n", b"0\n"])
    with pytest.raises(ValueError):
        client.sample()
    client.close()


@pytest.mark.parametrize("reply", [b"", b"x" * 257, socket.timeout("late"), b"1\nextra\n"])
def test_transport_failures_are_explicit(monkeypatch, reply):
    client, _ = client_with(monkeypatch, [reply])
    with pytest.raises((ValueError, OSError)):
        client.sample()
    client.close()


def test_identity_is_verified_again_on_reconnect(monkeypatch):
    sockets = [
        ScriptedSocket([b"KIKUSUI,PWR401L,ONE,1\n", b"1\n", b"2\n", b"0\n"]),
        ScriptedSocket([b"KIKUSUI,PWR401L,TWO,1\n"]),
    ]
    monkeypatch.setattr(socket, "socket", lambda *args: sockets.pop(0))
    client = ReadOnlyClient(KikusuiConfig(host="127.0.0.1"))
    client.sample()
    client.close()
    with pytest.raises(ValueError, match="identity changed"):
        client.sample()
    client.close()


def test_slow_trickle_cannot_extend_the_transaction_deadline(monkeypatch):
    clock = [0.0]
    client, sock = client_with(monkeypatch, [])
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    def trickle(count):
        clock[0] += 0.4
        return b"x"

    sock.recv = trickle
    with pytest.raises(TimeoutError, match="deadline"):
        client.sample()
    assert clock[0] < 1.7
    client.close()


def test_stop_interrupts_a_real_blocked_socket_read(tmp_path):
    receiver, peer = socket.socketpair()
    peer.settimeout(2)
    config = KikusuiConfig(host="127.0.0.1", timeout_s=5)
    client = ReadOnlyClient(config)
    client.sock = receiver
    messages = []
    logger = KikusuiLogger(config, tmp_path / "cu_blocked.csv", messages.append, client=client)
    try:
        logger.start()
        assert peer.recv(256) == b"MEAS:VOLT?\n"
        before = time.monotonic()
        assert logger.stop()
        assert time.monotonic() - before < 0.5
        assert not any("LOST" in m for m in messages)  # Stop is not an outage.
        assert read_rows(logger.path) == []
    finally:
        peer.close()
        logger.stop()


@pytest.mark.parametrize("values", [
    {"interval_s": 0}, {"interval_s": float("nan")}, {"timeout_s": 100},
    {"retry_s": -1}, {"dummy": "false"}, {"port": 5025.0}, {"timeout_s": True},
])
def test_config_bounds(values):
    with pytest.raises((ValueError, TypeError)):
        KikusuiConfig(host="127.0.0.1", **values)


def test_config_is_opt_in_and_rejects_typos(tmp_path):
    path = tmp_path / "kikusui.yml"
    assert load_config(path) is None
    path.write_text("dummy: true\ninterval_s: 1\n")
    assert load_config(path).dummy is True
    path.write_text("dummy: true\ninteval_s: 1\n")
    with pytest.raises(ValueError, match="Unknown"):
        load_config(path)


def wait_until(predicate, seconds=4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def read_rows(path):
    with path.open(encoding="utf-8") as source:
        return list(csv.DictReader(line for line in source if not line.startswith("#")))


class FlakyClient:
    identity = "KIKUSUI,PWR401L,TEST,1"

    def __init__(self):
        self.calls = 0

    def sample(self):
        self.calls += 1
        if self.calls in (2, 3):
            raise TimeoutError("LAN unplugged")
        return 2.4, 12.0, 1

    def close(self):
        pass


def test_outage_writes_missing_rows_warns_once_and_recovers(tmp_path):
    messages = []
    context = {"cathode_mv": 1500, "plasma_a": 0}
    logger = KikusuiLogger(
        KikusuiConfig(host="127.0.0.1", interval_s=0.1, retry_s=1),
        tmp_path / "cu_20260914_120000.csv", messages.append,
        context=lambda: context.copy(), client=FlakyClient(),
    )
    try:
        logger.start()
        wait_until(lambda: any("BACK" in m for m in messages))
    finally:
        assert logger.stop()
    rows = read_rows(logger.path)
    assert [r["status"] for r in rows[:4]] == ["ok", "unavailable", "unavailable", "ok"]
    for row in rows[1:3]:
        assert [row[k] for k in ("voltage_v", "current_a", "output_on")] == ["", "", ""]
        assert row["error"] == "LAN unplugged"
    assert rows[3]["current_a"] == "12.0"
    assert rows[3]["commanded_cathode_mv"] == "1500"
    assert sum("LOST" in m for m in messages) == 1
    assert sum("BACK" in m for m in messages) == 1
    assert context == {"cathode_mv": 1500, "plasma_a": 0}
    assert logger.path.name == "kikusui_20260914_120000.csv"


def test_stop_interrupts_long_wait_and_does_not_overwrite(tmp_path):
    messages = []
    config = KikusuiConfig(dummy=True, interval_s=60)
    logger = KikusuiLogger(config, tmp_path / "cu_20260914_120000.csv", messages.append)
    logger.start()
    wait_until(lambda: any("connected" in m for m in messages))
    before = time.monotonic()
    assert logger.stop()
    assert time.monotonic() - before < 0.5
    original = logger.path.read_bytes()
    assert read_rows(logger.path)[0]["status"] == "dummy"
    duplicate = KikusuiLogger(config, tmp_path / "cu_20260914_120000.csv", messages.append)
    duplicate.start()
    wait_until(lambda: not duplicate.thread.is_alive())
    assert duplicate.stop()
    assert logger.path.read_bytes() == original
    assert any("recording STOPPED" in m for m in messages)


# -- the two writes, against a supply that answers on loopback ---------------


class FakeSupply:
    """A PWR401L on 127.0.0.1: it speaks SCPI-RAW and keeps the transcript.

    No real supply is ever opened by this suite. The transcript is the point:
    it is how a press is proved to have gone out *between* polls, on the one
    socket, rather than from a second thread in the middle of one.
    """

    def __init__(self, stubborn=False, identity="KIKUSUI,PWR401L,FAKE,1"):
        self.identity = identity
        self.stubborn = stubborn  # a supply that ignores the write
        self.output_on = 0
        self.log = []
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(0.3)
        self.port = self.listener.getsockname()[1]
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _answer(self, line):
        self.log.append(line)
        if line == "*IDN?":
            return self.identity
        if line == "MEAS:VOLT?":
            return "2.400"
        if line == "MEAS:CURR?":
            return "12.000"
        if line == "OUTP?":
            return str(self.output_on)
        if line in ("OUTP 0", "OUTP 1"):
            if not self.stubborn:
                self.output_on = 1 if line.endswith("1") else 0
            return None  # a write answers nothing
        return "ERROR"

    def _serve(self):
        while not self.stopping.is_set():
            try:
                conn, _ = self.listener.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                conn.settimeout(0.3)
                rest = b""
                while not self.stopping.is_set():
                    try:
                        chunk = conn.recv(256)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not chunk:
                        break
                    rest += chunk
                    while b"\n" in rest:
                        line, rest = rest.split(b"\n", 1)
                        reply = self._answer(line.decode("ascii").strip())
                        if reply is not None:
                            conn.sendall(reply.encode("ascii") + b"\n")

    def close(self):
        self.stopping.set()
        self.listener.close()
        self.thread.join(2)

    def transcript(self):
        """The conversation, parsed into whole polls and whole presses.

        Raises if anything interleaves: every exchange on this socket is
        either a complete three-query poll or a complete write-and-readback,
        in order, with at most a poll cut short by the stop that ended the run.
        """
        stream = list(self.log)
        assert stream[:1] == ["*IDN?"]
        rest, polls, presses = stream[1:], 0, 0
        poll = ["MEAS:VOLT?", "MEAS:CURR?", "OUTP?"]
        while rest:
            if rest[:3] == poll:
                rest, polls = rest[3:], polls + 1
            elif rest[:2] in (["OUTP 0", "OUTP?"], ["OUTP 1", "OUTP?"]):
                rest, presses = rest[2:], presses + 1
            elif rest == poll[: len(rest)]:
                break  # the stop interrupted the last poll; nothing interleaved
            else:
                raise AssertionError("interleaved on one socket: {}".format(rest[:4]))
        return polls, presses


@pytest.fixture
def supply():
    made = FakeSupply()
    try:
        yield made
    finally:
        made.close()


def test_a_press_goes_out_between_polls_on_the_socket_the_recorder_owns(tmp_path, supply):
    """The whole path of the owner's press, at the wire.

    The recorder is polling; the press arrives from another thread; the write
    and its readback go out between two polls on the connection the recorder
    already has; the Log says it was confirmed; the sidecar carries a row of
    its own; and the snapshot the GUI reads is republished.
    """
    supply.output_on = 1
    messages = []
    logger = KikusuiLogger(
        KikusuiConfig(host="127.0.0.1", port=supply.port, interval_s=0.1),
        tmp_path / "cu_20260915_120000.csv", messages.append,
    )
    try:
        logger.start()
        wait_until(lambda: any("connected" in m for m in messages))
        assert logger.request_output(False) is True     # from this thread
        wait_until(lambda: any("output OFF" in m for m in messages))
        wait_until(lambda: logger.snapshot()["status"] == "ok")
    finally:
        assert logger.stop()

    assert "Kikusui output OFF (confirmed)" in messages
    assert supply.output_on == 0
    polls, presses = supply.transcript()
    assert (polls, presses) >= (2, 1)
    assert presses == 1

    rows = read_rows(logger.path)
    pressed = [row for row in rows if row["status"] == "output_off"]
    assert len(pressed) == 1
    # The supply was switched, not measured: the readback stands, and no
    # voltage or current is laid down for a moment nobody measured.
    assert pressed[0]["output_on"] == "0"
    assert pressed[0]["voltage_v"] == "" and pressed[0]["current_a"] == ""
    assert pressed[0]["error"] == ""
    assert float(pressed[0]["query_ms"]) >= 0
    # And the polls on either side of it are ordinary measured rows.
    assert [row["status"] for row in rows].count("ok") >= 2
    assert rows[-1]["current_a"] == "12.0"


def test_both_directions_travel_and_the_supply_follows(tmp_path, supply):
    messages = []
    logger = KikusuiLogger(
        KikusuiConfig(host="127.0.0.1", port=supply.port, interval_s=0.1),
        tmp_path / "cu_20260915_130000.csv", messages.append,
    )
    try:
        logger.start()
        wait_until(lambda: any("connected" in m for m in messages))
        assert logger.request_output(True) is True
        wait_until(lambda: "Kikusui output ON (confirmed)" in messages)
        assert supply.output_on == 1
        assert logger.request_output(False) is True
        wait_until(lambda: "Kikusui output OFF (confirmed)" in messages)
    finally:
        assert logger.stop()
    assert supply.output_on == 0
    polls, presses = supply.transcript()
    assert presses == 2
    assert [r["status"] for r in read_rows(logger.path) if r["status"].startswith("output")] == [
        "output_on", "output_off",
    ]


def test_a_supply_that_ignores_the_write_is_never_reported_as_confirmed(tmp_path):
    stubborn = FakeSupply(stubborn=True)
    stubborn.output_on = 1
    messages = []
    try:
        assert set_output(
            KikusuiConfig(host="127.0.0.1", port=stubborn.port), False, messages.append
        ) is False
        assert messages == ["Kikusui output OFF sent, readback 1"]
    finally:
        stubborn.close()


def test_the_one_shot_helper_connects_writes_reads_back_and_closes(supply):
    """With no recorder running there is nobody's socket to borrow."""
    supply.output_on = 1
    messages = []
    config = KikusuiConfig(host="127.0.0.1", port=supply.port)
    assert set_output(config, False, messages.append) is True
    assert supply.log == ["*IDN?", "OUTP 0", "OUTP?"]
    assert supply.output_on == 0
    assert set_output(config, True, messages.append) is True
    assert supply.output_on == 1
    assert messages == ["Kikusui output OFF (confirmed)", "Kikusui output ON (confirmed)"]
    # Each press opened and closed its own connection, and identified the
    # supply again before writing to it.
    assert supply.log.count("*IDN?") == 2


def test_a_press_with_no_lan_says_so_loudly_and_changes_nothing():
    """The LAN is gone: the press fails, says so, and the DAC is untouched."""
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # nothing listens there
    messages = []
    assert set_output(
        KikusuiConfig(host="127.0.0.1", port=port, timeout_s=0.3), False, messages.append
    ) is False
    assert len(messages) == 1
    assert messages[0].startswith("Kikusui output OFF FAILED: ")
    assert messages[0].endswith("; manual drive unchanged")


def test_a_press_on_dummy_hardware_is_simulated_and_says_so():
    """Nothing is connected, so nothing is claimed: the flag moves, the
    sentence says SIMULATED, and the press does not report success."""
    messages = []
    assert set_output(KikusuiConfig(dummy=True), False, messages.append) is False
    assert "SIMULATED" in messages[0] and "no supply is connected" in messages[0]
    client = DummyClient()
    assert client.sample() == (0.0, 0.0, 0)
    assert client.set_output(True) == 1
    assert client.sample() == (0.0, 0.0, 1)
    assert client.set_output(False) == 0
    assert client.sample()[2] == 0


def test_a_failed_press_writes_its_own_row_and_leaves_the_drive_alone(tmp_path):
    class Refusing:
        identity = "KIKUSUI,PWR401L,TEST,1"

        def sample(self):
            return 2.4, 12.0, 1

        def set_output(self, on):
            raise TimeoutError("LAN unplugged")

        def close(self):
            pass

    messages = []
    logger = KikusuiLogger(
        KikusuiConfig(host="127.0.0.1", interval_s=0.1),
        tmp_path / "cu_20260915_140000.csv", messages.append, client=Refusing(),
    )
    try:
        logger.start()
        wait_until(lambda: any("connected" in m for m in messages))
        assert logger.request_output(False) is True
        wait_until(lambda: any("FAILED" in m for m in messages))
    finally:
        assert logger.stop()
    assert (
        "Kikusui output OFF FAILED: LAN unplugged; manual drive unchanged" in messages
    )
    failed = [r for r in read_rows(logger.path) if r["status"] == "output_off_failed"]
    assert len(failed) == 1
    assert failed[0]["error"] == "LAN unplugged"
    assert failed[0]["output_on"] == ""


def test_a_press_with_no_live_recorder_is_refused_rather_than_swallowed(tmp_path):
    """Nothing may accept a press it has no thread to send."""
    logger = KikusuiLogger(
        KikusuiConfig(dummy=True, interval_s=0.1),
        tmp_path / "cu_20260915_150000.csv", lambda m: None,
    )
    assert logger.request_output(False) is False  # never started
    logger.start()
    wait_until(lambda: logger.snapshot()["status"] == "dummy")
    assert logger.stop()
    assert logger.request_output(False) is False  # already stopped


def test_a_press_queued_as_the_recorder_ends_is_answered_not_lost(tmp_path):
    messages = []
    logger = KikusuiLogger(
        KikusuiConfig(dummy=True, interval_s=60),
        tmp_path / "cu_20260915_160000.csv", messages.append,
    )
    logger.start()
    wait_until(lambda: any("connected" in m for m in messages))
    # Straight onto the queue, past the liveness check, as a press landing in
    # the instant a stop begins would.
    logger._presses.put(False)
    assert logger.stop()
    assert any(
        m.startswith("Kikusui output OFF FAILED: the telemetry recorder stopped first")
        for m in messages
    )


def test_snapshot_withholds_stale_failed_and_stopped_measurements(tmp_path, monkeypatch):
    logger = KikusuiLogger(KikusuiConfig(dummy=True), tmp_path / "cu_display.csv", lambda m: None)
    assert logger.snapshot()["status"] == "connecting"
    clock = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    logger._publish({"status": "dummy", "voltage_v": 2.4, "current_a": 12, "output_on": 1}, 100)
    snapshot = logger.snapshot()
    assert snapshot["current_a"] == 12
    snapshot["current_a"] = 999  # A consumer cannot corrupt the recorder's state.
    assert logger.snapshot()["current_a"] == 12
    clock[0] += 2.1
    assert logger.snapshot()["status"] == "stale"
    assert "current_a" not in logger.snapshot()
    logger._publish({"status": "unavailable", "error": "timeout"}, clock[0])
    assert "voltage_v" not in logger.snapshot()
    assert logger.snapshot()["error"] == "timeout"

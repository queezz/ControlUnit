"""Read-only transport, data-loss semantics and bounded recorder shutdown."""

import csv
import socket
import time

import pytest

from controlunit.devices.kikusui import (
    KikusuiConfig,
    KikusuiLogger,
    ReadOnlyClient,
    load_config,
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
    with pytest.raises(ValueError, match="Only telemetry"):
        client._query("OUTP ON", time.monotonic() + 1)
    client.close()
    assert sock.closed


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

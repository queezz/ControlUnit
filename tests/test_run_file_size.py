"""The run file's size in the web view's This run card (queezz, 2026-11-18:
"How about showing the file size, not just samples? I need MB, or Kb").

The main thread stats the file just after its own append and hands the
number to the status record; the page formats it. Unknown is None, never 0.
"""

import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from controlunit._version import __version__  # noqa: E402
from controlunit.web.status import RigStatus, state_body  # noqa: E402


def test_size_is_unknown_until_read_and_starts_again_with_each_run():
    status = RigStatus()
    assert state_body(status, __version__)["run"]["bytes"] is None

    status.start_run("cu_20261118_120000.csv")
    assert state_body(status, __version__)["run"]["bytes"] is None

    status.record_file_size(123456)
    assert state_body(status, __version__)["run"]["bytes"] == 123456
    assert status.read()["file_bytes"] == 123456

    # A stat that failed is unknown again, not the last number and not zero.
    status.record_file_size(None)
    assert state_body(status, __version__)["run"]["bytes"] is None

    status.record_file_size(5000)
    status.start_run("cu_20261118_130000.csv")
    assert state_body(status, __version__)["run"]["bytes"] is None


def test_size_ignores_what_is_not_a_size():
    status = RigStatus()
    status.record_file_size("not a number")
    assert status.read()["file_bytes"] is None
    status.record_file_size(-3)
    assert status.read()["file_bytes"] == 0


def test_each_append_reports_the_size_on_disk(tmp_path):
    pd = pytest.importorskip("pandas")
    main = pytest.importorskip("controlunit.main")

    path = tmp_path / "cu_20261118_120000.csv"
    path.write_text("date,Ip\n", encoding="ascii")
    owner = types.SimpleNamespace(
        savepaths={"ADC": str(path)},
        newdata={"ADC": pd.DataFrame({"date": ["2026-11-18 12:00:00"], "Ip": [0.5]})},
        web_status=RigStatus(),
    )
    owner._note_file_size = lambda name: main.MainApp._note_file_size(owner, name)

    main.MainApp.save_data(owner, "ADC")
    first = owner.web_status.read()["file_bytes"]
    assert first == os.path.getsize(path) > len("date,Ip\n")

    main.MainApp.save_data(owner, "ADC")
    assert owner.web_status.read()["file_bytes"] == os.path.getsize(path) > first


def test_a_file_that_cannot_be_read_leaves_the_size_unknown(tmp_path):
    main = pytest.importorskip("controlunit.main")
    owner = types.SimpleNamespace(
        savepaths={"ADC": str(tmp_path / "gone.csv")}, web_status=RigStatus()
    )
    owner.web_status.record_file_size(99)
    main.MainApp._note_file_size(owner, "ADC")
    assert owner.web_status.read()["file_bytes"] is None

    # Only the ADC file is the run file; the heater's is never reported.
    owner.web_status.record_file_size(99)
    main.MainApp._note_file_size(owner, "Membrane Heater")
    assert owner.web_status.read()["file_bytes"] == 99

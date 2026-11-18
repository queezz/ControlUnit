# The run file's size in This run — 2026-11-18, 4.31.0

queezz, with a screenshot of the Live tab during Kawabata's run
(`cu_20261116_173717.csv`, 68448 samples at 10 s): "How about showing the
file size, not just samples? I need MB, or Kb. In the current run."

## What changed

- `RigStatus.record_file_size(bytes)`: the run file's size, cleared by
  `start_run`. `/api/state` carries it as `run.bytes`, or `null` while it
  is not known.
- `MainApp._note_file_size`: one `os.path.getsize` on the main thread,
  right after `save_data`'s append and after `create_file` writes the
  header. It reads only the ADC file, and a failed stat reports unknown
  rather than keeping the old number. It never touches a worker, and its
  failure never stops the record.
- The This run card has a Size row under Samples. `fmtBytes` in `live.js`
  formats it as B, KB, MB or GB, counting 1 KB as 1024 bytes, as Explorer
  and `ls -lh` do; unknown shows as a dash.

## Verified

- Tests: `tests/test_run_file_size.py` (the status record; the size on disk
  after each append; a missing file; the heater's file ignored) and a node
  test of `fmtBytes` in `web_live_behavior.cjs`. Gates are in the commit.
- Scratch instance: `lab start controlunit-dummy --port 48937` under the
  scratch roots and home (4187 had no listener before or after). Started
  acquisition at 10 s sampling. The card read `1.3 KB` at 1336 bytes and
  1 sample, then `2307` bytes at 3 samples, matching the file on disk
  byte for byte. It kept updating through a reload and Back/Forward over
  Log and Lab.
- The right rail stayed sticky at an identical 76 px across 0/25/50/75/100%
  scroll at 1440x1000 and 1440x700. No console errors.
- `lab stop`: both processes gone, 48937 free.

## Deployed, 12:57

queezz chose "Push, deploy later", then: "You can stop, deploy, and
restart. No one is working, we have a meeting for the whole lab". Pushed
`24bb660..b0c22a3`.

At the time the rig was recording with no outputs live. The run was
`cu_20261116_173717.csv`: 68555 samples at 10 s, with Pd at 1e-6 and Pu2
at 1e-5 (Torr), and Kawabata held control from `.8`. A script from the
Pi's `/tmp` (it removed itself and its cookie jar) did the deploy:
- **Stop.** SIGTERM to the 4.30.1 program. The Log ends "Control released
  (acquisition stopped)" and "Program closing: SIGTERM, asked to stop by
  another program …; the run was stopped first, outputs to zero". The
  launcher wrote "exited with status 143". This is the graceful stop's
  first run on the rig while recording.
- **Pull.** `pull --ff-only` to `b0c22a3`, and `compileall` was clean.
- **Restart.** Started through `~/Desktop/aktest.sh` in lxterminal on
  `:0`. It answered as 4.31.0 "idle, not recording", and the Log said
  "Restored from the last run: Pd Torr 1e-6, Pu2 Torr 1e-5, sampling 10 s".
  No gauge had to be set by hand.
- **Recording again.** As the roster's Kuzmin Arseniy from the Pi itself:
  take over, then start acquisition. The new run is
  `cu_20261118_125740.csv` at 10 s. `/api/state` gave `run.bytes` 1892
  after two samples, and `ls -l` gave 1892 for the same file.
- **Kikusui.** Telemetry LOST eleven seconds in: the supply is off, with
  nobody at the rig.

AGENTS.md's note on the graceful stop now records both times it has been
seen on the rig. The stop rule stands, because no output has yet been live
when it ran.

`controlunit.log` still fails a UTF-8 read on one byte. It is 4.30.0's
degree sign of 2026-11-16 16:40:51 at offset 69418329, and the 2.2 MB
written after it decode cleanly.

agent: claude

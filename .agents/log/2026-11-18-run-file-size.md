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

## Not done

Not deployed. The rig was in Kawabata's run when the request came (Remote
on, measuring since 11-16 17:37). The pull waits for an idle rig and
queezz's word.

agent: claude

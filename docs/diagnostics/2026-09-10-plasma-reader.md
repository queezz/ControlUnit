# Acquisition survived the preanode grounding — 2026-09-10

The rig recorded throughout today's repeated plasma losses. No ADC exception
or recovery was logged, so this run supports continued acquisition but does
not demonstrate the new retry path recovering an I²C fault.

## Evidence

Read over SSH without changing the rig, 2026-09-10 around 20:00 JST:

- Rig checkout: `4c3ca18`, version 4.12.0.
- `cu_20260910_181445.csv`: 20,257 rows, all 26 columns, from
  18:14:45.715705 through 19:43:04.745302 JST.
- `controlunit.log` records the deliberate acquisition Stop and ADC thread
  stop at 19:43:05, followed by a new run at 19:43:12. No intervening reader
  stop, ADC read/step failure, recovery, or Reader lost/back message.
- `controlunit.stderr.log` has the launch marker at 18:14:28 and no subsequent
  output for this run. No traceback or errno was captured.
- The message log contains 372 NUL bytes elsewhere; it was read as text
  (`grep -a` and Python decoding), so ordinary grep's binary-file shortcut
  did not conceal diagnostic lines from this review.
- Sampling changed to 1 s at 18:17:00, then 0.1 s at 18:52:32. From 18:53
  onward, 17,107 successive intervals have median 0.161784 s and maximum
  0.498715 s (19:33:23.407578 → 19:33:23.906293). None exceeds 1 s.
  The configured 10 Hz is not achieved row cadence; the fast path waits its
  period before conversion and processing. Timing overhead is distinct from
  a reader death. The early slow-sampling period was excluded from this check.

## Relation to the lab observations

The September 10 journal records preanode shorting at 19:12, repeated losses
and recoveries through 19:27, and at 19:37 a measured 5 Ω from preanode to
ground, versus 2 MΩ to anode and 17 MΩ to cathode immediately after the
discharge. The owner confirms preanode grounding and plasma extinction.
These are the operator's hardware measurements, not measurements from the
ControlUnit: this CSV has no preanode voltage or resistance channel.

Today's cathode drive was manual, with PID off in the command log. It is
therefore not a repeat under identical conditions of yesterday's PID-driven
failures. It neither isolates the effect of the retry fix nor rules out a
PID-path contribution. Yesterday's I²C/EMI explanation remains a hypothesis:
without the original exception it was stronger than the evidence justified.
The precise electrical coupling path and physical reason for the preanode
short remain unmeasured.

## What this establishes

The new diagnostics are installed, and recording survived the reported
hardware failure episodes without a long gap. They captured no useful ADC
error on this run because none was reported. A future logged `ADC read
failed`, `ADC answering again`, or `ADC step failed` would distinguish a
recovered acquisition fault from a clean run. Continue preserving both logs
and the matching CSV; do not infer an errno from the absence of one.

Sources: rig files named above; PIHTI Log journal for September 9 and 10;
`controlunit/devices/adc.py` retry and fast sampling paths. A companion note
is indexed in the lab vault's Troubles hub. No pull or restart was performed.

## Timing follow-up: survival does not establish correct sampling

The owner challenged the 0.499 s maximum against the requested 0.1 s period.
That is a valid timing defect, not a clean timing result. Further read-only
analysis of the same 17,107 intervals gives mean 0.175640 s (about 5.69
rows/s), 95th percentile 0.249573 s and 99th percentile 0.270603 s. There
are 846 intervals above 0.25 s, 46 above 0.3 s and five above 0.4 s.
Percentiles use the sorted interval at floor((N-1)*p).

Four of the five intervals above 0.4 s occur at 19:33:14–26; the other is
19:27:43.651709–19:27:44.112594. The 19:33 minute has 21 intervals above
0.3 s. Before cathode operation, 18:53–19:08 already averages 0.161044 s
per row, with maximum 0.283088 s. From 19:33–19:38 the mean is 0.194339 s.
The chronology does not isolate plasma interference from increasing
application load or other timing causes.

One cause of the systematic rate shortfall is definite in source:
`collect_one_reading()` sleeps the entire configured period, then reads the
channels; row processing also occurs between timestamps. It does not
subtract that work from the next wait. This explains why 0.1 s is not a
0.1 s row cadence, but does not identify the extra delay in the worst bursts.

The ADC conversion-ready loop raises only after 10,000 polls, not after a
wall-time deadline. A slow successful read is not logged. Main-thread
history concatenation, CSV writing and plot updates are other candidate
costs; their contribution through scheduling/interpreter contention has not
been measured. CSV timestamps are assigned in the worker before row
construction, so these gaps are not merely delayed disk flush timestamps.

The present evidence distinguishes thread survival from timing quality.
Next diagnostic work should measure monotonic elapsed time for waiting,
channel reads, row processing and main-thread handling, and report overruns
even without exceptions. Use deadline scheduling for the requested cadence,
with an explicit policy for missed deadlines; do not invent missing samples
or compress their recorded timestamps. No acquisition code was changed in
this follow-up.

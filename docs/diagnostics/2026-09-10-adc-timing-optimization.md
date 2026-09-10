# ADC timing investigation — September 10, 2026

The requested 0.1 s was not the achieved sampling interval. The September 10
file averages 0.175640 s after 18:53, with a maximum of 0.498715 s. Code review
and off-device profiling establish substantial avoidable software cost. They
do not establish that every long interval was software rather than I²C or OS
scheduling. Local version 4.13.0 addresses the measured costs and records the
timing needed to distinguish them on the next rig run. It has not been deployed.

## Evidence and attribution

The [run investigation](2026-09-10-plasma-reader.md) identifies the files,
operator observations and interval calculation. Rig checkout was `4c3ca18`,
version 4.12.0. Reads were non-invasive: no restart, pull or hardware command.
The CSV has 20,257 complete rows; logging continued until the deliberate Stop.
There were no logged ADC read failures, step failures or recoveries in this
run. Thus retry recovery was not demonstrated. Preanode grounding was confirmed
by the operator; this CSV contains no preanode resistance or voltage channel.

Of 17,107 consecutive intervals after 18:53, 46 exceeded 0.3 s and five exceeded
0.4 s. The mean grew from 0.161044 s in 18:53–19:08 to 0.194339 s in
19:33–19:38. This is systematic cadence error plus bursts, not merely one
isolated half-second gap.

Partitioning intervals by full-file row index modulo three exposes a batch
pattern (phase labels are arbitrary):

| Window | Phase 0 mean | Phase 1 mean | Phase 2 mean |
| --- | ---: | ---: | ---: |
| 18:53–19:08 | 171.277 ms | 164.770 ms | 147.085 ms |
| 19:29–19:33 | 246.149 ms | 170.537 ms | 146.678 ms |
| 19:33–19:38 | 212.648 ms | 216.973 ms | 153.317 ms |

In 19:29–19:33, each phase has 426 intervals; the counts above 250 ms are
290, 15 and zero respectively. This supports investigating batch delivery and
GUI contention. It cannot alone identify which thread held the interpreter or
whether individual bus calls stalled. The old logs lack stage timings.

## Findings and implemented changes

1. **The fast loop slept the full requested period before doing work.**
   Scan, conversion, PID and batch construction were added to that sleep.
   A monotonic deadline now includes work in the period. Slow averaging windows
   use the same fixed end deadlines. Overdue slots are counted and skipped;
   no invented rows or catch-up bursts hide lost time. After an overrun the
   next deadline is one fresh period ahead. Recorded dates remain actual row
   capture times, not scheduled times.
2. **Two DataFrames were extended for every row.** Plain bounded lists now
   collect raw and converted rows; one typed DataFrame is constructed per
   emitted batch. Channel order and CSV columns stay unchanged. Ion-gauge
   conversion uses the mode/range captured with that row. Buffer length now
   determines batch size directly instead of an indirect step/modulus counter;
   STEP=3 still delivers three rows. Initial batch size is also derived from
   the configured sampling period.
3. **The main thread cast incoming values to an initially object-typed history.**
   It now preserves batch numeric and datetime types. Plot timestamps use a
   vectorized conversion instead of a Python callback per plotted row. In the
   baseline profile, 90,000 timestamp callbacks consumed roughly 1.07 s of
   1.375 s across 30 plot preparations at 20,000 history rows.
4. **ADC completion polling was a tight loop with a count-based fuse.**
   Busy polls now yield briefly, and an elapsed monotonic timeout uses the
   greater of 50 ms or four nominal conversion periods. The ready bit still
   determines whether a result may be read. Configuration words, mux switching,
   gain, data-rate selection and signed conversion remain unchanged. This
   bounds repeated polling, not an I²C syscall blocked inside the kernel.
5. **Successful but slow reads were silent.** `ADC timing` records mean/max
   period, row interval, read, processing and cycle durations, the slowest
   channel and missed deadlines. `ADC delivery` separates queue delay,
   history append, CSV save and display/publish costs. Summaries occur every
   30 s and at completion; slowdown warnings are rate-limited. Statistics use
   constant memory. These are observations, not guaranteed saved-row counts.
6. **Completed rows could remain below the batch threshold at Stop.** The
   worker now emits that completed tail. A partial scan or aborted average is
   discarded. This does not yet guarantee that queued signals reach disk
   during application exit; that is a separate main-thread lifecycle concern.

The ADS1115's conversion rate is not the whole multi-channel scan rate: mux,
configuration, ready polling and bus overhead also contribute. The ready-bit
approach accommodates oscillator variation; see the [TI datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf)
and [TI conversion-delay discussion](https://e2e.ti.com/support/data-converters-group/data-converters/f/data-converters-forum/143880/ads1115-conversion-delay-times).
The 50 ms timeout floor is a conservative software choice, not a datasheet
promise about Linux scheduling.

## Reproducible software benchmark

Same Windows PC, shared hardware-dev Python 3.14.5 / pandas 3.0.5, synthetic
three-row batches and a 300 s plot window at 10 Hz. Median times below use 200
batch preparations and 50 append/plot repetitions per history size. Hardware
reads, disk writes and actual Qt rendering are excluded. The Pi has pandas
1.5.3 and a different CPU; these ratios are not promised rig performance.

| Operation | Before | After |
| --- | ---: | ---: |
| Prepare and emit three rows | 20.756 ms | 0.841 ms |
| Append at 20,000 history rows | 7.777 ms | 2.256 ms |
| Prepare plots at 20,000 rows | 31.313 ms | 1.833 ms |
| Append at 100,000 rows | 29.784 ms | 6.992 ms |
| Prepare plots at 100,000 rows | 43.625 ms | 1.630 ms |

The portable `scripts/benchmark_adc.py` reproduces the workload and reports
environment, median and p95. It refuses hardware libraries before importing
device code. Run using the fleet's explicit hardware-dev interpreter, e.g.:

```text
<hardware-dev-python> scripts/benchmark_adc.py --output <scratch>/adc-benchmark.json
```

A repeat using the portable script returned 0.927 ms per three-row batch and
1.647 ms per 20,000-row plot preparation. Variability is expected; the durable
claim is the removal of specific measured costs, not a hard real-time bound.

## Validation and remaining work

Validation completed: 528 Python tests passed; strict MkDocs build and git
whitespace checks passed. The earlier mobile changes also passed 20 JavaScript
tests and browser checks at phone and desktop widths.

Deterministic tests exercise deadline spacing with processing overhead,
overruns without catch-up rows, period changes, fixed averaging windows,
partial-scan abort, completed tail emission, captured gauge metadata, numeric
types, plotting timestamp equivalence, ADC wire words/signed values and
elapsed timeout with slow bus calls. Existing reader-recovery tests remain.
PID gains, control law and hardware-first shutdown order were not changed.

Before declaring the 10 Hz problem resolved on hardware, collect at least a
comparable hour with the normal plot window and both closed/open web viewers.
Compare actual CSV interval median/p95/p99/max and missing deadlines against
the stage summaries. Rising `read` or one channel maximum points toward the
bus/converter path; rising `queue`/`display` points toward main-thread work.
Python thread contention can affect either, so compare the timestamps rather
than assigning a cause from one number. Do not induce plasma arcs for testing.

Remaining structural limits: history is still an unbounded DataFrame and each
append copies it; GUI display and logging share the main thread; Qt queued
data/done signals have no explicit run identity; application exit may occur
before a queued tail is saved; direct setters can arrive during a scan; the
channels are sequential, not simultaneous. These warrant focused follow-up
with measured costs and lifecycle tests. A process-based acquisition service
or ring-buffer redesign is not justified solely by the old gap histogram.

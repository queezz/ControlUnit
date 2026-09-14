# September 14 run and Kikusui telemetry

The preanode short is solved by the owner's physical repair to the plasma
source (confirmed in this session). The remaining findings concern control
software and measurement quality, not an unresolved preanode short.

## Experiment record

Read the September 14 PIHTI journal, its ControlUnit screenshots, the
completed `cu_20260914_173253.csv`, the event/launcher logs and the source
installed on the Pi. The rig reported 4.14.1; its checkout was
`32959f27745c2b0548af49781ad7706580d412b8`. All event times below are JST.

- 49,295 complete 26-field rows, no missing parsed values, strictly increasing
  timestamps, 17:32:53.711849–19:25:58.689335. Stop was deliberate; a new
  slow acquisition began at 19:26:02.
- Sampling changed to 1 s at 17:33:43 and back to 0.1 s at 18:07:32.
  Do not interpret the whole-file average interval as a missed 10 Hz target.
- During the plasma-test window 18:44:46–18:53:16: 5,098 rows, mean interval
  0.100043 s, median 0.099863 s, maximum 0.182482 s; no interval above 0.2 s.
- Upstream Baratron pressure at 18:45–18:53: median 4.854e-3 Torr,
  5th–95th percentiles 4.812e-3–4.988e-3 Torr.
- Two ADC errors before the test, at 18:31:35 and 18:36:05:
  `OSError(121, Remote I/O error)`, each automatically recovered after one
  failed read. Adjacent CSV gaps were 0.606 and 0.623 s (the log rounds to
  one second). Switching-transient causation is possible, not established.
  No later reader failure was found in this completed run.
- Other fast-segment timing outliers did occur outside the discharge window,
  including 1.216 s at 19:12:01. The good plasma cadence is not a claim that
  the entire evening had no timing delays.

The CSV SHA-256 is
`05b976b8f74046c32d28d170ff879c49b9b030a1287302d6bd30ae1b4b08c7a1`.
Source files were copied for analysis and not modified.

## PID handover

The 18:52 journal entry describes the 18:50:03 command to engage a 0.50 A
PID target. Manual drive before it was 1900 mV. The first CSV row showing
the PID command, at 18:50:04.113832, records **5500 mV**, sustained until
manual control resumes at 18:50:11.897668. Ip returns near its off-plasma
baseline during the episode.

Installed source shows that manual commands recreate the PID, but enabling
it does not reset its clock or initialize the output from the held drive.
Its first update counts roughly 169 s of manual operation as elapsed time.
With P=30 and I=40, the integral saturates at 4500 mV; the controller then
adds a 1000 mV offset outside that limit. An offline replay with 169 s and
input -0.25 A reproduces 5500 mV. The installed DAC driver clamps this to
code 4095, nominally 4.9988 V; it does not output 5.5 V or wrap to zero.

This establishes a software handover fault, not the complete physical cause
of extinction. There was no simultaneous PSU voltage/current/protection
record, so a full-scale command must not be presented as a measured filament
current pulse. The owner clarified that the student intended ignition plus
maintenance; the replacement should engage only on an established discharge.

Two further record caveats:

- Off-plasma Ip median at 18:41–18:43 was -0.325891 A, with no zero action
  logged in this run. Absolute plasma-current values and PID targets need
  a valid zero reference.
- `PresetV_cathode` stays zero during manual drive: that path bypasses the
  ADC worker's command record. The event log supplies the manual commands.
  Existing analog `Ci/Cv` channels are unwired placeholders.

## Read-only LAN proof and next work

The connected PWR401L, firmware VER01.24 BLD0056, answered `*IDN?`,
`MEAS:VOLT?`, `MEAS:CURR?` and `OUTP?` on TCP 5025. Output was off on both
checks, with -0.0045 V and approximately 0.0075–0.0083 A readback. Ten
voltage/current pairs from the office PC took 4.58 ms median and 19.53 ms
maximum. This establishes connectivity, not reliability during plasma.

Owner decision: log several normal manual discharges and bakes first, then
use those records to understand filament current, voltage, warm-up behaviour
and LAN reliability before fixing PID. The initial 4.15.0 recorder writes a
separate timestamped CSV, records missing polls and connection recovery, and
never sends output, setpoint, reset or remote-mode commands. Its setup and
data contract are in [Kikusui over LAN](../hardware/kikusui-lan.md).

Later filament-condition warnings should compare resistance V/I and power
VI at similar operating and thermal conditions against a healthy baseline.
Temperature, contacts, leads and geometry also affect resistance; a warning
cannot uniquely diagnose thinning, and today's file cannot establish a
resistance trend without the absent PSU measurements.

The owner also requested PIHTI Log's existing attachment flow be extended
to all available ControlUnit parameters at the instant of capture, as a
table and optionally a picture, with a possible labelled averaging window.
Fleet post `20260914-86630ead-525f3f` carries that request to `code/pihti-log`.
Kikusui live readouts and a snapshot API are follow-up integration work.

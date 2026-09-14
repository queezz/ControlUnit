# Logging the Kikusui over LAN

The cathode's own voltage and current are to be logged from the Kikusui
PWR401L (PWR-01 series) over its LAN port, not from its analog monitor
pins and not from a Hall sensor (owner decision 2026-09-11, "lan it is
then"). The reasoning is in [Cathode control](cathode-control.md) and in
the lab vault; this page is the how-to, with everything below taken from
Kikusui's PWR-01 Interface Manual (IB035082, 2020) and the PWR-01 FAQ.

## Why LAN

- J1's monitor outputs are referenced to the supply's output negative,
  which floats at cathode potential; reading them would need a second
  isolation stage and one more analog path into the ADC board whose I²C
  bus already fails under an arc.
- Ethernet is transformer-isolated by construction. Nothing electrical
  ties the supply to the Pi.
- The supply's own metering is calibrated and answers in volts and
  amperes; no rerouting of 30 A through a sensor.

## On the supply, once

1. Connect a straight category-5 cable from the rear **LAN** port (it has
   a cover; the RS232C port beside it is the same shape, read the label)
   to the lab switch.
2. Enable the interface: press CONFIG until **CF40** shows, turn the
   CURRENT knob to **ON**.
3. Choose how it gets an address: press CONFIG until **CF60** shows, turn
   the VOLTAGE knob to **CF61**, and set with the CURRENT knob:
   `110` = DHCP on, Auto-IP on, manual off (the factory default; fine on
   the lab VLAN if the router gives leases); `001` = manual, then enter
   the four octets in **CF62** to **CF65** and the subnet mask as a bit
   count in **CF66** (16 for 255.255.0.0, 24 for 255.255.255.0). The lab
   VLAN's addresses have been static for years, so a manual address
   beside the Pi's is the sensible choice.
4. Apply: **CF60: APPL** restarts the interface, or turn the POWER switch
   off and on. Changes to CF61–CF66 take effect only then.
5. Open `http://<address>/` in a browser: the interface board serves a
   page with the instrument information, the network settings and a
   remote-control panel. Setting a password there is optional; **CF60:
   LCI** resets the interface if the password is forgotten.

## Read-only logging (4.15.0)

The first stage records the supply while the operator drives discharges and
bakes manually. Collect normal behaviour before changing the plasma PID or
inventing filament-condition warning thresholds (owner decision 2026-09-14).
There is no automatic ignition and this logger sends no control commands.

On the Pi, create `~/.controlunit/kikusui.yml` with its actual address:

```yaml
host: 192.0.2.10  # example only: replace with the supply's numeric LAN address
port: 5025
interval_s: 0.5
timeout_s: 1.0
retry_s: 5.0
```

Configuration is read at acquisition Start. An absent file disables logging
with one message; an invalid file reports the problem without preventing
normal acquisition. The host is a numeric IPv4 or IPv6 address so DNS cannot
hold up shutdown. `interval_s` accepts 0.1–60 s, `timeout_s` 0.1–5 s, and
`retry_s` 1–60 s. The defaults record at about 2 Hz independently of the ADC's
sampling period. Long polls reduce telemetry cadence, never cause catch-up
bursts. For off-rig testing use `dummy: true`; rows say `dummy` and contain
synthetic zero output. Dummy hardware refuses real LAN configuration.

Each run creates `kikusui_YYYYMMDD_HHMMSS.csv` beside its
`cu_YYYYMMDD_HHMMSS.csv`. A header identifies the paired ADC file and schema
`controlunit-kikusui/v1`. The columns are:

| Column | Meaning |
|---|---|
| `date` | Receipt time in ISO format with the local UTC offset |
| `logger_elapsed_s` | Monotonic time since this recorder started |
| `query_ms` | Time for the poll, including reconnect/identity when needed |
| `voltage_v`, `current_a` | Supply's measured output in volts and amperes |
| `output_on` | Queried output-enable state, 0 or 1; not proof of delivered power |
| `commanded_cathode_mv` | Software's requested DAC command, captured before the poll; not measured DAC voltage |
| `plasma_target_a` | Software's PID target, captured before the poll; zero when off |
| `status` | `ok`, `unavailable`, or `dummy` |
| `error` | Failure description for an unavailable poll |
| `identity` | Supply identity on successful polls |

Every row is flushed. Existing telemetry files are never overwritten. A file
write failure stops this recorder with an explicit application-log message;
it does not stop the ADC or alter outputs. Voltage, current and output state
are queried sequentially, not simultaneously; the time column marks receipt,
not an instrument-provided measurement timestamp. Align with the ADC by time,
converting the offset-aware timestamp to the rig's local time as needed.
The DAC can clamp its command; the requested value is not proof of the
applied voltage. There is one row per attempted poll, not one row per nominal
sampling slot: use timestamps and status transitions to measure outage
duration, rather than counting unavailable rows as 0.5-second intervals.

**On LAN failure:** the entire poll is unavailable, its measurement/output
fields are empty, and the application Log says `Kikusui telemetry LOST` once
per outage. The background recorder retries and logs `BACK` on recovery.
There is no reuse of the last good reading as a new measurement, no zero
substitution, and no change to manual drive. Reconnection verifies model and
serial identity and sends only queries. Stop interrupts a connected read and
all retry/sampling waits; hardware shutdown takes precedence over waiting for
this recorder. A future PID that depends on telemetry will need its own
explicit loss-of-feedback policy.

The existing ADC `Ci/Cv` columns and the Cathode Measured cell are still the
old analog placeholders: **they are not these LAN measurements**. The separate
file preserves the original ADC schema and independent timing. From 4.16.0,
the Qt Cathode panel shows Kikusui V/I and recording/output state beneath
the manual controls. Hover for the file path and sample receipt time.
The display updates every 500 ms from a locked copy of a flushed CSV row.
Failed reads clear the numbers on the next display update; readings older
than the configured interval plus timeout plus 0.5 s are withheld as stale.
Stopping clears the readout. Simulated data is labelled SIMULATED.
From 4.17.0 the WebUI has full filament voltage/current cards under
**Kikusui** in Operate, Observe and Monitor. The existing small/big switch
sizes these readings too, and folding keeps both values on the summary.
The manual control no longer displays the unwired analog `Cv` placeholder
as a measured supply voltage. The ADC columns retain their original meaning.

`/api/state` carries a separate `kikusui` object: `status`, measured
`voltage_v`, `current_a`, `output_on`, receipt `date`, `age_s`,
`stale_after_s`, query timing, identity and the telemetry filename when
available. The main thread publishes the recorder snapshot; the web thread
reads plain locked values. Age continues increasing if the main thread
stalls, independently of ADC freshness. Non-fresh states omit V/I/output
fields, and browser-side expiry also clears the cards if requests hang.
These are instantaneous receipt-time measurements, not averaged ADC samples.
Filament resistance `V/I` and power `VI` can be derived during review; avoid
dividing near zero current and compare resistance under similar thermal and
operating conditions before interpreting it as thinning.

## Transport

Socket to port **5025** (SCPI-RAW), one line per command terminated with LF.
The recorder's complete wire command set is:

```text
*IDN?       -> identity (on connection/reconnection)
MEAS:VOLT?  -> output voltage in volts
MEAS:CURR?  -> output current in amperes
OUTP?       -> output-enable state, 0 or 1
```

The recorder maintains one socket, sends one query at a time and reads a
complete newline-terminated reply before sending another. A single `recv`
is not guaranteed to contain even one complete reply. One timeout bounds the
whole poll, including fragmented responses; invalid numbers, output states
or identity are failures rather than plausible-looking measurements.

It does not send `SYST:COMM:RLST REM`, output/setpoint commands, reset or
clear-status commands. Reading must not take over the front panel or clear
an instrument alarm. The existing J1 current control remains the actuator.

On 2026-09-14 the connected PWR401L (firmware VER01.24 BLD0056) answered
these queries with output off. Ten voltage/current pairs from the office PC
took 4.58 ms median, 19.53 ms maximum. This proves the transport, not its
reliability during plasma; discharges and bakes are the next evidence.

Six further read-only polls from the Pi itself on the same day succeeded
with output off, taking 2.772–3.266 ms per voltage/current/output poll.

## First run after deployment

With the machine-local configuration above present, start acquisition from
the rig GUI. The Cathode panel should show **Recording**, V/I and output
state; the Log names `kikusui_<run timestamp>.csv` alongside the ADC file.
During normal manual operation, compare those readings with the supply's
display. Stop acquisition normally and inspect the paired files. Capture
discharges and bakes before setting filament-condition thresholds or changing
PID behaviour. The logger cannot switch on or set the supply.

## Sources

- Kikusui PWR-01 Interface Manual, "LAN" (pp. 25–28), "Measurement"
  (p. 202), "Communication through RS232C, USB, or LAN" (p. 229).
- [Kikusui FAQ: fixed IP address on PWR-01](https://global.kikusui.co.jp/kikusupport/how-do-i-set-a-fixed-ip-address-for-lan-communication-on-pwr-01-series/)
- [Kikusui PWR-01 interface specifications](https://kikusuiamerica.com/spec/pwr-01_%E3%80%90common-specifications%E3%80%91interface/)

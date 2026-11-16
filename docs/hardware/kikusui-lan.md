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
   `110` = DHCP on, Auto-IP on, manual off (the factory default); `001` =
   manual, then enter the four octets in **CF62** to **CF65** and the
   subnet mask as a bit count in **CF66** (16 for 255.255.0.0, 24 for
   255.255.255.0). Use `110` unless the VLAN's administrators assigned the
   supply an address: a manual address picked by hand on a VLAN the lab
   does not run can be handed to a laptop by its DHCP, and was (see
   [Its address](#its-address) below). This step used to recommend a
   manual address beside the Pi's.
4. Apply: **CF60: APPL** restarts the interface, or turn the POWER switch
   off and on. Changes to CF61–CF66 take effect only then.
5. Open `http://<address>/` in a browser: the interface board serves a
   page with the instrument information, the network settings and a
   remote-control panel. Setting a password there is optional; **CF60:
   LCI** resets the interface if the password is forgotten.

## Its address

**The network is not the lab's.** The rig, the supply and the lab's PCs
are on Kyoto University's Optical Lab VLAN, run by the university
(queezz, 2026-11-16: "Network is KyoDai vlan, no control here"). Nothing
here can reserve an address in its DHCP.

**The supply's identity** (its own welcome page, 2026-09-14): model
PWR401L, serial AV000874, MAC address `00:0f:ce:04:68:81`, mDNS name
`PWR401L-00874.local`. The MAC and the name stay the same whatever its
address is.

**How it was set, and what went wrong.** On 2026-09-14 queezz entered
`10.249.254.10`, mask `255.255.255.192`, on the panel by hand (CF61 =
`001`; the welcome page showed default gateway `0.0.0.0`, which no DHCP
lease gives). `.10` lay inside the range the VLAN's DHCP hands out, and a
laptop was given it. From then on two machines answered for one address:
the link answered 84 % of polls on 2026-10-05 (when a browser at `.10`
also reached the web view), flapped LOST/BACK on 10-06 and 10-19, came
back on 10-07 only after a power cycle (the LAN lamp red, then green), and
on 2026-11-16 never answered a whole hydrogen run while the supply drove
the filament (20.2 A on its panel). That evening the Pi saw `.10` at MAC
`14:18:c3:e9:2f:46`, an Intel network card, not the supply, and the
supply's own name did not resolve: an LXI instrument that sees its address
taken lights its LAN lamp red and stops networking until it is restarted.
Vault: "Kikusui LAN lost to an address clash 2026-11-16".

**Signs of the same trouble again:** the Cathode card and the Log say the
LAN is lost while the supply's panel shows it driving; the LAN lamp on the
supply is red; the link flaps LOST/BACK while the supply is on.

**Moving it to a new address** (no output live first: the drive at 0 and
the supply's output off, or no run at all):

1. Power the supply off and on (clears a LAN fault).
2. CONFIG until **CF60**, VOLTAGE knob to **CF61**, CURRENT knob to
   **110** (DHCP). A manual address only if the VLAN's administrators gave
   one: then `001` and the octets in CF62–CF65, the mask bits in CF66.
3. **CF60: APPL**, or power off and on again.
4. After a minute, from the Pi: `getent hosts PWR401L-00874.local` gives
   the address it was leased (a reading, nothing is sent to the supply).
   The supply's welcome page at that address shows it too.
5. Put the address in `~/.controlunit/kikusui.yml` on the Pi as `host:`
   (numeric; the link does not resolve names), then Stop and Start
   acquisition: the recorder reads the file when a run starts. The Log
   should then say "Kikusui settings: … V, … A".

**If DHCP does not hold, a link of its own.** Nobody but the Pi talks to
the supply (queezz, 2026-11-16: "No one goes to that PSU page directly but
pi"), so it need not be on the VLAN at all: a USB Ethernet adapter on the
Pi, or a small switch or router serving only the two, with the supply on a
private address (for example `192.168.50.2`, the Pi's second port
`192.168.50.1`) entered once more on the panel. No laptop can then take
its address. The costs: the adapter, the Pi's second port to configure
(a session's work on his word), and the supply's own web page reachable
only through the Pi. Not done yet: DHCP is tried first (2026-11-16).

A DHCP lease may change over time; if the link loses the supply again with
its LAN lamp green, repeat step 4 and 5. Looking the name up at each
connection instead would make this automatic (the link takes only a
numeric address today, so that a name lookup can never stall a stop).

## Read-only logging (4.15.0)

The first stage records the supply while the operator drives discharges and
bakes manually. Collect normal behaviour before changing the plasma PID or
inventing filament-condition warning thresholds (owner decision 2026-09-14).
There is no automatic ignition, and until 2026-09-15 this logger sent no
command at all; it now sends the two output writes below, and only when a
person presses for them (see [The two writes](#the-two-writes)).

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
`controlunit-kikusui/v2` (v1 before 4.30.0, without the last four columns). The columns are:

| Column | Meaning |
|---|---|
| `date` | Receipt time in ISO format with the local UTC offset |
| `logger_elapsed_s` | Monotonic time since this recorder started |
| `query_ms` | Time for the poll's measurements, including reconnect/identity when needed; the settings are read after the row is stamped |
| `voltage_v`, `current_a` | Supply's measured output in volts and amperes |
| `output_on` | Queried output-enable state, 0 or 1; not proof of delivered power |
| `commanded_cathode_mv` | Software's requested DAC command, captured before the poll; not measured DAC voltage |
| `plasma_target_a` | Software's PID target, captured before the poll; zero when off |
| `status` | `ok`, `unavailable` or `dummy` for a poll; `output_on`, `output_off`, `output_on_failed` or `output_off_failed` for the row a press leaves |
| `error` | Failure description for an unavailable poll |
| `identity` | Supply identity on successful polls |
| `voltage_setting_v`, `current_setting_a` | The supply's own voltage and current settings (`VOLT?`, `CURR?`); from v2 |
| `oper_cond`, `ques_cond` | The OPERation and QUEStionable status condition words (`STAT:OPER:COND?`, `STAT:QUES:COND?`), recorded raw as integers; from v2 |

The settings and the status words were added on the owner's word (2026-11-13,
live: "Sure, read that") after the audit of the student runs: the 7.80 V
setting of 2026-10-02 had been raised by 11-13 with no record of when. The
Log says the settings once at the start of a run ("Kikusui settings: 10 V,
15 A"), and again whenever one of them changes or the questionable word
becomes nonzero or clears. Which OPERation bit means constant current and
which constant voltage is not decoded: the PWR-01 interface manual could not
be read when this was built, so the raw word is kept and its bits can be
read off a run that shows the supply move between the two. A status query
that fails leaves those four columns empty for that poll; the measurements
are unaffected. A link that failed (a timeout, a closed connection) is the
LAN, and the next poll asks again. An answer that could not be read (not a
number, out of range, or an infinity such as `9.9E+999`) is the supply:
after three of those in a row the settings are not asked for again that
run, said once ("Kikusui settings not readable …"). A Stop that closes the
socket under a status query is never reported as a failure. Until the
review of 2026-11-13 the first failure of either kind gave up for the run,
a Stop mid-query was logged as one, and an infinite status word raised an
error nothing caught, which stopped the whole recorder.

Every row is flushed. Existing telemetry files are never overwritten. A file
write failure stops this recorder with an explicit application-log message;
it does not stop the ADC or alter outputs. Voltage, current and output state
are queried sequentially, not simultaneously; the time column marks receipt,
not an instrument-provided measurement timestamp. Align with the ADC by time,
converting the offset-aware timestamp to the rig's local time as needed.
The DAC can clamp its command; the requested value is not proof of the
applied voltage. There is one row per answered poll, not one row per nominal
sampling slot, and one `unavailable` row per outage, its first: the supply is
switched off whenever it is not in use, and from 4.29.1 the retries through a
pump-down are not written (queezz, 2026-10-21: "A perfect noise"). An outage
runs from its `unavailable` row to the next row of any other status; files
before 4.29.1 have one `unavailable` row per retry.

**On LAN failure:** the entire poll is unavailable, its measurement/output
fields are empty, and the application Log says `Kikusui telemetry LOST` once
per outage, after three polls in a row have gone unanswered (about ten
seconds at the 5 s retry). The background recorder keeps checking every
`retry_s` and logs `BACK` when the supply answers again. A shorter silence is
a blip on the LAN: one `unavailable` row in the file and nothing in the Log.
There is no reuse of the last good reading as a new measurement, no zero
substitution, and no change to manual drive. Reconnection verifies model and
serial identity before anything is sent, writes included. Stop interrupts a connected read and
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
fields. The page holds the last good reading for ten seconds when one goes
missing — late, the LAN lost, the rig not answering — and changes nothing
meanwhile; after that the two cards turn grey with a dash and the word for
why, and the lamp goes dim, with or without another answer (4.23.2; owner,
2026-10-02: "We should not blink, and we shouldn't change state. But we can
gray those Kikusui panels when there is no response for a reasonable
time"). A state the rig names outright, stopped or a press just sent, is
shown at once. The server's own two-second rule is unchanged, and it is
still what refuses an output-on press.
These are instantaneous receipt-time measurements, not averaged ADC samples.
Filament resistance `V/I` and power `VI` can be derived during review; avoid
dividing near zero current and compare resistance under similar thermal and
operating conditions before interpreting it as thinning.

## The two writes

Owner decision 2026-09-15, live, in front of the standing rule of 2026-09-14
that this link was read-only: *"Kikusui has LAN now, I want the one-off signal
button in our control. Then we turn that one off no matter the dac voltage"*
and, the same day, *"Off and on. Why not? Then we have full cathode control
when powered"*. The link may now send exactly two commands, `OUTP 0` and
`OUTP 1`, and nothing else ever: no voltage or current setpoint, no `*RST`,
no status clear. The allowlist in `ReadOnlyClient` is the whole of it —
ten words since 2026-11-13, eight read-only queries and these two — and a
test holds it to those ten, checks every query ends in `?`, and proves that
`OUTP ON`, `VOLT 10`, `CURR 1`, `VOLT:PROT 12`, `STAT:OPER:ENAB 0` and `*RST`
raise before a byte is sent.

**The output is not the drive.** The cathode DAC feeds the supply's external
current-control input; the output is the supply's own switch between it and
the filament. Dropping the drive to zero is not the same as opening the
output, which is the press this exists for.

**Off is always allowed; on is gated.** Off asks nothing of anybody — no
Remote switch, no name, no lab's word, no acquisition — exactly as Stop all
outputs asks nothing, and Stop all outputs sends it too. On is a setter: the
Remote switch on the rig's screen, the lab's word where the machine holds
one, and the operator lock, all as any setpoint. On is refused outright while
the telemetry is not fresh (`the supply is not answering; turn it on at the
supply`), so nothing is closed onto a filament that nobody can see.

**Who sends it.** A press never runs on the Qt main thread and never waits on
the LAN there. While a run is recording, the press is handed to the
recorder's own thread, which carries it *between polls* on the socket it
already owns — one thread, one socket, and a press that arrives mid-poll
waits for the poll. With no recorder running, a short daemon thread opens its
own connection, verifies the supply's identity, writes, reads back and closes.
Either way the `OUTP?` readback is queried on the same connection and the Log
says one of three things:

```text
Kikusui output OFF (confirmed)                   the supply answered 0
Kikusui output OFF sent, readback 1              the write went out; the supply disagrees
Kikusui output OFF FAILED: <reason>; manual drive unchanged
```

with `ON` in place of `OFF` for the other direction, and a fourth line —
`Kikusui output OFF SIMULATED: no supply is connected` — on dummy hardware,
where the press moves a simulated flag and nothing else.

**In the sidecar.** A press writes one row of its own, with the readback in
`output_on`, no voltage or current (the supply was switched, not measured),
and `status` one of `output_on`, `output_off`, `output_on_failed`,
`output_off_failed`. No column is added and the schema line stays
`controlunit-kikusui/v1`; a reader that selects `status == "ok"` rows is
unaffected, and one that counts states should know these four. The recorder
publishes that row as its snapshot, so the Live page's Cathode card reads
`output off sent` for the one poll between the write and the next
measurement rather than a number nobody measured.

**On the web.** `POST /api/cathode-output` takes `{"on": false}` or
`{"on": true}`. On the Live page the Cathode card's heading line carries a
lamp: green while the telemetry is fresh and the output is closed, grey while
it is fresh and open, and an uncoloured ring while there is no fresh answer.
The word for that state — `output on`, `output off`, or the reason there is
none — is on the lamp's tooltip and, in full, on the two cathode readout
cards; the heading row has no width for it beside the PID/Manual switch, and
saying it twice on one screen is the defect fleet's Teaching law names.
Pressing the lamp sends the opposite of what it shows; from the dim state it
sends only off, which is the press no gate stands in front of.

## Transport

Socket to port **5025** (SCPI-RAW), one line per command terminated with LF.
The recorder's complete wire command set is:

```text
*IDN?       -> identity (on connection/reconnection)
MEAS:VOLT?  -> output voltage in volts
MEAS:CURR?  -> output current in amperes
OUTP?       -> output-enable state, 0 or 1
VOLT?       -> the voltage setting in volts          (from 4.30.0)
CURR?       -> the current setting in amperes        (from 4.30.0)
STAT:OPER:COND? -> OPERation condition word          (from 4.30.0)
STAT:QUES:COND? -> QUEStionable condition word       (from 4.30.0)
OUTP 0      -> open the output   (a press, never the recorder's own doing)
OUTP 1      -> close the output  (a press, gated; see The two writes)
```

The recorder maintains one socket, sends one query at a time and reads a
complete newline-terminated reply before sending another. A single `recv`
is not guaranteed to contain even one complete reply. One timeout bounds the
whole poll, the four settings queries included, and fragmented responses;
invalid numbers, output states or identity are failures rather than
plausible-looking measurements. The row's `date` and `query_ms` are taken
after the measurements and before the settings, so they say when the volts
and amperes were read.

It does not send `SYST:COMM:RLST REM`, any voltage or current setpoint, reset
or clear-status command. Reading must not take over the front panel or clear
an instrument alarm. The existing J1 current control remains the actuator:
the two writes switch the supply's output, they never set what it delivers.

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
PID behaviour. The logger sets nothing; the only thing it can switch is the output, and only
when somebody presses for it.

## Sources

- Kikusui PWR-01 Interface Manual, "LAN" (pp. 25–28), "Measurement"
  (p. 202), "Communication through RS232C, USB, or LAN" (p. 229).
- [Kikusui FAQ: fixed IP address on PWR-01](https://global.kikusui.co.jp/kikusupport/how-do-i-set-a-fixed-ip-address-for-lan-communication-on-pwr-01-series/)
- [Kikusui PWR-01 interface specifications](https://kikusuiamerica.com/spec/pwr-01_%E3%80%90common-specifications%E3%80%91interface/)

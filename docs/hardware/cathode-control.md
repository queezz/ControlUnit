# Cathode control

The cathode is a hot filament on a Kikusui PWR401L supply (PWR-01 series,
0–40 V, 0–40 A). The supply's output current follows a voltage on its
external current-control input, pins 11 (+) and 15 (−) of the rear J1
connector, and that voltage comes from the control unit's 12-bit MCP4725
DAC through an isolation stage. The program drives the cathode two ways;
either is chosen on the rig's **Cathode** dock or on the web Control tab's
Cathode group, and setting one turns the other off.

## PID

A plasma current in amperes (0–3 A). The plasma current PID, which runs
inside the ADC reader thread, moves the DAC every sample to hold the
measured `Ip` at the setpoint. "PID off" drops the DAC to zero.

Because the loop runs in the reader, it stops moving when the reader
stops. From 4.11.0 the reader retries a failed read instead of dying, and
the main thread writes "Reader lost" to the log if samples stop anyway;
before that, a dead reader meant "PID on" moved nothing, which read at the
rig as the supply not answering (2026-09-09).

## Manual

A voltage in millivolts (0–5000) held on the DAC with the PID off — the
knob, in software (owner direction 2026-09-09). The filament sits where a
person put it whatever the plasma does, and the drive is written from the
main thread straight to the DAC worker, so it works while the reader is
lost. The web Control tab offers ±1000/100/10/1 mV draft steps and a Set,
as the gas rows do. The log line is "Cathode drive set to N mV, PID off",
and the web record's `cathode_mv` carries what the DAC holds, whichever
mode put it there; `/api/health` says `outputs live: cathode drive` while
it is not zero.

Until 4.11.0 this row was the Settings dock's "Output voltage" in volts,
on the rig's screen only.

## The supply's own knob

The Kikusui obeys its external input only while its CONFIG parameter
**CF10 (Ext. CC)** is ON; with CF10 OFF the front-panel CURRENT knob sets
the current again, whatever the DAC holds. So to run the cathode by hand
with the Raspberry Pi out of the loop: turn the drive off in the program
(or stop acquisition), then on the supply press CONFIG, turn the VOLTAGE
knob to `CF10`, turn the CURRENT knob to `OFF`, and hold CONFIG until the
measured values return. The change applies at once. CF11 is the same
switch for voltage control and CF12 the input range (`Lo`, 0–5 V, the
factory setting: output current = 40 A × V<sub>ext</sub> / 5 V at the
supply's own input). Set CF10 back to ON to hand control to the program
again. The manual pages are scans in the lab vault under
`Hardware/Equipment/Kikusui Power Supplies.md`, and the lab's own page is
[aklab-howto](https://queezz.github.io/aklab-howto/hardware/equipment/kikusui-pwr/).

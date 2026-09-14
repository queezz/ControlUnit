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

## What the program will do

Socket to port **5025** (SCPI-RAW; the port is fixed), one line per
command, terminated with LF (`\n`). The two queries:

```text
*IDN?            → KIKUSUI,PWR401L,<serial>,<firmware>
MEASure:VOLTage? → the output voltage, in volts
MEASure:CURRent? → the output current, in amperes
```

The supply refreshes its measured voltage and current alternately every
25 ms, so asking faster than every 50 ms returns the previous value; the
rig samples at 0.1 s or slower, well inside that. `SYST:COMM:RLST REM` is
the manual's recommended first command in a program (it puts the panel in
remote); it is not required for measuring, and the program will not send
it, so the front panel keeps working while the rig logs.

A quick check from the office PC, once the address is known:

```powershell
& "$env:USERPROFILE\.venvs\hardware-dev\Scripts\python.exe" -c "import socket; s=socket.create_connection(('<address>', 5025), timeout=3); s.sendall(b'*IDN?\nMEAS:VOLT?\nMEAS:CURR?\n'); print(s.recv(256).decode())"
```

The build itself is described in `.agents/directions.md` (a worker beside
the DAC workers, the answers written as the `Ci` and `Cv` columns, NaN
and one log line when the supply does not answer, the address in
`~/.controlunit/kikusui.yml` on the Pi and never in git). The Cathode
group's Measured cell on the web already reads `Cv`, so it will simply
start showing volts.

## Sources

- Kikusui PWR-01 Interface Manual, "LAN" (pp. 25–28), "Measurement"
  (p. 202), "Communication through RS232C, USB, or LAN" (p. 229).
- [Kikusui FAQ: fixed IP address on PWR-01](https://global.kikusui.co.jp/kikusupport/how-do-i-set-a-fixed-ip-address-for-lan-communication-on-pwr-01-series/)
- [Kikusui PWR-01 interface specifications](https://kikusuiamerica.com/spec/pwr-01_%E3%80%90common-specifications%E3%80%91interface/)

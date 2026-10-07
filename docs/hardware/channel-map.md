# Channel Map

The canonical source is `controlunit/settings.yml` — the developer's
deliberate in-code data dictionary, written as a memory aid after long gaps
in work. Channel names, ADC addresses, gains, descriptions, and conversion
function identifiers all live there.

> *"I did that to not remember the modules. So I DID DOCUMENT THERE
> INTENTIONALLY."* — Arseniy

Hardware documentation (board layouts, signal conditioning, pin numberings,
datasheets) lives in the external hub:
[aklab-howto](https://queezz.github.io/aklab-howto/hardware/controlunit/).
Do not expect hardware build notes here.

## ADC signal channels

| Name | Signal | Sensor / notes |
|------|--------|----------------|
| `Ip` | Plasma current | Hall-effect sensor on channel 0, on the preanode supply's wire (owner statement 2026-10-07: "plasma current IS preanode current presently"): `25 * (Ip / Vhall - 0.4961) A`; supply-corrected since 4.22.0, with the existing provisional 5 A/V sensitivity at 5 V. Against that supply's panel it reads about 0.70 (0.60 A for 0.9 A on 2026-10-02, 1.54 for 2.2 A on 2026-10-05, a flat 3.53 A where the supply limited at 5 A on 2026-10-06), so the true sensitivity is nearer 7 A/V until the known-current calibration says the number. The resting ratio was the ideal 0.5 until 4.22.2 (files up to 2026-10-02 read 0.098 A low); each file's header carries the formula it was written with. |
| `Vhall` | Hall supply reference | Channel 1, read immediately after `Ip`, 10 V range (the 5 V range clips at 5.0176 V). Raw volts retained for diagnosis; no additional display or curve. |
| `Pu` | Upstream pressure | Pfeiffer single gauge PKR251 (currently operating in Pirani mode — cold-cathode discharge not igniting) |
| `Pd` | Downstream pressure | Ionization gauge, with `Place: "downstream"` in the settings for the Control dock and the web Gauges card to show beside its short name. Its controller's mode (0 Torr linear, 1 Pa log, or 2 off — the gauge switched off at its controller and declared so on the Control dock or the web Ion gauges card, when the raw volts are kept and `Pd_c` is NaN) and exponent are recorded per row as `IGmode` and `IGscale`, the columns the file has always had. |
| `Pu2` | Upstream pressure | Second ionization gauge, wired to channel 16 on 2026-09-15, with its own selector on the Control dock and the web Control tab, and `Place: "upstream"` in the settings for both to show beside its short name. Its mode (the same three codes as `Pd`'s) and exponent are recorded per row as `IGmode_Pu2` and `IGscale_Pu2`, appended after the original columns so nothing an old reader counts on moves. |
| `Bu` | Upstream Baratron | MKS 627, FS = 1 Torr |
| `Bd` | Downstream Baratron | MKS 628B, FS = 0.1 Torr |
| `MFC1` | H₂ flow | 20 SCCM range |
| `MFC2` | O₂ flow | 10 SCCM range |
| `Ci` | Cathode current | **Channel prepared in ADC map and on PCB; never actually measured.** Conversion function exists for consistency. |
| `Cv` | Cathode voltage | Same as `Ci` — prepared but not deployed |
| `T` | Membrane temperature | Now read off-Pi (NI on Windows). Channel definition remains. |
| `QMS_signal` | Sync trigger state | Boolean — logs whether GPIO sync is active during each row |

## Hall supply correction (4.22.0)

The reference must measure the supply feeding the Hall sensor, against the
same ADC ground. Queezz connected the PSU voltage on 2026-09-30. The prior
board inspection identifies the neighbouring terminal as channel 1 beside
`Ip` on channel 0; verify those voltages on the rig before deployment.

`Ip` names `Supply Channel`, `Nominal Supply`, `Zero Ratio`, and `Amperes
Per Volt` in settings. The values are 5 V, 0.4961 and 5 A/V; the ratio is
where the sensor was measured to rest with no current on 2026-09-30 and
2026-10-02, the same within 4 mA across both days. This
cancels proportional supply movement in both the zero and the sensitivity;
it does not replace a known-current calibration or correct ground offsets.
The recorded `Ip_c`, existing current readouts, and PID use the same
correction. Raw `Ip` and `Vhall` remain volts, and the CSV header records
the formula. Readers must use named CSV columns, as the new signal changes
column positions. Slow sampling converts the paired means stored in the row.

A missing, non-finite or out-of-range supply (configured limits 4–6 V)
makes `Ip_c` unavailable (`NaN`); the event is logged once and recovery is
logged too. No stale reference or fixed-voltage fallback is substituted.
The PID holds its existing command during that interval. Settings without
a supply channel retain `5 * (Ip - 2.52)`, with optional `Zero Voltage`
and `Amperes Per Volt` overrides. Settings version 1.5 activates the new
canonical map; older local settings need their customizations merged before
reuse. The rig had no local settings file on 2026-09-30.

The [noise investigation](../diagnostics/2026-09-19-hall-sensor-noise.md)
explains why the supply was added. Filters and longer baseline windows are
separate work; reassess noise with the newly wired reference first.

## DAC outputs

| Device | Signal | Notes |
|--------|--------|-------|
| DAC8532 ch1 | MFC1 (H₂) setpoint voltage | |
| DAC8532 ch2 | MFC2 (O₂) setpoint voltage | |
| MCP4725 | Plasma current (Ip) DAC | Behind galvanic I²C isolator since Apr 2026 |

## Conversion functions

Conversion polynomials are defined in `controlunit/devices/conversions.py`
with LaTeX in docstrings — physics inline with the code that uses it.

The polynomials come from external datasheets. The PKR251 datasheet, for
example, lives in [aklab-howto](https://queezz.github.io/aklab-howto/).

Dispatch is settings-driven: each channel in `settings.yml` carries a
`Conversion Function` key that maps to a function in `conversions.py` via
`AdcChannelProps.set_conversion_function()`. Adding a new instance of an
existing sensor type means editing YAML, not code.

## Settings versioning

The repo carries `controlunit/settings.yml` as canonical schema. The live
rig runs `~/.controlunit/settings.yml` with its own channel map. A
`Settings Version` key prevents silent drift after a schema bump:

```python
# controlunit/readsettings.py
if local_config["Settings Version"] == config["Settings Version"]:
    config = local_config
```

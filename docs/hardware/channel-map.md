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
| `Ip` | Plasma current | Hall-effect sensor: `5 * (v - 2.52) A` |
| `Pu` | Upstream pressure | Pfeiffer single gauge PKR251 (currently operating in Pirani mode — cold-cathode discharge not igniting) |
| `Pd` | Downstream pressure | Ionization gauge |
| `Bu` | Upstream Baratron | MKS 627, FS = 1 Torr |
| `Bd` | Downstream Baratron | MKS 628B, FS = 0.1 Torr |
| `MFC1` | H₂ flow | 20 SCCM range |
| `MFC2` | O₂ flow | 10 SCCM range |
| `Ci` | Cathode current | **Channel prepared in ADC map and on PCB; never actually measured.** Conversion function exists for consistency. |
| `Cv` | Cathode voltage | Same as `Ci` — prepared but not deployed |
| `T` | Membrane temperature | Now read off-Pi (NI on Windows). Channel definition remains. |
| `QMS_signal` | Sync trigger state | Boolean — logs whether GPIO sync is active during each row |

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

# Development History

Development at `ControlUnit` does not follow measurement campaigns.
It follows the opposite: long quiet periods while the rig runs, then
intense pushes during experimental downtime.

> *"Development is usually NOT tied to actual experiments. More on the
> opposite side. Accumulated necessity is implemented when there is a
> break in experiments and there is time."* — Arseniy

## Timeline

```
≈ 2018–2019  Echelle Spectra at NIFS / LHD.
             pyqtgraph + Qt threading + the "scientific Qt app"
             visual grammar. The template-source for ControlUnit.

2020-02 ──── Initial commit (queezz). Echelle-ported Worker + ThreadType
             enum. One class, all devices dispatched by enum.

2020-03 ──── "Untangling Ito-kun's threading mess". Renames, structural
             clean-up. Lab member helped untangle.

2020-06 ──── First numpy → pandas attempt (incomplete; sits for years).

2020–22 ──── Long quiet period. Rig is running, dev is teaching.

2022-06 ──── [REORGANIZE] make a package, add pdoc3 docs.
             Visual snapshot of "old" architecture preserved.

2023-04 ──── Multiple contributors arrive (Kshora, leprecon-pi /
             Miura-kun). Channel names evolve live during measurement runs.

2023-05 ──── ADC channel meta moved into AdcChannelProps + settings.yml.
             8 commits "worker: tuning ADC thread" — the buffer redesign.
             Pandas migration finally approaches.

2023-06 ──── Logging-to-file, sampling-time-from-GUI, gain switching.
             customTypes.py, ionizationGauge.py, pfeiffer.py DELETED
             (absorbed into conversions.py).

2024-08 ──── Worker super class split. Big-bang: 662 lines deleted from
             monolithic worker.py. Committed by Miura-kun from the lab Pi.
             Pandas migration lands.

2024-09 ──── MFC integration (DAC8532), MCP4725 addition.
             Mass rename: sensors/ → devices/, components/ → ui/.

2024-09/10 ─ First plasma-current PID by Arseniy.
             "Ip PID response detected (hardware)" — the rig closes loop.

2024 onward  TemperatureControl on Windows + NI.
             Heater path migrates out of ControlUnit.
             ControlUnit MAX6675 path becomes dormant.

2025-08 ──── Two Codex automated PRs: data-handling moved INTO workers,
             CoreLogic signal fix. Untested on hardware at merge time.

≈ 2025–2026  tclogger experiments. ESP32-based single-sensor instruments.
             First operational move toward "network of instruments".

2026-04 ──── Isolated DAC for plasma current (Kawabata-kun).
             Settings layout cleanup, Ip-PID OFF button.
             Cursor-assisted with direct on-rig testing.

2026-05 ──── "settings: debug false". Lab still active.

Hardware: Raspberry Pi 3B → Pi 4 (8 GB), transparent to software.
```

## Contributors

| Handle | Person | Role |
|---|---|---|
| `queezz` / Arseniy | Principal developer | Wrote and rewrote most of the system across all phases |
| `Tatsuemon` / Ito-kun | B4 student | Extended Echelle template for ADC; introduced I²C-per-read pattern |
| `leprecon-pi` / Miura-kun | Lab member | Pandas migration; Phase 4 big-bang split committed from the lab Pi |
| Kurokawa-kun | Earlier lab contributor | Left `kurokawa-dev/PWR.py` (SCPI driver for Kikusui PWR-401L); never integrated |
| Kawabata-kun | Later lab contributor | Final plasma-current PID loop and isolated DAC integration (Apr 2026) |
| `Kshora` | External contributor | Early MFC and MCP4725 work (PRs #1, #18, #19) |
| `codex/*` bot | LLM-authored PRs | PRs #20 and #21 (Aug 2025); untested on hardware at merge time |

> *"I was exploring and learning. My goal with this RasPi unit was to
> learn electronics. And I think I've succeeded."* — Arseniy

## Documentation strata

1. **2022 pdoc3 HTML** — archived at `archive/pdoc3/`. Documents the
   single-monolithic-`worker.py` architecture. Stale but valuable as a
   fossil snapshot.
2. **`settings.yml`** — deliberate in-code data dictionary. The most
   important single piece of documentation in the repository.
3. **`conversions.py`** — LaTeX physics inline in docstrings.
4. **`aklab-howto`** — external hardware documentation hub. Do not
   duplicate here; cross-link.
5. **`Archaeology.md`** — this project's primary historical record
   (2026 reconciled snapshot).

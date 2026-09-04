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

2023-04 ──── Multiple contributors arrive (Kurokawa-kun/`Kshora`,
             leprecon-pi/Miura-kun). Channel names evolve live during runs.

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

## Versions

The major number names an era, not a release schedule (owner decision
2026-09-04, on the fleet's rule to version by user-visible reality rather
than strict SemVer). The numbers before 4 were never stamped on a release;
they are the eras as Arseniy tells them, written here so the number in the
tab bar means something to a student.

| Major | Era | What the rig ran |
|---|---|---|
| 0 | The prototypes, 2020–2022 | The Echelle-derived monolithic worker; one class, every device by enum. |
| 1 | The later updates, 2023 | Channel metadata in `settings.yml`, the ADC buffer redesign, logging to file, gain switching. |
| 2 | Half the transition to separate workers, 2024 | The worker super class split and the pandas migration; MFC and MCP4725 integration; the first plasma-current PID. |
| 3 | The thread fix, 2024–2026 | Signal declarations and `DirectConnection` wiring so the workers stop cleanly; the isolated DAC; the PID controlling in amperes. This is the code the rig ran until 2026-09-04. |
| 4 | The rig on the lab network, from 2026-09-04 | The web view beside the Qt window: health for the ensemble of three, Live, Control behind the Remote switch, Log and Lab. |

Within an era the second number moves for a feature and the third for a
fix, and every copy of the number (`controlunit/_version.py`,
`pyproject.toml`) moves together.

## Contributors

| Handle | Person | Role |
|---|---|---|
| `queezz` / Arseniy | Principal developer | Wrote and rewrote most of the system across all phases |
| `Tatsuemon` / Ito-kun | B4 student | Extended Echelle template for ADC; introduced I²C-per-read pattern |
| `leprecon-pi` / Miura-kun | Lab member | Pandas migration; Phase 4 big-bang split committed from the lab Pi |
| Kurokawa-kun (`Kshora`) | Lab contributor | PRs #1, #18, #19 — early MFC and MCP4725 work; also left `kurokawa-dev/PWR.py` (SCPI driver for Kikusui PWR-401L, never integrated) |
| Kawabata-kun | Later lab contributor | Final plasma-current PID loop and isolated DAC integration (Apr 2026) |
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

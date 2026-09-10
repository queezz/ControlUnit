# ADC timing investigation and optimization

User challenged the 0.5 s gap at 0.1 s sampling and requested a proper investigation and optimization. Read-only rig evidence showed systematic drift and phase-three batch correlation. Profiled the actual row and plotting methods off-device before editing. Implemented deadline cadence, typed list-to-DataFrame batches, numeric history, vectorized timestamps, elapsed yielding ready polling, and constant-memory stage diagnostics. Version 4.13.0; pandas minimum 1.0 for DataFrame.attrs (rig 1.5.3).

Detailed evidence, benchmarks, source links and unresolved lifecycle/hardware limits: docs/diagnostics/2026-09-10-adc-timing-optimization.md. Portable benchmark scripts/benchmark_adc.py refuses real hardware libraries before imports. Existing mobile work remains in this working tree. No commit, push, pull, deployment, restart or output change.

Validation: full pytest and strict documentation gate recorded at final handoff; timing tests cover steady/overrun/retimed/averaged cadence, partial scan abort, buffered tail emission, conversion metadata, wire format and diagnostics. Worker-tail emission is not a proof of disk flush during application exit.

Final gates: 528 passed in 21.27 s; strict MkDocs build passed; git diff --check passed. Portable benchmark rerun confirmed the reductions.

September 11 follow-up: owner clarified that completed validated work should be committed, without waiting for a separate request. Updated AGENTS.md to make that default explicit; reran the commit gates and prepared the complete ADC/mobile/diagnostic changes for a local master commit. Push remains owner-authorized only.

Owner-requested Fleet defect report posted to Misha (code/fleet): 20260910-78656001-51c859, Clarify automatic local commits in cold-start guidance. Local commit default versus explicit push permission, conflicting policy drift, and orientation-only packet scope are the requested fixes.

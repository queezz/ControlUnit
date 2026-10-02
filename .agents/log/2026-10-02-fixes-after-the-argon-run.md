# The fixes after the argon run — 2026-10-02, evening

Queezz, on reading the analysis of the day's run: "Update settings, and
work on the fixes. Also the September runs had preanode grounded, so
don't take those for any meaningful measurements. And that's in the logs,
so you missed a bit." Three things, in that order of doing.

## The correction

The earlier entry of today settled the 7.5 s ripple's cause from the
2026-09-15 files. His journal of 2026-09-09 to 2026-09-11 records the
preanode grounding through the discharge; this session had not opened it
before reaching for September data. The conclusion is withdrawn in the
diagnostic page, the vault note and directions, and `AGENTS.md` now says
which runs count and sends a session to the journal first. The journal
also marks the repair on 2026-09-14 and calls the source fixed on
2026-09-15; his ruling names the September runs as a whole, so that
evening is excluded too until he says otherwise.

## What shipped

| Version | What |
| --- | --- |
| 4.22.2 | `Zero Ratio: 0.4961` for the Hall sensor (settings 1.6). |
| 4.22.3 | The window's history is a bounded store (`controlunit/history.py`); the file is written before anything is drawn; a late delivery skips its redraw; the lag is in the Log, `/api/state` and `/api/health`. |
| 4.23.0 | `CathodeLoop` replaces `simple_pid`: engage presets the integral to the held drive, 1000 mV from cold; the reader is told the manual drive, which the file records. |
| 4.23.1 | The Kikusui output press waits up to 0.6 s for the readback to agree. |
| 4.23.2 | Web: setter fields follow the rig; the PID's command on the card; a missing Kikusui reading held 10 s then greyed; the browser thins old points instead of dropping them; "behind" on the freshness pill. |

Gates before each commit: pytest (686 passing at the end) and
`mkdocs build --strict`. The node behaviour tests are not in the pytest
gate; they were run by hand, 50 passing:
`node --test tests/web_cathode_behavior.cjs tests/web_gas_behavior.cjs
tests/web_kikusui_behavior.cjs tests/web_live_behavior.cjs
tests/web_store_behavior.cjs` from the repository root.

Measured off-rig: a delivery costs 1.5 ms at 1,000 rows of history and at
180,000 (it was 27 ms rising to 1.3 s on the rig); in the running dummy
instance the whole delivery, file and redraw included, took 13.7 ms.

Not pushed, not pulled: the rig runs 4.22.1 on a 10 s run and was only
read. The rig's Python is 3.9 with pandas 1.5.3 and numpy 1.24.2, read
over SSH; the new code uses nothing newer than those, but it has run
only on this PC's 3.14.

## Perimeter Walk (4.23.2)

Scratch `lab start controlunit-dummy --port 48937` under scratch
`LAB_CONFIG`, `LAB_RUNTIME_ROOT` and `LAB_LOG_ROOT`, `LAB_VENV_ROOT` at
the real venvs, `HOME` and `USERPROFILE` in the session's scratch folder,
`QT_QPA_PLATFORM=offscreen`, a `kikusui.yml` with `dummy: true` there.
The listener's command line was read from its owning process
(`python -m controlunit.main --web --host 127.0.0.1 --port 48937`, child
of the tracked PID); 4187 had no listener before, during or after. Live
DOM through the in-app browser.

1. From Live: Log, Lab and the brand each landed at their own top
   (scrollY 0) with the right title.
2. The surface's own links are its anchors; see 3.
3. `#sec-who`, `#sec-plasma`, `#sec-sync`, `#sec-acquisition` and
   `#sec-gauge` each landed below the 56 px bar and on screen at 1280×700.
4. Back from Lab to Log to Live (with its hash), Forward to Log: each
   the expected page.
5. `location.reload()` on `/#sec-plasma`: the card open, the Drive field
   reading the applied 2064 mV, the feedback line right, no console error.
6. and 7. Both rails at 76 px at 0, 25, 50, 75 and 100 % of the scroll
   range, at 1280×1000 and at 1280×700.
8. Used as on the day: a second browser (curl with its own cookies) set
   1800 mV; this page's Drive field followed to 1800; −10 gave 1790; Set
   applied 1790. PID 0.50 A engaged "at 1790 mV (the drive already
   held)" and walked up at 16 mV/s on the dummy's fixed reading; the
   feedback line read "Held · PID 0.50 A · 1871 mV · Read Ip 0.098 A" on
   one line, no overflow at 1280 or at 375 px; Manual and Set took over
   at the loop's 2064 mV. A gas draft survived two polls. Stop all
   outputs zeroed the fields. PID from cold started at 1000 mV. With the
   state feed patched to lose the supply, the Cathode cards and the lamp
   held unchanged at 1.5, 4 and 8 s, were grey with "—" and "LAN lost" at
   11.5 s, and came back on the first good answer. With `data.behind`
   patched to 37.4 the pill read "0.1 s ago · 37.4 s behind" at the same
   height. Operate, Observe and Monitor switched; Escape walked back.
9. Nothing new is explained on the page; the one new word, "behind",
   appears only while it is true.

Not walked: 320 px (the pane would not emulate below 375) and the two
ends of a change of hands, which needs two origins — the operator lock
is per address, so a second browser on this PC is the same holder. That
path is covered by the node test alone.

`lab stop` after each of the two scratch runs: process tree gone, 48937
free, 4187 still without a listener.

## Left

In `directions.md`: the Settings group (the rail rework he asked for
again today), the loop's blindness to the Kikusui's voltage limit, one
owner question on the cold start, and the deployment, which waits on his
"push" and an idle rig.

agent: claude

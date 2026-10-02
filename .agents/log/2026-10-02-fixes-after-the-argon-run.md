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
| 4.24.0 | The Settings group dissolved: Sampling and QMS sync on the status line, Ion gauges a rail card of its own under Operator and access. |

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

## Perimeter Walk (4.24.0, the rail rework)

The same scratch recipe, a third run on 48937, stopped and port-checked
like the first two.

1. Log from Live, Back to Live: the expected pages, the status line there.
2. and 3. `#sec-acquisition` and `#sec-sync` land 72 px down, sixteen
   clear of the 56 px bar (they landed at 57 until the bare spans were
   given their own scroll margin; the card rule subtracts an inset they do
   not have). `#sec-gauge`, `#sec-who` and `#sec-plasma` land on screen.
4. Back and Forward as before.
5. Reload on `/#sec-acquisition`: 0.1 s pressed, the gauges card open.
6. and 7. Both rails at 76 px at five scroll depths, at 1280×1000 and
   1280×700. The right rail's content is 1116 px and scrolls inside the
   rail's own box, as before; the page does not scroll for it.
8. Pressed 1 s, then QMS sync on and off, then 0.1 s. The four sampling
   buttons are one width (52.8 px), so the chosen one's bold face moves
   none. With no sentence, "done: sampling 1 s" and a two-line refusal in
   the status place, the setters' and the first readout's addresses were
   identical (109.5 and 179.8 px); only a three-line sentence, longer than
   any the rig says, moved them. Rail order: Operator and access, Ion
   gauges, Display, This run. Observe hides the two setters and the gauges
   card (header 29 px); Monitor keeps the setters and carries the gauges in
   the drawer. With no run the four sampling buttons and the sync switch
   are disabled and the switch dims once; the gauges and Start stay live.
   At 375 px: pills, then Sampling, then QMS sync, then the sentence, no
   overflow. At 1700 px the whole line is one 29 px row.
9. Nothing is explained on the page that was not before: two names in the
   rail's label voice, "Sampling" and "QMS sync", and the controls.

One reading that looked like a defect and was not: the sync switch's thumb
read as not having moved. The pane does not advance CSS transitions; with
the transition switched off for the reading, the thumb was at 36.5 px.

## Deployed, 22:30 (4.24.0)

Queezz: "yes, do push ... the rig is running at 0.1 hertz, just logging
a vacuum, so it's not important. So we can push and actually test."

- `git push origin master`, `9b17ca7..c67fcd6`.
- The rig read `measuring`, no outputs, cathode and both gas lines at 0,
  the Kikusui unpowered. From the Pi itself, as the roster's session
  identity (`Kuzmin Arseniy queezz`, the one the 2026-09-30 deployment
  used) with the lab's word read from the Pi's own file and never
  printed: take control from his laptop, stop acquisition, health
  `idle, not recording`.
- `kill -TERM` on the program (outputs at zero), process gone,
  `git -C ~/work/aktest pull --ff-only` to `c67fcd6`.
- Before starting it: the two new modules run on the Pi's Python 3.9.2,
  pandas 1.5.3 and numpy 1.24.2 in a throwaway script (bounded history
  thinning, a bumpless first command of 1789 mV from a held 1790).
- Started through `~/Desktop/aktest.sh` in a terminal on display `:0`, as
  the shortcut does. Health: 4.24.0, `idle, not recording`; nothing in
  the stderr file.
- Gauges put back as found (Pd Torr 1e-8, Pu2 Torr 1e-5), acquisition
  started, 75 s left at the default 0.1 s to time the new path on the
  real hardware, then sampling 10 s: the vacuum log goes on in
  `cu_20261002_223317.csv`.

Measured on the rig in that minute: a delivery costs 15.8 ms in all
(file 3.4, history 4.3, redraw 8.1), queue 0.3 ms, no missed slots,
sample interval 0.1000 s. The un-zeroed plasma current reads +0.002 A
(sd 6.7 mA) where it read -0.098 A, `Ip/Vhall` 0.49619 against the
0.4961 now in the settings; the file's header carries the new formula.

Control is left with the session identity from 127.0.0.1; any browser
takes it back with Take over. Six scratch files this session put in the
Pi's `/tmp` (two helper scripts, a check script, a cookie jar, the fence
body, the morning's log excerpt) are removed.

Not exercised on the rig: anything that drives an output. The PID's
takeover, the cold start and the Kikusui press are tested off-rig only,
and the supply was unpowered.

## The cold start, improved (4.25.0, local)

His answer to the question the last commit left: "Since PID could light a
cold plasma, that means we should try and improve it." With no discharge
the loop now walks from 1000 mV at 25 mV/s to a 1900 mV ceiling and holds
there; lit, it regulates from the drive it reached; an arc's dropout is
not unlit; a plasma that goes out brings the drive down to the ceiling.
Nine new tests, 695 passing. Committed and not pushed: the push he gave
was for the fixes, and this changes how the cathode is driven.

On the 7.80 V: it is the supply's own voltage setting (CV), not a limit of
the PWR401L, and it has been changed at the panel since 2026-09-30, when a
query read 5 V. Recorded in directions with what would let the loop see it.

## Left

In `directions.md`: the push of 4.25.0, the loop's blindness to the
Kikusui's voltage setting, and the unbuilt rest of the 4.19 design.

agent: claude

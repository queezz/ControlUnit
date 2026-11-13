# By gauge / By vessel outside the gate — 2026-11-13, 4.29.2

Queezz, with a screenshot of the Live tab while a student held control of
the rig: "My student is working on the rig now, so don't touch that. But I
should be able to adjust what and how I see without taking over, now
should I?" The rig was not read or touched by this slice.

## What was wrong

The gate in `control.js` (`paintGate`) disables every button, input and
select inside `.sets`. The Pressure plots switch (`.pressure-grouping`,
By gauge / By vessel) carried `sets` since 4.9.0, so a browser without
control could not regroup its own plots. Open in `directions.md` since a
browser check on 2026-09-10; that item is removed.

Reproduced on a scratch instance: a second loopback address
(`curl --interface 127.0.0.2`) took control and started acquisition, the
in-app browser on 127.0.0.1 was a viewer (control is held by origin
address, so the same address would have counted as the holder). As a
viewer the page disabled 55 controls; every one was a setter except the
two grouping buttons.

Left gated on purpose: Zero Ip / Zero Bu / Zero Bd. They are rig-wide, and
`zero_ip` is subtracted from the current the PID regulates
(`devices/adc.py`), so a viewer zeroing Ip would move a running loop.

## What shipped

- `templates/_live_readings.html`: `sets` removed from the grouping block,
  with a comment saying why.
- `tests/test_web_page.py`: a parser walk over Live and Control asserting
  no view-only control (`data-pressure-group`, `data-scale-ig`,
  `data-scale-bar`, `data-scale-plasma`, `data-display`, `data-drawer`,
  `data-channel`) stands inside a `.sets` block, with a synthetic case
  proving the walk detects one.
- `docs/architecture/web-ui.md`, `.agents/CHANGELOG.md`, version 4.29.2.

Gates: pytest 720 passed; `mkdocs build --strict` clean; `node --test` 65
passed.

## Perimeter Walk

Fleet's RULES.md §10, `WEBUI.md` and `WEBUI-COOKBOOK.md` read in full
first. Scratch `lab start controlunit-dummy --port 48937` under scratch
`LAB_CONFIG`/`LAB_RUNTIME_ROOT`/`LAB_LOG_ROOT`, `USERPROFILE`/`HOME`
redirected to a scratch home through `[env.controlunit-dummy]`,
`QT_QPA_PLATFORM=offscreen`, `BROWSER` pointed at a no-op so lab opened
nothing; listener read by `OwningProcess`; 4187 had no listener
throughout; `lab stop` confirmed by a freed port; the real `~/work/cudata`
untouched. In-app browser pane, as a viewer:

1.–2. Tabs ControlUnit, Log, Lab pressed; the one in-page link (#sec-who).
3. #sec-who lands at 132 px, below the 56 px tab bar.
4. Back, Back, Forward land Log, Live, Log.
5. Reload on `?mode=monitor`: By vessel, pressed there, survives.
6.–7. Both rails at 76 px top, same left and width, at 0/25/50/75/100 %
   scroll, at 1280×1000 and 1280×700.
8. As a viewer: By vessel regroups to "Upstream · Pu + Pu2 + Bu" and
   "Downstream · Pd + Bd" and back, in Operate, in Monitor and at 375×812
   (no horizontal overflow); no POST leaves the page; control stays with
   the other address; the choice is kept in this browser's storage.
9. Nothing new is said on the page; the reason lives in the template
   comment.
10. A fresh load: no failed request. (Connection-refused lines earlier in
    the console were the page polling across the scratch restart.)

Not walked: the rig itself, by the owner's word.

agent: claude

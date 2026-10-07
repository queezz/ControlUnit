# The dev items from the diagnostic run — 2026-10-07, 4.29.0

Queezz, after his argon run of the evening: "I did a diagnostic run,
see pihti log, and get the dev items from my log, pick up your part
and develop, and post to pihti-diagram the other item." His journal of
[2026-10-07] gave five for ControlUnit and one for the Diagram.

Fourth slice of the day, the same shape: design here, implementation
on an Opus subagent, review, one fix and the Perimeter Walk here. The
subagent ran one `git stash`/`pop` to compare warnings against HEAD;
the pop failed on the index and it dropped the stash after proving the
tree held everything. Checked here: the uncommitted directions edits
were intact and no stash remained. Told not to use git beyond reading;
the next packet will say so in words.

## The Diagram's item

Letter `20261007-677c6c98-ca9550` to `code/pihti-vacuum-diagram`: fix the
"unroughed gas enters TMP" warning, in his words ("We inject gas via
precision needle valves or MFCs to make plasma, which is the designed
mode of operation"), the same point the 2026-10-02 letter relayed, now
a direct ask; and that ControlUnit will carry each gauge's off mark in
its state for the Diagram to read.

## What shipped here

1. "The Monitor mode needs signal cards selector as all others do." A
   press hides a readout card in Monitor too; one hidden set for the
   three modes.
2. "mode buttons are same as gauges and all else in monitor, bad." The
   mode switch wears the house's segmented track, three segments and a
   sliding thumb (`.seg-toggle--3`), so it never reads as three more
   choice buttons. Its home, its docking and its phone Menu form are
   unchanged.
3. "The current card keeps changing width." The Cathode card's
   feedback line wraps instead of widening the card past the 21rem
   rail, the rail's cards have `min-width: 0`, and Read Ip is written
   at a fixed width (`0.098 A`, `-0.005 A`).
4. "I need a toggle in ControlUnit for IGs to be off… it should be
   known that the signal on that channel is noise." Off is a third mode
   beside Torr and Pa, on the rig's dock and the web Ion gauges card.
   The row's mode column carries 2, the raw volts are kept and the
   converted value is NaN; the file's header says so per gauge; the
   log says "Pd declared off"; the card reads "—" with the tag "off",
   the folded row "—", the curve is not drawn and its pill says "off";
   `/api/state` carries the mode as before. Found and fixed on the way:
   a NaN sample reached the browser as literal `NaN` in the JSON, which
   no browser parses, so the page would have frozen the first time a
   gauge was Off — and would today for a Hall reading with no valid
   supply. Non-finite samples are now `null` in the API.
5. "Kikusui output button in WebUI not working." The rig log says why:
   the supply's LAN was lost from 17:08:59 and came back only when he
   power-cycled the supply at 18:02; both presses at 17:31 timed out.
   The press now says so: "the supply's LAN did not answer (lost since
   17:08). Press OUTPUT on the supply, or power-cycle it to bring its
   LAN back; the DAC drive is unchanged", in the log and, a poll later,
   on the page. The identity check and the allowlist are untouched.

Not done on the Qt side: the rig's own plot draws an Off gauge's NaN
rows as gaps rather than hiding the curve, and a mode change made on
the rig's own combo still writes no Log line (only the web command
does), because the same updater runs at startup. Both said in the
report, both small, neither asked for.

Gates: pytest 711 passed; `mkdocs build --strict`; `node --test` 65
passed. Version 4.29.0, changelog, `docs/architecture/web-ui.md`,
`docs/hardware/channel-map.md`, `settings.yml`'s comment.

## Perimeter Walk

Scratch `lab start controlunit-dummy --port 48937` under scratch roots
and a scratch home, listener read by `OwningProcess`, 4187 without a
listener throughout, `lab stop` at the end with the port confirmed
free. Live DOM through the in-app browser pane, 1280×1000 and 375×812.

1.–4. Tabs, anchors, Back and Forward were walked three times today on
   this page; this slice changes no link, anchor or address.
5. The hidden set, the display choices and the mode survive a reload
   (walked for 4.27.0 and 4.28.0 on the same storage).
6.–7. Rails unchanged in offset and width; the left rail's cards now
   cannot grow past it (card 321 px inside a 336 px rail with a manual
   drive held and the feedback line wrapped).
8. As an operator with a run going: the switch's thumb is 80 px, one
   segment, and moves 0, 80 and 160 px for Operate, Observe and
   Monitor. In Monitor a press hid Bd and its pill appeared; cards keep
   tab index 0. Pd pressed Off: "done: Pd declared off", the card "—"
   with "off", the pill "off", the folded row "—", the gauges' summary
   "Pd Off 1e-3", `/api/state` without a NaN; Torr pressed: the number
   and the curve back. On the phone the switch sits in the Menu as a
   full-width three-segment track, the readouts under the strip. At
   1280 in Monitor the strip is one row with outputs idle and two with
   "outputs live · cathode drive" on the pills (the pills alone are 332
   px then); at his 2000 px it is one row either way.
9. Nothing explained twice: "off" on a card and on its pill is state.
10. Console: nothing.

Not walked: the output press failure's sentence (the dummy supply
cannot lose its LAN; covered by `tests/test_kikusui.py` and the Qt
test), and 320 px.

## Left

`directions.md`: the "declared off" item is trimmed to what remains
(the plasma supplies, the heuristics); the Bu jump on IG power-off and
the Pirani reading stand as reported. The rig runs 4.28.0; 4.29.0 is
committed and not pushed. Pushing and deploying it is his to say.

agent: claude

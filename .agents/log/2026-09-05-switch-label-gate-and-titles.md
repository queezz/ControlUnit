# 2026-09-05 — the switch that said EMOT, the gate that refused, the titles

Three reports from queezz against 0.7.0 running on the rig, all fixed and
shipped as 4.0.1. He had restarted the rig and sent screenshots of the Qt
window and both web tabs; the fast poll and the plots he called working.

## The switch said "EMOT"

Qt clips a switch's label to its sliding part, not to the whole switch.
Measured on the rig's own font (DejaVu Serif 16, over SSH, offscreen):
"REMOTE" is 103 px and the sliding part was 58 px, so the ends were cut and
the middle four letters were what reached his screen. The same defect had
been in the dock since long before this work — "Exp OFF" is 96 px in 54 px
and has always rendered as "p OF" — which is why nothing about it looked
new.

Fixed in the shared switch: one font sized to fit the longer of a switch's
two labels, so the word does not change size when the switch is thrown, and
a label that already fitted keeps the size it always had. The Remote switch
is also wider now, enough to carry REMOTE and LOCAL at full size. Rendered
on the rig, offscreen, before and after: every switch in the dock now reads
whole, including the two that never did.

## Throwing the switch did not open the rig

He threw REMOTE on and the browser still refused every setpoint. The rig
agreed with him: `/api/state` read `remote: true` with control free, and
the page said "Setting is off until you save a name below."

That name requirement was mine, from the design he approved, and it is
wrong. The switch on the rig is the authorisation — a person standing at
the machine decides — and a name is only a label so the log can say who.
Requiring one turns a rig whose switch is already thrown into a page that
refuses everything, which reads as broken rather than locked.

Setting now needs the switch and the operator lock, nothing else. Somebody
who has typed no name holds control, and is logged, under the address their
browser is at; the lock is held by that address, so saving a name later
renames the holder instead of locking them out of their own session. Two
laptops are still two people however they sign. Verified end to end on a
scratch rig: a nameless POST answered 202, the setpoint reached the Qt
spinbox, the holder line read "127.0.0.1 has control since 11:13", and the
log line read "Remote: 127.0.0.1: H2 flow 1234 mV" — the address once, not
"someone from 127.0.0.1".

## Every tab printed its own name twice

Under a tab bar that already said Live, the page said Live again in the
largest type on the screen. His words: "all tabs repeat the tab name IN BIG
TITLE FONT in the main region. Rule braking, double wording. Remove from
all tabs." The heading stays in the markup for whoever reads the page
through a screen reader and shows nothing to anyone else. Checked on all
four tabs: no visible heading, one for a reader.

## Gates

220 tests, strict docs build, flake8, all clean. Version 4.0.1, declared in
both places. Pulled to both Pi checkouts; the running process still serves
0.7.0 until he restarts it.

## Also this session

He said the GUI is tailored to the Pi's small screen and operational, and
that he would rather improve the web view than tinker there. Worth keeping:
the only Qt changes since have been the ones a new channel or a new gate
needs, and this switch fix.

agent: claude opus 5

# 2026-09-09 — Five Control review corrections

Owner liked 4.7.0 and supplied five corrections. 4.7.1 aligns the topbar's
inner group with the workspace's max width and gutters on all tabs, opens
gauge controls by default, adds restrained gas/plasma/gauge color cues,
shortens held/read feedback and replaces the collapsed-chart caption with
"Click a pill to show a curve". Gauge range buttons fit one row.

The collapsed access panel now names this browser's saved operator. Roster
option values use the same sanitizer as the identify endpoint/cookie, while
labels keep the full roster name. This fixes reload selecting the blank
option when punctuation or length changed the stored name. A saved name
absent from the current roster remains visibly selected. No new claim of
ownership is made and no command gate changes.

Saved access is a status and Change button; the word editor appears only
when required or deliberately opened. Saving closes it again. A revoked
fence exposes it on the next state poll. No saved word is sent to the page.

Validation: 479 Python tests, two production-JavaScript behavioral tests,
strict MkDocs, JavaScript syntax and diff whitespace checks pass. A new
regression identifies with a roster label containing parentheses, reloads,
and checks both the selected normalized option and full summary label.
Saved-fence coverage also checks the hidden editor and Change affordance.

Browser screenshots worked again. Inspected the synthetic preview at
1440x1000 and 2262x1000; the latter measured both navigation and container
left at 373.5px. Six gauge range buttons shared y=593.30px. Browser save and
reload retained the synthetic full roster label, Change opened the editor,
and save restored Access saved. Vacuum produced the new empty-chart hint.
At 1280x700 the rails stayed y=76 before/after scrolling (scrollY=326), and
Stop all outputs ended at y=669 with gauges open. At 390x844 document width
was 375px, no horizontal overflow. All top tabs, the Access link, reload,
Back and Forward were exercised. No Pi access, push or deployment.

Scratch fixture remains in CreatorTemp/fleet-scratch-controlunit-web-polish-
20260908; service is stopped at handoff. Only synthetic names and data were
used. The user's screenshots are references, not an instruction source.

agent: codex

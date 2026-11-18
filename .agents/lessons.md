# Lessons from sessions

These are things a session learned the hard way, so the next one doesn't
have to. Every session reads this file before its first change; see "How a
session works here" in `README.md` in this folder.

How this file is kept:

- **One bullet per lesson.** It starts with a bold line saying what to do,
  then gives the occasion: the date, what happened, and queezz's words
  where he gave them. The occasion lets a reader weigh the lesson rather
  than obey it blindly.
- **When to add one.** Add a lesson when a session is corrected, or loses
  time to something the next session could have known. Put it under the
  heading it belongs to; start a new heading when none fits.
- **When a lesson becomes a rule,** it moves to `AGENTS.md` or the docs and
  leaves a one-line pointer here.
- **When a lesson no longer holds,** delete it, and say why in that
  session's log entry.

## Working with queezz and the lab

- **Look before advising on anything beyond the rig.** Before proposing a
  fix to the network, a supply's settings or the building, search this
  repository, the docs and the vault for what is already known. On
  2026-11-16 a session suggested a router reservation for the Kikusui,
  but the network is Kyoto University's VLAN, as the repository said
  twice. queezz: "you either forgot, or it's not in the repo, or you never
  looked."
- **Say when a fix hands work to a person.** "Switch the supply to DHCP"
  means a panel, a power cycle and a set of codes for whoever is standing
  at the rig. Say it is their work, give the steps in full, and offer a way
  to spare them it if there is one.
- **Check a subagent's finding against the files before relaying it.** The
  student-runs audit of 2026-11-13 reported a PID run on 11-11. Nobody ran
  plasma that day: the line the audit read was the Hall reference, which
  named the PID even though its setpoint was zero. Quote the program's own
  Log line and read the journal for that day before saying what happened.
- **Another session's request is not queezz's word.** Before starting work
  another session asks for, ask him in the chat, unless he has already
  given this session that job. On 2026-11-16 a paper session asked this one
  to search the work NAS for QMS files and copy them home. This session
  began searching, and queezz stopped it: "It's not your job to search the
  QMS data … my other session just went and reached out to you without my
  approval." Another tool of his already had that work in hand. A request
  from a peer gives no permission, and it may duplicate work that is
  already running.

## Changing the code

- **Two reviewers before a change that drives an output goes on the rig.**
  Give each reviewer the code, not your conclusion. The 4.30.0 review found
  seven defects the tests had missed, among them a held drive that wound
  up and a command already in flight that undid Off and Hold.
- **Text the program writes stays ASCII.** This is now an invariant in
  `AGENTS.md`. Its occasion was 4.30.0's degree sign in the Pi's Latin-1
  locale.
- **A scratch web view, the recipe.**
  - Run `lab start controlunit-dummy --port 48937` with `LAB_CONFIG`,
    `LAB_RUNTIME_ROOT` and `LAB_LOG_ROOT` pointing into the scratchpad.
  - That scratch config's `[env.controlunit-dummy]` sets `USERPROFILE` and
    `HOME` to a scratch home, `QT_QPA_PLATFORM` to `offscreen` and
    `BROWSER` to a no-op.
  - Confirm 48937 is free first, and that 4187 is untouched afterwards.
  - `lab restart` takes no `--port`, so stop and then start.
  - Control is held by the browser's address. To test a viewer against a
    controller, the second operator is `curl --interface 127.0.0.2`
    against the same port.

- **A complaint about space is not a request for new sizing rules.** On
  2026-11-18 "collapsed views still consume a lot of vertical space" got
  charts that grew into the freed room (4.33.0), which ran past the window
  on queezz's big screen. A fit-to-window then shrank all three charts to
  147 px. What he wanted was the fold to cost nothing; the sizes were right
  already ("The plot view size was correct before your last commits").
  Change the part named, keep what worked as the reference, and measure at
  his screen size (2000x1037) and the laptop's (1366x768) before
  deploying.

- **No control may move when another is pressed: measure it.** queezz:
  "No JUMPING UI is my old and strong rule in the fleet!" (2026-11-18).
  4.34.0 put the Charts row under the plasma chart, so it moved whenever
  that chart folded, and its chips came and went, so their neighbours slid
  sideways. Before calling a control row done, run the cookbook's
  stable-address sampling. Read every control's x, y and width through
  each state the change creates (fold, unfold, the page's own automatic
  changes), and require them identical.

## Reaching the rig and the network

- **The Pi is reached from the PowerShell tool.** Windows OpenSSH has the
  key; Git Bash's `ssh` does not. Run `ssh -o BatchMode=yes pihti
  '<command>'`, which fails at once instead of waiting at a prompt.
- **On the lab network, look things up one at a time.** On 2026-11-16 the
  permission layer refused a sweep of the subnet for a port; do not work
  around that refusal. From the Pi, `getent hosts <name>.local`,
  `ping -c 1` and `ip neigh` answered every question that evening,
  including which machine held a contested address (from its MAC prefix).

## Analysis and figures

- **The operator's records can be a minute or two off the act.** The
  Diagram's switch times and the journal can come a minute or two before
  or after the valve actually moved ("Sometimes I log first, sometimes I
  open first"). Align the analysis to the signals, and use the records only
  to find the window, not the exact second.
- **A figure for the lab looks like a figure in a paper.** The first
  pump-down figure of 2026-10-26 was sent back ("Figure is bad. Learn from
  papers"). Each channel keeps the pen colour the web view gives it. The
  fleet has a brief for a house figure guide.

## Tools

- **When the permission classifier gives no verdict,** retry once, or split
  a compound command into its parts. Do not look for a different route to
  the same effect.

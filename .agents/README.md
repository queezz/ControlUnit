# The agent surface of ControlUnit

This folder is where a session working in this repository reads what is
open and records what it did. Policy lives elsewhere: `AGENTS.md` at the
root for this repository's environment, commands and invariants; the fleet
repository's `RULES.md`, `WEBUI.md` and `WEBUI-COOKBOOK.md` for what holds
across every project. Nothing here overrides either.

## What is here

- `directions.md` — open work only: decisions waiting on queezz, defects
  reported and not yet fixed, and work that is ready to build. An item
  leaves this file when it ships or when its answer is recorded; a durable
  rule graduates out to `AGENTS.md` or the docs rather than living here.
- `log/` — one dated entry per session that changed something, named
  `YYYY-MM-DD-<what-it-was>.md`. A log records what a session did, what it
  measured and what it left; it is evidence, never policy.

## How a session works here

1. Read `AGENTS.md`, this file, and the newest entry in `log/`, in that
   order, then the fleet brief. A task that touches the web view also reads
   the fleet's web UI law and cookbook completely before the first change.
2. Work off-rig against the dummy hardware in the shared `hardware-dev`
   environment. The rig is the Raspberry Pi and is never used as a test bed:
   look at it over SSH, read-only, and leave a running acquisition alone.
3. Verify a web change in a real browser against a scratch instance on a
   loopback address and a confirmed-free port, with `HOME` redirected so no
   data file or log lands in the owner's own folders. Run the cookbook's
   Perimeter Walk, all ten steps, before calling a UI change done.
4. Run the gates in `AGENTS.md`, stage by path, commit with a sentence-case
   imperative title and the bare trailer `agent: <name>`. Push when
   queezz says so in the chat; tags are queezz's.
5. Write the log entry, trim `directions.md` to what is still open, and
   send anything meant for another project as a letter through fleet post.

## Deploying to the rig

The rig's checkout, `~/work/aktest` on the Pi, pulls from `master`, and the
rig is restarted from its desktop shortcut, which calls
`scripts/run_controlunit.sh`. The restart is queezz's, always. The pull is a
session's to do (owner decision 2026-09-07, amending the earlier rule that
kept both for him) once master is on the remote and the rig is neither
acquiring nor driving an output — read `/api/health` first and refuse while
it says `outputs live:`, the check `AGENTS.md` writes out in full: check
over SSH that no `controlunit.main` process is running,
`git -C ~/work/aktest pull --ff-only`, and confirm the commit matches
master. Pushing master is done when queezz says so, in this chat, and not
otherwise; a session never pulls a checkout that is ahead of the remote.
The names roster reaches the Pi by `scripts/push_roster.ps1`, which is
also a session's to run on his word.

## Lessons from sessions

What a session learned the hard way and the next one should not have to.
Each lesson names its occasion so it can be weighed, and leaves this list
for `AGENTS.md` or the docs once it hardens into a rule.

- **Look before advising on anything beyond the rig.** Before proposing a
  fix to the network, a supply's settings or the building, search this
  repository, the docs and the vault for what is already known. On
  2026-11-16 a session suggested a router reservation for the Kikusui;
  the network is Kyoto University's VLAN, as the repository said twice.
  queezz: "you either forgot, or it's not in the repo, or you never
  looked."
- **Say when a fix hands work to a person.** "Switch the supply to DHCP"
  is a panel, a power cycle and a set of codes for whoever is standing at
  the rig. Name it as their work, give the steps in full, and offer what
  would spare them it, if anything does.
- **Check a subagent's finding against the files before relaying it.**
  The student-runs audit of 2026-11-13 reported a PID run on 11-11; nobody
  ran plasma that day, and the line it read was the Hall reference, which
  named the PID with its setpoint at zero. Quote the program's own Log
  line, read the journal for that day, and only then say what happened.
- **Two reviewers before a change that drives an output goes on the rig.**
  Give each the code, not the conclusion. The 4.30.0 review found seven
  defects the tests had missed, among them a held drive that wound up and
  a command already in flight that undid Off and Hold.
- **Text the program writes stays ASCII.** The Pi runs in a Latin-1 locale
  (`en_AU`); 4.30.0's degree sign reached the Log as byte 0xB0, which no
  UTF-8 reader accepts. `AGENTS.md` carries this as an invariant.
- **The Pi is reached from the PowerShell tool.** Windows OpenSSH has the
  key; Git Bash's `ssh` does not. `ssh -o BatchMode=yes pihti '<command>'`
  then fails fast instead of waiting at a prompt.
- **On the lab network, look things up one at a time.** A sweep of the
  subnet for a port was refused by the permission layer on 2026-11-16 and
  is not to be worked around. From the Pi, `getent hosts <name>.local`,
  `ping -c 1` and `ip neigh` answered every question that evening,
  including which machine held a contested address (by its MAC prefix).
- **A scratch web view, the recipe.** `lab start controlunit-dummy --port
  48937` with `LAB_CONFIG`, `LAB_RUNTIME_ROOT` and `LAB_LOG_ROOT` pointing
  into the scratchpad; that scratch config's `[env.controlunit-dummy]`
  sets `USERPROFILE` and `HOME` to a scratch home, `QT_QPA_PLATFORM` to
  `offscreen` and `BROWSER` to a no-op. Confirm 48937 is free first and
  that 4187 is untouched after. `lab restart` takes no `--port`: stop,
  then start. Control is held by the browser's address, so a second
  operator for a viewer-versus-controller test is `curl --interface
  127.0.0.2` against the same port.
- **The operator's records are a minute apart from the act.** The
  Diagram's switch times and the journal lead or trail the valve by a
  minute or two ("Sometimes I log first, sometimes I open first"). Align
  analysis to the signals; use the records to find the window, not the
  second.
- **A figure for the lab looks like a figure in a paper.** The first
  pump-down figure of 2026-10-26 was turned back ("Figure is bad. Learn
  from papers"). Channels keep the pen colours the web view gives them;
  the fleet has a brief for a house figure guide.
- **When the permission classifier gives no verdict,** retry once, or
  split a compound command into its parts; do not reach for a different
  route to the same effect.

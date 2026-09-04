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
   imperative title and the bare trailer `agent: <name>`. Pushing is not
   gated here; tags are queezz's.
5. Write the log entry, trim `directions.md` to what is still open, and
   send anything meant for another project as a letter through fleet post.

## Deploying to the rig

Nothing deploys itself. The Pi's checkouts pull from `master` and the rig
is restarted from its desktop shortcut, which calls
`scripts/run_controlunit.sh`. Both are queezz's to do, on a rig that is not
acquiring, and a handoff names the exact commands rather than running them.

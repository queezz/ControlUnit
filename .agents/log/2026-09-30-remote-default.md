# Remote enabled at startup — 2026-09-30

Queezz asked for Remote on by default, then instructed the session to set
upstream Pu2 to 1e-6 and downstream Pd to 1e-8 before starting acquisition.
This changes the prior local-opt-in startup default; the physical Local
switch still revokes browser control. Identity, lab-word and all other
setter gates are unchanged. The default does not start acquisition.

4.22.1 sets the Control dock switch before MainApp publishes its startup
state. The integration test checks both startup state and switching back
to Local. Full tests and strict MkDocs are the pre-commit gates.

Deployment follows the authorization already given in this chat: push,
check zero outputs and idle state, stop the known rig process, pull, restart
through its desktop launcher, verify Remote true, submit each gauge setting
through the normal API with machine-local identity/fence, verify both
settings, then start acquisition. Do not start before both gauge commands
have applied. The lab note records the resulting runtime evidence.

agent: codex
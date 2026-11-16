# The Kikusui's address: a clash at .10, moved to DHCP — 2026-11-16

Queezz, during Kawabata's hydrogen test after the 4.30.1 deployment, with a
screenshot of the Cathode card reading "LAN lost" while the drive was
applied: "the PSU seems to be off. Why then it reads 2V applied??", then
"Yep, it's on... But no data."

## Diagnosis (read-only from the Pi)

- The run's Log: the PID engaged at 1900 mV on no discharge, then at
  2200 mV with Ip 0.188 A, and held 1.47–1.52 A at about 2395 mV; the
  journal has 20.2 A on the supply's panel. The supply was driving; only
  its link was silent, from 17:00:39, ten seconds after Start.
- `kikusui.yml` named `10.249.254.10`. The neighbour table had `.10` at MAC
  `14:18:c3:e9:2f:46` (Intel, a PC), not answering ping. The rig's stderr
  had a browser at `.10` on 2026-10-05 (TLS "Bad request version").
- The journal of 2026-09-14, 19:18–19:21, and its screenshots of the
  supply's own page: queezz set `10.249.254.10`, mask `255.255.255.192`,
  gateway `0.0.0.0` (so by hand, CF61 = `001`), MAC `00:0f:ce:04:68:81`,
  name `PWR401L-00874.local`.

Two machines on one address: the cause of every LAN flap since October.

Mistakes here, corrected in the chat: the first advice was a router
reservation (queezz: "router, why do you suggest that? Because you either
forgot, or it's not in the repo, or you never looked. Network is KyoDai
vlan, no control here" — the repo said so twice), and "switch the PSU to"
handed the panel's knob work back without saying so. A sweep of the subnet
for port 5025 was refused by the permission layer and not worked around.

## The fix

queezz at the rig after the run: power cycle, CF61 = `110` (DHCP), CF60
APPL; "Lan is green now. Hunt the psu". `getent hosts
PWR401L-00874.local` on the Pi: `10.249.254.28`, where the neighbour table
showed the supply's MAC and it answered ping. The Pi's
`~/.controlunit/kikusui.yml` set to that address, the old file kept as
`kikusui.yml.bak-20261116`. Stop and Start on the rig's screen ("That
worked"): connected 17:37:17, 2672 polls answered, the first reading of
the supply's settings, **17 V, 18 A**; output off throughout; questionable
word 4 at 17:59:30 and LOST 16 s later, at what looks like the supply
being switched off.

## Written down

- `docs/hardware/kikusui-lan.md`: the setup step no longer recommends a
  hand-picked address; a new section "Its address" (identity, history,
  signs, the steps to move it, where it is now, a link of its own as the
  fallback).
- AGENTS.md: the supply's address is a DHCP lease, and what to do when the
  link loses it.
- directions: the address item removed (its "done when" met); the 7.80 V
  entry gains the 17 V reading.
- Vault: "Kikusui LAN lost to an address clash 2026-11-16" and its
  Troubles line.

Open: finding the supply by name at each connection would make a moved
lease automatic (the link takes only numeric addresses so that a lookup
can never stall a stop).

agent: claude

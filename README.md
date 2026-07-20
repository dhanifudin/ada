# ada — WiFi presence detection agent

Local Python agent that scans the campus WiFi network for registered device
MAC addresses and reports presence to the Supabase backend used by the
`rdosen4` web platform (sibling directory). This directory has no direct
dependency on `rdosen4` — the only shared piece of config is the Supabase
project URL/keys.

`rdosen4/supabase/schema.sql` must be applied (and at least one user +
device registered) before this agent can resolve a MAC to a person.

## How it works

Every `SCAN_INTERVAL` seconds the agent:
1. Asks a **detector** for the set of MAC addresses currently visible on the network.
2. Feeds them through a `PresenceTracker` that keeps a MAC "active" until it
   hasn't been seen for `PRESENCE_TIMEOUT` seconds (smooths brief scan misses).
3. Calls the Supabase `report_presence` RPC with the active MAC list, using
   the **service_role key** (server-side only — never expose this key).

The RPC resolves MACs → users via the `devices` allowlist, flips their
`presence` row to `present`, and separately flips previously-present users
to `absent` once they exceed the timeout — so the board self-heals even if
the agent restarts.

## Detectors

Set `DETECTOR` in `.env`:

| Value          | Privilege needed        | Notes |
|----------------|--------------------------|-------|
| `neigh_table`  | **None** (default)       | Reads `ip neigh show` (the OS ARP/neighbor cache). Optionally runs a plain ICMP ping sweep of `SUBNET_CIDR` first (ordinary `ping`, no raw sockets) to populate more entries. Only sees devices the host has exchanged traffic with. |
| `arp_scan`     | `cap_net_raw` or root    | Uses the `arp-scan` tool for an active, more complete scan. Grant the capability once instead of running the agent as root: `sudo setcap cap_net_raw+ep $(which arp-scan)`. If the agent hits a permission error at startup or mid-run, it automatically falls back to `neigh_table` and logs a warning. |
| `controller`   | API credentials          | Not implemented yet — a stub for a future Unifi/Mikrotik/OpenWRT controller-API integration, which would give a complete client list without relying on ARP visibility at all. |

If you're not sure what's available on the target network, start with
`neigh_table` — it needs no special privileges and works out of the box.

## Setup

```bash
cd ada
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: SUPABASE_URL, SUPABASE_SERVICE_KEY (service_role, from Supabase
# project settings -> API), SUBNET_CIDR for your network, etc.
python -m agent.main
```

You should see log lines like:
```
ada agent starting: detector=neigh_table schema=dosen4 interval=30s timeout=600s
scan: 4 detected, 4 active
```

The agent talks to a dedicated **`dosen4`** Postgres schema (not `public`)
— see `../rdosen4/supabase/schema.sql`. That schema must also be added to
Supabase Dashboard → Project Settings → API → "Exposed schemas", or the
`report_presence` RPC call will 404. `SUPABASE_SCHEMA` in `.env` defaults
to `dosen4` and normally doesn't need changing.

### Running as a service

Copy `systemd/ada-agent.service` to `/etc/systemd/system/`, adjust
`WorkingDirectory`/`ExecStart` to where you deployed the agent, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ada-agent
```

## MAC address registration caveat (important)

Modern iOS/Android devices use a **randomized "private" MAC address per
SSID** by default. That randomized MAC is stable for a given network, so
the allowlist approach still works — but each person must register the
MAC their device actually presents **on the campus SSID specifically**,
not the one printed on a settings screen for a different network. Two ways
to get the right MAC:

- Have the user join the campus WiFi, then check their device's WiFi
  settings for "this network's" MAC/private address.
- Or have them disable "Private Address"/"Random MAC" for that one SSID,
  so it uses the hardware MAC consistently.

Devices are registered in Supabase (`devices` table) — see
`../rdosen4/supabase/seed.sql` for an example, or use Supabase Studio.

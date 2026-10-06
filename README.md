# Wiser firmware tools

Tools and notes for enumerating and downloading Schneider Electric Wiser Zigbee
firmware. The main method recreates the Wiser Home 6.6.2 cloud flow and asks a
registered Wiser hub for its software matrix. Firmware comparison and application
inspection helpers are included for completeness.

No account credentials, access tokens, captured account data, APKs, or firmware
binaries are committed here.

## Quick start

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export WISER_APP_AUTHORIZATION='Basic ...'
python scripts/fetch_wiser_matrix.py
python scripts/download_wiser_firmware.py wiser-matrix.json
python scripts/check_wiser_updates.py
```

`WISER_APP_AUTHORIZATION` must contain the application authorization value from
Wiser Home's production API configuration. It is deliberately not committed.
The fetcher prompts for the Wiser Home email and password, writes private raw
responses under `private/`, and writes a normalized `wiser-matrix.json` in the
current directory. Passwords and bearer tokens are not written to disk.

Requirements for the Wiser method:

- a functioning Wiser Home account;
- at least one hub registered to that account;
- the hub online and reachable through Wiser's cloud relay.

The matrix is hub-wide, so the individual Zigbee products do not need to be
paired. The registered hub is needed because the matrix is obtained from the
hub's `/v2` state via the cloud relay, not from a public catalogue endpoint.

See [docs/wiser.md](docs/wiser.md) for the protocol and file-name format and
[docs/analysis.md](docs/analysis.md) for inspecting firmware.

## Scripts

- `fetch_wiser_matrix.py` — authenticate, locate the account hub, relay a
  request to `/v2`, and extract `rus.swMatrix`.
- `extract_wiser_matrix.py` — extract/normalize a matrix from a previously
  captured relay response.
- `download_wiser_firmware.py` — download every component in a normalized or
  raw Wiser matrix and verify sizes/hashes when available.
- `check_wiser_updates.py` — compare the live matrix with `state/last-check.json`,
  report additions/removals/changes, and advance the baseline.
- `compare_puck_firmware.py` — normalized ARM Thumb function comparison.
- `dump_il.py` — small .NET IL dumper used to inspect old Xamarin assemblies.

## Security

Treat files under `private/` as sensitive. They can contain account, site, hub,
and device identifiers. The Wiser application's HTTP Basic client credential is
required to emulate the app, but it is intentionally supplied at runtime rather
than committed.

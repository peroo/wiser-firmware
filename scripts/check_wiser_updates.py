#!/usr/bin/env python3
"""Report Wiser firmware changes since the previous check."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from extract_wiser_matrix import find_matrix
from fetch_wiser_matrix import fetch_matrix


def snapshot(matrix: dict) -> dict:
    components = {}
    for release in matrix.get("systemRelease", []):
        for device in release.get("deviceType", []):
            device_id = str(device.get("deviceTypeId", "unknown"))
            for component in device.get("swComponent", []):
                kind = str(component.get("swComponentType", "unknown"))
                key = f"{device_id}/{kind}"
                components[key] = {
                    "version": component.get("swComponentVersion"),
                    "file": component.get("repositoryFile"),
                    "path": component.get("repositoryPath"),
                    "systemVersion": release.get("systemVersion"),
                }
    return {
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": {
            "protocol": matrix.get("repositoryProtocol"),
            "host": matrix.get("repositoryHost"),
            "port": matrix.get("repositoryPort"),
        },
        "components": dict(sorted(components.items())),
    }


def describe(label: str, key: str, value: dict) -> None:
    print(f"{label:7} {key}: {value.get('version')} ({value.get('file')})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="Wiser Home account email (prompted if omitted)")
    parser.add_argument("--password", help="discouraged; prompt is safer")
    parser.add_argument("--hub", type=int, default=0)
    parser.add_argument("--private-dir", type=Path, default=Path("private"))
    parser.add_argument("--state", type=Path, default=Path("state/last-check.json"))
    parser.add_argument("--matrix", type=Path, help="compare a local matrix/capture instead of contacting Wiser")
    parser.add_argument("--no-update", action="store_true", help="do not advance the saved baseline")
    args = parser.parse_args()

    if args.matrix:
        matrix = find_matrix(json.loads(args.matrix.read_text()))
    else:
        email = args.email or os.environ.get("WISER_EMAIL") or input("Wiser account email: ").strip()
        password = args.password or os.environ.get("WISER_PASSWORD") or getpass.getpass("Wiser account password: ")
        matrix = fetch_matrix(email, password, args.hub, args.private_dir)
        password = ""
    current = snapshot(matrix)

    if not args.state.exists():
        print(f"No prior state at {args.state}; establishing a baseline with {len(current['components'])} component(s).")
        changed = True
    else:
        previous = json.loads(args.state.read_text())
        old = previous.get("components", {})
        new = current["components"]
        added = sorted(new.keys() - old.keys())
        removed = sorted(old.keys() - new.keys())
        modified = sorted(key for key in new.keys() & old.keys() if new[key] != old[key])
        for key in added:
            describe("added", key, new[key])
        for key in modified:
            describe("old", key, old[key])
            describe("new", key, new[key])
        for key in removed:
            describe("removed", key, old[key])
        changed = bool(added or removed or modified)
        if not changed:
            print(f"No firmware changes since {previous.get('checkedAt', 'the previous check')}.")
        else:
            print(f"Changes: {len(added)} added, {len(modified)} updated, {len(removed)} removed.")

    if not args.no_update:
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
        print(f"Updated baseline: {args.state}")
    return 1 if changed and args.no_update else 0


if __name__ == "__main__":
    raise SystemExit(main())

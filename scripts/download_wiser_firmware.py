#!/usr/bin/env python3
"""Download all firmware components referenced by a Wiser software matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlunsplit

import requests


def iter_components(matrix: dict):
    protocol = str(matrix.get("repositoryProtocol", "HTTPS")).lower()
    host = matrix["repositoryHost"]
    port = matrix.get("repositoryPort")
    netloc = f"{host}:{port}" if port and not (protocol == "https" and port == 443) else host
    for release in matrix.get("systemRelease", []):
        for device in release.get("deviceType", []):
            for component in device.get("swComponent", []):
                filename = component["repositoryFile"]
                path = str(PurePosixPath("/") / component.get("repositoryPath", "").lstrip("/") / filename)
                yield release, device, component, urlunsplit((protocol, netloc, quote(path), "", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("firmware"))
    parser.add_argument("--list", action="store_true", help="print URLs without downloading")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    matrix = json.loads(args.matrix.read_text())
    session = requests.Session()
    manifest = []

    for release, device, component, url in iter_components(matrix):
        filename = Path(component["repositoryFile"]).name
        target = args.output_dir / filename
        if args.list:
            print(url)
            continue
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if target.exists() and not args.overwrite:
            data = target.read_bytes()
            status = "existing"
        else:
            response = session.get(url, timeout=90)
            response.raise_for_status()
            data = response.content
            target.write_bytes(data)
            status = "downloaded"
        digest = hashlib.sha512(data).hexdigest()
        print(f"{status}: {target} ({len(data)} bytes)")
        manifest.append({
            "systemVersion": release.get("systemVersion"),
            "deviceTypeId": device.get("deviceTypeId"),
            "componentType": component.get("swComponentType"),
            "componentVersion": component.get("swComponentVersion"),
            "filename": filename,
            "url": url,
            "size": len(data),
            "sha512": digest,
        })

    if not args.list:
        manifest_path = args.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

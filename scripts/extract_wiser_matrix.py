#!/usr/bin/env python3
"""Extract rus.swMatrix from a Wiser relay capture or /v2 response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def unwrap(value: object) -> object:
    if isinstance(value, dict) and "body" in value:
        body = value["body"]
        value = json.loads(body) if isinstance(body, str) else body
    return value


def find_matrix(value: object) -> dict:
    value = unwrap(value)
    if isinstance(value, dict):
        if {"repositoryHost", "systemRelease"} <= value.keys():
            return value
        rus = value.get("rus")
        if isinstance(rus, dict) and isinstance(rus.get("swMatrix"), dict):
            return rus["swMatrix"]
        for child in value.values():
            try:
                return find_matrix(child)
            except ValueError:
                pass
    elif isinstance(value, list):
        for child in value:
            try:
                return find_matrix(child)
            except ValueError:
                pass
    raise ValueError("no Wiser software matrix found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=Path("wiser-matrix.json"))
    args = parser.parse_args()
    matrix = find_matrix(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n")
    count = sum(
        len(d.get("swComponent", []))
        for r in matrix.get("systemRelease", [])
        for d in r.get("deviceType", [])
    )
    print(f"Wrote {count} component(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

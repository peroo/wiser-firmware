#!/usr/bin/env python3
"""Fetch the software matrix exposed by a registered Wiser Home hub."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
from pathlib import Path

import requests

LOGIN_URL = "https://api-nl.wiserair.com/Login"
CLOUD_URL = "https://api-nl.wiserair.com"
RELAY_PATH = "/api/wcs2/rpc/public_genie/web_action"

APP_AUTHORIZATION = os.environ.get("WISER_APP_AUTHORIZATION")


def save_private(directory: Path, name: str, value: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = directory / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    path.chmod(0o600)
    return path


def decode_relay(response: dict) -> object:
    if response.get("resultCode") != 200:
        raise RuntimeError(
            f"hub relay failed: {response.get('resultCode')}: "
            f"{response.get('errorString', response.get('body', 'unknown error'))}"
        )
    body = response.get("body")
    return json.loads(body) if isinstance(body, str) else body


def matrix_from_state(state: object) -> dict:
    if not isinstance(state, dict):
        raise RuntimeError("hub /v2 response was not an object")
    matrix = state.get("rus", {}).get("swMatrix")
    if not isinstance(matrix, dict):
        raise RuntimeError("hub /v2 response did not contain rus.swMatrix")
    return matrix


def fetch_matrix(email: str, password: str, hub: int, private_dir: Path) -> dict:
    """Authenticate and return one registered hub's software matrix."""
    if not APP_AUTHORIZATION:
        raise RuntimeError(
            "WISER_APP_AUTHORIZATION is required; set it to the Basic "
            "Authorization value from Wiser Home's production API configuration"
        )
    session = requests.Session()
    session.headers["User-Agent"] = "WiserHome/6.6.2"
    login_response = session.post(
        LOGIN_URL,
        headers={"Authorization": APP_AUTHORIZATION},
        data={
            "grant_type": "password", "username": email,
            "password": password, "remember": "true",
        },
        timeout=30,
    )
    login_response.raise_for_status()
    login = login_response.json()
    token = login.get("access_token") or login.get("accessToken") or login.get("AccessToken")
    if not token:
        raise RuntimeError(f"login response contained no recognized access token: {sorted(login)}")

    auth = {"Authorization": f"Bearer {token}"}
    account_response = session.get(CLOUD_URL + "/api/account/summary", headers=auth, timeout=30)
    account_response.raise_for_status()
    account = account_response.json()
    save_private(private_dir, "account-summary.json", account)
    controllers = []
    for entry in account if isinstance(account, list) else [account]:
        for device in entry.get("Devices", []):
            controller = device.get("ControllerId")
            if controller:
                controllers.append(controller)
    if not controllers:
        raise RuntimeError("the account has no registered Wiser hub ControllerId")
    if hub < 0 or hub >= len(controllers):
        raise RuntimeError(f"hub index {hub} is outside 0..{len(controllers) - 1}")

    relay_response = session.post(
        CLOUD_URL + RELAY_PATH,
        headers={
            **auth,
            "Content-Type": "application/json",
            "Wiser-deviceId": base64.b64encode(controllers[hub].encode()).decode(),
        },
        json={"method": "WebMethod_GET", "urlPath": "/v2"},
        timeout=60,
    )
    relay_response.raise_for_status()
    relay = relay_response.json()
    save_private(private_dir, "relay-v2.json", relay)
    return matrix_from_state(decode_relay(relay))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="Wiser Home account email (prompted if omitted)")
    parser.add_argument("--password", help="discouraged; prompt is safer")
    parser.add_argument("--hub", type=int, default=0, help="zero-based registered hub index")
    parser.add_argument("--output", type=Path, default=Path("wiser-matrix.json"))
    parser.add_argument("--private-dir", type=Path, default=Path("private"))
    args = parser.parse_args()

    email = args.email or input("Wiser account email: ").strip()
    password = args.password or getpass.getpass("Wiser account password: ")
    matrix = fetch_matrix(email, password, args.hub, args.private_dir)
    password = ""
    args.output.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n")

    releases = matrix.get("systemRelease", [])
    components = sum(
        len(device.get("swComponent", []))
        for release in releases
        for device in release.get("deviceType", [])
    )
    print(f"Saved {len(releases)} release(s), {components} component(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

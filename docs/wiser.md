# Wiser Home firmware enumeration

## Discovery

The working flow was recovered from Wiser Home 6.6.2, a Xamarin/.NET Android
application. The relevant production endpoints and embedded client Basic
credential were found in `WiserHome.Core.dll`, particularly the production API
configuration. `dump_il.py` is useful for repeating that inspection.

The newer 7.6.0 APK has a different layout and is not needed for this flow.

## Protocol

1. POST a password-grant form to `https://api-nl.wiserair.com/Login`, using the
   Basic credential embedded in Wiser Home 6.6.2.
2. Use the returned bearer token to GET `/api/account/summary` from the same
   service.
3. Read a registered hub's `ControllerId` from the account response.
4. Base64-encode that value into the `Wiser-deviceId` request header.
5. POST a relay request to `/api/wcs2/rpc/public_genie/web_action`:

   ```json
   {"method":"WebMethod_GET","urlPath":"/v2"}
   ```

6. The relay envelope's `body` is itself JSON. The firmware catalogue is at
   `rus.swMatrix`.

The matrix contains a repository protocol, host and port plus one or more system
releases. Each release contains device types and software components. A download
URL is formed as:

```text
{protocol}://{host}:{port}{repositoryPath}{repositoryFile}
```

`fetch_wiser_matrix.py` performs all of these steps and selects the first hub by
default. Supply the application credential through `WISER_APP_AUTHORIZATION` and
use `--hub N` when an account has multiple hubs. The credential is not included
in this repository. The scripts automatically load the ignored repository
`.env`; after a successful interactive login they save `WISER_EMAIL` and
`WISER_PASSWORD` there with owner-only permissions for subsequent checks.

## Checking for updates

Run:

```sh
python scripts/check_wiser_updates.py
```

The script compares the live catalogue with `state/last-check.json`, reports
added, updated, and removed device/component entries, then records the current
catalogue as the new baseline. Use `--no-update` for a CI-style check that leaves
the baseline unchanged and exits with status 1 when differences exist. Use
`--matrix FILE` to check a saved relay capture without contacting Wiser.

## Filename convention

Typical Zigbee images are named like:

```text
105E-000D-030000FF-0000-01FF.zigbee
```

One-line description: the predictable name encodes the Zigbee manufacturer,
image type, firmware/file version, and hardware-version range.

`105E` is Schneider Electric's Zigbee manufacturer code. The exact formatting
varies for older products, so consumers should trust the Zigbee OTA header and
matrix metadata rather than parsing the filename as the authority.

## Historical exploratory calls

During discovery, these hub paths were tried through the relay:

```text
/v2/domain/System/FotaEnabled
/v2/domain/SoftwareMatrix
/v2/SoftwareMatrix
/v2/domain/Device
/v2/UpgradeInformation
/v2/SystemRelease
/v2/SoftwareComponent
/v2/sw_matrix
/api/mgmt/v1/upgrades/
/v2
/v2/schema
/v2/domain
```

`/v2` was the useful call: it returned both the device state and
`rus.swMatrix`. `/v2/domain` also exposed `UpgradeInfo`, but that contains only
the filenames and is insufficient to construct repository URLs by itself.

## Publishing to zigbee-OTA

Prefer the original vendor URL and original filename when the upstream remains
stable. The Koenkk/zigbee-OTA index can point directly at those URLs; committing
duplicate binaries is unnecessary. Verify the OTA header, version, image type,
manufacturer code and checksum before proposing an entry. Hardware min/max and
`modelId` constraints should only be added when the vendor metadata or known
hardware compatibility justifies them; arbitrary zero bounds add no safety.

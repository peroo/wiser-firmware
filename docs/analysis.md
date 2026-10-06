# Firmware inspection and comparison

Schneider `.zigbee` files use the standard Zigbee OTA container. Parse the OTA
header first to establish manufacturer code, image type, file version, optional
hardware bounds, total image size and sub-elements.

The examined SmartDim puck packages were signed rather than application-level
encrypted. A signed bootloader or signed OTA image should not be described as
encrypted merely because it is not directly replaceable. Extracting the
application sub-element may still yield ordinary ARM Thumb code and strings.

`compare_puck_firmware.py` compares two extracted plaintext ARM Thumb images. It
discovers functions from the vector table, canonicalizes addresses and branch
targets, and reports exact normalized function matches plus changed string
references:

```sh
python scripts/compare_puck_firmware.py old.bin new.bin
```

It assumes the vector table begins at offset `0x100`, matching the images that
motivated the script. Adjust `VECTOR_BASE` for a different extracted layout.

For Xamarin-era Wiser APK analysis, extract the managed DLLs and use:

```sh
python scripts/dump_il.py WiserHome.Core.dll ProductionApiConfiguration
```

APK and firmware binaries are deliberately ignored by Git. Keep originals and
private captures outside the repository or under ignored directories.

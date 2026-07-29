# PLC profiles

This library provides canonical profiles for the KV families listed below. Device ranges differ by model. Your application selects the catalog with a canonical PLC profile name such as `keyence:kv-7000`; the library does not query the PLC to choose a profile for you. Models not represented below, including KV-700 and KV-1000, do not currently have a canonical profile.
Use package-root `plc_profile_descriptors()` to enumerate canonical names, display labels,
connection eligibility, and XYM base profiles for a UI. Store the canonical profile string,
not the display name.

Verified hardware available for focused validation is maintained once in the
shared [KEYENCE KV Host Link profile catalog](https://github.com/fa-yoshinobu/plc-comm-hostlink-profiles#verified-hardware-available-for-validation).

## Device families and ranges

Device-family notation, type suffixes, XYM aliases, and static range tables are shared across the KV Host Link libraries. Use the common [KV Host Link Device Ranges](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/kv/device-ranges/) page for those details.

The table below identifies the canonical profile names, intended hardware, and
address notation. Device ranges remain in the shared reference above.

## Supported PLC profiles

| Canonical profile | Display name | Intended hardware | Address notation |
| --- | --- | --- | --- |
| `keyence:kv-nano` | KEYENCE KV-NANO | `KV-N24nn`, `KV-N40nn`, `KV-N60nn`, `KV-NC32T` | Native KV notation. |
| `keyence:kv-nano-xym` | KEYENCE KV-NANO (XYM) | Same KV-NANO family | XYM aliases over `keyence:kv-nano`. |
| `keyence:kv-3000` | KEYENCE KV-3000 | `KV-3000` | Native KV notation. |
| `keyence:kv-3000-xym` | KEYENCE KV-3000 (XYM) | Same KV-3000 family | XYM aliases over `keyence:kv-3000`. |
| `keyence:kv-5000` | KEYENCE KV-5000 | `KV-5000`, `KV-5500` | Native KV notation. |
| `keyence:kv-5000-xym` | KEYENCE KV-5000 (XYM) | Same KV-5000 family | XYM aliases over `keyence:kv-5000`. |
| `keyence:kv-7000` | KEYENCE KV-7000 | `KV-7000`, `KV-7300`, `KV-7500` | Native KV notation. |
| `keyence:kv-7000-xym` | KEYENCE KV-7000 (XYM) | Same KV-7000 family | XYM aliases over `keyence:kv-7000`. |
| `keyence:kv-8000` | KEYENCE KV-8000 | `KV-8000`, `KV-8000A` | Native KV notation. |
| `keyence:kv-8000-xym` | KEYENCE KV-8000 (XYM) | Same KV-8000 family | XYM aliases over `keyence:kv-8000`. |
| `keyence:kv-x500` | KEYENCE KV-X500 | `KV-X310`, `KV-X500`, `KV-X520`, `KV-X530`, `KV-X550` | Native KV notation. |
| `keyence:kv-x500-xym` | KEYENCE KV-X500 (XYM) | Same KV-X500 family | XYM aliases over `keyence:kv-x500`. |

## How to select

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options):
        print("Connected")


asyncio.run(main())
```

Catalog selection is separate from connection setup:

```python
from hostlink import device_range_catalog_for_plc_profile

def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-7000")
    print(catalog.plc_profile)


if __name__ == "__main__":
    main()
```

Choose the canonical profile in your application settings, project file, or UI. Do not depend on runtime model probing for catalog selection.

Unsupported strings fail immediately. Use the exact strings in the table above.

## Model-specific cautions

KV-NANO profiles do not include `EM`, `FM`, `ZF`, or `AT`. Use `DM` for first reads and check the device range catalog before using model-specific areas.

KV-NANO, KV-3000, and KV-5000 catalogs include `CTH` and `CTC` range rows. The address parser accepts both device types; actual availability remains model- and unit-dependent and must be checked against the selected catalog and PLC configuration.

KV-3000 and KV-5000 profiles include `AT`, but timer/counter preset writes (`WS`/`WSS`) are documented for KV-8000/7000-series only.

KV-7000 and KV-8000 profiles are the documented profiles for timer/counter preset writes (`WS`/`WSS`). They do not include `CTH` or `CTC`.

KV-X500 profiles do not include `AT`, `VM`, `VB`, `CTH`, or `CTC`. Use the shared [KV Host Link Troubleshooting & Codes](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/kv/troubleshooting-codes/) page for common address-shape and unsupported-device symptoms.

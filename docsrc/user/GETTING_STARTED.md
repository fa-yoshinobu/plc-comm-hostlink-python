# Getting started

## Start here

This page gets you from an empty Python project to your first KEYENCE KV Host Link read. You will choose the canonical profile `keyence:kv-8000`, connect to your PLC at `192.168.250.100:8501`, read `DM0`, then write and restore a test register.

## Prerequisites

| Requirement | Value |
|---|---|
| Python | Python 3.10 or newer. |
| PLC network | Your KV PLC must be reachable from your PC. |
| Host Link port | Use port `8501` for TCP or UDP unless your PLC connection node is configured differently. |

## Install

```bash
pip install kv-hostlink
```

## Choose profile

```python
from hostlink import device_range_catalog_for_plc_profile


def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-8000")
    print(catalog.plc_profile)


if __name__ == "__main__":
    main()
```

Use the exact canonical profile string that matches your PLC model. The library does not infer the device range catalog from the PLC model response.

## First read

```python
import asyncio
from hostlink import HostLinkConnectionOptions, device_range_catalog_for_plc_profile, open_and_connect, read_typed


async def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-8000")
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        dm0 = await read_typed(client, "DM0", "U")
        print(f"DM0 = {dm0}")


if __name__ == "__main__":
    asyncio.run(main())
```

Expected output:

```text
DM0 = 123
```

Your number will match the current value stored in `DM0` on your PLC.

## First write

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_typed, write_typed


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        test_address = "DM100"
        original = await read_typed(client, test_address, "U")
        try:
            await write_typed(client, test_address, "U", 1234)
            readback = await read_typed(client, test_address, "U")
            print(f"{test_address} = {readback}")
        finally:
            await write_typed(client, test_address, "U", original)


if __name__ == "__main__":
    asyncio.run(main())
```

Only write to a test address that is safe for your machine and program.

## Confirm success

1. The profile snippet prints `keyence:kv-8000`.
2. The connection opens without a timeout.
3. The first read prints a value for `DM0`.
4. The write example prints the value written to `DM100`.
5. The `finally` block restores the original test-register value.

## If it does not work

| Symptom | Check |
|---|---|
| The connection fails immediately. | Default port is `8501`, not `1025`; double-check the connection node port. |
| Profile selection fails. | Use one of the exact strings in [PLC profiles](PROFILES.md); aliases and combined old names are rejected. |
| Reads fail while you are trying the first example. | Start with `DM` word reads; do not start with timer/counter or expansion buffer access. |
| Timer/counter preset writes return `E1`. | Timer/Counter preset writes (`WS`/`WSS`) are only supported on KV-8000/7000-series. |

## Next steps

- Open the runnable samples: [samples README](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/tree/main/samples).
- Continue with the [Usage guide](USAGE_GUIDE.md) and [Gotchas](GOTCHAS.md).

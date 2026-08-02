# Getting started

## Start here

This page gets you from an empty Python project to your first KEYENCE KV Host Link read. You will choose the canonical profile `keyence:kv-8000`, connect to your PLC at `192.168.250.100:8501`, read `DM0`, then write and restore a test register.

## Prerequisites

| Requirement | Value |
|---|---|
| Python | Python 3.10 or newer. |
| PLC network | Your KV PLC must be reachable from your PC. |
| Host Link port | Use port `8501` for TCP or UDP unless your PLC connection node is configured differently. |

The library intentionally supports IPv4 endpoints only. KEYENCE targets in
this contract do not support IPv6, so IPv6 literals and IPv6 transport are not
accepted.

## Install

```bash
pip install plc-comm-kv-hostlink
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
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
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
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options) as client:
        test_address = "DM100"
        original = await read_typed(client, test_address, "U")
        write_confirmed = False
        try:
            await write_typed(client, test_address, "U", 1234)
            write_confirmed = True
            readback = await read_typed(client, test_address, "U")
            print(f"{test_address} = {readback}")
        finally:
            if write_confirmed:
                await write_typed(client, test_address, "U", original)


if __name__ == "__main__":
    asyncio.run(main())
```

Only write to a test address that is safe for your machine and program.
The example restores the saved value after a confirmed write, including when
readback fails. If the write result is outcome-unknown, it deliberately avoids
a blind restore or retry: reopen the client, inspect `DM100`, and reconcile the
actual value explicitly. If restoration fails, also inspect and reconcile the
register manually; do not assume that the saved value was restored.

## Confirm success

1. The profile snippet prints `keyence:kv-8000`.
2. The connection opens without a timeout.
3. The first read prints a value for `DM0`.
4. The write example prints the value written to `DM100`.
5. The `finally` block restores a confirmed write; an outcome-unknown write is
   reconciled explicitly instead of being retried blindly.

## If it does not work

| Symptom | Check |
|---|---|
| The connection fails immediately. | Default port is `8501`, not `1025`; double-check the connection node port. |
| Profile selection fails. | Use one of the exact strings in [PLC profiles](PROFILES.md); aliases and combined old names are rejected. |
| Reads fail while you are trying the first example. | Start with `DM` word reads; do not start with timer/counter or expansion buffer access. |
| Timer/counter preset writes return `E1`. | Timer/Counter preset writes (`WS`/`WSS`) are only supported on KV-8000/7000-series. |

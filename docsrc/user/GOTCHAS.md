# Gotchas

## Timer/counter preset write returns E1

| Field | Detail |
|---|---|
| Symptom | A timer or counter preset write returns `E1`. |
| Root cause | Host Link preset writes through `WS`/`WSS` are supported on KV-8000/7000-series, not on KV-3000, KV-5000, or KV-NANO. |
| Fix | Do not write timer/counter presets on unsupported models; use `read_timer`, `read_counter`, or `read_timer_counter` for safe reads. |

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_timer


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", port=8501)
    async with await open_and_connect(options) as client:
        timer = await read_timer(client, "T0")
        print(timer.preset)


if __name__ == "__main__":
    asyncio.run(main())
```

## AT device fails on KV-X500

| Field | Detail |
|---|---|
| Symptom | Reading `AT0` fails or the range catalog reports no `AT` entry for KV-X500. |
| Root cause | `AT` is not available in `keyence:kv-x500` or `keyence:kv-x500-xym`. |
| Fix | Check the selected profile before using `AT`, and avoid `AT` on KV-X500 projects. |

```python
from hostlink import device_range_catalog_for_plc_profile


def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-x500")
    entry = catalog.entry("AT")
    print(f"AT supported: {entry.supported if entry else False}")


if __name__ == "__main__":
    main()
```

## X or Y address rejected

| Field | Detail |
|---|---|
| Symptom | `X` or `Y` raises an address parse or PLC device-number error. |
| Root cause | `X` and `Y` use decimal-bank plus hex-bit notation. `X10F` means bank 10, bit F. |
| Fix | Use `X10F` or `Y10F`, and select an `-xym` profile when you want XYM aliases. |

```python
from hostlink import normalize_address


def main() -> None:
    print(normalize_address("X10F"))


if __name__ == "__main__":
    main()
```

## R, MR, LR, or CR address rejected

| Field | Detail |
|---|---|
| Symptom | `R`, `MR`, `LR`, or `CR` raises an address parse or PLC device-number error. |
| Root cause | These families use KEYENCE two-digit bit notation. |
| Fix | Use forms such as `R200` or `MR100`; do not treat the full suffix as one hexadecimal number. |

```python
from hostlink import normalize_address


def main() -> None:
    print(normalize_address("MR100"))


if __name__ == "__main__":
    main()
```

## Wrong port causes an immediate timeout

| Field | Detail |
|---|---|
| Symptom | The connection times out immediately even though the PLC responds on the network. |
| Root cause | KV Host Link uses port `8501`, not the SLMP/Computerlink port `1025`. |
| Fix | Set `port=8501` in `HostLinkConnectionOptions`. |

```python
from hostlink import HostLinkConnectionOptions


def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", port=8501)
    print(options)


if __name__ == "__main__":
    main()
```

## keyence:kv-3000-5000 rejected

| Field | Detail |
|---|---|
| Symptom | `device_range_catalog_for_plc_profile("keyence:kv-3000-5000")` raises `HostLinkProtocolError`. |
| Root cause | The old combined profile no longer exists. KV-3000 and KV-5000 are separate canonical profiles. |
| Fix | Use `keyence:kv-3000`, `keyence:kv-3000-xym`, `keyence:kv-5000`, or `keyence:kv-5000-xym`. |

```python
from hostlink import device_range_catalog_for_plc_profile


def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-5000")
    print(catalog.plc_profile)


if __name__ == "__main__":
    main()
```

## Non-canonical profile string rejected

| Field | Detail |
|---|---|
| Symptom | A short name, display label, or old alias raises `HostLinkProtocolError`. |
| Root cause | The range catalog accepts only exact canonical profile strings. It does not infer the profile from a PLC model response. |
| Fix | Store the canonical string from [PLC profiles](PROFILES.md) in your project settings or UI value. |

```python
from hostlink import available_plc_profiles


def main() -> None:
    for profile in available_plc_profiles():
        print(profile)


if __name__ == "__main__":
    main()
```

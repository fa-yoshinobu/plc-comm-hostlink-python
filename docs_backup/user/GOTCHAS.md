# Gotchas

## Timer/counter preset write returns E1

If a timer/counter preset write returns error `E1`, only KV-8000/7000-series support `WS`/`WSS`.

Fix: do not write presets on other models.

## AT device fails on some models

If reading `AT0` or similar returns an error or zero on some models, the AT digital trimmer is not available on KV-X500.

Fix: check the device range catalog first.

```python
from hostlink import device_range_catalog_for_plc_profile

catalog = device_range_catalog_for_plc_profile("keyence:kv-x500")
entry = catalog.entry("AT")
print(f"AT supported: {entry.supported if entry else False}")
```

## X or Y address rejected

If an X or Y address raises a parse error, X/Y use decimal-bank + hex-bit notation.

Fix: use `X10F`, not `X275`.

```python
from hostlink import normalize_address

print(normalize_address("X10F"))
```

## R/MR/LR/CR address rejected

If an R, MR, LR, or CR address raises a parse error, these families use two-digit bit notation.

Fix: use `R200`, not hex-only notation.

```python
from hostlink import normalize_address

print(normalize_address("MR100"))
```

## Connection fails immediately

If the connection times out immediately, the default port is `8501`, not `1025`.

Fix: set `port=8501` in `HostLinkConnectionOptions`.

```python
from hostlink import HostLinkConnectionOptions

options = HostLinkConnectionOptions(host="192.168.250.100", port=8501)
```

## PLC profile is wrong for your project

If a UI shows the wrong register range table, the application selected the wrong canonical PLC profile.

Fix: store the correct `keyence:...` profile in your application settings instead of probing the PLC model at runtime.

```python
from hostlink import device_range_catalog_for_plc_profile

catalog = device_range_catalog_for_plc_profile("keyence:kv-7000")
print(catalog.resolved_plc_profile)
```

# plc-comm-hostlink-python / samples

Sample scripts for the `hostlink` package (KEYENCE KV Host Link).

All scripts accept `--host` (required) and `--port` (default 8501) unless
noted otherwise. Run any script with `--help` for full usage.

## Scripts

| File | Description |
|---|---|
| `high_level_sync.py` | All high-level synchronous API helpers |
| `high_level_async.py` | All high-level asynchronous API helpers |
| `basic_test.py` | Basic read/write communication test |
| `grand_unified_test.py` | Comprehensive multi-command communication test |
| `exhaustive_address_test.py` | Exhaustive address format validation |
| `full_pattern_validation.py` | Full command pattern validation |
| `stress_test.py` | Stress test for reliability and throughput |
| `ultimate_dm_stress.py` | DM area stress test |
| `extreme_validation.py` | Extreme edge-case validation |

## Quick start

```
python samples/high_level_sync.py --host 192.168.250.100
python samples/high_level_async.py --host 192.168.250.100
```

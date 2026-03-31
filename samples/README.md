# plc-comm-hostlink-python / samples

Sample scripts for the `hostlink` package.

## User-Facing High-Level Examples

These examples use the recommended helper API only.

| File | Primary APIs | Description |
|---|---|---|
| `high_level_async.py` | `HostLinkConnectionOptions`, `open_and_connect`, `normalize_address`, `read_typed`, `write_typed`, `read_words_single_request`, `read_dwords_single_request`, `read_words_chunked`, `read_dwords_chunked`, `write_bit_in_word`, `read_named`, `poll` | Full walkthrough of the current high-level helper API |
| `high_level_sync.py` | `HostLinkConnectionOptions`, `open_and_connect`, `normalize_address`, `read_typed`, `write_typed`, `read_words_single_request`, `read_dwords_single_request`, `read_words_chunked`, `read_dwords_chunked`, `write_bit_in_word`, `read_named`, `poll` | CLI entrypoint that walks the same high-level helper API |
| `basic_high_level_rw.py` | `read_typed`, `write_typed` | Focused typed read/write example |
| `named_snapshot.py` | `read_named` | Mixed snapshot example using `read_named` |
| `polling_monitor.py` | `poll` | Repeated snapshot example using `poll` |

Run examples:

```bash
python samples/high_level_async.py --host 192.168.250.100
python samples/high_level_sync.py --host 192.168.250.100
python samples/basic_high_level_rw.py --host 192.168.250.100
python samples/named_snapshot.py --host 192.168.250.100
python samples/polling_monitor.py --host 192.168.250.100 --poll-count 5
```

CI validates these entrypoints with `python scripts/check_user_samples.py`,
which compiles each sample and runs `--help` for every user-facing script.

## Maintainer Validation Scripts

These scripts are for validation, stress, or edge-case testing rather than
normal application examples.

| File | Description |
|---|---|
| `basic_test.py` | Basic communication validation |
| `grand_unified_test.py` | Comprehensive multi-command validation |
| `exhaustive_address_test.py` | Address format validation |
| `full_pattern_validation.py` | Command pattern validation |
| `stress_test.py` | Reliability and throughput stress test |
| `ultimate_dm_stress.py` | DM-area stress test |
| `extreme_validation.py` | Extreme edge-case validation |

# Samples

## What is here

This directory contains runnable scripts for the recommended high-level KEYENCE KV Host Link API. Each sample requires a PLC host and canonical PLC profile; the examples below use Host Link port `8501`.

Use only test addresses that are safe for your PLC program before you run any write example.

## How to run

```bash
python samples/high_level_async.py --host 192.168.250.100 --plc-profile keyence:kv-8000 --port 8501
```

```bash
python samples/high_level_sync.py --host 192.168.250.100 --plc-profile keyence:kv-8000 --port 8501
```

```bash
python samples/basic_high_level_rw.py --host 192.168.250.100 --plc-profile keyence:kv-8000 --port 8501
```

```bash
python samples/polling_reconnect.py --host 192.168.250.100 --plc-profile keyence:kv-8000 --port 8501
```

```bash
python samples/named_snapshot.py --host 192.168.250.100 --plc-profile keyence:kv-8000 --port 8501
```

```bash
python samples/polling_monitor.py --host 192.168.250.100 --plc-profile keyence:kv-8000 --port 8501 --poll-count 5
```

## Sample index

| Project | What it demonstrates |
|---|---|
| `high_level_async.py` | Async connection setup, typed reads/writes, block reads, bit-in-word updates, named snapshots, and polling. |
| `high_level_sync.py` | A synchronous CLI entrypoint that runs the same high-level async workflow with `asyncio.run`. |
| `basic_high_level_rw.py` | A compact typed read/write example for unsigned, signed, double-word, and float values. |
| `polling_reconnect.py` | Read-only polling loop with automatic reconnect and backoff after transport loss. |
| `named_snapshot.py` | A focused mixed snapshot using `read_named`. |
| `polling_monitor.py` | A repeated snapshot loop using `poll`. |
| `basic_test.py` | Low-level model, mode, and basic DM read/write validation. |

`basic_test.py` writes `DM0` during initial connection validation. Run it only against a PLC and address range that are safe for your machine and program.

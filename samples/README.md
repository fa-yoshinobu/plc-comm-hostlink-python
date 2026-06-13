# Samples

This directory contains runnable scripts that demonstrate the recommended high-level KEYENCE KV Host Link API. Each user-facing sample accepts a PLC host and uses Host Link port `8501` by default.

## How to run

```bash
python samples/high_level_async.py --host 192.168.250.100 --port 8501
```

```bash
python samples/high_level_sync.py --host 192.168.250.100 --port 8501
```

```bash
python samples/basic_high_level_rw.py --host 192.168.250.100 --port 8501
```

```bash
python samples/named_snapshot.py --host 192.168.250.100 --port 8501
```

```bash
python samples/polling_monitor.py --host 192.168.250.100 --port 8501 --poll-count 5
```

## Sample index

| Project | What it demonstrates |
|---|---|
| `high_level_async.py` | Async connection setup, typed reads/writes, block reads, bit-in-word updates, named snapshots, and polling. |
| `high_level_sync.py` | A synchronous CLI entrypoint that runs the same high-level async workflow with `asyncio.run`. |
| `basic_high_level_rw.py` | A compact typed read/write example for unsigned, signed, double-word, and float values. |
| `named_snapshot.py` | A focused mixed snapshot using `read_named`. |
| `polling_monitor.py` | A repeated snapshot loop using `poll`. |

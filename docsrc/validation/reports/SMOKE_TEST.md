# E2E Smoke Test Guide

## Purpose

`scripts/e2e_smoke_test.py` performs a practical connectivity and protocol sanity check against a real PLC.

Default flow:

1. Connect to PLC
2. Query model (`?K`)
3. Query operating mode (`?M`)
4. Query error number (`?E`)
5. Single read (`RD`)
6. Consecutive read (`RDS`)
7. Invalid command check (expects `E1`)

Optional flow:

1. Write roundtrip (`WR` + readback + restore original value)

## Basic usage

```bash
python scripts/e2e_smoke_test.py --host 192.168.250.100
```

## With write test enabled

```bash
python scripts/e2e_smoke_test.py --host 192.168.250.100 --allow-write --write-device DM100 --write-format .U --write-value 1234
```

## UDP mode

```bash
python scripts/e2e_smoke_test.py --host 192.168.250.100 --transport udp
```

## Notes

- Write test is disabled by default.
- The write test always restores the original value after write/readback.
- If your PLC blocks unknown commands, you can disable invalid-command testing:

```bash
python scripts/e2e_smoke_test.py --host 192.168.250.100 --no-test-error-response
```


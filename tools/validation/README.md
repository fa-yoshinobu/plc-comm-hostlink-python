# Host Link Python Validation Tools

These scripts are maintainer lab validation tools, not ordinary user samples.
They can write many PLC devices or run long stress loops.

Run them from the repository root against a prepared test PLC only.

```bash
python tools/validation/full_pattern_validation.py 192.168.250.100 keyence:kv-8000 8501 tcp
python tools/validation/exhaustive_address_test.py 192.168.250.100 keyence:kv-8000 8501 tcp
python tools/validation/extreme_validation.py 192.168.250.100 keyence:kv-8000 8501 tcp
python tools/validation/grand_unified_test.py 192.168.250.100 keyence:kv-8000 8501 tcp
python tools/validation/stress_test.py 192.168.250.100 keyence:kv-8000 8501 tcp
python tools/validation/ultimate_dm_stress.py 192.168.250.100 keyence:kv-8000 8501 tcp
```

The argument form is:

```text
<host> <plc-profile> [port] [transport]
```

Keep normal user-facing examples in `samples/`.

# Getting Started

## Start Here

Use this package when you want the shortest Python path to KEYENCE KV Host Link communication through the public high-level API.

Recommended first path:

1. Install `kv-hostlink`.
2. Open one connection with `open_and_connect`.
3. Read one safe `DM` word.
4. Write only to a known-safe test word or bit after the first read is stable.

## First PLC Registers To Try

Start with these first:

- `DM0`
- `DM10`
- `DM100:S`
- `DM200:D`
- `DM50.3`

Do not start with these:

- large chunked reads
- validation sweeps
- addresses outside the current public register table

## Minimal Async Pattern

```python
from hostlink import HostLinkConnectionOptions, open_and_connect

options = HostLinkConnectionOptions(host="192.168.250.100", port=8501)
```

## First Successful Run

Recommended order:

1. `read_typed(client, "DM0", "U")`
2. `write_typed(client, "DM10", "U", value)` only on a safe test word
3. `read_named(client, ["DM0", "DM1:S", "DM2:D", "DM4:F", "DM10.0"])`

## Common Beginner Checks

If the first read fails, check these in order:

- correct host and port
- start with `DM` instead of a timer/counter or less common area
- use one scalar read before trying `.bit` or typed views

## Next Pages

- [Supported PLC Registers](./SUPPORTED_REGISTERS.md)
- [Latest Communication Verification](./LATEST_COMMUNICATION_VERIFICATION.md)
- [User Guide](./USER_GUIDE.md)

# Pr_HOST-LINK-COMMUNICATION-FUNCTION

Python library for KEYENCE KV-XLE02 Host Link communication.

## Structure

- `hostlink/`: library implementation
- `docs/host_link_protocol.md`: protocol reference
- `docs/api_reference.md`: API reference for `HostLinkClient`

## Quick Start

```python
from hostlink import HostLinkClient

with HostLinkClient("192.168.0.10", transport="tcp") as plc:
    plc.change_mode("RUN")
    value = plc.read("DM200.S")
    plc.write("DM200.S", 1234)
    values = plc.read_consecutive("R100", 4)
```

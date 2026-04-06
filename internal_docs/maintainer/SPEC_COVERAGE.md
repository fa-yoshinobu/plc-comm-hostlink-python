# Host Link Specification Coverage

This matrix tracks what is covered in the Python library and documentation.

## 1. Protocol and Transport

| Item | Status | Notes |
| --- | --- | --- |
| ASCII framing (`CR`, optional `LF`) | Covered | Implemented in `protocol.py` and `client.py` |
| TCP communication | Covered | Stream receive with CR/LF splitting |
| UDP communication | Covered | Datagram request/response flow |
| Error response parsing (`E0/E1/E2/E4/E5/E6`) | Covered | `HostLinkError` decoder included |

## 2. Command Coverage

| Group | Command | Status |
| --- | --- | --- |
| Operation | `M`, `ER`, `?E`, `?K`, `?M`, `WRT` | Covered |
| Forced | `ST`, `RS`, `STS`, `RSS` | Covered |
| Read | `RD`, `RDS`, `RDE` | Covered |
| Write | `WR`, `WRS`, `WRE`, `WS`, `WSS` | Covered |
| Monitor | `MBS`, `MWS`, `MBR`, `MWR` | Covered |
| Other | `RDC`, `BE`, `URD`, `UWR` | Covered |

## 3. Validation Coverage

| Rule type | Status | Notes |
| --- | --- | --- |
| Device range validation | Covered | Per device type range table |
| Data format suffix validation | Covered | `\"\", .U, .S, .D, .L, .H` |
| Consecutive count limits | Covered | Device and format dependent limits |
| Command-specific allowed device types | Covered | `ST/RS`, `MBS/MWS`, `RDC`, `WS/WSS` |
| Expansion unit argument ranges | Covered | `unit_no`, `address`, `count` |

## 4. Documentation Coverage

| Document | Status | Scope |
| --- | --- | --- |
| `docsrc/host_link_protocol.md` | Covered | Protocol rules, command syntax, constraints |
| `docsrc/api_reference.md` | Covered | Public API, signatures, behavior |
| `docsrc/spec_coverage.md` | Covered | Coverage matrix and traceability |

## 5. Known Practical Boundaries

- CPU family/version-specific runtime differences are handled by PLC responses (`E*`) and not fully simulated in code.
- PLC-side timing/load-dependent behavior cannot be validated offline.
- Network and hardware setup parameters are described as operational inputs; they are not enforced by the library.



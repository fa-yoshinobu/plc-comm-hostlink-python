# KEYENCE KV HOST LINK Protocol Notes

## 1. Communication Overview

- Roles:
  - PLC Ethernet unit: server
  - PC application: client
- Transport: `TCP/IP` or `UDP/IP`
- Port: `8501` (configurable)
- Encoding: `ASCII`

## 2. Frame Rules

### 2.1 Command frame

```text
<COMMAND> [<PARAM> ...] CR
```

- `CR` (`0x0D`) is the command separator.
- Optional `LF` (`0x0A`) after `CR` is accepted by the PLC.

### 2.2 Response frame

```text
<DATA | OK | E*> CR LF
```

Examples:

```text
OK\r\n
1 0 1 0\r\n
E1\r\n
```

## 3. Data Format Suffixes

- `.U`: unsigned 16-bit decimal
- `.S`: signed 16-bit decimal
- `.D`: unsigned 32-bit decimal
- `.L`: signed 32-bit decimal
- `.H`: 16-bit hexadecimal

## 4. Device Range Table

| Device | Range |
| --- | --- |
| R | 0..199915 |
| B | 0..7FFF |
| MR | 0..399915 |
| LR | 0..99915 |
| CR | 0..7915 |
| VB | 0..F9FF |
| DM | 0..65534 |
| EM | 0..65534 |
| FM | 0..32767 |
| ZF | 0..524287 |
| W | 0..7FFF |
| TM | 0..511 |
| Z | 1..12 |
| T / TC / TS | 0..3999 |
| C / CC / CS | 0..3999 |
| AT | 0..7 |
| CM | 0..7599 |
| VM | 0..589823 |

XYM aliases supported by protocol:

- `X` (relay), `Y` (internal auxiliary), `M` (latch), `L` (data memory), `D` (extended data memory), `E` (file register), `F` (file register)

## 5. Exception Responses

| Code | Meaning |
| --- | --- |
| E0 | Abnormal device No. |
| E1 | Abnormal command |
| E2 | Program not registered |
| E4 | Write disabled |
| E5 | Unit error |
| E6 | No comments |

## 6. Command Reference

### 6.1 Operation

- `M0` / `M1`
  - `M0`: PROGRAM mode
  - `M1`: RUN mode
- `ER`
- `?E`
- `?K`
- `?M`
- `WRT YY MM DD hh mm ss w`
  - `w`: `0=Sun ... 6=Sat`

### 6.2 Forced ON/OFF

- `ST <device>`
- `RS <device>`
- `STS <device> <count>`
- `RSS <device> <count>`

Allowed device types for forced commands:

- `R, B, MR, LR, CR, T, C, VB`

`count` range for `STS/RSS`: `1..16`

### 6.3 Read

- `RD <device[.fmt]>`
- `RDS <device[.fmt]> <count>`
- `RDE <device[.fmt]> <count>` (legacy-compatible with `RDS`)

### 6.4 Write

- `WR <device[.fmt]> <value>`
- `WRS <device[.fmt]> <count> <v1> ... <vn>`
- `WRE <device[.fmt]> <count> <v1> ... <vn>` (legacy-compatible with `WRS`)
- `WS <device[.fmt]> <value>`
- `WSS <device[.fmt]> <count> <v1> ... <vn>`

`WS/WSS` device type restriction:

- only `T` or `C`

### 6.5 Monitor

- `MBS <dev1> <dev2> ...`
- `MWS <dev1[.fmt]> <dev2[.fmt]> ...`
- `MBR`
- `MWR`

Monitor register size limit:

- up to `120` devices

`MBS` allowed types:

- `R, B, MR, LR, CR, T, C, VB`

`MWS` allowed types:

- `R, B, MR, LR, CR, VB, DM, EM, FM, W, TM, Z, TC, TS, CC, CS, CM, VM`

### 6.6 Others

- `RDC <device>`
- `BE <bank_no>` (`0..15`)
- `URD <unit_no> <address> [.fmt] <count>`
- `UWR <unit_no> <address> [.fmt] <count> <v1> ... <vn>`

`RDC` allowed types:

- `R, B, MR, LR, CR, DM, EM, FM, ZF, W, TM, Z, T, C, CM`

Expansion unit parameters:

- `unit_no`: `0..48`
- `address`: `0..59999`

## 7. Consecutive Count Limits

For `RDS/RDE/WRS/WRE`:

| Device family | `.U/.S/.H` or bit/omitted | `.D/.L` |
| --- | --- | --- |
| R, B, MR, LR, CR, VB, DM, EM, FM, ZF, W, CM, VM, X, Y, M, L, D, E, F | 1..1000 | 1..500 |
| TM | 1..512 | 1..256 |
| Z | 1..12 | 1..12 |
| T, TC, TS, C, CC, CS | 1..120 | 1..120 |
| AT | 1..8 | 1..8 |

For `URD/UWR`:

- `.U/.S/.H` or omitted: `1..1000`
- `.D/.L`: `1..500`

## 8. Implementation Notes

- TCP receive should be stream-oriented and split by CR/LF delimiters.
- `E*` responses should be handled as errors/exceptions.
- For `.D/.L` access, 32-bit pairing constraints apply on PLC side.

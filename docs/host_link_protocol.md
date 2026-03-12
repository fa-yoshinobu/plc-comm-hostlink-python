# KEYENCE KV HOST LINK Protocol Notes

## 1. Communication Overview

- Roles: PLC Ethernet unit is the server, PC application is the client.
- Transport: `TCP/IP` or `UDP/IP`
- Port: `8501` (changeable in unit settings)
- Encoding: `ASCII`
- Terminators:
  - Command: `CR` (`0x0D`) required, optional `LF` (`0x0A`)
  - Response: `CR LF`

## 2. Frame Format

### 2.1 Command

```text
<COMMAND> [<PARAM> ...] CR
```

Example:

```text
RDS R100 4\r
```

### 2.2 Response

```text
<DATA or OK or E*> CR LF
```

Examples:

```text
OK\r\n
1 0 1 0\r\n
E1\r\n
```

## 3. Data Format Suffixes

- `.U`: 16-bit unsigned decimal
- `.S`: 16-bit signed decimal
- `.D`: 32-bit unsigned decimal
- `.L`: 32-bit signed decimal
- `.H`: 16-bit hexadecimal

## 4. Main Device Ranges (used in the library)

- `R`: 0..199915
- `B`: 0..7FFF
- `MR`: 0..399915
- `LR`: 0..99915
- `CR`: 0..7915
- `DM`: 0..65534
- `EM`: 0..65534
- `FM`: 0..32767
- `ZF`: 0..524287
- `W`: 0..7FFF
- `TM`: 0..511
- `Z`: 1..12
- `T/TC/TS/C/CC/CS`: 0..3999
- `CM`: 0..7599
- `VM`: 0..589823

Notes:

- Some ranges vary by CPU series/version.
- XYM aliases (`X/Y/M/L/D/E/F`) are also supported by specification.

## 5. Error Responses

- `E0`: Abnormal device No.
- `E1`: Abnormal command
- `E2`: Program not registered
- `E4`: Write disabled
- `E5`: Unit error
- `E6`: No comments (mainly for `RDC`)

## 6. Full Command List

### 6.1 Operation Commands

- `M0` / `M1` (change mode: PROGRAM / RUN)
- `ER` (clear error)
- `?E` (check error number)
- `?K` (query model code)
- `?M` (confirm operating mode)
- `WRT YY MM DD hh mm ss w` (set time, `w`: `0=Sun` to `6=Sat`)

### 6.2 Forced ON/OFF

- `ST <device>` (forced set)
- `RS <device>` (forced reset)
- `STS <device> <count>` (continuous forced set)
- `RSS <device> <count>` (continuous forced reset)
- `count` range: 1..16

### 6.3 Read

- `RD <device[.fmt]>`
- `RDS <device[.fmt]> <count>`
- `RDE <device[.fmt]> <count>` (legacy-compatible, same behavior as `RDS`)

### 6.4 Write

- `WR <device[.fmt]> <value>`
- `WRS <device[.fmt]> <count> <v1> ... <vn>`
- `WRE <device[.fmt]> <count> <v1> ... <vn>` (legacy-compatible, same behavior as `WRS`)
- `WS <device[.fmt]> <value>`
- `WSS <device[.fmt]> <count> <v1> ... <vn>`

Notes:

- `WS/WSS` are KV-LE20A compatible commands for timer/counter set values.
- On unsupported CPU families, `WS/WSS` may return `E1`.

### 6.5 Monitor

- `MBS <dev1> <dev2> ...` (register bit monitor table, max 120)
- `MWS <dev1[.fmt]> <dev2[.fmt]> ...` (register word monitor table, max 120)
- `MBR` (read bit monitor table)
- `MWR` (read word monitor table)

### 6.6 Other

- `RDC <device>` (read comment, up to 32 characters)
- `BE <bank_no>` (file register bank switch, 0..15)
- `URD <unit_no> <address> [.fmt] <count>`
  - `unit_no`: 00..48
  - `address`: 0..59999
- `UWR <unit_no> <address> [.fmt] <count> <v1> ... <vn>`
  - `unit_no`: 00..48
  - `address`: 0..59999

## 7. Implementation Notes

- Always send/receive ASCII text frames.
- Parse responses by frame terminator (`CR/LF`) and process one frame at a time.
- For TCP streams, buffer until terminator is found.
- Treat `E*` responses as exceptions in client logic.
- `.D/.L` (32-bit) requires attention to data simultaneity rules.

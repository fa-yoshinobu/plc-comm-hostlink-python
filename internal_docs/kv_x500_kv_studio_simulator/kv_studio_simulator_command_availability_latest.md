# KV STUDIO Simulator Host Link Command Availability

Date: 2026-06-21 JST

## Summary

The KV STUDIO Simulator endpoint was tested over `127.0.0.1:8501/TCP`.

- Protocol: KEYENCE KV Host Link
- Frame terminator: CR
- Owner process during test: `ACCommServer2.exe`
- Reported model code: `62`
- Reported model: `KV-X500`
- Local client PLC profile: `keyence:kv-x500`

Result:

- Basic connection and model query succeeded.
- Device read/write commands for `DM` and `MR` succeeded.
- Consecutive read/write commands, including legacy consecutive commands,
  succeeded.
- Forced set/reset commands succeeded and were restored.
- Expansion unit buffer read/write succeeded for the sampled address.
- `?E`, `?M`, monitor registration/read, and bank switch returned simulator
  error responses.
- Clock set and PROGRAM mode change were not executed because they intentionally
  change simulator state.

## Write Safety

Writable checks used `DM100`, `DM101`, `MR100`, and `MR101`, and restored the
original values after the test.

Post-test confirmation:

- `DM100` readback: `0`
- `MR100` readback: `0`
- TCP port `8501` remained in LISTEN state.

## Command Matrix

| Code | Category | Command | Result | Detail |
|:--:|:--|:--|:--:|:--|
| `?K` | System | Query model | OK | code=`62`, model=`KV-X500` |
| `?E` | System | Check error number | NG | `E7` |
| `?M` | System | Confirm operating mode | NG | `E7` |
| `RD` | Device | Read `DM0.U` | OK | value=`0` |
| `RD` | Device | Read `MR100` | OK | value=`0` |
| `RDS` | Device | Read consecutive `DM0.U x2` | OK | values=`[0, 0]` |
| `RDE` | Device | Read consecutive legacy `DM0.U x2` | OK | values=`[0, 0]` |
| `WR` | Device | Write `DM100.U` and restore | OK | after=`4660`, restored=`0` |
| `WR` | Device | Write `MR100` and restore | OK | after=`1`, restored=`0` |
| `WRS` | Device | Write consecutive `DM100.U x2` and restore | OK | after=`[1, 2]`, restored=`[0, 0]` |
| `WRE` | Device | Write consecutive legacy `DM100.U x2` and restore | OK | after=`[3, 4]`, restored=`[0, 0]` |
| `MBS`/`MBR` | Monitor | Register/read monitor bits `MR100/MR101` | NG | `E1` |
| `MWS`/`MWR` | Monitor | Register/read monitor words `DM100/DM101` | NG | `E1` |
| `RDC` | Comment | Read comment `DM0` | NG | `E6` no comments |
| `ST`/`RS` | Forced | Forced set/reset `MR100` and restore | OK | after_set=`1`, after_reset=`0`, restored=`0` |
| `STS`/`RSS` | Forced | Forced set/reset consecutive `MR100 x2` and restore | OK | after_set=`[1, 1]`, after_reset=`[0, 0]`, restored=`[0, 0]` |
| `ER` | System | Clear error | OK | accepted |
| `M1` | System | Change mode RUN only | OK | accepted |
| `BE` | System | Switch bank `0` | NG | `E1` |
| `URD` | Expansion | Read expansion unit buffer unit `0`, addr `0.U x1` | OK | values=`[0]` |
| `UWR` | Expansion | Write expansion unit buffer same value unit `0`, addr `0.U` | OK | accepted |
| `WRT` | Clock | Set time | SKIP | not executed; changes simulator clock |
| `M0` | System | Change mode PROGRAM | SKIP | not executed; would switch simulator out of RUN |

## Conclusion

For this KV STUDIO Simulator session, Host Link TCP communication over
`127.0.0.1:8501` is available.

Core device read/write, consecutive read/write, forced bit operations, and
sampled expansion buffer commands are usable. Some system/monitor commands
return valid Host Link error responses from the simulator and should be treated
as unavailable in this session unless simulator settings or target model change.

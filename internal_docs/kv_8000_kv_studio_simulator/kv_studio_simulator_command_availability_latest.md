# KV STUDIO Simulator Host Link Command Availability

Date: 2026-06-21 JST

## Summary

The KV STUDIO Simulator endpoint was tested over `127.0.0.1:8501/TCP`.

- Protocol: KEYENCE KV Host Link
- Frame terminator: CR
- Owner process during test: `ACCommServer2.exe`
- Reported model code: `57`
- Reported model: `KV-8000`
- Local client PLC profile used for this test: `keyence:kv-8000`

Result:

- Basic connection and model query succeeded.
- `?E` and `?M` succeeded in this session.
- Device read/write commands for `DM` and `MR` succeeded and were restored.
- Consecutive read/write commands, including legacy variants, succeeded.
- Forced set/reset commands succeeded and were restored.
- `M0` PROGRAM mode and `M1` RUN mode commands succeeded; the final state was
  restored with `M1`.
- Sampled expansion unit buffer read/write succeeded.
- Timer/counter set-value commands, monitor registration/read, bank switch, and
  clock set returned simulator error responses.

## Write Safety

Writable checks used `DM100`, `DM101`, `MR100`, and `MR101`, and restored the
original values after the test.

Post-test confirmation:

- `DM100` restored to `0`
- `MR100` restored to `0`
- TCP port `8501` remained in LISTEN state before the command run.

## Command Matrix

| Code | Category | Command | Result | Detail |
|:--:|:--|:--|:--:|:--|
| `?K` | System | Query model | OK | code=`57`, model=`KV-8000` |
| `?E` | System | Check error number | OK | `000` |
| `?M` | System | Confirm operating mode | OK | `0` |
| `RD` | Device | Read `DM0.U` | OK | value=`0` |
| `RD` | Device | Read `DM1.S` | OK | value=`0` |
| `RD` | Device | Read `DM2.D` | OK | value=`0` |
| `RD` | Device | Read `DM4.L` | OK | value=`0` |
| `RD` | Device | Read `DM6.H` | OK | value=`0000` |
| `RD` | Device | Read `MR100` | OK | value=`0` |
| `RDS` | Device | Read consecutive `DM0.U x2` | OK | values=`[0, 0]` |
| `RDE` | Device | Read consecutive legacy `DM0.U x2` | OK | values=`[0, 0]` |
| `WR` | Device | Write `DM100.U` and restore | OK | after=`1234`, restored=`0` |
| `WR` | Device | Write `MR100` and restore | OK | after=`1`, restored=`0` |
| `WRS` | Device | Write consecutive `DM100.U x2` and restore | OK | after=`[1, 2]`, restored=`[0, 0]` |
| `WRE` | Device | Write consecutive legacy `DM100.U x2` and restore | OK | after=`[3, 4]`, restored=`[0, 0]` |
| `WS` | Timer/Counter | Write set value `T0.D` same-value | NG | `E0` |
| `WSS` | Timer/Counter | Write set value consecutive `T0.D x2` same-value | NG | `E0` |
| `MWS`/`MWR` | Monitor | Register/read monitor words `DM100/DM101` | NG | `E1` |
| `MBS`/`MBR` | Monitor | Register/read monitor bits `MR100/MR101` | NG | `E1` |
| `RDC` | Comment | Read comment `DM0` | NG | `E6` no comments |
| `ST`/`RS` | Forced | Forced set/reset `MR100` and restore | OK | set=`1`, reset=`0`, restored=`0` |
| `STS`/`RSS` | Forced | Forced set/reset consecutive `MR100 x2` and restore | OK | set=`[1, 1]`, reset=`[0, 0]`, restored=`[0, 0]` |
| `M1` | System | Change mode RUN | OK | accepted |
| `M0` | System | Change mode PROGRAM | OK | accepted |
| `M1` | System | Change mode RUN restore | OK | accepted |
| `BE` | System | Switch bank `0` | NG | `E1` |
| `WRT` | Clock | Set time to current PC time | NG | `E1` |
| `URD` | Expansion | Read expansion unit buffer unit `0`, addr `0.U x1` | OK | values=`[0]` |
| `UWR` | Expansion | Write expansion unit buffer same value unit `0`, addr `0.U` | OK | accepted |
| `ER` | System | Clear error | OK | accepted |
| `INVALID` | Other | Invalid command error response | OK | expected `E1` error response |
| `?K` | Final | Reconnect/query model after test | OK | code=`57`, model=`KV-8000` |
| `RD` | Final | `DM100` final readback | OK | value=`0` |
| `RD` | Final | `MR100` final readback | OK | value=`0` |

## Conclusion

For this KV STUDIO Simulator session, Host Link TCP communication over
`127.0.0.1:8501` is available.

Core device read/write, consecutive read/write, forced bit operations, mode
change, and sampled expansion buffer commands are usable. Timer/counter
set-value, monitor, bank switch, and clock set commands returned valid Host Link
error responses in this simulator session.

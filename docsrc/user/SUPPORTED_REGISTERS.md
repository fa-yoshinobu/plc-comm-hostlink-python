# Supported registers

This page lists the device families exposed by the Python high-level API. The exact range limits come from the selected canonical profile in [PLC profiles](PROFILES.md).

## Word device families

| Family | Notation | Example | Notes |
|---|---|---|---|
| `DM` | Decimal | `DM0` | General data memory. Start here for first reads. |
| `EM` | Decimal | `EM0` | Extended data memory on KV-3000 and newer profiles except KV-NANO. |
| `FM` | Decimal | `FM0` | File memory on KV-3000 and newer profiles except KV-NANO. |
| `ZF` | Decimal | `ZF0` | File register area on KV-3000 and newer profiles except KV-NANO. |
| `W` | Hexadecimal | `W0` | Link register word area. |
| `CM` | Decimal | `CM0` | Control memory word area. |
| `TM` | Decimal | `TM0` | Timer-related word area. |
| `VM` | Decimal | `VM0` | Variable memory word area; not available on KV-X500 profiles. |

## Bit device families

| Family | Notation | Example | Notes |
|---|---|---|---|
| `R` | Decimal with two-digit bit | `R200` | Relay bits. |
| `B` | Hexadecimal | `B0000` | Link relay bits. |
| `MR` | Decimal with two-digit bit | `MR100` | Internal relay bits. |
| `LR` | Decimal with two-digit bit | `LR100` | Latch relay bits. |
| `CR` | Decimal with two-digit bit | `CR100` | Control relay bits. |
| `VB` | Hexadecimal | `VB0` | Variable memory bits; not available on KV-X500 profiles. |
| `X` | Decimal bank plus hex bit | `X10F` | Input alias in XYM profiles only. |
| `Y` | Decimal bank plus hex bit | `Y10F` | Output alias in XYM profiles only. |
| `M` | Decimal | `M0` | Internal relay alias in XYM profiles only. |
| `L` | Decimal | `L0` | Latch relay alias in XYM profiles only. |

## Timer, counter, and index families

| Family | Category | Example | Notes |
|---|---|---|---|
| `T` | Timer/counter | `T0` | Timer status, current value, and preset helpers. |
| `C` | Timer/counter | `C0` | Counter status, current value, and preset helpers. |
| `AT` | Timer/counter catalog category | `AT0` | Digital trimmer; not available on KV-NANO or KV-X500 profiles. |
| `CTH` | Timer/counter catalog category | `CTH0` | High-speed counter area on KV-NANO, KV-3000, and KV-5000 profiles only. |
| `CTC` | Timer/counter catalog category | `CTC0` | High-speed counter area on KV-NANO, KV-3000, and KV-5000 profiles only. |
| `Z` | Index | `Z1` | Index registers. KV-X500 profiles expose `Z1` through `Z10`; other profiles expose `Z1` through `Z12`. |

## Type suffixes

| Form | Example | Meaning |
|---|---|---|
| `:U` | `DM100:U` | Unsigned 16-bit word. |
| `:S` | `DM100:S` | Signed 16-bit word. |
| `:D` | `DM100:D` | Unsigned 32-bit double word. |
| `:L` | `DM100:L` | Signed 32-bit double word. |
| `:F` | `DM100:F` | IEEE 754 32-bit floating-point value. |
| `:BIT` | `CR000:BIT` | Direct bit device value. |
| `.n` | `DM100.A` | Bit `n` inside a word, where `n` is hexadecimal `0` to `F`. |
| `:COMMENT` | `DM100:COMMENT` | Device comment text through `read_named`. |

Helper-layer address text must include the intended type. Use `DM100:U`, not plain `DM100`, when reading an unsigned word through `read_named`.

## Addressing notes

| Symptom | Rule |
|---|---|
| `X` or `Y` is rejected. | Use decimal-bank plus hex-bit notation, such as `X10F`. |
| `R`, `MR`, `LR`, or `CR` is rejected. | Use KEYENCE two-digit bit notation, such as `R200` or `MR100`. |
| `AT`, `VM`, `VB`, `CTH`, or `CTC` is rejected on KV-X500. | Select the correct profile and check the range catalog before using model-specific areas. |
| A read works on one PLC but not another. | The canonical profile controls the supported range table; see [PLC profiles](PROFILES.md). |

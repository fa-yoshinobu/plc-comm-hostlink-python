# Supported registers

This page lists the device families exposed by the Python high-level API. The exact range limits come from the selected canonical profile in [PLC profiles](PROFILES.md).

## Word device families

| Family | Notation | Example | Notes |
|---|---|---|---|
| `DM` | Decimal | `DM0:U` | General data memory. Start here for first reads. |
| `EM` | Decimal | `EM0:U` | Extended data memory on KV-3000 and newer profiles except KV-NANO. |
| `FM` | Decimal | `FM0:U` | File memory on KV-3000 and newer profiles except KV-NANO. |
| `ZF` | Decimal | `ZF0:U` | File register area on KV-3000 and newer profiles except KV-NANO. |
| `W` | Hexadecimal | `W0:U` | Link register word area. |
| `CM` | Decimal | `CM0:U` | Control memory word area. |
| `TM` | Decimal | `TM0:U` | Timer-related word area. |
| `VM` | Decimal | `VM0:U` | Variable memory word area; not available on KV-X500 profiles. |

## Bit device families

| Family | Notation | Example | Notes |
|---|---|---|---|
| `R` | Decimal with two-digit bit | `R200:BIT` | Relay bits. |
| `B` | Hexadecimal | `B0000:BIT` | Link relay bits. |
| `MR` | Decimal with two-digit bit | `MR100:BIT` | Internal relay bits. |
| `LR` | Decimal with two-digit bit | `LR100:BIT` | Latch relay bits. |
| `CR` | Decimal with two-digit bit | `CR100:BIT` | Control relay bits. |
| `VB` | Hexadecimal | `VB0:BIT` | Variable memory bits; not available on KV-X500 profiles. |
| `X` | Decimal bank plus hex bit | `X10F:BIT` | Input alias in XYM profiles only. |
| `Y` | Decimal bank plus hex bit | `Y10F:BIT` | Output alias in XYM profiles only. |
| `M` | Decimal | `M0:BIT` | Internal relay alias in XYM profiles only. |
| `L` | Decimal | `L0:BIT` | Latch relay alias in XYM profiles only. |

## Timer, counter, and index families

| Family | Category | Example | Notes |
|---|---|---|---|
| `T` | Timer/counter | `T0` | Timer status, current value, and preset helpers. |
| `C` | Timer/counter | `C0` | Counter status, current value, and preset helpers. |
| `AT` | Timer/counter catalog category | `AT0` | Digital trimmer; not available on KV-NANO or KV-X500 profiles. |
| `CTH` | Timer/counter catalog category | `CTH0` | Catalog entry only. High-speed counter range row on KV-NANO, KV-3000, and KV-5000 profiles; not accepted by the address parser. |
| `CTC` | Timer/counter catalog category | `CTC0` | Catalog entry only. High-speed counter range row on KV-NANO, KV-3000, and KV-5000 profiles; not accepted by the address parser. |
| `Z` | Index | `Z1` | Index registers. KV-X500 profiles expose `Z1` through `Z10`; other profiles expose `Z1` through `Z12`. |

## Type suffixes

| Form | Example | Meaning |
|---|---|---|
| `:U` | `DM100:U` | Unsigned 16-bit word. |
| `:S` | `DM100:S` | Signed 16-bit word. |
| `:D` | `DM100:D` | Unsigned 32-bit double word. |
| `:L` | `DM100:L` | Signed 32-bit double word. |
| `:F` | `DM100:F` | IEEE 754 32-bit floating-point value. |
| `:H` | `DM100:H` | Hexadecimal 16-bit word text. |
| `:BIT` | `CR000:BIT` | Direct bit device value. |
| `.n` | `DM100.A` | Bit `n` inside a word, where `n` is hexadecimal `0` to `F`. |
| `:COMMENT` | `DM100:COMMENT` | Device comment text through `read_named`. |

Helper-layer address text must include the intended type. Use `DM100:U`, not plain `DM100`, when reading an unsigned word through `read_named`.

## Addressing notes

| Symptom | Rule |
|---|---|
| `X` or `Y` is rejected. | Use decimal-bank plus hex-bit notation, such as `X10F`. |
| `R`, `MR`, `LR`, or `CR` is rejected. | Use KEYENCE two-digit bit notation, such as `R200:BIT` or `MR100:BIT`. |
| `AT`, `VM`, `VB`, `CTH`, or `CTC` is rejected on KV-X500. | Select the correct profile and check the range catalog before using model-specific areas. |
| `CTH` or `CTC` is rejected on a profile whose catalog shows those rows. | Treat `CTH` and `CTC` as catalog metadata only; they are not accepted as address input. |
| A read works on one PLC but not another. | The canonical profile controls the supported range table; see [PLC profiles](PROFILES.md). |

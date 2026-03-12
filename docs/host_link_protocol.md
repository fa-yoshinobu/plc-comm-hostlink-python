# KEYENCE KV HOST LINK プロトコル整理（KV-XLE02）

`marker_manual/HOST LINK.pdf`（13章）をもとに、Python 実装向けに整理した仕様です。

## 1. 通信概要

- 通信相手: PLC 側 Ethernet ユニット（サーバ）と PC 側アプリ（クライアント）
- 伝送: `TCP/IP` または `UDP/IP`
- ポート: `8501`（変更可能）
- 文字コード: `ASCII`
- 終端:
  - コマンド: `CR`（`0x0D`）必須、`LF`（`0x0A`）は付与可
  - 応答: `CR LF`

## 2. フレーム形式

### 2.1 コマンド

```text
<COMMAND> [<PARAM> ...] CR
```

例:

```text
RDS R100 4\r
```

### 2.2 応答

```text
<DATA or OK or E*> CR LF
```

例:

```text
OK\r\n
1 0 1 0\r\n
E1\r\n
```

## 3. データ形式サフィックス

- `.U`: 16bit unsigned decimal
- `.S`: 16bit signed decimal
- `.D`: 32bit unsigned decimal
- `.L`: 32bit signed decimal
- `.H`: 16bit hex

## 4. 代表デバイス範囲（実装採用）

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

補足:

- 一部デバイスは CPU シリーズや機能バージョンで上限が変わる記述あり（13-17, 13-22）。
- `X/Y/M/L/D/E/F` の XYM 表記も仕様上利用可。

## 5. エラー応答

- `E0`: Device No. 異常
- `E1`: Command 異常
- `E2`: Program 未登録
- `E4`: 書き込み禁止
- `E5`: Unit/PLC エラー
- `E6`: コメント無し（主に `RDC`）

## 6. 全コマンド仕様

### 6.1 運用系

- `M`（モード変更）
  - `M0` = PROGRAM
  - `M1` = RUN
- `ER`（エラークリア）
- `?E`（エラー番号照会）
- `?K`（機種コード照会）
- `?M`（動作モード照会）
- `WRT`（時刻設定）
  - `WRT YY MM DD hh mm ss w`
  - `w`: `0=Sun ... 6=Sat`

### 6.2 強制 ON/OFF

- `ST <device>`（強制セット）
- `RS <device>`（強制リセット）
- `STS <device> <count>`（連続強制セット）
- `RSS <device> <count>`（連続強制リセット）
  - `count` は 1..16

### 6.3 読み出し

- `RD <device[.fmt]>`
- `RDS <device[.fmt]> <count>`
- `RDE <device[.fmt]> <count>`（互換コマンド、動作は `RDS` と同等）

### 6.4 書き込み

- `WR <device[.fmt]> <value>`
- `WRS <device[.fmt]> <count> <v1> ... <vn>`
- `WRE <device[.fmt]> <count> <v1> ... <vn>`（互換コマンド、動作は `WRS` と同等）
- `WS <device[.fmt]> <value>`
- `WSS <device[.fmt]> <count> <v1> ... <vn>`
  - `WS/WSS` は KV-LE20A 互換。`T/C` 系の set 値書き込み用途。
  - KV-8000/7000 以外では `E1` になる記述あり。

### 6.5 モニタ

- `MBS <dev1> <dev2> ...`（bit monitor 登録、最大 120）
- `MWS <dev1[.fmt]> <dev2[.fmt]> ...`（word monitor 登録、最大 120）
- `MBR`（bit monitor 読み出し）
- `MWR`（word monitor 読み出し）

### 6.6 その他

- `RDC <device>`（コメント読み出し、最大32文字）
- `BE <bank_no>`（ファイルレジスタ BANK 切替、0..15）
- `URD <unit_no> <address> [.fmt] <count>`
  - `unit_no`: 00..48
  - `address`: 0..59999
- `UWR <unit_no> <address> [.fmt] <count> <v1> ... <vn>`
  - `unit_no`: 00..48
  - `address`: 0..59999

## 7. 実装上の注意

- すべて ASCII テキストで送受信する。
- 受信は `CR/LF` 区切りで 1 応答フレームずつ処理する。
- `TCP` はストリームなので、終端までバッファリングして切り出す。
- `E*` 応答は例外として扱い、上位でリトライやログを実施する。
- `.D/.L`（32bit）はデバイス境界の同時性注意（13-33）。


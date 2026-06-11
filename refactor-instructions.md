# refactor-instructions.md

plc-comm-hostlink-python のリファクタリング指示書。
この文書は実装担当モデル向けの完結した作業指示である。実装前にこの文書全体を読むこと。

> **最重要の前提**: このパッケージは PyPI に公開済み(`kv-hostlink` 0.1.11)であり、
> KEYENCE KV 上位リンク(Host Link)の ASCII フレームは実機 KV-5000 / KV-X500 での
> 検証記録(`TODO.md`)に紐づく。
> **公開 API と送信フレームの文字列を 1 文字たりとも変えてはならない。**
>
> このリポジトリは Python 一族の中では比較的健全(utils.py は async 単系統、
> docs カバレッジ/サンプル検査が CI に組み込み済み)。本タスクの中心は
> **`client.py` 内の同期/非同期クライアントの複製縮約**と
> **sync/async ワイヤ同一性の安全網追加**であり、規模は中程度でよい。

---

## Objective

公開 API・送信フレーム文字列を一切壊さずに:

1. **sync/async のワイヤ同一性を固定する特性テストを追加する**(安全網。最優先)
2. **`HostLinkClient` / `AsyncHostLinkClient` の複製コマンドロジックを
   `HostLinkBase` の純粋メソッド(フレーム組立・応答デコード)へ抽出する**
3. (任意)`utils.py`(870 行)内の read-plan 機構の非公開モジュール分離

---

## Project Understanding

### 何のライブラリか

KEYENCE KV シリーズと上位リンクプロトコル(ASCII コマンド `RD` / `RDS` / `WR` / `WRS` /
`URD` / `UWR` 等、TCP/UDP)で通信する Python ライブラリ。Rust 版・.NET 版・Node-RED 版と
高レベル契約を共有。`src/` レイアウト。

### モジュール構成(src/hostlink/、計約 2,600 行)

| ファイル | 行数 | 内容 |
|---|---|---|
| `utils.py` | 870 | **文書化された推奨ユーザー面**(`open_and_connect` / `read_typed` / `read_named` / `poll`、async 単系統)+ read-plan 最適化(`_try_compile_read_named_plan` 562 行〜)+ アドレスヘルパ |
| `client.py` | 791 | `HostLinkBase`(91 行〜共有部)+ `HostLinkClient`(222 行〜、同期)+ `AsyncHostLinkClient`(551 行〜)— **コマンドメソッドが 2 クラスで手書きミラー** |
| `device_ranges.py` | 332 | モデル別レンジカタログ |
| `device.py` | 314 | アドレス解析・検証 |
| `__init__.py` | 127 | 公開面の re-export(docstring が推奨入口の一覧) |

### テスト / CI

- `tests/test_comprehensive.py`(358)/ `test_spec_compliance.py`(181)ほか
- `run_ci.bat`: ruff check → ruff format --check → mypy src →
  `scripts/check_high_level_docs.py` → `scripts/check_user_samples.py` →
  pytest(`PYTHONPATH=src`)
- `scripts/e2e_smoke_test.py` は実機向け。実行しない。

---

## Behaviors To Preserve(絶対に壊さない既存挙動)

1. **公開 API**: `src/hostlink/__init__.py` の export 一覧とモジュールパス。
2. **送信フレームの文字列**: ASCII コマンドボディ(CR 終端含む)。Rust 版の
   golden ベクトルと同じものが契約。
3. **プロトコル固定事項**(TODO.md / Rust 版指示書と共通):
   - `AT` は書込ヘルパが**送信前に**拒否、32bit 点扱い
   - `T` / `C` プリセット書込の機種制限
   - 拡張ユニットアクセス(`URD` / `UWR`)の実機検証済み挙動
4. **read-plan(`read_named` のバッチ最適化)の分割規則と結果順序**。
5. **依存ゼロ / バージョン 0.1.11 / CHANGELOG**: 変更しない。

---

## Non-Negotiables(交渉不可の制約)

- 最初に `git status` を確認する。未コミット変更があれば混ぜず、報告して停止する。
- 編集前に Baseline Commands をすべて実行し、結果(テスト件数含む)を記録する。
- 変更は小さく戻しやすい単位(1 コマンド群ずつ)。コミットはユーザーの指示があるまで行わない。
- 無関係な整形・「ついで」リファクタリングをしない。
- 依存を追加しない。`pyproject.toml` / `MANIFEST.in` を変更しない。
- 抽出メソッドは `HostLinkBase` の非公開メソッド(`_build_*` / `_decode_*`)とし、
  公開しない。
- 既存テストの既存アサーションを変更しない(追加のみ可)。
- 実機 PLC への接続を行わない。
- 正しさが不明な場合は実装を止め、「Stop And Ask」として質問を報告書に書く。

---

## Stop And Ask Conditions(即時停止して質問する条件)

- **パリティテストで sync と async の送信文字列が食い違った**(= 既にドリフト)。
  どちらが正かは実機検証記録に紐づくため、勝手に直さず両方を併記して質問。
- 既存テストが自分の変更後に落ちた ⇒ 即座に巻き戻して報告
- 公開名・フレーム文字列・例外文言に影響しうる変更が必要に見えた
- CI の docs カバレッジ/サンプル検査スクリプトが自分の変更で落ちた
- 本書の Debt Map に無い大きな問題を発見した(報告のみ)

---

## Baseline Commands

作業ディレクトリ: リポジトリルート。Python 3.10+。実機 PLC 不要・接続禁止。

```bat
git status
python -m ruff check src tests scripts samples
python -m ruff format --check src tests scripts samples
python -m mypy src
python scripts\check_high_level_docs.py
python scripts\check_user_samples.py
set PYTHONPATH=src
python -m pytest tests          & rem テスト件数を記録
```

---

## Debt Map

行番号は調査時点(main, commit `ca4a200`)のアンカー。ドリフトしていたら宣言名で探すこと。

### D1. sync/async ワイヤ同一性テストの不在 【実装可 / 最優先】

- **根拠**: `HostLinkClient` と `AsyncHostLinkClient` はコマンドメソッドを手書きミラー
  しているが、「同じ呼び出しで同じフレーム文字列を送る」保証テストが無い。
- **改善案**: 送信文字列を記録するモックトランスポートで、全コマンドメソッドについて
  sync/async の出力を**互いに比較**する `tests/test_sync_async_parity.py` を追加。
  期待値は手書きしない(どちらが正かを判断しない)。
- **リスク**: 低。

### D2. `client.py` のコマンドメソッド複製 【実装可 / 主作業】

- **根拠**: `HostLinkClient`(222〜551 行)と `AsyncHostLinkClient`(551〜891 行)が
  フレーム組立・応答デコードを各自実装。共有は `HostLinkBase`(91〜222 行)の一部のみ。
- **改善案**: 「コマンド文字列の組立」と「応答のデコード」を `HostLinkBase` の
  純粋メソッドへ 1 コマンドずつ抽出し、両クライアントは送受信だけを行う形にする。
  D1 のパリティテストが変更前後の同一性を保証する。
- **リスク**: 中。D1 完了後に着手。

### D3. `utils.py` 内の read-plan 機構の同居 【任意・小】

- **根拠**: `_try_compile_read_named_plan`(562 行〜)以下の最適化機構が
  公開ヘルパと同居(Rust 版 helpers.rs の D2、.NET 版 Extensions と同型)。
- **改善案**: 非公開モジュール(例: `src/hostlink/_read_plan.py`)へ move-only 分離。
  時間や確信が足りなければ提案として報告するだけでよい。

### D4. その他(現状維持 / 報告のみ)

- `utils.py` という名前が推奨ユーザー面を指している点は slmp-python と同じ命名負債だが、
  公開モジュールパスのため**変更禁止**(提案のみ)。
- `device.py` / `device_ranges.py` は健全。触らない。

---

## Implementation Phases

### Phase 0: 現状確認

1. `git status` 確認(クリーンでなければ停止・報告)
2. Baseline Commands を実行し、結果を記録

### Phase 1: パリティテスト(D1)

1. モックトランスポート + 全コマンドのパリティテスト追加
2. 食い違いが出たコマンドは Stop And Ask に記録し D2 対象から外す

### Phase 2: 複製抽出(D2)

1. read 系 → write 系 → モニタ系 → 運転制御系 → 拡張ユニット系の順に 1 群ずつ抽出
2. 各群ごとに pytest + mypy + ruff

### Phase 3: read-plan 分離(D3、任意)

実施しない場合は提案として報告。

### Phase 4: 検証と報告

全 Verification Requirements を最終実行し、Reporting Format に従って報告。

---

## Verification Requirements

各フェーズ完了時に最低限(Baseline Commands と同一セット):

```bat
python -m ruff check src tests scripts samples
python -m ruff format --check src tests scripts samples
python -m mypy src
python scripts\check_high_level_docs.py
python scripts\check_user_samples.py
set PYTHONPATH=src
python -m pytest tests
```

- テスト件数が baseline から増えていること
- `git diff` で確認: `__init__.py` 無変更、公開シグネチャ無変更、
  `pyproject.toml` / `CHANGELOG.md` / `samples/` 無変更

---

## Reporting Format

1. **Baseline 結果**: 実行コマンドと結果(テスト件数)
2. **パリティ表**: コマンド × 一致/食い違い/未対応
3. **抽出一覧**: コマンド群 × 抽出先メソッド
4. **各フェーズの検証結果**: 最後に実行したコマンドと結果(失敗を隠さない)
5. **Stop And Ask**: 発生した質問と停止範囲
6. **提案事項**: D3 / 命名(実装しない)
7. **未実施事項**

---

## Out-of-scope Items(やらないこと)

- 公開 API・モジュールパス・公開名の変更(`utils.py` rename を含む。提案のみ)
- 送信フレーム文字列・例外文言の変更
- `device.py` / `device_ranges.py` の変更
- `scripts/` / `samples/` / `docsrc/` / `internal_docs/` の変更
- バージョン変更、`CHANGELOG.md` 更新、PyPI 公開
- 依存追加、CI 変更
- 実機 PLC を使う検証(`e2e_smoke_test.py` を実行しない)
- 兄弟リポジトリの変更

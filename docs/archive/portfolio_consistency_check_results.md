# ポートフォリオ一貫性確認結果

## 実行日時
2025-01-12

## 実行条件
- リバランス日: 2023-01-31
- パラメータファイル: `params_operational_24M_lambda0.00_20260112.json`

## 結果サマリー

### portfolio_hash の比較

| ルート | 使用関数 | portfolio_hash | 銘柄数 |
|--------|----------|----------------|--------|
| **optimize route** | `_select_portfolio_with_params` | `a3345a28b21d846b0b1971a6d774033c` | 12 |
| **compare route (v1)** | `select_portfolio` (longterm_run.py) | `e410761ec219cee22fd69ec24e1d7887` | 12 |
| **compare route (v2)** | `_select_portfolio_with_params` | `a3345a28b21d846b0b1971a6d774033c` | 12 |
| **production route** | `select_portfolio` (longterm_run.py) | `e410761ec219cee22fd69ec24e1d7887` | 12 |

### 比較結果

- ❌ **optimize route と production route: 不一致**
  - optimize: `a3345a28b21d846b0b1971a6d774033c`
  - production: `e410761ec219cee22fd69ec24e1d7887`

- ❌ **compare route (v1) と optimize route: 不一致**
  - compare (v1): `e410761ec219cee22fd69ec24e1d7887`
  - optimize: `a3345a28b21d846b0b1971a6d774033c`

- ✅ **compare route (v2) と optimize route: 一致**
  - compare (v2): `a3345a28b21d846b0b1971a6d774033c`
  - optimize: `a3345a28b21d846b0b1971a6d774033c`

## 詳細結果

### optimize route（最適化ルート）

**使用関数**: `_select_portfolio_with_params`

**選定銘柄**:
- ['9075', '4063', '8020', '2282', '7593', '6134', '8015', '3291', '5706', '4042', '3696', '4739']

**重み**: 全て等ウェイト（0.083333 = 1/12）

**portfolio_hash**: `a3345a28b21d846b0b1971a6d774033c`

### compare route（比較ルート）

#### v1: `select_portfolio` (longterm_run.py)

**使用関数**: `select_portfolio` (longterm_run.py)

**portfolio_hash**: `e410761ec219cee22fd69ec24e1d7887`

#### v2: `_select_portfolio_with_params`

**使用関数**: `_select_portfolio_with_params`

**portfolio_hash**: `a3345a28b21d846b0b1971a6d774033c`

**注意**: 現時点で `compare_lambda_penalties.py` は `select_portfolio` (longterm_run.py) を使用しているため、v1が実際の動作です。

### production route（本番運用ルート）

**使用関数**: `select_portfolio` (longterm_run.py)

**選定銘柄**:
- ['9075', '4063', '8037', '8020', '2282', '7593', '6134', '8015', '3291', '8566', '5706', '4042']

**重み**: 全て等ウェイト（0.083333 = 1/12）

**portfolio_hash**: `e410761ec219cee22fd69ec24e1d7887`

## 銘柄の違い

### optimize route と production route の比較

**共通銘柄（10銘柄）**:
- 9075, 4063, 8020, 2282, 7593, 6134, 8015, 3291, 5706, 4042

**optimize route のみ（2銘柄）**:
- 3696, 4739

**production route のみ（2銘柄）**:
- 8037, 8566

## 問題点の確認

### 1. 最適化ルートと本番運用ルートの不一致

**現状**:
- 最適化ルート: `_select_portfolio_with_params`（等ウェイト版）を使用
- 本番運用ルート: `select_portfolio` (longterm_run.py) を使用

**問題**: 最適化している戦略と、実際に運用する戦略が違う状態。この状態で再最適化しても、最終的に本番に載せた瞬間に「思ったのと違う」が再発する可能性があります。

### 2. 比較ルートと最適化ルートの不一致

**現状**:
- 比較ルート: `select_portfolio` (longterm_run.py) を使用
- 最適化ルート: `_select_portfolio_with_params`（等ウェイト版）を使用

**問題**: 比較ルートが最適化ルートと異なる関数を使用しているため、比較結果が最適化結果と一致しない可能性があります。

## 解決策

### オプション1: 本番も `_select_portfolio_with_params`（等ウェイト版）に統一（推奨）

**変更が必要なファイル**:
1. `src/omanta_3rd/jobs/compare_lambda_penalties.py`
   - `select_portfolio` → `_select_portfolio_with_params` に変更

2. `src/omanta_3rd/jobs/batch_longterm_run.py`
   - `select_portfolio` → `_select_portfolio_with_params` に変更

**メリット**:
- 最適化/比較/本番で同じ選定ロジックを使用
- 最適化結果が本番に反映される

**デメリット**:
- 本番運用の選定ロジックが変更される
- 既存の本番ポートフォリオとの整合性を確認する必要がある

### オプション2: 最適化/比較を本番ロジック（`select_portfolio`）に戻す

**変更が必要なファイル**:
1. `src/omanta_3rd/jobs/optimize.py`
   - `_select_portfolio_with_params` → `select_portfolio` に戻す

2. `src/omanta_3rd/jobs/optimize_timeseries.py`
   - `_select_portfolio_with_params` → `select_portfolio` に戻す

**メリット**:
- 本番運用の選定ロジックを変更しない
- 既存の本番ポートフォリオとの整合性を維持

**デメリット**:
- 以前のスコア比例ウェイト戦略の選定ロジックを採用できない
- 最適化結果が改善されない可能性がある

## 推奨アクション

1. **統一方針の決定**: オプション1（本番も `_select_portfolio_with_params` に統一）を推奨
2. **実装変更**: `compare_lambda_penalties.py` と `batch_longterm_run.py` を修正
3. **再確認**: 修正後、再度 `verify_portfolio_consistency.py` を実行して一致を確認
4. **最適化の再実行**: 統一後、最適化を再実行


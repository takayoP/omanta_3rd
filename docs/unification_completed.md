# ポートフォリオ選定ロジックの統一完了

## 統一結果

### 確認スクリプト実行結果（2025-01-12）

**実行条件**:
- リバランス日: 2023-01-31
- パラメータファイル: `params_operational_24M_lambda0.00_20260112.json`

**結果**:
- ✅ **optimize route と production route: 一致**
  - portfolio_hash: `a3345a28b21d846b0b1971a6d774033c`
  - 使用関数: `_select_portfolio_with_params`（等ウェイト版）
- ✅ **compare route (v2) と optimize route: 一致**
  - portfolio_hash: `a3345a28b21d846b0b1971a6d774033c`
  - 使用関数: `_select_portfolio_with_params`（等ウェイト版）
- ❌ **compare route (v1) と optimize route: 不一致**
  - compare route (v1): `select_portfolio` (longterm_run.py) を使用
  - **注意**: `compare_lambda_penalties.py`は既に修正済み。v1は旧実装の確認用。

## 変更完了ファイル

### 1. `src/omanta_3rd/jobs/optimize.py`
- ✅ `_select_portfolio_with_params`関数の重み計算を等ウェイトに変更
- ✅ `_select_portfolio_for_rebalance_date`関数で`_select_portfolio_with_params`を使用
- ✅ `_run_single_backtest`関数で`_select_portfolio_with_params`を使用

### 2. `src/omanta_3rd/jobs/optimize_timeseries.py`
- ✅ `_select_portfolio_for_rebalance_date`関数で`_select_portfolio_with_params`を使用

### 3. `src/omanta_3rd/jobs/compare_lambda_penalties.py`
- ✅ `run_backtest_with_params_file`関数で`_select_portfolio_with_params`を使用
- ✅ インポートを`select_portfolio`から`_select_portfolio_with_params`に変更

### 4. `src/omanta_3rd/jobs/batch_longterm_run.py`
- ✅ `run_monthly_portfolio_and_performance`関数で`_select_portfolio_with_params`を使用
- ✅ 循環インポートを避けるため、関数内でインポート

## 統一された選定ロジック

### 使用関数
- **全ルート**: `_select_portfolio_with_params`（等ウェイト版）

### 選定ロジック
1. **フィルタリング**: 流動性フィルタ、ROEフィルタ
2. **スコア計算**: `value_score`, `size_score`, `quality_score`, `growth_score`, `record_high_score`を計算
3. **Core score計算**: 各スコアを重み付けして`core_score`を計算
4. **プール選定**: `core_score`で上位`pool_size`件を選定
5. **最終選定**: `entry_score`でソート（オプション）→ セクターキャップ適用 → `target_min`〜`target_max`件を選定
6. **重み計算**: **等ウェイト**（`1.0 / n`）

## 次のステップ

1. **最適化の再実行**: 統一後、最適化を再実行して、train期間の超過リターンが改善されるか確認
2. **λ比較の再実行**: 最適化結果が改善されたら、λ比較も再実行
3. **本番再最適化**: 最終的に、本番再最適化（`reoptimize_all_candidates.py`）を実行

## 注意事項

- 以前のスコア比例ウェイト戦略の選定ロジック（train期間で13.49%の超過リターンを達成）を採用しつつ、最終的な重みは等ウェイトを維持
- 最適化/比較/本番で同じ選定ロジックを使用するため、最適化結果が本番に反映される
- `select_portfolio`（`longterm_run.py`）は本番運用では使用されなくなった（最適化ルートと統一）

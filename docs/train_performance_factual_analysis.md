# train期間の超過リターンが低い問題：事実確認と分析

## 実際のデータ確認

### 比較結果

**以前の結果（2026年1月11日、`as_of_date=2023-12-31`）**:
- `train_dates_first`: `2018-01-31`
- `train_dates_last`: `2020-12-30`
- `num_train_periods`: `36`
- `end_date`: `2023-12-31`
- `train_performance.mean_annual_excess_return_pct`: **`13.49%`**

**現在の結果（2026年1月12日、`as_of_date=2023-12-31`、実際の`end_date`は`2021-12-31`）**:
- `train_dates_first`: `2018-01-31`
- `train_dates_last`: `2020-12-30` ✅ **同じ**
- `num_train_periods`: `36` ✅ **同じ**
- `end_date`: `2021-12-31` ⚠️ **異なる**
- `train_performance.mean_annual_excess_return_pct`: **`1.44%`**

### 重要な発見

1. **`train_dates_last`は同じ**（`2020-12-30`）
2. **`num_train_periods`も同じ**（36）
3. **`end_date`が異なる**（`2023-12-31` vs `2021-12-31`）

**算術的確認**：
- `train_dates_last = 2020-12-30`の場合、`eval_end = 2020-12-30 + 24ヶ月 = 2022-12-30`
- どちらの`end_date`（`2023-12-31`または`2021-12-31`）でも、`eval_end (2022-12-30) <= as_of_date`を満たすので評価可能

**結論**: `train_dates`は同じなので、`as_of_date`の違いが直接的な原因では**ない**可能性が高いです。

## 算術的確認

### `split_rebalance_dates`の動作確認

24Mホライズンで`train_end_date=2022-12-31`の場合：
- `train_dates_last = 2020-12-30`
- `eval_end = 2020-12-30 + 24ヶ月 = 2022-12-30`
- `eval_end (2022-12-30) <= train_end_date (2022-12-31)` ✅

**結論**: `split_rebalance_dates`は正しく`eval_end <= train_end_date`で絞れています。

### `calculate_longterm_performance`での評価確認

`as_of_date=2023-12-31`の場合：
- `train_dates_last = 2020-12-30`のポートフォリオの`eval_end = 2022-12-30`
- `eval_end (2022-12-30) <= as_of_date (2023-12-31)` ✅

**結論**: 算術的には、`as_of_date=end_date`でも評価可能です。

## 確認すべきポイント

### 1. 以前の結果との比較

以前の結果（`as_of_date=2025-12-31`）と現在の結果（`as_of_date=2023-12-31`）で以下を比較：
- `train_dates_last`が同じか
- `num_train_periods`が同じか
- `train_performance.num_portfolios`（実際に評価されたポートフォリオ数）が同じか

### 2. calculate_longterm_performanceのログ確認

実際のログから以下を確認：
- `総ポートフォリオ数`（入力されたrebalance_dates数）
- `評価成功`（実際に使用されたrebalance_dates数）
- `スキップ`（除外されたrebalance_dates数）
- `スキップ理由内訳`（特に「ホライズン未達」の件数）

### 3. 評価されたポートフォリオの最大eval_end

実際に評価されたポートフォリオの最大`eval_end`を確認：
- `max_eval_end_used`をログに追加（実装済み）

これにより、「as_of_dateが小さすぎて落ちている」のか「そもそもtrain_datesが想定と違う」のかが一発で分かります。

## 推測される原因

### 可能性1：等ウェイトへの統一の影響（最も可能性が高い）

**重要な発見**: `train_dates`は同じなのに、パフォーマンスが大きく異なる

以前の実行では、`optimize`側が**スコア比例ウェイト**を使用していた可能性があります。

その場合：
- 以前: スコア比例ウェイト → 高いスコアの銘柄に多く投資 → 高いパフォーマンス（13.49%）
- 現在: 等ウェイト → 全銘柄に均等投資 → 低いパフォーマンス（1.44%）

これは、以前の最適化結果が**「スコア比例ウェイト戦略」**に対して最適化されていたため、等ウェイトに統一したことでパフォーマンスが低下した可能性があります。

### 可能性2：最適化結果のパラメータが異なる

以前の結果と現在の結果で、最適化されたパラメータが異なる可能性があります：

**以前の結果**:
- `w_value`: 0.558 (55.8%)
- `w_forward_per`: 0.631 (63.1%)
- `bb_weight`: 0.319 (31.9%)

**現在の結果**（確認が必要）

### 可能性3：評価条件の違い

以前の実行と現在の実行で、以下の条件が異なっていた可能性があります：
- `require_full_horizon`の設定
- `train_end_date`の設定
- `as_of_date`の設定（ただし、`train_dates`が同じなので直接的な原因ではなさそう）

## 次のステップ

1. **以前の結果JSONを確認**：`train_dates_last`、`num_train_periods`、`train_performance`を比較
2. **実際のログを確認**：除外件数と最大eval_endを確認
3. **原因特定**：上記の情報から「splitが想定通りか／as_ofで落ちてるか／以前は条件が違っていたか」を判定
4. **必要に応じて修正**：原因が特定できたら、適切な修正を実施


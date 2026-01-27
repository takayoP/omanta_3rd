# ポートフォリオ選定ロジックの変更：スコア比例ウェイト戦略の選定ロジックを採用

## 変更の背景と目的

### 問題の認識

以前のスコア比例ウェイト戦略（`_select_portfolio_with_params`）は、train期間で**13.49%の超過リターン**を達成していました。しかし、等ウェイトに統一した現在の実装では、同じパラメータで**-2.54%**と悪い結果になっています。

これは、以前のスコア比例ウェイト戦略の**選定ロジック**が優れていたことを示しています。

### ユーザーの要求

- **ポートフォリオにおける保有割合は等ウェイトにしてほしい**（これは維持）
- **以前のスコア比例ウェイト戦略の選定ロジックを採用してほしい**

### 実装方針

以前のスコア比例ウェイト戦略（`_select_portfolio_with_params`）の選定ロジックを使用しつつ、最終的な重みは等ウェイトにする。

## 選定ロジックの違い

### 以前のスコア比例ウェイト戦略（`_select_portfolio_with_params`）

1. **フィルタリング**: 流動性フィルタ、ROEフィルタ
2. **スコア計算**: `value_score`, `size_score`, `quality_score`, `growth_score`, `record_high_score`を計算
3. **Core score計算**: 各スコアを重み付けして`core_score`を計算
4. **プール選定**: `core_score`で上位`pool_size`件を選定
5. **最終選定**: `entry_score`でソート（オプション）→ セクターキャップ適用 → `target_min`〜`target_max`件を選定
6. **重み計算**: **スコア比例ウェイト**（`core_score / total_score`）

### 現在の等ウェイト戦略（`select_portfolio` in `longterm_run.py`）

1. **フィルタリング**: 流動性フィルタ、ROEフィルタ
2. **プール選定**: `core_score`で上位`pool_size`件を選定（`core_score`は`build_features`で既に計算済み）
3. **最終選定**: `entry_score`でソート（オプション）→ セクターキャップ適用 → `target_min`〜`target_max`件を選定
4. **重み計算**: **等ウェイト**（`1.0 / n`）

### 変更後の実装

1. **フィルタリング**: 流動性フィルタ、ROEフィルタ
2. **スコア計算**: `value_score`, `size_score`, `quality_score`, `growth_score`, `record_high_score`を計算（以前のスコア比例ウェイト戦略と同じ）
3. **Core score計算**: 各スコアを重み付けして`core_score`を計算（以前のスコア比例ウェイト戦略と同じ）
4. **プール選定**: `core_score`で上位`pool_size`件を選定（以前のスコア比例ウェイト戦略と同じ）
5. **最終選定**: `entry_score`でソート（オプション）→ セクターキャップ適用 → `target_min`〜`target_max`件を選定（以前のスコア比例ウェイト戦略と同じ）
6. **重み計算**: **等ウェイト**（`1.0 / n`）← **変更点**

## 変更ファイルと実装詳細

### 1. `src/omanta_3rd/jobs/optimize.py`

#### 変更①: `_select_portfolio_with_params`関数の重み計算を等ウェイトに変更

**変更箇所**: 307-312行目

**変更前**:
```python
# Weight calculation
total_score = sel_df["core_score"].sum()
if total_score > 0:
    sel_df["weight"] = sel_df["core_score"] / total_score
else:
    sel_df["weight"] = 1.0 / len(sel_df)
```

**変更後**:
```python
# Weight calculation: 等ウェイト（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
n = len(sel_df)
sel_df["weight"] = 1.0 / n
```

**説明**: 選定ロジックは以前のスコア比例ウェイト戦略と同じ（`core_score`でプール選定 → `entry_score`でソート → セクターキャップ適用）を維持しつつ、最終的な重みは等ウェイトに変更。

#### 変更②: `_select_portfolio_for_rebalance_date`関数で`_select_portfolio_with_params`を使用

**変更箇所**: 448-449行目

**変更前**:
```python
# ポートフォリオを選択（等ウェイト：本番運用と同じ）
portfolio = select_portfolio(feat, strategy_params=strategy_params)
```

**変更後**:
```python
# ポートフォリオを選択（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
```

**説明**: `select_portfolio`（`longterm_run.py`）の代わりに`_select_portfolio_with_params`（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）を使用。

#### 変更③: `_run_single_backtest`関数で`_select_portfolio_with_params`を使用

**変更箇所**: 362-363行目

**変更前**:
```python
# ポートフォリオを選択（等ウェイト：本番運用と同じ）
portfolio = select_portfolio(feat, strategy_params=strategy_params)
```

**変更後**:
```python
# ポートフォリオを選択（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
```

**説明**: `select_portfolio`（`longterm_run.py`）の代わりに`_select_portfolio_with_params`（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）を使用。

#### 変更④: 関数のdocstringを更新

**変更箇所**: 153-168行目

**変更前**:
```python
def _select_portfolio_with_params(
    feat: pd.DataFrame,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> pd.DataFrame:
    """
    パラメータ化されたポートフォリオ選択
    
    Args:
        feat: 特徴量DataFrame
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
    
    Returns:
        選択されたポートフォリオ
    """
```

**変更後**:
```python
def _select_portfolio_with_params(
    feat: pd.DataFrame,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> pd.DataFrame:
    """
    パラメータ化されたポートフォリオ選択（等ウェイト版）
    
    以前のスコア比例ウェイト戦略の選定ロジックを使用しつつ、
    最終的な重みは等ウェイトにする。
    
    Args:
        feat: 特徴量DataFrame
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
    
    Returns:
        選択されたポートフォリオ（等ウェイト）
    """
```

### 2. `src/omanta_3rd/jobs/optimize_timeseries.py`

#### 変更: `_select_portfolio_for_rebalance_date`関数で`_select_portfolio_with_params`を使用

**変更箇所**: 312-316行目

**変更前**:
```python
# ポートフォリオを選択（等ウェイト：本番運用と同じ）
# build_featuresで既にcore_scoreとentry_scoreが計算済みのため、select_portfolioを使用
print(f"        [_select_portfolio] ポートフォリオ選択開始: {rebalance_date}")
sys.stdout.flush()
portfolio = select_portfolio(feat, strategy_params=strategy_params)
```

**変更後**:
```python
# ポートフォリオを選択（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
print(f"        [_select_portfolio] ポートフォリオ選択開始: {rebalance_date}")
sys.stdout.flush()
from ..jobs.optimize import _select_portfolio_with_params
portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
```

**説明**: `select_portfolio`（`longterm_run.py`）の代わりに`_select_portfolio_with_params`（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）を使用。

## 選定ロジックの詳細比較

### 以前のスコア比例ウェイト戦略（`_select_portfolio_with_params`）の選定ロジック

1. **フィルタリング**:
   - 流動性フィルタ: `liquidity_60d >= quantile(liquidity_quantile_cut)`
   - ROEフィルタ: `roe >= roe_min`

2. **スコア計算**:
   - `value_score`: `w_forward_per * (1.0 - forward_per_pct) + w_pbr * (1.0 - pbr_pct)`
   - `size_score`: `pct_rank(log_mcap, ascending=True)`
   - `quality_score`: `pct_rank(roe, ascending=True)`
   - `growth_score`: `0.4 * op_growth_score + 0.4 * profit_growth_score + 0.2 * op_trend_score`
   - `record_high_score`: `record_high_forecast_flag`

3. **Core score計算**:
   ```python
   core_score = (
       w_quality * quality_score +
       w_value * value_score +
       w_growth * growth_score +
       w_record_high * record_high_score +
       w_size * size_score
   )
   ```

4. **プール選定**: `core_score`で上位`pool_size`件を選定

5. **最終選定**:
   - `use_entry_score=True`の場合: `entry_score`でソート → `core_score`でソート
   - セクターキャップ適用（各セクター最大`sector_cap`件）
   - `target_min`〜`target_max`件を選定

6. **重み計算**: `weight = core_score / total_score`（スコア比例）

### 現在の等ウェイト戦略（`select_portfolio` in `longterm_run.py`）の選定ロジック

1. **フィルタリング**:
   - 流動性フィルタ: `liquidity_60d >= quantile(liquidity_quantile_cut)`
   - ROEフィルタ: `roe >= roe_min`

2. **プール選定**: `core_score`で上位`pool_size`件を選定（`core_score`は`build_features`で既に計算済み）

3. **最終選定**:
   - `use_entry_score=True`の場合: `entry_score`でソート → `core_score`でソート
   - セクターキャップ適用（各セクター最大`sector_cap`件）
   - `target_min`〜`target_max`件を選定

4. **重み計算**: `weight = 1.0 / n`（等ウェイト）

### 変更後の実装（以前のスコア比例ウェイト戦略の選定ロジック + 等ウェイト）

1. **フィルタリング**: 以前のスコア比例ウェイト戦略と同じ
2. **スコア計算**: 以前のスコア比例ウェイト戦略と同じ（`value_score`, `size_score`, `quality_score`, `growth_score`, `record_high_score`を計算）
3. **Core score計算**: 以前のスコア比例ウェイト戦略と同じ
4. **プール選定**: 以前のスコア比例ウェイト戦略と同じ
5. **最終選定**: 以前のスコア比例ウェイト戦略と同じ
6. **重み計算**: **等ウェイト**（`1.0 / n`）← **変更点**

## 期待される効果

1. **選定ロジックの改善**: 以前のスコア比例ウェイト戦略の選定ロジック（13.49%の超過リターンを達成）を使用
2. **重みは等ウェイト**: ユーザーの要求通り、最終的な重みは等ウェイトを維持
3. **train期間の超過リターン向上**: 以前のスコア比例ウェイト戦略の選定ロジックを使用することで、train期間の超過リターンが改善される可能性がある

## 確認事項

1. **最適化の再実行**: この変更後、最適化を再実行して、train期間の超過リターンが改善されるか確認
2. **λ比較の再実行**: 最適化結果が改善されたら、λ比較も再実行
3. **本番再最適化**: 最終的に、本番再最適化（`reoptimize_all_candidates.py`）を実行

## 注意事項

- この変更は、**選定ロジック**を以前のスコア比例ウェイト戦略に戻すものであり、**重みは等ウェイトを維持**します
- `select_portfolio`（`longterm_run.py`）は本番運用で引き続き使用されますが、最適化ルートでは`_select_portfolio_with_params`（等ウェイト版）を使用します
- 最適化ルート（`optimize.py`, `optimize_timeseries.py`, `optimize_longterm.py`）と比較ルート（`compare_lambda_penalties.py`）の両方で、同じ選定ロジックを使用するようになりました

## 変更ファイル一覧

1. `src/omanta_3rd/jobs/optimize.py`
   - `_select_portfolio_with_params`関数の重み計算を等ウェイトに変更
   - `_select_portfolio_for_rebalance_date`関数で`_select_portfolio_with_params`を使用
   - `_run_single_backtest`関数で`_select_portfolio_with_params`を使用
   - 関数のdocstringを更新

2. `src/omanta_3rd/jobs/optimize_timeseries.py`
   - `_select_portfolio_for_rebalance_date`関数で`_select_portfolio_with_params`を使用

## まとめ

以前のスコア比例ウェイト戦略の選定ロジック（train期間で13.49%の超過リターンを達成）を採用しつつ、最終的な重みは等ウェイトを維持する実装に変更しました。これにより、選定ロジックの優位性を活かしつつ、ユーザーの要求（等ウェイト）を満たすことができます。
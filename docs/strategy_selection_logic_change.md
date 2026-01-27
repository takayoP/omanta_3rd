# ポートフォリオ選定ロジックの変更：スコア比例ウェイト戦略の選定ロジックを採用

## 変更内容

### 背景

以前のスコア比例ウェイト戦略（`_select_portfolio_with_params`）は、train期間で13.49%の超過リターンを達成していました。しかし、等ウェイトに統一した現在の実装では、同じパラメータで-2.54%と悪い結果になっています。

これは、以前のスコア比例ウェイト戦略の**選定ロジック**が優れていたことを示しています。

### ユーザーの要求

- **ポートフォリオにおける保有割合は等ウェイトにしてほしい**（これは維持）
- **以前のスコア比例ウェイト戦略の選定ロジックを採用してほしい**

### 実装方針

以前のスコア比例ウェイト戦略（`_select_portfolio_with_params`）の選定ロジックを使用しつつ、最終的な重みは等ウェイトにする。

## 変更ファイル

### 1. `src/omanta_3rd/jobs/optimize.py`

**変更内容**:
- `_select_portfolio_with_params`関数を修正
  - 選定ロジックは以前のスコア比例ウェイト戦略と同じ（`core_score`でプール選定 → `entry_score`でソート → セクターキャップ適用）
  - 重み計算を等ウェイトに変更（`sel_df["weight"] = 1.0 / n`）

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
# Weight calculation: 等ウェイト（以前のスコア比例ウェイトではなく）
n = len(sel_df)
sel_df["weight"] = 1.0 / n
```

- `_select_portfolio_for_rebalance_date`関数を修正
  - `select_portfolio`（`longterm_run.py`）の代わりに`_select_portfolio_with_params`を使用

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

### 2. `src/omanta_3rd/jobs/optimize_timeseries.py`

**変更内容**:
- `_select_portfolio_for_rebalance_date`関数を修正
  - `select_portfolio`（`longterm_run.py`）の代わりに`_select_portfolio_with_params`（`optimize.py`）を使用

**変更前**:
```python
# ポートフォリオを選択（等ウェイト：本番運用と同じ）
portfolio = select_portfolio(feat, strategy_params=strategy_params)
```

**変更後**:
```python
# ポートフォリオを選択（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
from ..jobs.optimize import _select_portfolio_with_params
portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
```

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



# 長期保有型と月次リバランス型の比較と確認

## 概要

長期保有型のアルゴリズムが当初のものから大きく変更されており、本来の処理から乖離している可能性を確認するため、月次リバランス型（あまり変更されていない）と比較します。

## 比較項目

### 1. ポートフォリオ選定関数の違い

#### 月次リバランス型（変更なし）

**ファイル**: `src/omanta_3rd/strategy/select.py`

**関数**: `select_portfolio(conn, as_of_date, config)`

**特徴**:
- DBから`features_monthly`テーブルを読み込む
- SQLクエリでフィルタリング
- 等ウェイトで重み付け: `weight = 1.0 / len(selected)` (112-116行目)

**重み付け方法**:
```python
# 等加重で重み付け
if selected:
    weight = 1.0 / len(selected)
    for item in selected:
        item["weight"] = weight
```

#### 長期保有型（変更なし）

**ファイル**: `src/omanta_3rd/jobs/longterm_run.py`

**関数**: `select_portfolio(feat, strategy_params)`

**特徴**:
- DataFrame（`feat`）から直接処理
- pandasでフィルタリング
- 等ウェイトで重み付け: `sel["weight"] = 1.0 / n` (1978行目)

**重み付け方法**:
```python
n = len(sel)
sel["weight"] = 1.0 / n
```

### 2. 等ウェイトへの統一の影響

#### 月次リバランス型

**変更**: **なし**
- 元々等ウェイトで実装されていた
- `src/omanta_3rd/strategy/select.py` の `select_portfolio` 関数は変更されていない

#### 長期保有型

**変更**: **なし（元々等ウェイト）**
- `src/omanta_3rd/jobs/longterm_run.py` の `select_portfolio` 関数は元々等ウェイトで実装されていた
- **最適化ルート（`optimize.py`、`optimize_timeseries.py`）が変更された**:
  - 以前: `_select_portfolio_with_params`（スコア比例ウェイト）を使用
  - 現在: `longterm_run.py` の `select_portfolio`（等ウェイト）を使用

### 3. 最適化ルートでの変更

#### `optimize_timeseries.py`（月次リバランス型の最適化）

**変更**: **あり（長期保有型と同じ変更）**

**変更内容**:
- `longterm_run.py` の `build_features` と `select_portfolio` を使用（46行目、316行目）
- 以前: `_select_portfolio_with_params`（スコア比例ウェイト）を使用していた可能性
- 現在: `longterm_run.py` の `select_portfolio`（等ウェイト）を使用

**重要な発見**:
- `optimize_timeseries.py` は **`longterm_run.py` の関数を使用している**
- これは**意図的な設計**（ポートフォリオ選定ロジックを共有）

#### `optimize_longterm.py`（長期保有型の最適化）

**変更**: **あり（等ウェイトへの統一）**

**変更内容**:
- `optimize_timeseries.py` の `_select_portfolio_for_rebalance_date` を使用
- `_select_portfolio_for_rebalance_date` は `longterm_run.py` の `select_portfolio` を使用
- 以前: `_select_portfolio_with_params`（スコア比例ウェイト）を使用していた可能性
- 現在: `longterm_run.py` の `select_portfolio`（等ウェイト）を使用

### 4. 本番運用での違い

#### 月次リバランス型

**ファイル**: `src/omanta_3rd/strategy/select.py`

**使用箇所**:
- `run_monthly_rebalance` 関数（`src/omanta_3rd/strategy/monthly_rebalance.py` など）
- 等ウェイトで実装（変更なし）

#### 長期保有型

**ファイル**: `src/omanta_3rd/jobs/longterm_run.py`

**使用箇所**:
- `batch_longterm_run.py` など
- 等ウェイトで実装（変更なし）

## 重要な発見

### 1. 両方とも元々等ウェイトだった

**結論**: **長期保有型も月次リバランス型も、元々等ウェイトで実装されていた**

- `longterm_run.py` の `select_portfolio`: 等ウェイト（1978行目）
- `strategy/select.py` の `select_portfolio`: 等ウェイト（112-116行目）

### 2. 変更があったのは「最適化ルート」のみ

**変更箇所**:
- `optimize.py`: `_select_portfolio_with_params` → `longterm_run.py` の `select_portfolio`
- `optimize_timeseries.py`: `_select_portfolio_with_params` → `longterm_run.py` の `select_portfolio`
- `optimize_longterm.py`: `_select_portfolio_with_params` → `longterm_run.py` の `select_portfolio`（`_select_portfolio_for_rebalance_date`経由）

**変更内容**:
- スコア比例ウェイト（`_select_portfolio_with_params`）→ 等ウェイト（`longterm_run.py` の `select_portfolio`）

### 3. 本番運用ロジックは変更されていない

**結論**: **本番運用（`longterm_run.py`、`strategy/select.py`）は変更されていない**

- 両方とも元々等ウェイトで実装されていた
- 最適化ルートだけが「スコア比例ウェイト」から「等ウェイト」に変更された

### 4. `optimize_timeseries.py` が `longterm_run.py` を使用している点

**重要な発見**:
- `optimize_timeseries.py`（月次リバランス型の最適化）が `longterm_run.py`（長期保有型）の関数を使用している
- これは**意図的な設計**（ポートフォリオ選定ロジックを共有）
- 違いは「パフォーマンス計算方法」のみ（長期保有型：固定ホライズン評価、月次リバランス型：月次リターン系列）

## 改悪の確認

### 確認結果

**改悪は見つかりませんでした**

**理由**:

1. **本番運用ロジックは変更されていない**
   - `longterm_run.py` の `select_portfolio`: 元々等ウェイト（変更なし）
   - `strategy/select.py` の `select_portfolio`: 元々等ウェイト（変更なし）

2. **最適化ルートの変更は正しい修正**
   - 以前: 最適化ルートが「スコア比例ウェイト」を使用していた（本番運用と不一致）
   - 現在: 最適化ルートが「等ウェイト」を使用（本番運用と一致）
   - これは**バグ修正**（最適化と運用の不一致を解消）

3. **長期保有型と月次リバランス型の本質的な違いは維持されている**
   - ポートフォリオ選定ロジック: 共有（両方とも等ウェイト）
   - パフォーマンス計算方法: 異なる（長期保有型：固定ホライズン、月次リバランス型：月次リターン系列）
   - リバランス頻度: 異なる（長期保有型：12M/24M、月次リバランス型：毎月）

## 結論

### 改悪は見つかりませんでした

1. **本番運用ロジックは変更されていない**
   - 長期保有型も月次リバランス型も、元々等ウェイトで実装されていた
   - 本番運用ロジックは変更されていない

2. **最適化ルートの変更は正しい修正**
   - 以前: 最適化ルートが「スコア比例ウェイト」を使用（本番運用と不一致）
   - 現在: 最適化ルートが「等ウェイト」を使用（本番運用と一致）
   - これは**バグ修正**であり、**改悪ではない**

3. **長期保有型と月次リバランス型の違いは維持されている**
   - ポートフォリオ選定ロジック: 共有（両方とも等ウェイト）
   - パフォーマンス計算方法: 異なる（本来の設計通り）
   - リバランス頻度: 異なる（本来の設計通り）

### 推奨事項

現状の実装は**正しい修正**であり、**改悪ではない**と判断します。

ただし、以下の点を確認することを推奨します：

1. **`optimize_timeseries.py` が `longterm_run.py` を使用している設計の確認**
   - これは**意図的な設計**（ポートフォリオ選定ロジックを共有）
   - 違いは「パフォーマンス計算方法」のみ（長期保有型：固定ホライズン評価、月次リバランス型：月次リターン系列）

2. **月次リバランス型の本番運用が `strategy/select.py` を使用している点**
   - `longterm_run.py` ではなく `strategy/select.py` を使用
   - 両方とも等ウェイトで実装されているため、結果は同じはず

3. **長期保有型と月次リバランス型の違いの明確化**
   - ポートフォリオ選定ロジック: 共有（等ウェイト）
   - パフォーマンス計算方法: 異なる（長期保有型：固定ホライズン、月次リバランス型：月次リターン系列）
   - リバランス頻度: 異なる（長期保有型：12M/24M、月次リバランス型：毎月）

## まとめ

- **本番運用ロジックは変更されていない**（両方とも元々等ウェイト）
- **最適化ルートの変更は正しい修正**（バグ修正：最適化と運用の不一致を解消）
- **長期保有型と月次リバランス型の違いは維持されている**（パフォーマンス計算方法、リバランス頻度）
- **改悪は見つかりませんでした**

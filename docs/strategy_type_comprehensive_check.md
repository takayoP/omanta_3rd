# 戦略タイプの総点検：長期保有型 vs 月次リバランス型

## 確認目的

`optimize_longterm.py`が`optimize_timeseries.py`の`_run_single_backtest_portfolio_only`を使用している点について、混同がないか総点検します。

## 確認結果

### 1. `_run_single_backtest_portfolio_only`の役割

**結論：これは「ポートフォリオ選定のみ」を行う関数です。**

- **入力**: `rebalance_date`, `strategy_params`, `entry_params`
- **出力**: ポートフォリオDataFrame（`code`, `weight`, `core_score`, `entry_score`等）
- **処理内容**:
  1. `build_features`で特徴量を構築
  2. `select_portfolio`でポートフォリオを選定
  3. **パフォーマンス計算は行わない**

### 2. 長期保有型と月次リバランス型の違い

#### ポートフォリオ選定ロジック
- **共通**: 両方とも`build_features` + `select_portfolio`を使用
- **理由**: ポートフォリオ選定ロジック自体は同じ（等ウェイト、同じフィルタリング、同じセクターキャップ等）

#### パフォーマンス計算方法
- **長期保有型** (`optimize_longterm.py`):
  - 固定ホライズン評価（例：24ヶ月保有）
  - `calculate_portfolio_performance`を使用（`optimize_longterm.py:378行目`）
  - 評価指標：累積リターン、年率リターン、最大ドローダウン等

- **月次リバランス型** (`optimize_timeseries.py`):
  - 月次リバランス戦略（ti→ti+1の月次リターン）
  - `calculate_timeseries_returns_from_portfolios`を使用（`optimize_timeseries.py:190行目`）
  - 評価指標：Sharpe ratio等

### 3. `optimize_longterm.py`での使用状況

```python
# optimize_longterm.py:257-263行目
portfolio = _run_single_backtest_portfolio_only(
    rebalance_date,
    strategy_params_dict,
    entry_params_dict,
    features_dict.get(rebalance_date) if features_dict else None,
    prices_dict.get(rebalance_date) if prices_dict else None,
)

# その後、calculate_longterm_performance内で：
# - 固定ホライズン評価（horizon_months、318-321行目）
# - calculate_portfolio_performanceを使用（378行目）
# - 長期保有型の評価指標を計算
```

### 4. `optimize_timeseries.py`での使用状況

```python
# optimize_timeseries.py:155行目付近
portfolio = _run_single_backtest_portfolio_only(...)

# その後、objective_timeseries内で：
# - calculate_timeseries_returns_from_portfoliosを使用（190行目）
# - 月次リバランス型の評価指標を計算
```

## 結論

### **意図的な共用（混同ではない）**

理由：
1. **ポートフォリオ選定ロジックは共通**
   - 長期保有型も月次リバランス型も、同じ`build_features` + `select_portfolio`を使用
   - ポートフォリオ選定のロジック自体に違いはない

2. **違いは「パフォーマンス計算方法」のみ**
   - 長期保有型：固定ホライズン評価
   - 月次リバランス型：月次リターン系列

3. **`_run_single_backtest_portfolio_only`は「ポートフォリオ選定のみ」を行う関数**
   - パフォーマンス計算は行わない
   - 両方で使用可能

## 推奨事項

### 1. 関数名の明確化（オプション）

`_run_single_backtest_portfolio_only`という名前は「backtest」を含んでいるが、実際には「ポートフォリオ選定のみ」を行う関数です。より明確な名前に変更することを推奨します：

- `_select_portfolio_for_rebalance_date`（推奨）
- `_create_portfolio_for_rebalance_date`

### 2. ドキュメントの追加

`_run_single_backtest_portfolio_only`のdocstringに、以下の点を明記することを推奨します：

- この関数は「ポートフォリオ選定のみ」を行う
- パフォーマンス計算は行わない
- 長期保有型と月次リバランス型の両方で使用可能
- 違いは「パフォーマンス計算方法」のみ


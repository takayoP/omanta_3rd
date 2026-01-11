# 統一完了：compare側とoptimize側の実装を統一（等ウェイト）

## 実施内容

**案B（最小変更）**で対応し、optimize側を本番運用と同じ等ウェイト（`select_portfolio`）に統一しました。

## 修正ファイル

### 1. `src/omanta_3rd/jobs/optimize.py`

#### `_run_single_backtest`関数（324-390行目）
- **変更前**: `build_features`にパラメータを渡さず、`_select_portfolio_with_params`を使用（スコアベースの重み）
- **変更後**: `build_features`に`strategy_params`と`entry_params`を渡し、`select_portfolio`を使用（等ウェイト）

```python
# 変更前
feat = build_features(conn, rebalance_date)
portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)

# 変更後
feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
portfolio = select_portfolio(feat, strategy_params=strategy_params)
```

#### `_run_single_backtest_portfolio_only`関数（414-462行目）
- 同様の変更を適用

### 2. `src/omanta_3rd/jobs/optimize_timeseries.py`

#### `_run_single_backtest_portfolio_only`関数（259-359行目）
- **変更前**: `build_features`にパラメータを渡さず、`entry_score`を再計算し、`_select_portfolio_with_params`を使用
- **変更後**: `build_features`に`strategy_params`と`entry_params`を渡し、`entry_score`の再計算を削除し、`select_portfolio`を使用

```python
# 変更前
feat = build_features(conn, rebalance_date)
# entry_scoreを再計算（311-339行目）
feat = _calculate_entry_score_with_params(feat, prices_win, entry_params)
portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)

# 変更後
feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
# entry_scoreの再計算を削除（build_featuresで計算済み）
portfolio = select_portfolio(feat, strategy_params=strategy_params)
```

#### 不要なインポートを削除（62-69行目）
- `_entry_score_with_params`
- `_calculate_entry_score_with_params`
- `_select_portfolio_with_params`

### 3. `src/omanta_3rd/jobs/optimize_longterm.py`

#### 不要なインポートを削除（47-52行目）
- `_entry_score_with_params`
- `_calculate_entry_score_with_params`
- `_select_portfolio_with_params`

**注意**: `optimize_longterm.py`は`optimize_timeseries.py`の`_run_single_backtest_portfolio_only`を使用しているため、修正は不要でした。

## 統一の効果

### 変更前
- **compare側（本番運用）**: `select_portfolio`（等ウェイト）を使用
- **optimize側（最適化）**: `_select_portfolio_with_params`（スコアベースの重み）を使用
- **問題**: 最適化と運用で戦略が異なるため、最適化結果が運用で再現できない

### 変更後
- **compare側（本番運用）**: `select_portfolio`（等ウェイト）を使用
- **optimize側（最適化）**: `select_portfolio`（等ウェイト）を使用
- **統一**: 最適化と運用で同じ戦略を使用するため、最適化結果が運用で再現できる

## 次のステップ

### 1. 修正後の確認（必須）

同じparamsファイル、同じ`rebalance_date`（2023-01-31）で、以下の項目が一致することを確認：

- `params_hash`: 一致（既に確認済み）
- `portfolio_hash`: **一致すること（これがゴール）**
- `selected_codes`: 一致
- `weights`: 一致（12銘柄なら全部 1/12）
- `entry_date / exit_date`: 一致
- `total_return_pct / topix_return_pct`: 一致

### 2. 再最適化（推奨）

統一前の最適化結果は「スコア加重戦略」を前提に最適化されたものなので、統一後は「等ウェイト戦略」で再最適化することを推奨します：

- λ比較（Step 2-A/2-B）をやり直し
- 本番再最適化（`reoptimize_all_candidates.py`）を実行

これは「手戻り」ではなく、やっと「運用する戦略」を正しく最適化できる状態になった、ということです。

## 技術的な詳細

### なぜこの変更で動作するのか

1. **`build_features`が`core_score`と`entry_score`を計算している**
   - `build_features`（longterm_run.py）は1741-1747行目で`core_score`を計算
   - 1676-1689行目で`entry_score`を計算
   - 両方とも`out_cols`に含まれている（1900-1908行目）

2. **`select_portfolio`は計算済みスコアを使用**
   - `select_portfolio`（longterm_run.py）は`build_features`で計算済みの`core_score`と`entry_score`を使用
   - 等ウェイトで重みを計算（`sel["weight"] = 1.0 / n`、1978行目）

3. **`_select_portfolio_with_params`の再計算は冗長だった**
   - `_select_portfolio_with_params`（optimize.py）は`core_score`と`entry_score`を再計算していたが、パラメータが同じなら結果は同じ
   - スコアベースの重みで計算していた（`sel_df["weight"] = sel_df["core_score"] / total_score`、310行目）

### コードの簡潔性

- `_select_portfolio_with_params`の再計算ロジック（217-265行目）が不要になった
- `optimize_timeseries.py`の`entry_score`再計算ロジック（311-339行目）が不要になった
- コードがより簡潔になり、保守性が向上した

## まとめ

- **統一完了**: compare側とoptimize側の実装を統一（等ウェイト）
- **修正ファイル**: `optimize.py`、`optimize_timeseries.py`、`optimize_longterm.py`（インポートのみ）
- **関数名変更**: `_run_single_backtest_portfolio_only` → `_select_portfolio_for_rebalance_date`（役割を明確化）
- **次のステップ**: 修正後の確認（`portfolio_hash`の一致）と再最適化


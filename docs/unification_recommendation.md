# 統一方法の推奨（確定版）

## 比較結果

### 重要な違い

1. **`core_score`の計算**
   - `select_portfolio`: `build_features`で計算済みの`core_score`を使用
   - `_select_portfolio_with_params`: `core_score`を再計算（217-265行目）

2. **`entry_score`の計算**
   - `select_portfolio`: `build_features`で計算済みの`entry_score`を使用
   - `_select_portfolio_with_params`: `entry_score`を再計算（177-197行目）、ただし既に計算済みならスキップ

3. **重みの計算**（唯一の本質的な違い）
   - `select_portfolio`: 等ウェイト（`sel["weight"] = 1.0 / n`）
   - `_select_portfolio_with_params`: スコアベース（`sel_df["weight"] = sel_df["core_score"] / total_score`）

### 結論

**案B（最小変更）で対応可能です。**

理由：
1. **銘柄選定ロジックは同じ**
   - フィルタリング、プール選択、エントリースコアでのソート、セクターキャップ、最小銘柄数チェックは同じ

2. **スコア計算の違いは問題にならない**
   - `build_features`が`core_score`と`entry_score`を計算している
   - `select_portfolio`は計算済みのスコアを使用する前提
   - パラメータが同じなら、`build_features`で計算されたスコアと`_select_portfolio_with_params`で再計算したスコアは同じ

3. **重みの計算だけが異なる**
   - これは`select_portfolio`の1978行目を変更するだけで解決
   - または、optimize側で`select_portfolio`を使用する

## 推奨対応：案B（最小変更）

optimize側で`_select_portfolio_with_params`の代わりに`select_portfolio`を使用する。

ただし、以下の点に注意：
1. `build_features`で`entry_score`が計算済みであること（確認済み：`entry_params`を受け取って計算）
2. `build_features`で`core_score`が計算済みであること（確認が必要）

### 実装手順

1. `optimize_timeseries.py`の`_run_single_backtest_portfolio_only`を修正
   - `_select_portfolio_with_params`の代わりに`select_portfolio`を使用
   - `build_features`に`entry_params`を渡す必要がある（既に渡している）

2. 2023-01-31で`portfolio_hash`が一致するか確認

3. 一致すれば、統一完了


# entry_score/core_scoreキャッシュ問題の修正

## 問題の概要

最適化において、`entry_score`（および`core_score`）がキャッシュされ、trialごとに異なるパラメータを試してもスコアが変わらない問題が発生していました。

### 問題の原因

1. **FeatureCacheでのスコア計算**
   - `FeatureCache.warm()`が`build_features`を呼び出す際、`entry_params`を渡していない
   - デフォルトの`PARAMS`で計算された`entry_score`がキャッシュに保存される

2. **スキップロジック**
   - `_select_portfolio_with_params`が「`entry_score`が既に存在する場合は再計算をスキップ」するロジックを持っていた
   - キャッシュされた`entry_score`が存在するため、trialごとに異なる`entry_params`を試しても再計算されない

3. **最適化の破綻**
   - Optunaがtrialごとに`entry_params`を変えても、実際には同じ`entry_score`が使用される
   - 探索が無意味になり、最適化結果が崩れる

## 修正内容

### 1. FeatureCacheでスコアを削除

`src/omanta_3rd/backtest/feature_cache.py`の`_build_features_single`メソッドを修正：

```python
# 重要: entry_scoreとcore_scoreは最適化でtrialごとに異なるparamsで計算されるため、
# キャッシュには含めない（削除する）
# これにより、_select_portfolio_with_paramsで常に正しいparamsで再計算される
score_columns_to_remove = ["entry_score", "core_score"]
removed_columns = [col for col in score_columns_to_remove if col in feat.columns]
if removed_columns:
    feat = feat.drop(columns=removed_columns)
    print(f"[FeatureCache._build_features_single] スコアを削除しました（{rebalance_date}）: {removed_columns}")
```

### 2. _select_portfolio_with_paramsで常に再計算

`src/omanta_3rd/jobs/optimize.py`の`_select_portfolio_with_params`関数を修正：

```python
# entry_scoreを計算（パラメータ化版）
# 重要: 最適化ではtrialごとに異なるentry_paramsが使用されるため、
# キャッシュされたentry_scoreは使用しない（常に再計算）
# FeatureCacheではentry_scoreを削除しているため、常に再計算される
print(f"        [_select_portfolio] entry_scoreを計算します（entry_paramsに基づく）")
# ... 価格データを取得して再計算 ...
```

## 影響範囲

### 修正が必要なファイル

1. `src/omanta_3rd/backtest/feature_cache.py`
   - `_build_features_single`: スコアを削除

2. `src/omanta_3rd/jobs/optimize.py`
   - `_select_portfolio_with_params`: スキップロジックを削除、常に再計算

### 影響を受けないファイル

- `src/omanta_3rd/jobs/optimize_timeseries.py`
  - `_select_portfolio_for_rebalance_date`は`_select_portfolio_with_params`を呼び出すだけなので、修正不要

- `src/omanta_3rd/jobs/optimize_longterm.py`
  - 同様に`_select_portfolio_with_params`を使用しているため、修正の恩恵を受ける

## 確認事項

### 修正前の問題

- 最適化で`entry_params`を変えても`entry_score`が変わらない
- 最適化結果が期待通りに改善しない
- キャッシュされたスコアが使用される

### 修正後の期待動作

- `entry_score`は常に`entry_params`に基づいて再計算される
- `core_score`は`_select_portfolio_with_params`内で常に再計算される（既存の実装）
- 最適化で正しくパラメータ探索が行われる

## 注意事項

1. **キャッシュの再構築**
   - 既存のキャッシュファイルには`entry_score`と`core_score`が含まれている可能性がある
   - 修正後はキャッシュを再構築することを推奨（`--force-rebuild`オプションまたはキャッシュディレクトリの削除）

2. **パフォーマンス**
   - `entry_score`の再計算は価格データの取得が必要なため、若干のオーバーヘッドが発生する
   - しかし、最適化の正確性を優先する

3. **本番運用**
   - 本番運用（`longterm_run.py`）では`FeatureCache`を使用しないため、影響なし
   - `build_features`は`entry_params`を受け取って正しく計算する

## 関連ドキュメント

- `docs/next_chat_session_prompt.md`: 次のチャットセッション用プロンプト
- `docs/system_specification_for_chatgpt_analysis.md`: システム仕様書

## 修正日

2026年1月12日


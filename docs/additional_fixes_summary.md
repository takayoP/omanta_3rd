# 追加修正と確認手順のまとめ

## 実施した追加修正

### 地雷1: 既存キャッシュ読み込み時にスコア列が残る可能性 → **修正済み**

`FeatureCache._load_cache()`メソッドで、既存キャッシュから読み込んだ場合でも`entry_score`と`core_score`を削除するように修正しました。

**修正内容**:
```python
# rebalance_dateごとに分割
features_dict = {}
for rebalance_date, group in combined_features.groupby("rebalance_date"):
    feat = group.drop(columns=["rebalance_date"]).copy()
    
    # 重要: 既存キャッシュから読み込んだ場合でも、entry_score/core_scoreを削除
    score_columns_to_remove = ["entry_score", "core_score"]
    removed_columns = [col for col in score_columns_to_remove if col in feat.columns]
    if removed_columns:
        feat = feat.drop(columns=removed_columns)
        print(f"[FeatureCache._load_cache] スコアを削除しました（{rebalance_date}）: {removed_columns}")
    
    features_dict[rebalance_date] = feat
```

**効果**: `--force-rebuild-cache`を忘れても、古いキャッシュから読み込んだ場合でも安全に使用できます。

### 地雷2: `_select_portfolio_with_params`がfeatを破壊的に変更 → **既に対応済み**

`_select_portfolio_with_params`の冒頭で`df = feat.copy()`を実行しているため、featが破壊的に変更されることはありません。

**確認済み**: 214行目で`df = feat.copy()`が実行されています。

### 地雷3: 本番・compare・optimizeの統一性 → **確認スクリプト作成**

本番運用（`longterm_run.py`の`select_portfolio`）と最適化（`_select_portfolio_with_params`）の統一性を確認するスクリプトを作成しました。

## 確認手順

### 自動検証スクリプト

`scripts/verify_cache_fix.py`を実行すると、以下の3つのチェックを自動で実行します：

1. **チェック1: キャッシュにentry_score/core_scoreが含まれていない**
   - キャッシュから読み込んだ特徴量にスコア列が含まれていないことを確認

2. **チェック2: entry_paramsを変えるとentry_scoreが変わる**
   - 異なる`entry_params`でentry_scoreの分布が変わることを確認
   - これが通れば「探索が探索になっていない」問題は解消

3. **チェック3: 同じparamsで再実行すると同じ結果になる**
   - 決定性を確認（同じparamsで同じ結果が得られる）

### 実行方法

```powershell
python scripts/verify_cache_fix.py
```

### 期待される出力

```
キャッシュ修正の検証を開始します...

================================================================================
チェック1: キャッシュにentry_score/core_scoreが含まれていないことを確認
================================================================================
[FeatureCache._load_cache] スコアを削除しました（2023-01-31）: ['entry_score', 'core_score']
✓ OK: キャッシュにスコア列は含まれていません

================================================================================
チェック2: entry_paramsを変えるとentry_scoreが変わることを確認
================================================================================
✓ OK: entry_scoreの分布が異なります（平均値の差分: 0.1234）
   entry_paramsの違いが正しく反映されています

================================================================================
チェック3: 同じparamsで再実行すると同じ結果になることを確認
================================================================================
✓ OK: 2回の実行で同じ銘柄が選定されました（12銘柄）
✓ OK: entry_scoreも一致しています（最大差分: 0.00e+00）

================================================================================
検証結果サマリー
================================================================================
✓ PASS: チェック1: キャッシュにスコア列が含まれていない
✓ PASS: チェック2: entry_paramsを変えるとentry_scoreが変わる
✓ PASS: チェック3: 同じparamsで再実行すると同じ結果になる

✓ すべてのチェックがパスしました。修正は正しく機能しています。
```

## 修正の完全性

### 修正前の問題

1. `FeatureCache.warm()`でデフォルトPARAMSの`entry_score`がキャッシュに保存される
2. `_select_portfolio_with_params`が「entry_scoreが存在するなら再計算スキップ」
3. trialごとに異なる`entry_params`を試しても、キャッシュされたスコアが使用される

### 修正後の動作

1. ✅ `FeatureCache._build_features_single`: 新規構築時にスコア列を削除
2. ✅ `FeatureCache._load_cache`: 既存キャッシュ読み込み時にもスコア列を削除
3. ✅ `_select_portfolio_with_params`: スキップロジックを削除し、常に再計算
4. ✅ `_select_portfolio_with_params`: `df = feat.copy()`でfeatを保護

### 防御の多層化

- **第1層**: 新規キャッシュ構築時にスコア列を削除
- **第2層**: 既存キャッシュ読み込み時にもスコア列を削除（`--force-rebuild`忘れ対策）
- **第3層**: `_select_portfolio_with_params`で常に再計算（念のため）

これにより、どの経路からキャッシュが読み込まれても安全です。

## 次のステップ

1. **検証スクリプトを実行**
   ```powershell
   python scripts/verify_cache_fix.py
   ```

2. **最適化を実行（キャッシュ再構築付き）**
   ```powershell
   python -m omanta_3rd.jobs.optimize_longterm `
     --start 2018-01-31 `
     --end 2024-12-31 `
     --study-type C `
     --n-trials 200 `
     --train-end-date 2023-12-31 `
     --as-of-date 2024-12-31 `
     --horizon-months 24 `
     --lambda-penalty 0.00 `
     --force-rebuild-cache
   ```

3. **結果を確認**
   - 最適化ログで「entry_scoreを計算します」が表示されること
   - trialごとに異なる`entry_params`が使用されていること
   - 最適化結果が以前と異なる（改善または現実的な結果）こと

## 注意事項

修正後は、以前「見かけ上うまくいっていた」最適化が：

- trainが下がる / ばらつく可能性がある
- ただしtrialの多様性が増える（探索がちゃんと効く）

という挙動になることがあります。これは**悪化ではなく、バグが取れて現実が見えた**可能性があります。


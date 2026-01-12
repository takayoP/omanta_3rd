# キャッシュ再構築手順

## 概要

`entry_score`と`core_score`のキャッシュ問題を修正したため、既存のキャッシュを再構築する必要があります。

## 方法1: `--force-rebuild-cache`オプションを使用（推奨）

最適化実行時に`--force-rebuild-cache`オプションを指定すると、既存のキャッシュを無視して再構築します。

### 例: Study Cの最適化を実行（キャッシュ再構築付き）

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type C \
  --n-trials 200 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --force-rebuild-cache
```

## 方法2: キャッシュディレクトリを手動で削除

特定の期間のキャッシュのみを削除する場合：

### Windows (PowerShell)

```powershell
# 特定の期間のキャッシュを削除（例: 2018-01-31_2024-12-30）
Remove-Item "cache/features/features_2018-01-31_2024-12-30_v1.parquet"
Remove-Item "cache/features/prices_2018-01-31_2024-12-30_v1.parquet"
Remove-Item "cache/features/metadata_2018-01-31_2024-12-30_v1.json"

# または、すべてのキャッシュを削除
Remove-Item "cache/features/*" -Recurse
```

### Linux/Mac

```bash
# 特定の期間のキャッシュを削除
rm cache/features/features_2018-01-31_2024-12-30_v1.parquet
rm cache/features/prices_2018-01-31_2024-12-30_v1.parquet
rm cache/features/metadata_2018-01-31_2024-12-30_v1.json

# または、すべてのキャッシュを削除
rm -rf cache/features/*
```

## 確認事項

### 修正前の問題

- キャッシュに`entry_score`と`core_score`が含まれていた
- 最適化でtrialごとに異なる`entry_params`を試しても、キャッシュされたスコアが使用される
- パラメータ探索が正しく機能しない

### 修正後の動作

- `FeatureCache`で`entry_score`と`core_score`を削除
- `_select_portfolio_with_params`で常に`entry_params`に基づいて再計算
- 最適化で正しくパラメータ探索が行われる

## 推奨手順

1. **最適化を実行する前にキャッシュを再構築**
   - `--force-rebuild-cache`オプションを使用するか、該当期間のキャッシュを削除

2. **最適化を実行**
   - 修正後のコードで最適化を実行
   - trialごとに異なる`entry_params`が正しく反映されることを確認

3. **結果を確認**
   - 最適化結果が改善されているか確認
   - パラメータ探索が正しく行われているか確認（Optunaの可視化など）

## 注意事項

- キャッシュの再構築には時間がかかります（期間によって異なりますが、数分〜数十分）
- 既存のキャッシュを削除すると、次回の最適化実行時に自動的に再構築されます
- `--force-rebuild-cache`オプションを使用すると、既存のキャッシュがあっても再構築されます


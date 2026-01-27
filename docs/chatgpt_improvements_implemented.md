# ChatGPTフィードバックに基づく改善実装

## 実装日
2026年1月21日

## 実装した改善

### 1. ✅ RSI/BBの方向をcategoricalパラメータ化（最重要）

**問題点**:
- `trial.number % 2`で方向を決定していた
- 並列数や途中再開でtrial番号の割り当てが変わり、再現性が壊れる
- Optunaが方向を学習できない

**修正内容**:
```python
# 修正前
if trial.number % 2 == 0:
    rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)  # 順張り
else:
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)  # 逆張り

# 修正後
rsi_direction = trial.suggest_categorical("rsi_direction", ["momentum", "reversal"])
if rsi_direction == "momentum":
    rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)  # 順張り
else:  # reversal
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)  # 逆張り
```

**効果**:
- ✅ 再現性が向上（同じseedで同じ結果が得られる）
- ✅ Optunaが方向を学習できる
- ✅ 並列実行や途中再開でも結果が一貫

### 2. ✅ 目的関数をmedian/trimmed meanに変更（過学習対策）

**問題点**:
- meanは外れ値に弱く、trainだけ「数本の大当たり」で上がる
- p10はポートフォリオ数が少ないと不安定

**修正内容**:
- `objective_type`パラメータを追加（"mean", "median", "trimmed_mean"）
- `calculate_longterm_performance`から`annual_excess_returns_list`を返すように修正
- 目的関数で`objective_type`に応じて集計方法を変更

```python
# 目的関数の集計方法を選択
if objective_type == "median":
    base_excess = median_excess  # 中央値（外れ値に強い）
elif objective_type == "trimmed_mean":
    base_excess = trim_mean(annual_excess_returns_list, 0.1)  # 上下10%カット
else:  # "mean"
    base_excess = mean_excess  # 平均（従来通り）
```

**コマンドライン引数**:
```powershell
--objective-type mean          # 平均（デフォルト）
--objective-type median        # 中央値（推奨）
--objective-type trimmed_mean  # 上下10%カット平均
```

**効果**:
- ✅ 過学習のリスクを低減
- ✅ 外れ値に強い目的関数
- ✅ 後方互換性を維持（デフォルトはmean）

## 未実装の改善（今後の検討事項）

### 3. コア重みの正規化を改善

**問題点**:
- 個々のサンプル下限を0.01にしていても、正規化後は0.01未満になり得る

**改善案**:
- Dirichlet分布を使用する
- または、正規化後に最小比率を保証

**優先度**: 中（現状でも動作はしている）

### 4. 評価設計の改善

**問題点**:
- テストが「ある1年の12本（2022年など）」でサンプル数が少ない
- 評価がブレやすい

**改善案**:
- 複数年を順にtestして平均する（時系列CV）

**優先度**: 中（現状でも動作はしている）

### 5. 並列化設定の調整

**問題点**:
- 二重並列（Optuna trial並列 + trial内バックテスト並列）が再現性と安定性の敵

**改善案**:
- どちらか片側だけ並列にする

**優先度**: 低（現状でも動作はしている）

## 確認チェックリスト

- [x] RSI/BBの方向をcategoricalパラメータ化
- [x] 目的関数をmedian/trimmed meanに変更
- [ ] 同一seedで2回回して`best_params`/`best_value`が一致するか（確認が必要）
- [ ] `direction`をcategorical化して1回回し、結果が安定するか（確認が必要）
- [ ] median目的で結果が改善するか（確認が必要）

## 使用方法

### 基本的な使用方法（median目的）

```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 `
  --end 2024-12-31 `
  --study-type A `
  --n-trials 200 `
  --objective-type median `
  --train-end-date 2023-12-31 `
  --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --lambda-penalty 0.00 `
  --n-jobs 4 `
  --bt-workers 8
```

### trimmed_mean目的

```powershell
--objective-type trimmed_mean
```

**注意**: `trimmed_mean`を使用する場合は`scipy`が必要です。

## 期待される効果

1. **再現性の向上**: 同じseedで同じ結果が得られる
2. **過学習の低減**: median/trimmed_mean目的により、外れ値に強い
3. **Optunaの学習改善**: 方向をパラメータとして学習できる

## 次のステップ

1. 修正後のコードで最適化を再実行
2. 同一seedで2回実行して再現性を確認
3. median目的とmean目的の結果を比較
4. 必要に応じて、残りの改善（3-5）を実装


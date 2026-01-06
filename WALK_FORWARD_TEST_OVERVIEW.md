# Walk-Forward Analysis テスト概要

## テストの目的

長期保有型投資戦略のWalk-Forward Analysis（roll方式）を実行し、`entry_score`パラメータの最適化ロジック改善の効果を検証します。

## 重要な変更点

### 1. `entry_score`パラメータ探索の改善

#### 変更前の問題点
- RSIとBB Z-scoreのパラメータに順序制約（`rsi_max > rsi_base`, `bb_z_max > bb_z_base`）があり、逆張り戦略（`max < base`）を探索できなかった
- 制約違反時に`TrialPruned`でスキップされ、指定した試行回数（例：30回）が満たされない可能性があった

#### 変更後の改善
- **対称探索**: `rsi_base`/`rsi_max`と`bb_z_base`/`bb_z_max`を独立に同一範囲からサンプリング
  - RSI: `[15.0, 85.0]`の範囲から独立にサンプリング
  - BB Z-score: `[-3.5, 3.5]`の範囲から独立にサンプリング
- **最小幅制約**: パラメータの幅が小さすぎる場合を防止
  - RSI: `abs(rsi_max - rsi_base) >= 20.0`
  - BB Z-score: `abs(bb_z_max - bb_z_base) >= 1.0`
- **再サンプリング**: 制約違反時は`TrialPruned`でスキップせず、制約を満たすまで再サンプリング
  - 最大100回まで再試行
  - 再サンプリング回数を`trial.user_attrs`に記録
- **再現性の確保**: 再サンプリング時に`trial.number`と`trial._trial_id`からシードを生成し、`np.random.RandomState`を使用

### 2. シード設定の改善

- `walk_forward_longterm.py`: 既にシード設定済み（`TPESampler(seed=seed)`）
- `optimize_longterm.py`: `main`関数でOptunaのsamplerにシードを設定するように修正
- 再サンプリング時もtrial固有のシードを使用して再現性を確保

## テスト設定

### 実行コマンド
```bash
python walk_forward_longterm.py \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --horizon 12 \
  --fold-type roll \
  --n-trials 30 \
  --study-type C \
  --train-min-years 2.0 \
  --holdout-eval-year 2025 \
  --n-jobs-fold 1 \
  --n-jobs-optuna 1 \
  --seed 42
```

### パラメータ設定

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| `--start` | `2020-01-01` | データ開始日 |
| `--end` | `2025-12-31` | データ終了日 |
| `--horizon` | `12` | ホライズン（月数） |
| `--fold-type` | `roll` | Fold分割方式（roll方式） |
| `--n-trials` | `30` | 最適化試行回数（各fold） |
| `--study-type` | `C` | スタディタイプ（A/B統合・広範囲探索） |
| `--train-min-years` | `2.0` | 最小Train期間（年） |
| `--holdout-eval-year` | `2025` | 評価終了年でホールドアウトを指定 |
| `--seed` | `42` | 乱数シード（再現性のため固定） |
| `--n-jobs-fold` | `1` | Fold間の並列数（安定優先） |
| `--n-jobs-optuna` | `1` | Optunaの並列数（安定優先） |

### `entry_score`パラメータ探索範囲

| パラメータ | 探索範囲 | 最小幅制約 | 説明 |
|-----------|---------|-----------|------|
| `rsi_base` | `[15.0, 85.0]` | - | RSI基準値（順張り/逆張り両対応） |
| `rsi_max` | `[15.0, 85.0]` | `abs(rsi_max - rsi_base) >= 20.0` | RSI最大値（順張り/逆張り両対応） |
| `bb_z_base` | `[-3.5, 3.5]` | - | BB Z-score基準値（順張り/逆張り両対応） |
| `bb_z_max` | `[-3.5, 3.5]` | `abs(bb_z_max - bb_z_base) >= 1.0` | BB Z-score最大値（順張り/逆張り両対応） |

**注意**: `rsi_max < rsi_base`や`bb_z_max < bb_z_base`の場合、逆張り戦略（売られすぎ買い）になります。

## 期待される成果物

1. **`walk_forward_longterm_12M_roll_evalYear2025.json`**
   - 各foldの最適化結果とテスト期間のパフォーマンス
   - 集計結果（平均、標準偏差など）

2. **`params_by_fold.json`**
   - 各foldの最適パラメータ（`best_params`）

3. **`params_operational.json`**
   - 暫定運用パラメータ（全foldの結果から選択）

## 検証ポイント

### 1. 試行回数の確認
- 各foldで`n_trials=30`の試行が確実に実行されているか
- 制約違反によるスキップが発生していないか（`trial.user_attrs`の`rsi_resampled`/`bb_resampled`を確認）

### 2. パラメータ探索の多様性
- 順張り戦略（`rsi_max > rsi_base`, `bb_z_max > bb_z_base`）と逆張り戦略（`rsi_max < rsi_base`, `bb_z_max < bb_z_base`）の両方が探索されているか
- `trial.user_attrs`の`rsi_direction`/`bb_direction`を確認

### 3. パフォーマンスの改善
- 前回のテスト結果（2022-2023期間でパフォーマンスが悪かった）と比較
- 特に2022-2023期間のfoldでの改善を確認

### 4. 再現性の確認
- 同じシード（42）で再実行した場合、同じ結果が得られるか

## 技術的な実装詳細

### 再サンプリングロジック

```python
# trialのシードに基づいた再現可能な乱数生成器を作成
trial_seed = hash((trial.number, getattr(trial, '_trial_id', trial.number))) % (2**31)
rng = np.random.RandomState(trial_seed)

# 最小幅制約を満たすまで再サンプリング
while abs(rsi_max - rsi_base) < rsi_min_width and retry_count < max_retries:
    rsi_base = rng.uniform(RSI_LOW, RSI_HIGH)
    rsi_max = rng.uniform(RSI_LOW, RSI_HIGH)
    retry_count += 1
```

### `entry_score`計算ロジック

`entry_score`は以下の式で計算されます：

```python
# BB Z-scoreスコア（sigmoidで平滑化）
if abs(bb_z_max - bb_z_base) >= bb_z_min_width:
    raw_score = (z - bb_z_base) / (bb_z_max - bb_z_base)
    k = 3.0
    sigmoid_score = 1.0 / (1.0 + np.exp(-k * (raw_score - 0.5)))
    bb_score = sigmoid_score

# RSIスコア（sigmoidで平滑化）
if abs(rsi_max - rsi_base) >= rsi_min_width:
    raw_score = (rsi - rsi_base) / (rsi_max - rsi_base)
    k = 3.0
    sigmoid_score = 1.0 / (1.0 + np.exp(-k * (raw_score - 0.5)))
    rsi_score = sigmoid_score

# 期間別スコア（20日、60日、90日）の最大値
entry_score = max(period_scores)
```

**順張り戦略**（`rsi_max > rsi_base`）: RSIが高いほど高スコア
**逆張り戦略**（`rsi_max < rsi_base`）: RSIが低いほど高スコア

## 前回のテスト結果との比較

### 前回の問題点
- 2022-2023期間でパフォーマンスが悪かった
- `entry_score`と`profit_growth`が負の相関を示していた
- 順張り戦略のみが探索され、逆張り戦略が探索されていなかった可能性

### 今回の改善点
- 順張り/逆張りの両方を対称に探索
- 最小幅制約により、パラメータの幅が小さすぎる場合を防止
- Sigmoid平滑化により、スコアが0/1に張り付くのを防止
- 試行回数を確実に実行（スキップなし）

## 実行時間の目安

- 各fold: 約30試行 × 試行あたりの計算時間
- 全fold数: データ期間と`train_min_years`に依存
- 並列化: `n_jobs_fold=1`, `n_jobs_optuna=1`のため、逐次実行

## 注意事項

1. **メモリ使用量**: 各trialで大量のメモリを使用する可能性があるため、並列数を1に設定
2. **実行時間**: 逐次実行のため、完了まで時間がかかる可能性がある
3. **再現性**: シード（42）を固定しているため、同じ条件で再実行すれば同じ結果が得られる

## 次のステップ

テスト完了後、以下を確認：
1. 各foldのパフォーマンス結果
2. 最適パラメータの分布（順張り/逆張りの割合）
3. 2022-2023期間の改善状況
4. 再サンプリングの発生頻度（`rsi_resampled`/`bb_resampled`の有無）










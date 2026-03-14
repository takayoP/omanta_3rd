# Study Aのbest近傍での局所探索実装計画

## 分析結果の要約

### Study A vs Study Bの比較結果

1. **最適化の到達点**
   - Study A: Best Value ≈4.3まで到達
   - Study B: Best Value ≈2.0で頭打ち

2. **ハイパラ重要度**
   - Study A: `roe_min` 0.29, `w_size` 0.17, `rsi_base` 0.13（分散）
   - Study B: `w_size` 0.43（集中）

3. **Study Aのbestパラメータ**
   - `roe_min`: 0.0236
   - `w_size`: 0.336（正規化後）
   - その他: `w_quality` 0.437, `w_value` 0.143, `w_growth` 0.074, `w_record_high` 0.010

## 局所探索の設計方針

### 探索するパラメータ（重要度が高い）

1. **`roe_min`**: 0.00〜0.06 くらいで刻む（best: 0.0236）
2. **`w_size`**: 0.25〜0.45 くらいで刻む（best: 0.336）

### 固定するパラメータ（重要度が低い）

以下のパラメータは、Study Aのbest値で固定：
- `w_forward_per`: 0.3335（重要度低）
- `bb_weight`: 0.3921（重要度低: 0.04）
- `liquidity_quantile_cut`: 0.2100（重要度低）

### 中間的な扱い（小幅探索）

以下のパラメータは、best値の±10%程度で探索：
- `w_quality`: 0.437 ± 0.04 → [0.40, 0.48]
- `w_value`: 0.143 ± 0.01 → [0.13, 0.15]
- `w_growth`: 0.074 ± 0.01 → [0.06, 0.08]
- `w_record_high`: 0.010 ± 0.005 → [0.005, 0.015]
- `rsi_base`: 78.99 ± 5.0 → [74, 84]
- `rsi_max`: 67.02 ± 5.0 → [62, 72]
- `bb_z_base`: -2.83 ± 0.3 → [-3.1, -2.5]
- `bb_z_max`: -2.22 ± 0.3 → [-2.5, -1.9]

## 実装方法

### オプション1: 新しいstudy_type "A_local"を追加

**メリット**:
- 既存のStudy A/B/Cと明確に区別できる
- 実装がシンプル

**デメリット**:
- study_typeが増える

### オプション2: `local_search`フラグを追加

**メリット**:
- study_typeを増やさない
- 柔軟性が高い

**デメリット**:
- 実装が複雑になる可能性

## 推奨実装（オプション1）

新しいstudy_type "A_local"を追加し、Study Aのbest近傍で探索する実装を行います。

### 探索範囲の定義

```python
if study_type == "A_local":
    # 重要度が高いパラメータ: 広めに探索
    roe_min = trial.suggest_float("roe_min", 0.00, 0.06)
    w_size = trial.suggest_float("w_size", 0.25, 0.45)
    
    # 重要度が中程度のパラメータ: 小幅探索
    w_quality = trial.suggest_float("w_quality", 0.40, 0.48)
    w_value = trial.suggest_float("w_value", 0.13, 0.15)
    w_growth = trial.suggest_float("w_growth", 0.06, 0.08)
    w_record_high = trial.suggest_float("w_record_high", 0.005, 0.015)
    
    # 重要度が低いパラメータ: 固定
    w_forward_per = 0.3335  # best値で固定
    bb_weight = 0.3921  # best値で固定
    liquidity_quantile_cut = 0.2100  # best値で固定
    
    # RSI/BB: 小幅探索
    rsi_base = trial.suggest_float("rsi_base", 74.0, 84.0)
    rsi_max = trial.suggest_float("rsi_max", 62.0, 72.0)
    bb_z_base = trial.suggest_float("bb_z_base", -3.1, -2.5)
    bb_z_max = trial.suggest_float("bb_z_max", -2.5, -1.9)
```

## 実行コマンド例

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A_local \
  --n-trials 100 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 4 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

## 期待される効果

1. **探索次元の削減**: 13パラメータ → 約10パラメータ（3つ固定）
2. **探索範囲の縮小**: 重要度の高いパラメータに集中
3. **到達率の向上**: 「谷に入れない」問題の再発抑制

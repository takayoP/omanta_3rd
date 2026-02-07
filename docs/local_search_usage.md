# Study Aのbest近傍での局所探索（A_local）使用方法

## 概要

`study_type="A_local"`を使用することで、Study Aのbestパラメータの近傍で局所探索を行います。

## 設計方針

### 探索するパラメータ（重要度が高い）

1. **`roe_min`**: 0.00〜0.06（best: 0.0236）
2. **`w_size`**: 0.25〜0.45（best: 0.336、正規化後）

### 小幅探索するパラメータ（重要度が中程度）

- `w_quality`: 0.40〜0.48（best: 0.437）
- `w_value`: 0.13〜0.15（best: 0.143）
- `w_growth`: 0.06〜0.08（best: 0.074）
- `w_record_high`: 0.005〜0.015（best: 0.010）
- `rsi_base`: 74.0〜84.0（best: 78.99）
- `rsi_max`: 62.0〜72.0（best: 67.02）
- `bb_z_base`: -3.1〜-2.5（best: -2.83）
- `bb_z_max`: -2.5〜-1.9（best: -2.22）

### 固定するパラメータ（重要度が低い）

- `w_forward_per`: 0.3335（best値で固定）
- `bb_weight`: 0.3921（best値で固定）
- `liquidity_quantile_cut`: 0.2100（best値で固定）
- `rsi_direction`: "reversal"（best値が逆張りなので固定）
- `bb_direction`: "reversal"（best値が逆張りなので固定）

## 実行コマンド

### 基本実行

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

### 推奨実行手順

#### ステップ1: ウォームアップ（TPEが初期点を学習できる状態を作る）

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A_local \
  --n-trials 30 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 4 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

#### ステップ2: 本番探索（必要なら並列を増やす）

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
  --n-jobs 4 \
  --bt-workers 8 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

## 期待される効果

1. **探索次元の削減**: 13パラメータ → 約10パラメータ（3つ固定）
2. **探索範囲の縮小**: 重要度の高いパラメータに集中
3. **到達率の向上**: 「谷に入れない」問題の再発抑制

## 注意事項

1. **初期点の投入**: `--initial-params-json`で1/21のbest_paramsを初期点として投入することを推奨します。
2. **並列化**: ウォームアップ段階では`n_jobs=1`で実行し、TPEが初期点を学習できる状態を作ります。
3. **目的関数**: `mean`でまず「1/21の谷に戻れる」ことを確認してから、`median`/`trimmed_mean`を別studyとして試すことを推奨します。

## 参考

- `docs/local_search_implementation_plan.md`: 実装計画の詳細
- `docs/next_steps_after_diagnosis.md`: 次のステップのガイド

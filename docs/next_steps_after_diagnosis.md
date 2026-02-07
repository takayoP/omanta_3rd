# 診断結果に基づく次のステップ

## 診断結果サマリー

### ✅ 確定したこと
1. **固定ホライズン評価は正常**: 評価設計に問題はない
2. **未来リークなし**: 実装は正しい
3. **ケースAが確定**: 1/21のbest_paramsが現在でも良い（Test期間で4.07%）

### 原因の特定
- **戦略の「良い領域」は存在する**
- **1/29の最適化がそこに到達できていない**
- 原因は「探索空間の変更/サンプラーの挙動/並列/乱数/制約」の可能性が高い

---

## 推奨される実行順序

### ステップ1: 1/21のbest_paramsを初期点として投入（最優先）

1/21のbest_paramsを初期点としてOptunaに投入することで、「良い谷」に確実に到達できます。

**実行コマンド**:
```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 200 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 4 \
  --bt-workers 8 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

**期待される効果**:
- 1/21のbest_paramsが初期点として投入され、少なくとも1回は評価される（並列時は完了順は前後し得る）
- TPEサンプラーがその近傍を探索する
- より良い結果が得られる可能性が高い

**注意**: 並列実行時（`n_jobs>1`）は、初期点が「最初に完了する」とは限りません。キューには入りますが、実行・完了順は前後し得ます。

---

### ステップ2: 探索空間を1/21のbest_paramsの近傍に絞る（局所探索）

1/21のbest_paramsの各パラメータに対して、±幅を設定して探索範囲を絞ります。

**注意**: この機能は現在実装されていません。必要に応じて、`objective_longterm`関数内で探索範囲を調整してください。

**例**:
```python
# 1/21のbest_params
best_params_1_21 = {
    "w_quality": 0.4416,
    "rsi_base": 78.99,
    # ...
}

# 近傍探索（±10%）
w_quality = trial.suggest_float("w_quality", 
    best_params_1_21["w_quality"] * 0.9, 
    best_params_1_21["w_quality"] * 1.1)
```

---

### ステップ3: 目的関数をmedian/trimmed_meanに変更（別Studyとして）

外れ値に強い目的関数を使用することで、より安定した最適化が可能です。

**重要**: 目的関数を変えると最適解も変わるため、**別Studyとして**実行することを推奨します。

**実行コマンド（別Study名を指定）**:
```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 200 \
  --study-name optimization_longterm_studyA_median_20260129 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type median \
  --n-jobs 4 \
  --bt-workers 8 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

**選択肢**:
- `mean`: 平均（デフォルト、外れ値に弱い）
- `median`: 中央値（外れ値に強い）
- `trimmed_mean`: 上下10%カット平均（外れ値に強い）

**推奨順序**:
1. まず`mean`で「1/21の谷に戻れる」ことを確認（再現性回復）
2. 次に`median`/`trimmed_mean`を別studyとして回し直して比較

---

## 1/21のbest_paramsの詳細

```json
{
  "w_quality": 0.4416,
  "w_growth": 0.0744,
  "w_record_high": 0.0101,
  "w_size": 0.3388,
  "w_value": 0.1448,
  "w_forward_per": 0.3335,
  "roe_min": 0.0236,
  "bb_weight": 0.3921,
  "liquidity_quantile_cut": 0.2100,
  "rsi_base": 78.99,
  "rsi_max": 67.02,
  "bb_z_base": -2.83,
  "bb_z_max": -2.22
}
```

**方向**:
- RSI: 逆張り（rsi_base > rsi_max）
- BB: 逆張り（bb_z_base < bb_z_max、両方負）

**パフォーマンス**:
- Train期間: 4.38%（元の結果）→ 4.11%（再評価）
- Test期間: 4.29%（元の結果）→ 4.07%（再評価）

---

## 推奨される実行手順（2段階起動）

warm startをTPEに効かせたい場合、以下の2段階起動が推奨されます。

### ステップ0: 初期点が正しく評価されるか確認

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 1 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 1 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

**確認ポイント**:
- 初期点のvalueが想定どおり（train≈4.1%）になればOK
- enqueued trialがpruneされず完走する

### ステップ1: ウォームアップ（TPEが初期点を学習できる状態を作る）

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
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

**注意**: 並列は片側だけ（Optuna並列 or BT並列のどちらか）にします。二重並列（OptunaもBTも並列）は、探索順序・リソース競合・再現性の面で不利になりやすいです。

### ステップ2: 本番探索（必要なら並列を増やす）

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 200 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 4 \
  --bt-workers 8 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

ここで初めて`n_jobs`を上げます（または`bt_workers`を上げます）。

---

## 注意事項

1. **初期点の投入**: `enqueue_trial`で投入されたtrialは、少なくとも1回は評価されます。並列実行時は完了順が前後し得ます。

2. **探索範囲の調整**: 初期点を投入しても、探索範囲が広すぎると、良い領域から離れる可能性があります。必要に応じて、探索範囲を調整してください。

3. **並列化の影響**: 並列実行により、探索順序が変わる可能性があります。再現性を重視する場合は、`n_jobs=1`, `bt_workers=1`で実行してください。

4. **目的関数の変更**: `median`/`trimmed_mean`への切替は「別Study」として扱うのが安全です。目的関数を変えると最適解も変わるため、同じstudyに混ぜるとログ解釈が難しくなります。

---

## 参考: 診断結果の詳細

詳細は`docs/diagnosis_results.md`を参照してください。

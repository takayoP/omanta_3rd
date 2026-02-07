# 本番反映前のゲートチェックリスト

## 目的

Study A_localの結果を本番運用に反映する前に、以下のゲートを通過する必要があります。

## 現在の状況

- **Train期間（最良値）**: 5.2007%
- **Test期間（平均）**: 6.0341%
- **Test期間（勝率）**: 100%（12/12）
- **評価設計**: 固定ホライズン評価・未来リークなし（確認済み）

## ゲートチェックリスト

### Gate 1: 再現性（局所探索が"偶然の当たり"じゃない確認）

**目的**: 同じ設定でseedを変えて複数回実行し、Test期間の平均超過リターンが極端にブレないことを確認

**実行方法**:
```bash
# seed=42（既に実行済み）
# seed=123で実行
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 `
  --end 2024-12-31 `
  --study-type A_local `
  --n-trials 100 `
  --train-end-date 2023-12-31 `
  --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --lambda-penalty 0.00 `
  --objective-type mean `
  --n-jobs 1 `
  --bt-workers 4 `
  --random-seed 123 `
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json

# seed=456で実行
# seed=789で実行
# seed=999で実行
```

**判定基準**:
- [ ] 3〜5回実行して、Test期間の平均超過リターンが**±1%ポイント以内**でブレない
- [ ] ブレが大きい場合は、探索が不安定（将来も急変しやすい）可能性がある

**スクリプト**: `scripts/gate1_reproducibility_check.ps1`（作成予定）

---

### Gate 2: コスト感度

**目的**: 取引コストを考慮した場合でも、Test期間の平均超過リターンがプラスを維持することを確認

**実行方法**:
```bash
# cost_bps=10で評価
python scripts/evaluate_params_with_cost.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260131_220810.json `
  --test-dates 2022-01-31,2022-02-28,2022-03-31,2022-04-28,2022-05-31,2022-06-30,2022-07-29,2022-08-31,2022-09-30,2022-10-31,2022-11-30,2022-12-30 `
  --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --cost-bps 10

# cost_bps=25で評価
# cost_bps=50で評価
```

**判定基準**:
- [ ] `cost_bps=10`でTest平均超過が**プラスを維持**
- [ ] `cost_bps=25`でTest平均超過が**プラスを維持**（長期なら10〜25bpsでも耐えるのが目安）
- [ ] `cost_bps=50`でTest平均超過が**プラスを維持**（余裕があれば）

**スクリプト**: `scripts/gate2_cost_sensitivity.py`（作成予定）

---

### Gate 3: 別期間での検証（2025は温存したまま）

**目的**: 2022だけが良い（たまたま）を除外するため、別の期間でも検証

**実行方法**:

#### 追加検証①: Test=2021（as_of=2023-12-31）

```bash
python scripts/evaluate_params_other_period.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260131_220810.json `
  --test-start-date 2021-01-31 `
  --test-end-date 2021-12-30 `
  --as-of-date 2023-12-31 `
  --horizon-months 24
```

#### 追加検証②: Test=2020（as_of=2022-12-31）

```bash
python scripts/evaluate_params_other_period.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260131_220810.json `
  --test-start-date 2020-01-31 `
  --test-end-date 2020-12-30 `
  --as-of-date 2022-12-31 `
  --horizon-months 24
```

**判定基準**:
- [ ] Test=2021で平均超過リターンが**プラスを維持**
- [ ] Test=2020で平均超過リターンが**プラスを維持**
- [ ] 2022だけが良い（たまたま）を除外できる

**スクリプト**: `scripts/gate3_other_periods_validation.py`（作成予定）

---

### Gate 4: 最終GO/NO-GO（ホールドアウト2025を1回だけ使う）

**目的**: 2025ホールドアウトを1回だけ評価して最終判定

**重要**: ここで改善のために再チューニングしたら、その瞬間ホールドアウトじゃなくなるので注意

**実行方法**:
```bash
python scripts/evaluate_params_holdout_2025.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260131_220810.json `
  --holdout-start-date 2025-01-31 `
  --holdout-end-date 2025-12-31 `
  --as-of-date 2025-12-31 `
  --horizon-months 24
```

**判定基準**:
- [ ] 2025ホールドアウトで平均超過リターンが**プラスを維持**
- [ ] パラメータを凍結（params_hash/logic_version固定）
- [ ] ここで再チューニングしない（ホールドアウトの意味がなくなる）

**スクリプト**: `scripts/gate4_holdout_2025.py`（作成予定）

---

### Gate 5: 運用実装の一致（再発防止）

**目的**: optimize≠本番の再発を防ぐため、同一rebalance_dateでselected_codes/weights/portfolio_hashが一致することを確認

**実行方法**:
```bash
python scripts/gate5_implementation_consistency.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260131_220810.json `
  --rebalance-date 2022-01-31 `
  --compare-with-production
```

**判定基準**:
- [ ] 同一rebalance_dateで`selected_codes`が一致
- [ ] 同一rebalance_dateで`weights`が一致（等ウェイト運用ならweightsも一致）
- [ ] 同一rebalance_dateで`portfolio_hash`が一致

**スクリプト**: `scripts/gate5_implementation_consistency.py`（作成予定）

---

## 優先順位

### 最優先（必須）
- **Gate 2**: コスト感度（実運用では必須）
- **Gate 4**: 2025ホールドアウト（本番反映の最終判定）

### 推奨（時間があれば）
- **Gate 1**: 再現性（探索の安定性確認）
- **Gate 3**: 別期間での検証（2022だけが良いを除外）

### 運用開始前（必須）
- **Gate 5**: 運用実装の一致（再発防止）

---

## パラメータの凍結

Gate 4を通過したら、以下のパラメータを凍結します：

### 最終パラメータセット（Study A_local best）

```json
{
  "w_quality": 0.4463,
  "w_value": 0.1312,
  "w_growth": 0.0566,
  "w_record_high": 0.0054,
  "w_size": 0.3605,
  "w_forward_per": 0.3335,
  "w_pbr": 0.6665,
  "roe_min": 0.0302,
  "liquidity_quantile_cut": 0.2100,
  "rsi_base": 79.46,
  "rsi_max": 70.28,
  "rsi_direction": "reversal",
  "bb_z_base": -3.07,
  "bb_z_max": -2.17,
  "bb_direction": "reversal",
  "bb_weight": 0.3921,
  "rsi_weight": 0.6079,
  "rsi_min_width": 10.0,
  "bb_z_min_width": 0.5
}
```

### params_hashに含めるべきキー一覧

以下のキーをparams_hashに含める：
- `w_quality`, `w_value`, `w_growth`, `w_record_high`, `w_size`
- `w_forward_per`, `w_pbr`
- `roe_min`, `liquidity_quantile_cut`
- `rsi_base`, `rsi_max`, `rsi_direction`
- `bb_z_base`, `bb_z_max`, `bb_direction`
- `bb_weight`, `rsi_weight`
- `rsi_min_width`, `bb_z_min_width`

---

## 参考

- Study A_local結果: `optimization_result_optimization_longterm_studyA_local_20260131_220810.json`
- 1/21のStudy A結果: `optimization_result_optimization_longterm_studyA_20260121_204615.json`

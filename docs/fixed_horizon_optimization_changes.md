# 固定ホライズン最適化への修正内容

## 修正概要

従来の「ロールで（実質as_ofまで）運用する形での最適化」から、「固定ホライズンで評価する最適化」に変更しました。

これにより、**目的関数（最適化で最大化したもの）と実運用で欲しいもの（12M/24M固定窓の成績）が一致**します。

---

## 主な変更点

### 1. `split_rebalance_dates()`関数の修正

**変更内容:**
- `horizon_months`と`require_full_horizon`パラメータを追加
- train期間では`eval_end <= train_end_date`を満たすリバランス日だけを使用

**効果:**
- 時系列リーク対策: train期間のポートフォリオの評価終点がtrain期間を超えない
- 固定ホライズン制約: 各ポートフォリオは`rebalance_date + horizon_months`で評価

**実装:**
```python
def split_rebalance_dates(
    ...,
    horizon_months: Optional[int] = None,
    require_full_horizon: bool = True,
) -> Tuple[List[str], List[str]]:
    # train期間では`eval_end <= train_end_date`を満たすものだけを使用
    if require_full_horizon and horizon_months is not None:
        train_end_dt = datetime.strptime(train_end_date, "%Y-%m-%d")
        train_dates = []
        for rebalance_date in candidate_train_dates:
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
            if eval_end_dt <= train_end_dt:
                train_dates.append(rebalance_date)
```

---

### 2. 目的関数の改善（下振れ罰の追加）

**変更内容:**
- 平均超過リターンに加えて、P10超過リターンによる下振れ罰を追加
- 目的関数: `平均超過 - 0.1 × min(0, P10超過)`

**効果:**
- 平均だけを押し上げる過学習を抑制
- 下振れリスク（P10）を考慮した最適化

**実装:**
```python
# 目的関数: 平均超過 - 下振れ罰
mean_excess = perf["mean_annual_excess_return_pct"]
p10_excess = perf.get("p10_annual_excess_return_pct", 0.0)
downside_penalty = 0.1 * min(0.0, p10_excess)  # P10が負の場合のみペナルティ
objective_value = mean_excess + downside_penalty
```

---

### 3. `calculate_longterm_performance()`の改善

**変更内容:**
- P10、P25、minの超過リターンを返り値に追加
- 下振れ罰の計算に必要な指標を提供

**効果:**
- 目的関数で下振れ罰を計算可能に
- 最適化結果の分析が容易に

---

### 4. `main()`関数での固定ホライズン制約の適用

**変更内容:**
- `split_rebalance_dates()`呼び出し時に`horizon_months`と`require_full_horizon=True`を渡す

**効果:**
- train期間では`eval_end <= train_end_date`を満たすリバランス日だけを使用

---

## 最適化の実行方法

### 基本的な実行（12M候補）

```bash
python -m omanta_3rd.jobs.reoptimize_all_candidates \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --n-trials 200 \
  --train-end-date 2022-12-31
```

### パラメータ説明

- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD、24Mの場合は自動調整される可能性あり）
- `--as-of-date`: 評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）
- `--train-end-date`: 学習期間の終了日（YYYY-MM-DD、Noneの場合は"2022-12-31"）
  - **重要**: 固定ホライズン制約により、train期間では`eval_end <= train_end_date`を満たすリバランス日だけを使用
  - 例: `train_end_date="2022-12-31"`、`horizon_months=24`の場合、train期間では`rebalance_date + 24M <= 2022-12-31`を満たすものだけを使用

---

## 最適化の設計（推奨）

ChatGPTの推奨に基づいた設計：

### 期間分割（例）

- **train**: 2020-2022（`eval_end <= 2022-12-31`を満たすリバランス日）
  - 12Mの場合: 2020-01-31 ～ 2021-12-29（eval_end <= 2022-12-31）
  - 24Mの場合: 2020-01-31 ～ 2020-12-30（eval_end <= 2022-12-31）
- **test**: 2023-2025（固定ホライズン評価）
- **holdout**: （将来の拡張: 完全未使用期間を確保）

### 目的関数

- 平均超過リターン - 0.1 × min(0, P10超過リターン)
  - 係数0.1は小さめで、下振れリスクを軽く考慮する程度
  - より強い下振れ対策が必要な場合は係数を調整可能

---

## 期待される効果

### 1. 目的関数と運用設計の一致

- 固定ホライズンで最適化 → 固定ホライズンで評価
- Step2/Step3の比較結果が安定

### 2. リーク疑いの減少

- `eval_end = rb + horizon`が最適化でも評価でも一貫
- train/test分割で時系列リーク対策

### 3. 過学習の抑制

- 下振れ罰により、平均だけを押し上げる過学習を抑制
- P10を考慮した、より堅実な最適化

---

## 注意点

### 1. train期間のサンプル数

固定ホライズン制約により、特に24Mの場合、train期間のサンプル数が減少する可能性があります。

**対策:**
- `start_date`を早める（例: 2018-01-01）
- `train_end_date`を調整する

### 2. holdout期間の確保

現状はtrain/testの2分割ですが、将来的にはholdout期間を完全未使用にすることを推奨します。

**拡張案:**
- train: 2020-2022（`eval_end <= 2022-12-31`）
- val: 2023（`eval_end <= 2023-12-31`）
- holdout: 2024-2025（完全未使用）

---

## 修正ファイル

1. `src/omanta_3rd/jobs/optimize_longterm.py`
   - `split_rebalance_dates()`: 固定ホライズン制約を追加
   - `objective_longterm()`: 下振れ罰を追加
   - `calculate_longterm_performance()`: P10/min超過リターンを返り値に追加

2. `src/omanta_3rd/jobs/reoptimize_all_candidates.py`
   - 既に対応済み（`train_end_date`のデフォルトが"2022-12-31"）

---

## 次のステップ

1. **固定ホライズンで再最適化を実行**
   ```bash
   python -m omanta_3rd.jobs.reoptimize_all_candidates \
     --start 2020-01-01 \
     --end 2025-12-31 \
     --n-trials 200 \
     --train-end-date 2022-12-31
   ```

2. **再最適化後のStep2/Step3を再実行**
   - 固定ホライズン最適化 → 固定ホライズン比較の一本化
   - 結果の改善を確認

3. **（オプション）holdout期間を追加**
   - val/holdoutの3分割に拡張
   - より厳密なOOS評価

---

**作成日**: 2026-01-10  
**作成者**: AI Assistant  
**目的**: 固定ホライズン最適化への修正内容を文書化


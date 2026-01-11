# λ比較の方法と既存結果の活用可能性

## 結論

**現状では、既存の最適化結果から再採点することはできません。**
理由：各trialの`mean_excess`と`p10_excess`がOptunaのstudy DBに保存されていないため。

**確認結果**:
- `optuna_operational_24M_20260109.db`: `mean_excess`と`p10_excess`が保存されていない ❌
- `optuna_12M_momentum_20260109.db`: `mean_excess`と`p10_excess`が保存されていない ❌

**今後の最適化からは可能になります**（修正を実装したため）

ただし、**既に最適化が完了しているstudy DBには適用されません**。

---

## 現状の確認結果

### 現在保存されている情報

Optunaのstudy DB（例：`optuna_operational_24M_20260109.db`）には以下の情報が保存されています：

- **`trial.value`**: 目的関数の値（`objective_value = mean_excess + downside_penalty`）
  - 注意：これはλが適用された後の値なので、元の`mean_excess`と`p10_excess`を分離できない

- **`trial.user_attrs`**: 
  - `rsi_direction`: RSIの方向（順張り/逆張り）
  - `bb_direction`: BBの方向（順張り/逆張り）
  - `rsi_width`: RSIの幅
  - `bb_z_width`: BB Z-scoreの幅

- **`trial.params`**: 最適化パラメータ（rsi_base, rsi_max, bb_z_base, bb_z_max等）

### 保存されていない情報

- **`mean_excess`**: 平均年率超過リターン（%ポイント）
- **`p10_excess`**: P10年率超過リターン（%ポイント）
- **`n_periods`**: P10算出に使ったサンプル数

これらの情報がないため、既存のstudy DBから「λを変えて再採点」することはできません。

---

## λ比較の2つの方法（ChatGPTの説明）

### ① 既存の最適化結果を「採点し直すだけ」（すぐ終わる）

**前提条件**: 各trialの`mean_excess`と`p10_excess`が保存されていること

**方法**: 各trialについて、異なるλ値で目的関数を再計算

```python
# 各trialについて、異なるλ値で目的関数を再計算
for trial in study.trials:
    mean_excess = trial.user_attrs.get("mean_excess")
    p10_excess = trial.user_attrs.get("p10_excess")
    
    # λ=0.00で再採点
    objective_00 = mean_excess  # 下振れ罰なし
    
    # λ=0.05で再採点
    downside_penalty_05 = 0.05 * min(0, p10_excess)
    objective_05 = mean_excess + downside_penalty_05
```

**メリット**:
- **非常に高速**（最適化を実行しない）
- 既存の最適化結果を活用できる

**デメリット**:
- 各trialの`mean_excess`と`p10_excess`が保存されている必要がある（現状は保存されていない）
- λを変えたときに、Optunaが「その目的関数で良い内部パラメータ」を探すわけではない
  - つまり、λ=0.00で最適化した結果を、λ=0.05の目的関数で再採点するだけ
  - 本来なら、λ=0.05で最適化すれば、Optunaが「λ=0.05の目的関数で良いパラメータ」を探す

### ② λごとに「最適化を回す」（時間がかかる）

**方法**: 各λ値（0.00, 0.03, 0.05, 0.08）で、目的関数を変えて最適化を実行

**メリット**:
- **λを変えたときに、Optunaが「その目的関数で良い内部パラメータ」を探す**

**デメリット**: **毎回最適化が走る** = 時間がかかる（4本で約4倍の時間）

---

## 推奨アプローチ（ChatGPT推奨）

### Step 1（すぐ終わる、ただし現状は不可）: 既存結果の再採点

まず①で、手元の結果から：
- λ=0.00, 0.03, 0.05, 0.08で再採点
- 「どのλで最良trialが変わるか」を確認

**ただし、現状は`mean_excess`と`p10_excess`が保存されていないため、この方法は使用できません。**

### Step 2（本番）: λごとに最適化を実行（2段階アプローチ推奨）

計算コストと判断のブレを減らすため、**2段階で進めることを推奨します**。

#### Step 2-A: まずλ=0.00と0.05で比較（推奨）

**目的**: λが下振れリスクに与える影響を確認

**実行方法**:
```bash
python -m omanta_3rd.jobs.compare_lambda_penalties \
    --params-id operational_24M \
    --start-date 2018-01-01 \
    --end-date 2025-12-31 \
    --as-of-date 2025-12-31 \
    --train-end-date 2022-12-31 \
    --lambda-values 0.00 0.05 \
    --n-trials 200
```

**所要時間**: 2つのλ値で約2倍の時間（例：100分）

**判断基準**:
- λ=0.05がλ=0.00より優れている場合 → Step 2-Bへ
- λ=0.00がλ=0.05より優れている場合 → λ=0.00で確定

#### Step 2-B: 有望な場合、4点で比較（λ=0.00, 0.03, 0.05, 0.08）

**目的**: 最適なλ値を決定

**実行方法**:
```bash
python -m omanta_3rd.jobs.compare_lambda_penalties \
    --params-id operational_24M \
    --start-date 2018-01-01 \
    --end-date 2025-12-31 \
    --as-of-date 2025-12-31 \
    --train-end-date 2022-12-31 \
    --lambda-values 0.00 0.03 0.05 0.08 \
    --n-trials 200
```

**所要時間**: 4つのλ値で約4倍の時間（例：200分、約3.3時間）

**判断基準**:
- 各λ値の`test_mean_excess_return_pct`と`p10_excess_return_pct`を比較
- リスクとリターンのバランスを考慮して最適なλを選択

---

## 将来的な改善案：既存結果の再採点を可能にする

### 現状の問題

既存のstudy DBには、各trialの`mean_excess`と`p10_excess`が保存されていないため、再採点ができません。

### 改善案

`trial.set_user_attr`で、各trialの`mean_excess`と`p10_excess`を保存するように修正します。

**実装場所**: `src/omanta_3rd/jobs/optimize_longterm.py`の`objective_longterm`関数

**実装内容**:
```python
# 各trialのuser_attrsに保存
trial.set_user_attr("mean_excess", mean_excess)
trial.set_user_attr("p10_excess", p10_excess)
trial.set_user_attr("n_periods", n_periods)
```

**効果**:
- 今後の最適化結果から「既存結果の再採点」が可能になります
- ただし、**過去に完了したtrial（既存DB）には適用されません**

---

## まとめ

### 現状（既存のstudy DB）

- **既存の最適化結果から再採点することはできない**
  - 理由: `mean_excess`と`p10_excess`が保存されていない
  - 確認済み: `optuna_operational_24M_20260109.db`、`optuna_12M_momentum_20260109.db`ともに保存されていない ❌

- **今後のλ比較**: `compare_lambda_penalties.py`を使用して、各λ値で最適化を実行する必要がある
  - **推奨アプローチ（2段階）**: まずλ=0.00と0.05で比較（Step 2-A）→ 有望なら4点で比較（Step 2-B）
  - 所要時間: 
    - Step 2-A: 2つのλ値で約2倍の時間（例：100分）
    - Step 2-B: 4つのλ値で約4倍の時間（例：200分、約3.3時間）

### 今後の改善（実装済み）

- **修正を実装済み**: `trial.set_user_attr`で`mean_excess`と`p10_excess`を保存するように修正しました
  - 今後の最適化結果から「既存結果の再採点」が可能になります
  - ただし、**過去に完了したtrial（既存DB）には適用されません**

**注意（再採点の限界）**:
- 再採点は「探索済みtrialの中で並べ替える」だけなので、**λを変えたときに本来見つかる解が探索されていない**可能性がある
- 推奨アプローチ: まず再採点で当たりをつける（高速）→ 必要なら、そのλで少しだけ追加trialを回す（補完）

---

## 2025年1月の修正内容

### 1. 計算方法の統一

**問題点**: 最適化の目的関数と評価指標で異なる計算方法を使用していた
- **最適化**: `(1 + 累積超過)^(1/t) - 1` （累積超過を年率化）
- **評価**: `(1+total)^(1/t) - (1+topix)^(1/t)` （年率化してから差を取る）

これにより、最適化で最大化している指標と評価で使う指標が異なり、最適化が遠回りになる可能性がありました。

**解決策**: 目的関数と評価指標を「年率化してから差を取る」方法に統一

**実装場所**:
- `src/omanta_3rd/jobs/optimize_longterm.py`: `calculate_longterm_performance`関数（464-493行目）

**変更内容**:
- 変更前: 累積超過リターンを年率化 `(1 + excess)^(1/t) - 1`
- 変更後: 年率総リターンと年率TOPIXリターンを計算して差を取る `(1+total)^(1/t) - (1+topix)^(1/t)`

**効果**:
- 最適化の目的関数と評価指標が同じ計算方法を使用
- 最適化と評価の不一致が解消
- 実運用に近い指標（CAGR型）で最適化が行われる

### 2. test_datesの統一

**問題点**: `compare_lambda_penalties`関数で、`test_mean_excess_return_pct`と`avg_annualized_excess_return_pct`で異なる`test_dates`を使用していた

- **`test_mean_excess_return_pct`**: `optimize_longterm_main`内で決定された`test_dates`（24Mの場合は`end_date - 24months`から決定）
- **`avg_annualized_excess_return_pct`**: `compare_lambda_penalties`内で生成された`test_dates`（元の`end_date`から決定）

これにより、同じλ値でも異なる`test_dates`で計算され、結果が比較不能になっていました（例：15.66% vs 1.49%）。

**解決策**: `optimize_longterm_main`で実際に使われた`test_dates`を`compare_lambda_penalties`でも使用

**実装内容**:

1. **`optimize_longterm_main`の修正**（`src/omanta_3rd/jobs/optimize_longterm.py` 1257-1270行目）
   - 使用した`test_dates`と`train_dates`を結果JSONに保存
   - `test_dates_first`、`test_dates_last`、`num_test_periods`も保存

2. **`compare_lambda_penalties`の修正**（`src/omanta_3rd/jobs/compare_lambda_penalties.py` 492-516行目）
   - 最適化結果から`test_dates`を読み込んで使用
   - 後方互換性: `test_dates`がない場合は従来の方法で生成

3. **結果への追加**（同ファイル 545-558行目）
   - 結果に`test_dates_first`、`test_dates_last`、`num_test_periods`を保存（検証用）

**効果**:
- `test_mean_excess_return_pct`と`avg_annualized_excess_return_pct`が同じ`test_dates`で計算される
- 結果に`test_dates`情報を保存し、再発を検知しやすくなる
- 後方互換性: 既存の最適化結果（`test_dates`がない場合）でも動作

**参考**: ChatGPTの指摘（2025年1月）に基づく修正。詳細はChatGPTとの対話記録を参照。

# train期間の超過リターンが低い問題の調査

## 問題

train期間での超過リターンが非常に低い：

**以前の結果（2026年1月11日、`as_of_date=2025-12-31`）**：
- train超過: **13.49%** (λ=0.00), **8.80%** (λ=0.05)

**現在の結果（2026年1月12日、`as_of_date=2023-12-31`）**：
- train超過: **1.44%** (λ=0.00), **0.76%** (λ=0.05)

## 重要な発見

### 1. train期間の評価で使用される`as_of_date`

`objective_longterm`関数（854行目）で`calculate_longterm_performance`を呼び出している際、`as_of_date=as_of_date`を渡しています。

この`as_of_date`は`optimize_longterm_main`で設定されており、`as_of_date`が指定されていない場合は`end_date`を使用しています（972-973行目）。

**問題点**：
- train期間の評価で、`as_of_date=end_date`（現在は2023-12-31）を使用している
- しかし、train期間では`train_end_date=2022-12-31`までを使用すべき
- **train期間の評価では、`as_of_date=train_end_date`を使用すべきではないか？**

### 2. `require_full_horizon=True`の影響

`split_rebalance_dates`関数（109-116行目）では、`require_full_horizon=True`かつ`horizon_months`が指定されている場合、train期間では`eval_end <= train_end_date`を満たすものだけを使用しています。

24Mホライズンの場合：
- `train_end_date=2022-12-31`
- train期間では`eval_end <= train_end_date`を満たすものだけを使用
- つまり、`rebalance_date + 24M <= 2022-12-31`を満たすもの
- つまり、`rebalance_date <= 2020-12-31`のものしかtrainに含まれない

しかし、`calculate_longterm_performance`では`as_of_date=2023-12-31`を使用しているため、`require_full_horizon=True`の場合、`eval_end <= as_of_date`を満たすものだけが評価されます。

24Mホライズンの場合：
- `rebalance_date <= 2020-12-31`のものは`eval_end <= 2024-12-31`となる
- `as_of_date=2023-12-31`では、`eval_end=2024-12-31`のものは`eval_end > as_of_date`のため、**評価できない**

**つまり、train期間に含まれるrebalance_dates（`rebalance_date <= 2020-12-31`）のポートフォリオは、`as_of_date=2023-12-31`では評価できない可能性があります。**

### 3. 以前の結果との比較

以前の結果（`as_of_date=2025-12-31`）の場合：
- train期間に含まれるrebalance_dates（`rebalance_date <= 2020-12-31`）のポートフォリオは、`eval_end <= 2024-12-31`となる
- `as_of_date=2025-12-31`では、`eval_end <= 2024-12-31`のものは`eval_end <= as_of_date`のため、**評価可能**

## 仮説

train期間の評価で使用される`as_of_date`が`end_date`（2023-12-31）になっているため、train期間に含まれるrebalance_dates（`rebalance_date <= 2020-12-31`）のポートフォリオが評価できない、または評価対象が大幅に制限されている可能性があります。

## 確認すべきポイント

1. **`objective_longterm`でのtrain期間の評価**
   - train期間の評価で使用される`as_of_date`は何か
   - `end_date`（2023-12-31）なのか、`train_end_date`（2022-12-31）なのか
   - 現在は`as_of_date=end_date`を使用しているが、これが問題の可能性

2. **`split_rebalance_dates`でのtrain期間のフィルタリング**
   - train期間に含まれるrebalance_datesはどれだけか
   - 24Mホライズンの場合、`train_end_date=2022-12-31`で、train期間に含まれるrebalance_datesは`rebalance_date <= 2020-12-31`のもの
   - これらのポートフォリオの`eval_end`は`<= 2024-12-31`となる
   - `as_of_date=2023-12-31`では、`eval_end <= 2023-12-31`のものだけが評価可能
   - つまり、`rebalance_date <= 2019-12-31`のものしか評価できない可能性

3. **以前の結果との比較**
   - 以前の結果（`as_of_date=2025-12-31`）では、train期間のポートフォリオが評価可能だった
   - 現在の結果（`as_of_date=2023-12-31`）では、train期間のポートフォリオが評価できない、または評価対象が大幅に制限されている可能性

## 推奨される修正

train期間の評価では、`as_of_date=train_end_date`を使用すべきです。

理由：
- train期間のポートフォリオは、`train_end_date`までに評価可能である必要がある
- `as_of_date=end_date`を使用すると、train期間のポートフォリオが評価できない、または評価対象が大幅に制限される可能性がある
- 以前の結果（`as_of_date=2025-12-31`）では、たまたま`as_of_date`が大きかったため、train期間のポートフォリオが評価可能だった

ただし、`objective_longterm`関数では`as_of_date`を受け取っているため、`optimize_longterm_main`で`as_of_date=train_end_date`を渡すか、`objective_longterm`関数内でtrain期間の評価時は`train_end_date`を使用するように修正する必要があります。

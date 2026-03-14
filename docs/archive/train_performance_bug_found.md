# train期間の超過リターンが低い問題：バグ発見

## 問題

train期間での超過リターンが非常に低い：

**以前の結果（2026年1月11日、`as_of_date=2025-12-31`）**：
- train超過: **13.49%** (λ=0.00), **8.80%** (λ=0.05)

**現在の結果（2026年1月12日、`as_of_date=2023-12-31`）**：
- train超過: **1.44%** (λ=0.00), **0.76%** (λ=0.05)

## 重要な訂正（算術ミスの修正）

### 私の最初の説明の誤り

最初の説明では以下のように書きましたが、これは**算術ミス**です：

> 24Mホライズンの場合、`rebalance_date <= 2020-12-31`のものは`eval_end <= 2024-12-31`となる
> `as_of_date=2023-12-31`では、`eval_end <= 2023-12-31`のものだけが評価可能
> つまり、**`rebalance_date <= 2019-12-31`のものしか評価できない**

**誤り**：
- 24M（24ヶ月）なら、`2020-12-31 + 24ヶ月 = 2022-12-31`です
- つまり、`rebalance_date <= 2020-12-31`の場合、`eval_end <= 2022-12-31`となります
- `as_of_date=2023-12-31`では、`eval_end <= 2022-12-31`のものは`eval_end <= as_of_date`を満たすので、**評価可能です**

### 正しい理解

**`split_rebalance_dates`でのtrain期間のフィルタリング**：
- `require_full_horizon=True`かつ`horizon_months=24`の場合、train期間では`eval_end <= train_end_date`を満たすものだけを使用
- `train_end_date=2022-12-31`の場合、`rebalance_date <= 2020-12-31`のものしかtrainに含まれない
- これらのポートフォリオの`eval_end`は`<= 2022-12-31`となる

**`calculate_longterm_performance`での評価**：
- `as_of_date=2023-12-31`の場合、`require_full_horizon=True`なら`eval_end <= as_of_date`を満たすものだけが評価される
- `rebalance_date <= 2020-12-31`の場合、`eval_end <= 2022-12-31`となる
- `eval_end <= 2022-12-31 <= as_of_date(2023-12-31)`なので、**評価可能です**

**結論**：
- もし`split_rebalance_dates`が正しく`eval_end <= train_end_date`で絞れているなら、`as_of_date=end_date`でも`as_of_date=train_end_date`でも結果は同じになるはずです
- つまり、**「as_of_date=end_dateが原因でtrainが低い」という説明は成立しません**（少なくとも算術的には）

## 確認すべきポイント

### 1. train_datesの範囲と件数の確認

実際のログで以下を確認する必要があります：
- `train_dates_first`（最初のtrain期間のrebalance_date）
- `train_dates_last`（最後のtrain期間のrebalance_date）
- `num_train_periods`（train期間のrebalance_date数）

24Mホライズンで`train_end_date=2022-12-31`の場合：
- `train_dates_last`が`2020-12-31`近辺になっているはず（`eval_end<=train_end`を守っていれば）

### 2. calculate_longterm_performanceでの除外件数の確認

train評価の中で以下を確認する必要があります：
- 入力された`rebalance_dates`数
- 実際に使用された`rebalance_dates`数
- `eval_end > as_of_date`で除外された件数（「ホライズン未達」）
- 使用されたポートフォリオの最大`eval_end`

### 3. split_rebalance_datesの動作確認

`split_rebalance_dates`が本当に`eval_end <= train_end_date`で絞れているかを確認する必要があります。

もし`split_rebalance_dates`が`rebalance_date <= train_end_date`でしか絞れていない場合（`eval_end <= train_end_date`を守っていない場合）：
- 24Mでは`rebalance_date`が2021〜2022にかかると`eval_end`が2023〜2024まで伸びる
- `as_of_date=2025-12-31`の以前の実行では、それらも評価できてしまい、trainに"未来（train_end_date以降）のリターン"が混ざる
- `as_of_date=2023-12-31`の今の実行では、`eval_end>2023-12-31`の分が落ちる

この場合に問題なのは**as_of_date**ではなく、そもそも**train分割が「eval_end<=train_end」を守れていない**こと（＝学習ラベルが未来へはみ出している可能性）です。

## より自然な説明

train超過の大きな差（13.49% → 1.44%）は事実として出ていますが、これを「as_of_dateの渡し間違い」と決め打つより、以下の要因の方が現実的です：

1. **評価条件が変わった**（as_of/end_date、test年、等ウェイト統一などが連鎖している）
2. 以前の実行は**別の比較条件（または別ロジック）**が混ざっていた可能性がある（不一致が多かった）
3. 24Mはtrain/testの取り方が特殊で、内部testが空になったり表示が紛らわしかったりする（test超過=0.00問題の延長）

## 修正方法

train期間の評価では、`as_of_date=train_end_date`を使用すべきです。

### 修正案1：`objective_longterm`関数に`train_end_date`を追加

`objective_longterm`関数のシグネチャを変更し、train期間の評価時は`as_of_date=train_end_date`を使用するようにします。

```python
def objective_longterm(
    trial: optuna.Trial,
    train_dates: List[str],
    study_type: Literal["A", "B", "C"],
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
    horizon_months: int = 24,
    require_full_horizon: bool = True,
    as_of_date: Optional[str] = None,  # test期間用
    train_end_date: Optional[str] = None,  # train期間用（追加）
    lambda_penalty: float = 0.0,
) -> float:
    # ...
    perf = calculate_longterm_performance(
        train_dates,
        strategy_params,
        entry_params,
        cost_bps=cost_bps,
        n_jobs=n_jobs,
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=horizon_months,
        require_full_horizon=require_full_horizon,
        as_of_date=train_end_date if train_end_date else as_of_date,  # train期間用
    )
```

`optimize_longterm_main`での呼び出し：

```python
objective_fn = lambda trial: objective_longterm(
    trial,
    train_dates,
    study_type,
    cost_bps,
    backtest_n_jobs,
    features_dict=features_dict,
    prices_dict=prices_dict,
    horizon_months=horizon_months,
    require_full_horizon=True,
    as_of_date=as_of_date,  # test期間用
    train_end_date=train_end_date,  # train期間用（追加）
    lambda_penalty=lambda_penalty,
)
```

### 修正案2：`objective_longterm`関数内で`train_end_date`を計算

`train_dates`から`train_end_date`を推測する方法もありますが、明示的に渡す方が安全です。

## 確認すべきポイント

1. **`compare_lambda_penalties`でのtrain期間の評価**
   - `compare_lambda_penalties`でも同様の問題がある可能性
   - `optimize_longterm_main`の内部評価で`train_perf`を計算している場合、同じ問題がある可能性

2. **test期間の評価**
   - test期間の評価では、`as_of_date=end_date`を使用するのが正しい（変更不要）

3. **以前の結果との整合性**
   - 以前の結果（`as_of_date=2025-12-31`）では、たまたま`as_of_date`が大きかったため、train期間のポートフォリオが評価可能だった
   - 修正後は、train期間の評価が正しく行われるようになり、以前の結果と比較可能になる

## 次のステップ

1. **修正を実装**
   - `objective_longterm`関数に`train_end_date`パラメータを追加
   - train期間の評価時は`as_of_date=train_end_date`を使用

2. **再実行**
   - 修正後に24Mのλ比較を再実行
   - train期間の超過リターンが改善されることを確認

3. **結果の比較**
   - 修正前後の結果を比較
   - train期間の評価対象数が増えることを確認


# train期間の超過リターンが低い問題の調査（修正版）

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

## 推奨される確認方法

### 確認①：train_datesの範囲と件数

最適化結果JSONまたはログから以下を確認：
- `train_dates_first` / `train_dates_last` / `num_train_periods`
- 24Mなら、`train_end_date=2022-12-31`で**train_last_rbが2020年末近辺**になっているはず（`eval_end<=train_end`を守っていれば）

### 確認②：calculate_longterm_performanceが落としている件数

train評価の中で以下をログ出力：
- `n_input_dates`（入力されたrebalance_dates数）
- `n_used_dates`（実際に使用されたrebalance_dates数）
- `n_excluded_incomplete_horizon`（`eval_end > as_of_date`で落ちた件数）
- `max_eval_end_used`（使用されたポートフォリオの最大eval_end）

これを出せば、「as_of_dateが小さすぎて落ちている」のか「そもそもtrain_datesが想定と違う」のかが一発で分かります。

## 修正案について（安全性の観点）

「train評価のas_of_dateをtrain_end_dateにする」という修正は、**"trainの成績を上げるため"というより**：

- train評価が将来に触れないことを二重に保証する（保険）
- 設計意図（trainはtrain_end_dateまでの結果で目的関数を計算する）をコード上明確にする

という意味では**良い改善**です。

ただし重要なのは：
- それで**trainが増える**とは限らない（むしろ同じか減る可能性）
- 「trainが低い原因」の説明としては、算術が崩れているので**原因断定には使えない**

## 次のステップ

1. **まず事実確認**：実際のログから`train_dates_last`と`num_train_periods`（またはtrain_max_rb）を確認
2. **calculate_longterm_performanceのログ**：除外件数と最大eval_endを確認
3. **原因特定**：上記の情報から「splitが想定通りか／as_ofで落ちてるか」を判定
4. **必要に応じて修正**：原因が特定できたら、適切な修正を実施




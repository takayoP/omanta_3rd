# 24Mホライズンでのλ比較における`require_full_horizon`の設定について

## 問題の背景

### 発生したエラー
24Mホライズンで`compare_lambda_penalties`を実行した際、以下のエラーが発生しました：

```
❌ データ分割エラー: No test dates found after 2022-12-31
```

その後、`test_dates`は正しく取得できましたが、`run_backtest_with_params_file`で以下のエラーが発生：

```
λ値               平均超過      P10(超過)       勝率       切替回数      期間数      train超過       test超過
----------------------------------------------------------------------------------------------------
λ=0.00            エラー
λ=0.05            エラー
```

### 原因分析

1. **24Mホライズンの特性**：
   - 24Mホライズンは、リバランス日から24ヶ月後の評価終了日まで保有する戦略
   - 例：2023-01-31のポートフォリオの評価終了日は2025-01-31

2. **`require_full_horizon=True`の場合**：
   - ホライズン未達のポートフォリオ（`eval_end_date > as_of_date`）は評価から除外される
   - `as_of_date`が2023-12-31の場合、2023-01-31のポートフォリオの評価終了日は2025-01-31となり、`as_of_date`より後なので「ホライズン未達」として除外される
   - 結果として、test期間（2023-01-31 ～ 2023-12-29）のすべてのポートフォリオが除外され、`valid_dates`が空になる
   - `performances`が空になり、`run_backtest_with_params_file`がエラーを返す

3. **`run_backtest_with_params_file`の処理**：
   ```python
   # 固定ホライズン制約でフィルタリング
   valid_dates = []
   as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
   for rebalance_date in all_dates:
       rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
       eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
       if not require_full_horizon or eval_end_dt <= as_of_dt:
           valid_dates.append(rebalance_date)
   
   if not performances:
       return {"error": "パフォーマンスデータがありません"}
   ```

## 提案された修正

### 修正内容
`compare_lambda_penalties`内で`run_backtest_with_params_file`を呼ぶ際、24Mホライズンの場合は`require_full_horizon=False`に設定：

```python
# 24Mホライズンの場合、as_of_dateが現在日付に近いとtest期間のポートフォリオが
# すべて「ホライズン未達」として除外される可能性があるため、
# require_full_horizon=Falseとする（ホライズン未達のポートフォリオも評価に含める）
require_full_horizon_for_compare = False if horizon_months == 24 else True
backtest_result = run_backtest_with_params_file(
    params_file_path,
    test_dates[0],
    test_dates[-1],
    as_of_date,
    require_full_horizon=require_full_horizon_for_compare,
    rebalance_dates=test_dates,
)
```

## この修正の影響と懸念点

### 影響

1. **評価期間の短縮**：
   - `require_full_horizon=False`の場合、評価期間は`as_of_date`まで（短縮される）
   - 例：2023-01-31のポートフォリオは、2025-01-31まで評価されるべきだが、2023-12-31までしか評価されない
   - 実際の保有期間は約11ヶ月（24ヶ月の約46%）

2. **比較の公平性**：
   - 24Mホライズンのポートフォリオが短縮期間で評価される
   - 12Mホライズンのポートフォリオは完全な12ヶ月間で評価される可能性が高い
   - 異なるホライズンの比較では、評価期間が異なるため、直接比較できない

3. **年率化への影響**：
   - 短縮期間での年率化リターンは、実際の24Mホライズンでの年率化リターンとは異なる可能性がある
   - ただし、`calculate_annualized_return_from_period`は実際の保有期間で年率化するため、数学的には正しい

### 懸念点

1. **設計意図との整合性**：
   - 24Mホライズンは「24ヶ月間保有」を前提としている
   - `require_full_horizon=False`にすると、この前提が崩れる

2. **最適化との整合性**：
   - `optimize_longterm_main`内のtrain期間評価では`require_full_horizon=True`を使用
   - `compare_lambda_penalties`のtest期間評価で`require_full_horizon=False`を使用すると、評価条件が異なる

3. **代替案の検討**：
   - `as_of_date`を24ヶ月後（2025-12-31）に設定する案
   - ただし、これは「未来のデータ」を見ることになり、リークが発生する

## 検討すべき点

### 1. 比較の目的
λ比較の目的は、異なるλ値での戦略の性能を比較することです。この目的のためには：
- **同じ条件で評価されたポートフォリオ**が必要
- 評価期間が異なると、比較の公平性が損なわれる可能性がある

### 2. 24Mホライズンの評価方法
24Mホライズンの評価には、以下の選択肢があります：

**選択肢A：`require_full_horizon=False`（提案された修正）**
- メリット：評価可能なポートフォリオが存在する
- デメリット：評価期間が短縮される（実際のホライズンより短い）

**選択肢B：`as_of_date`を24ヶ月後に設定**
- メリット：完全な24ヶ月間で評価できる
- デメリット：「未来のデータ」を見ることになり、リークが発生する（不適切）

**選択肢C：評価期間を調整して比較**
- 例：24Mホライズンのポートフォリオを12ヶ月間で評価し、12Mホライズンと比較
- メリット：同じ評価期間で比較できる
- デメリット：24Mホライズンの本来の性能を反映しない

**選択肢D：test期間を調整**
- 例：test期間を`train_end_date - 24ヶ月`以前に設定
- メリット：完全な24ヶ月間で評価できる
- デメリット：test期間が短くなる、または存在しない可能性がある

### 3. 最適化との整合性
`optimize_longterm_main`内のtrain期間評価では`require_full_horizon=True`を使用しています。これは：
- train期間では、`train_end_date`を`as_of_date`として使用
- 24Mホライズンの場合、`train_end_date`（2022-12-31）より24ヶ月前（2020-12-31）以前のリバランス日のみが評価対象
- この条件を満たすリバランス日が存在するため、train期間では正常に動作する

一方、test期間では：
- `as_of_date`が2023-12-31
- test期間のリバランス日は2023-01-31以降
- 24Mホライズンの場合、すべてのtest期間のポートフォリオが「ホライズン未達」となる

## 質問事項

1. **`require_full_horizon=False`の設定は適切か？**
   - 24Mホライズンの場合、短縮期間での評価を許容するべきか？
   - 評価期間が異なると、比較の公平性が損なわれるか？

2. **最適化との整合性**
   - train期間では`require_full_horizon=True`、test期間では`require_full_horizon=False`とするのは適切か？
   - 評価条件が異なると、最適化の結果と比較の結果が整合しない可能性がある

3. **代替案の評価**
   - 他の選択肢（選択肢C、Dなど）を検討すべきか？
   - あるいは、24Mホライズンの評価方法自体を見直すべきか？

4. **設計意図との整合性**
   - 24Mホライズンは「24ヶ月間保有」を前提としているが、この前提を崩すことが許容されるか？
   - 短縮期間での評価を「暫定評価」として扱うべきか？

## 参考情報

- `run_backtest_with_params_file`の実装：`src/omanta_3rd/jobs/compare_lambda_penalties.py`（225-232行目）
- `compare_lambda_penalties`の実装：`src/omanta_3rd/jobs/compare_lambda_penalties.py`（587-594行目）
- `optimize_longterm_main`のtest期間評価：`src/omanta_3rd/jobs/optimize_longterm.py`（1264-1276行目）
- `calculate_longterm_performance`の実装：`src/omanta_3rd/jobs/optimize_longterm.py`（約300-500行目）




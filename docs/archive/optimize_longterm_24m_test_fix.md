# optimize_longterm.py の24Mホライズンtest期間評価の修正

## 問題

`optimize_longterm.py`で24Mホライズンの最適化を実行した際、test期間の評価で以下の問題が発生していました：

- test_datesが2023年のrebalance日（2023-01-31〜2023-12-29）になっている
- 24Mホライズンだと、eval_endが2025年になる（例：2023-01-31 + 24M = 2025-01-31）
- `as_of_date=2023-12-31`なので、すべてのtest期間のポートフォリオが「ホライズン未達」として除外される
- 結果として、test期間の評価結果がすべて0%になる

## 修正内容

`optimize_longterm.py`の`optimize_longterm_main`関数で、24Mホライズンの場合にtest_datesを`as_of_date`で評価可能な範囲に制限する処理を追加しました。

### 修正ロジック

```python
# 24Mホライズンの場合、test_datesをas_of_dateで評価可能な範囲に制限
# これにより、test期間の評価で「ホライズン未達」が発生しないようにする
if horizon_months == 24 and as_of_date and require_full_horizon:
    from datetime import datetime as dt
    as_of_dt = dt.strptime(as_of_date, "%Y-%m-%d")
    # eval_end <= as_of_date を満たすtest_datesのみを使用
    # つまり、rebalance_date + 24M <= as_of_date を満たすもの
    max_rebalance_dt = as_of_dt - relativedelta(months=horizon_months)
    max_rebalance_date = max_rebalance_dt.strftime("%Y-%m-%d")
    
    original_test_count = len(test_dates)
    test_dates = [d for d in test_dates if d <= max_rebalance_date]
    
    if len(test_dates) < original_test_count:
        print(f"⚠️  24Mホライズンのため、test_datesを{max_rebalance_date}以前に制限しました")
        print(f"   元のtest_dates数: {original_test_count} → 制限後: {len(test_dates)}")
        if len(test_dates) == 0:
            print(f"   ⚠️  警告: test_datesが空になりました。as_of_dateを{as_of_date}より後に設定するか、")
            print(f"      または24Mホライズンのtest期間を前倒しする必要があります。")
```

### 例

- `as_of_date = 2023-12-31`
- `horizon_months = 24`
- 元のtest_dates: 2023-01-31〜2023-12-29（12件）

修正後：
- `max_rebalance_date = 2023-12-31 - 24M = 2021-12-31`
- 制限後のtest_dates: 2021-01-29〜2021-12-30（12件、2021年のrebalance日）

これにより、test期間のポートフォリオがすべて「ホライズン未達」として除外される問題が解決されます。

## 注意事項

1. **`compare_lambda_penalties.py`との整合性**: `compare_lambda_penalties.py`では、`optimize_longterm_main`が保存した`test_dates`を再利用するため、この修正により`compare_lambda_penalties.py`でも正しいtest_datesが使用されます。

2. **最適化結果への影響**: この修正により、test期間の評価が正しく行われるようになりますが、最適化自体（train期間での最適化）には影響しません。

3. **警告メッセージ**: test_datesが空になった場合、警告メッセージが表示されます。この場合、`as_of_date`を調整するか、test期間を前倒しする必要があります。

## 関連ファイル

- `src/omanta_3rd/jobs/optimize_longterm.py`: 修正対象ファイル
- `src/omanta_3rd/jobs/compare_lambda_penalties.py`: `optimize_longterm_main`が保存した`test_dates`を使用


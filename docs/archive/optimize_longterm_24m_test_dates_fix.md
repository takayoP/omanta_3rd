# optimize_longterm.py の24Mホライズンtest_dates修正とWindows並列処理対応

## 変更概要

`optimize_longterm.py`で24Mホライズンの最適化を実行した際に発生していた以下の問題を修正しました：

1. **test_datesが空になる問題**: 24Mホライズンで`as_of_date=2023-12-31`、`train_end_date=2022-12-31`の場合、`test_dates`が空になり、test期間の評価ができない
2. **Windowsでの並列処理エラー**: `ProcessPoolExecutor`を使用した並列処理で、プロセスが異常終了するエラーが発生

## 問題の詳細

### 問題1: test_datesが空になる問題

**発生条件**:
- `horizon_months = 24`
- `as_of_date = 2023-12-31`
- `train_end_date = 2022-12-31`

**原因**:
1. `split_rebalance_dates`で`train_end_date=2022-12-31`を指定すると、`test_dates`は2023年以降のrebalance日になる
2. その後、24Mホライズンの制限で`max_rebalance_date = as_of_date - 24M = 2021-12-31`より後がすべて除外される
3. 結果として、`test_dates`が空になる

**影響**:
- `optimize_longterm_main`内でtest期間の評価ができない
- 最適化中にtest期間のパフォーマンスを確認できない
- `compare_lambda_penalties`では別途`test_dates`を調整しているが、`optimize_longterm_main`と`compare_lambda_penalties`で`test_dates`が一致しない可能性がある

### 問題2: Windowsでの並列処理エラー

**発生エラー**:
```
エラー (2020-02-28): A process in the process pool was terminated abruptly while the future was running or pending.
RuntimeError: No portfolios were generated
```

**原因**:
- Windowsでは`ProcessPoolExecutor`が`spawn`方式を使用するため、プロセス間でオブジェクトをpickle化する必要がある
- 複雑なオブジェクト（DataFrame、データベース接続など）のpickle化が失敗することがある
- プロセスが異常終了し、`No portfolios were generated`エラーが発生

## 修正内容

### 修正1: test_datesの再計算ロジック追加

`optimize_longterm_main`内で、24Mホライズンで`test_dates`が空になった場合、`compare_lambda_penalties`と同じロジックで`test_dates`を再計算するようにしました。

**修正箇所**: `src/omanta_3rd/jobs/optimize_longterm.py` (1077-1120行目付近)

```python
# 24Mホライズンの場合、test_datesが空になったら、compare_lambda_penaltiesと同じロジックで再計算
if horizon_months == 24 and as_of_date and train_end_date and not test_dates:
    from datetime import datetime as dt
    as_of_dt = dt.strptime(as_of_date, "%Y-%m-%d")
    test_max_dt = as_of_dt - relativedelta(months=24)
    test_max_date = test_max_dt.strftime("%Y-%m-%d")
    
    train_end_dt = dt.strptime(train_end_date, "%Y-%m-%d")
    train_max_dt = train_end_dt - relativedelta(months=24)
    train_max_date = train_max_dt.strftime("%Y-%m-%d")
    
    # test期間は (train_max_dt, test_max_dt] に限定（train期間と重複しないように）
    test_dates = []
    for d in rebalance_dates:
        d_dt = dt.strptime(d, "%Y-%m-%d")
        if d_dt > train_max_dt and d_dt <= test_max_dt:
            test_dates.append(d)
    
    if test_dates:
        print(f"⚠️  24Mホライズンのため、test_datesを再計算しました（compare_lambda_penaltiesと同じロジック）")
        print(f"   train_max_rb (train期間の最終rebalance): {train_max_date}")
        print(f"   test_max_rb (test期間の最終rebalance): {test_max_date}")
        print(f"   件数: {len(test_dates)}")
        print(f"   最初: {test_dates[0] if test_dates else 'N/A'}")
        print(f"   最後: {test_dates[-1] if test_dates else 'N/A'}")
    else:
        print(f"⚠️  警告: test_datesが空です（train_max_rb: {train_max_date}, test_max_rb: {test_max_date}）。")
        print(f"   compare_lambda_penaltiesで別途調整されます。")
```

**ロジックの説明**:
- `train_max_rb = train_end_date - 24M`: train期間の最終rebalance日（`eval_end <= train_end_date`を満たすrebalanceの最終日）
- `test_max_rb = as_of_date - 24M`: test期間の最終rebalance日（`eval_end <= as_of_date`を満たすrebalanceの最終日）
- `test_dates = (train_max_rb, test_max_rb]`: train期間と重複しないtest期間のrebalance日

**効果**:
- `optimize_longterm_main`内でtest期間の評価が可能になる
- `compare_lambda_penalties`と同じ`test_dates`が使用される
- 最適化中にtest期間のパフォーマンスを確認できる

### 修正2: Windowsでの並列処理対応

`ProcessPoolExecutor`を`ThreadPoolExecutor`に変更しました。

**修正箇所**: `src/omanta_3rd/jobs/optimize_longterm.py` (233行目、260行目)

```python
# 変更前
from concurrent.futures import ProcessPoolExecutor, as_completed
with ProcessPoolExecutor(max_workers=n_jobs) as executor:

# 変更後
from concurrent.futures import ThreadPoolExecutor, as_completed
with ThreadPoolExecutor(max_workers=n_jobs) as executor:
```

**理由**:
- Windowsでの`ProcessPoolExecutor`の問題を回避
- I/Oバウンドな処理（データベースアクセス、特徴量計算）には有効
- ポートフォリオ選定は主にI/Oバウンドなので、実用上問題なし

**注意事項**:
- `ThreadPoolExecutor`はGILの制約があるため、CPUバウンドな処理には効果が限定的
- ただし、ポートフォリオ選定は主にI/Oバウンドなので、実用上問題なし

## 修正前後の動作比較

### 修正前

```
リバランス日数: 72
最初: 2018-01-31
最後: 2023-12-29

      [split_rebalance_dates] 24Mホライズンのため、test_datesを2021-12-31以前に制限しました
      元のtest_dates数: 12 → 制限後: 0
⚠️  警告: test_datesが空です（train_end_date=2022-12-31, as_of_date=2023-12-31, max_rebalance_date=2021-12-31）。compare_lambda_penaltiesで別途調整されます。
学習データ: 36日 (50.0%)
  最初: 2018-01-31
  最後: 2020-12-30
テストデータ: 0日 (0.0%)
  最初: N/A
  最後: N/A
```

### 修正後

```
リバランス日数: 72
最初: 2018-01-31
最後: 2023-12-29

      [split_rebalance_dates] 24Mホライズンのため、test_datesを2021-12-31以前に制限しました
      元のtest_dates数: 12 → 制限後: 0
⚠️  24Mホライズンのため、test_datesを再計算しました（compare_lambda_penaltiesと同じロジック）
   train_max_rb (train期間の最終rebalance): 2020-12-31
   test_max_rb (test期間の最終rebalance): 2021-12-31
   件数: 12
   最初: 2021-01-29
   最後: 2021-12-30
学習データ: 36日 (50.0%)
  最初: 2018-01-31
  最後: 2020-12-30
テストデータ: 12日 (16.7%)
  最初: 2021-01-29
  最後: 2021-12-30
```

## 関連ファイル

- `src/omanta_3rd/jobs/optimize_longterm.py`: 修正対象ファイル
- `src/omanta_3rd/jobs/compare_lambda_penalties.py`: `test_dates`の計算ロジックの参考
- `docs/windows_parallel_processing_fix.md`: Windows並列処理対応の詳細

## 確認事項

1. **test_datesの計算ロジック**: `optimize_longterm_main`と`compare_lambda_penalties`で同じ`test_dates`が使用されることを確認
2. **並列処理の動作**: Windowsでの並列処理エラーが発生しないことを確認
3. **test期間の評価**: `optimize_longterm_main`内でtest期間の評価が正しく実行されることを確認

## 今後の改善案

1. **test_datesの計算ロジックの共通化**: `optimize_longterm_main`と`compare_lambda_penalties`で同じロジックを使用するように、共通関数を作成する
2. **並列処理の選択**: プラットフォームに応じて`ProcessPoolExecutor`と`ThreadPoolExecutor`を自動選択する

## 参考資料

- `docs/windows_parallel_processing_fix.md`: Windows並列処理対応の詳細
- `docs/optimize_longterm_24m_test_fix.md`: 24Mホライズンtest期間評価の修正（以前の修正）


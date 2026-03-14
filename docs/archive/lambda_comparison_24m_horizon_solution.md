# 24Mホライズンでのλ比較の適切な解決策

## ChatGPTの評価結果

ChatGPTの評価によると、`require_full_horizon=False`の設定は「動かすための暫定回避策」としては成立するが、設計意図（24M=24ヶ月保有）を崩すため、λ比較（評価・意思決定）に使う修正としては推奨されない。

## 推奨される解決策：代替案2（test期間を手前にずらす）

### 方針
24Mホライズンの場合、`require_full_horizon=True`を維持し、test期間を手前にずらして、24ヶ月の完全なホライズンで評価できるようにする。

### 理論的背景

24Mホライズンで`require_full_horizon=True`を守ると：
- `eval_end = rebalance_date + 24M`
- `eval_end <= as_of_date`のrebalanceのみが評価対象
- `as_of_date`が2023-12-31の場合、評価できるrebalanceは2021-12-31以前に限られる

### データ分割の設計

**現在の設定**：
- `train_end_date`: 2022-12-31
- `as_of_date`: 2023-12-31
- test期間: 2023-01-31 ～ 2023-12-29（24Mホライズンではすべて「ホライズン未達」）

**推奨される設計（24Mホライズン用）**：
- `train_end_date`: 2022-12-31
- `as_of_date`: 2023-12-31（2025年データを残すため）
- test期間: 2021-01-31 ～ 2021-12-31（24M満了が可能、eval_end = 2023-01-31 ～ 2023-12-31）

**3分割の設計（より明確な区切り）**：
- train期間: 2016-01-31 ～ 2020-12-31（古い期間）
- validation（λ比較）期間: 2021-01-31 ～ 2021-12-31（24M満了が可能、eval_end = 2023-01-31 ～ 2023-12-31）
- holdout（最終確認）期間: 2022-01-31 ～ 2022-12-31（→ eval_end = 2024-01-31 ～ 2024-12-31、2025年の価格を使用）

### 実装上の考慮事項

1. **学習に必要なデータ量**：
   - 学習に必要なデータは過去3年分
   - 2021-12-31をtest期間の最後とする場合、train期間は2018-12-31以前が必要
   - 現在の設定（train_end_date: 2022-12-31）では、train期間は2018-01-31 ～ 2020-12-31となり、約3年間
   - **結論**: 案2でも十分なサンプルが取れる

2. **`optimize_longterm_main`との整合性**：
   - `optimize_longterm_main`は`train_end_date`を基準にtrain/test分割を行う
   - 24Mホライズンの場合、train期間では`eval_end <= train_end_date`を満たすrebalanceのみを使用
   - test期間は`train_end_date`より後のrebalanceを使用
   - しかし、24Mホライズンの場合、`train_end_date`より後のrebalanceはすべて「ホライズン未達」となる

3. **`compare_lambda_penalties`でのtest期間設定**：
   - 現在は`optimize_longterm_main`から`test_dates`を取得している
   - しかし、24Mホライズンの場合、`optimize_longterm_main`の`test_dates`はすべて「ホライズン未達」となる
   - **解決策**: `compare_lambda_penalties`で、24Mホライズンの場合、test期間を`train_end_date - 24ヶ月`以前に設定する

### 実装案

`compare_lambda_penalties`内で、24Mホライズンの場合：

1. `optimize_longterm_main`を呼ぶ際に、`end_date`を`train_end_date - 24ヶ月`に設定
   - これにより、test期間が`train_end_date - 24ヶ月`以前になる
   - train期間は`train_end_date - 24ヶ月`以前で、`eval_end <= train_end_date`を満たすrebalanceのみを使用

2. ただし、`optimize_longterm_main`内で`as_of_date`を使用してリバランス日の範囲を決定するように修正済み（`evaluation_end_date = as_of_date if as_of_date else end_date`）
   - この修正により、リバランス日の範囲は`as_of_date`まで取得される
   - しかし、train/test分割は`train_end_date`を基準に行われる
   - 24Mホライズンの場合、test期間は`train_end_date`より後のrebalanceとなるが、これらはすべて「ホライズン未達」となる

3. **より適切な実装**：
   - `optimize_longterm_main`を呼ぶ際に、`end_date`を`train_end_date - 24ヶ月`に設定（train期間のrebalance範囲を制限）
   - `as_of_date`は2023-12-31のまま（2025年データを残す）
   - `optimize_longterm_main`内で、リバランス日の範囲は`as_of_date`まで取得されるが、train/test分割は`train_end_date`を基準に行われる
   - しかし、24Mホライズンの場合、`train_end_date`より後のrebalanceはすべて「ホライズン未達」となるため、test期間が空になる

4. **別の実装案**：
   - `compare_lambda_penalties`内で、24Mホライズンの場合、test期間を明示的に`train_end_date - 24ヶ月`以前に設定
   - `optimize_longterm_main`を呼ぶ際に、`end_date`を`train_end_date - 24ヶ月`に設定し、`train_end_date`も調整する
   - しかし、これではtrain期間が短くなりすぎる可能性がある

5. **推奨実装**：
   - `compare_lambda_penalties`内で、24Mホライズンの場合、`run_backtest_with_params_file`を呼ぶ際に、test期間を`train_end_date - 24ヶ月`以前のrebalanceに限定
   - ただし、`optimize_longterm_main`から取得した`test_dates`は使用せず、新しく計算する
   - または、`optimize_longterm_main`の`test_dates`を無視し、`compare_lambda_penalties`でtest期間を再計算する

### 具体的な実装手順

1. **`require_full_horizon=False`の修正を元に戻す**
   - `compare_lambda_penalties.py`で`require_full_horizon=True`を維持

2. **24Mホライズンでのtest期間設定を修正**
   - `compare_lambda_penalties`内で、24Mホライズンの場合、test期間を`as_of_date - 24ヶ月`以前に設定
   - これにより、`eval_end = rebalance_date + 24M <= as_of_date`を満たすrebalanceのみが評価対象となる
   - `optimize_longterm_main`から取得した`test_dates`は使用せず、新しく計算する

3. **`optimize_longterm_main`との整合性**
   - `optimize_longterm_main`は`train_end_date`を基準にtrain/test分割を行う
   - 24Mホライズンの場合、`optimize_longterm_main`の`test_dates`はすべて「ホライズン未達」となるため、`compare_lambda_penalties`では使用しない
   - `compare_lambda_penalties`で、24Mホライズンの場合、test期間を新しく計算する（`as_of_date - 24ヶ月`以前）

### 実装コード

```python
if horizon_months == 24:
    # 24Mホライズンの場合、eval_end <= as_of_dateを満たすrebalanceのみが評価対象となる
    # つまり、rebalance_date <= as_of_date - 24ヶ月 のrebalanceのみが評価可能
    # test期間をas_of_date - 24ヶ月以前に設定する必要がある
    # また、train期間と重複しないように、train_max_rbより後のrebalanceのみをtest期間とする
    # train_max_rb = train_end_date - 24M (trainに入るrebalanceの最終日)
    # test_max_rb = as_of_date - 24M (testに入るrebalanceの最終日)
    # test_rb = (train_max_rb, test_max_rb]
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    test_max_dt = as_of_dt - relativedelta(months=24)
    test_max_date = test_max_dt.strftime("%Y-%m-%d")
    
    train_end_dt = datetime.strptime(train_end_date, "%Y-%m-%d")
    train_max_dt = train_end_dt - relativedelta(months=24)
    train_max_date = train_max_dt.strftime("%Y-%m-%d")
    
    # 生成範囲はtest_max_dtまでで十分
    all_dates = get_monthly_rebalance_dates(start_date, test_max_date)
    
    # test期間は (train_max_dt, test_max_dt] に限定（train期間と重複しないように）
    test_dates = []
    for d in all_dates:
        d_dt = datetime.strptime(d, "%Y-%m-%d")
        if d_dt > train_max_dt and d_dt <= test_max_dt:
            test_dates.append(d)
    
    if not test_dates:
        results[f"λ={lambda_val:.2f}"] = {"error": f"24Mホライズン: 評価可能なtest期間のリバランス日が見つかりません（train_max_rb: {train_max_date}, test_max_rb: {test_max_date}）"}
        continue
else:
    # 12Mホライズンの場合、optimize_longterm_mainで実際に使われたtest_datesを取得
    test_dates = optimization_result.get("test_dates")
    # ... 後方互換性の処理 ...
```

### 実装のポイント

1. **24Mホライズンの場合のみ、test期間を再計算**
   - 12Mホライズンの場合は、従来通り`optimize_longterm_main`から`test_dates`を取得

2. **test期間の計算方法**
   - `train_max_rb = train_end_date - 24M`（trainに入るrebalanceの最終日、`eval_end <= train_end_date`を満たす）
   - `test_max_rb = as_of_date - 24M`（testに入るrebalanceの最終日、`eval_end <= as_of_date`を満たす）
   - `test_rb = (train_max_rb, test_max_rb]`（test期間はtrain期間と重複しないように、train_max_rbより後のrebalanceのみ）
   - 例: `as_of_date=2023-12-31`, `train_end_date=2022-12-31` の場合
     - `test_max_rb = 2021-12-31`
     - `train_max_rb = 2020-12-31`
     - `test_rb = (2020-12-31, 2021-12-31]` → **2021年がtest期間**

3. **`require_full_horizon=True`を維持**
   - 24Mホライズンでも`require_full_horizon=True`を維持することで、設計意図（24M=24ヶ月保有）が維持される
   - 評価期間が短縮されないため、比較の公平性が保たれる

### 注意事項

1. **test期間の短縮**：
   - test期間が2021年のみになるため、testサンプル数が減る（12ヶ月分のみ）
   - P10が不安定になりやすいため、P20やCVaR10も併記することが推奨される

2. **train期間の確保**：
   - 学習に必要なデータは過去3年分
   - 2021-12-31をtest期間の最後とする場合、train期間は2018-12-31以前が必要
   - 現在の設定（train_end_date: 2022-12-31）では、train期間は2018-01-31 ～ 2020-12-31となり、約3年間
   - **結論**: 十分なサンプルが取れる

3. **2025年データの保持**：
   - `as_of_date`を2023-12-31に設定することで、2025年のデータを残す
   - holdout（最終確認）期間として、2022年のrebalanceを評価する場合、2025年の価格を使用する
   - ただし、これはλ比較の範囲外

## 結論

代替案2（test期間を手前にずらす）を採用し、24Mホライズンでも`require_full_horizon=True`を維持する。

これにより：
- 設計意図（24M=24ヶ月保有）が維持される
- 最適化と評価の条件が一致する
- 2025年のデータを残すことができる
- 十分なサンプルが取れる（学習に必要なデータは過去3年分）


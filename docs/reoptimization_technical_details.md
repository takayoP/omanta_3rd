# 候補パラメータ再最適化の技術的詳細

## 問題の詳細

### (A) 未来参照リークの疑い

**問題点：**
```python
# 修正前のコード（問題あり）
latest_date = pd.read_sql_query("SELECT MAX(date) FROM prices_daily", conn)
eval_date = latest_date  # DBの最新日を使用
```

**具体例：**
- 2021-01-31のリバランスを評価する場合
- DBに2026-01-08までのデータがあると、2026-01-08まで評価してしまう
- これは「2021年のリバランスを2026年までの情報で評価」という未来参照

**修正後：**
```python
# 修正後のコード
eval_end_date = rebalance_date + relativedelta(months=horizon_months)
if require_full_horizon and eval_end_date > as_of_date:
    continue  # 除外
eval_date = min(eval_end_date, as_of_date)  # as_of_dateを明示的に指定
```

**確認方法：**
実行ログで以下を確認：
```
[calculate_longterm_performance] 2021-01-31 → eval_end=2023-01-31 (holding=2.00年, horizon=24M)
```
- `eval_end_date`が`rebalance_date + 24M`になっているか
- DBの最新日（2026-01-08など）が使われていないか

### (B) 学習/テスト分割が時系列ではない

**問題点：**
```python
# 修正前のコード（問題あり）
shuffled = rebalance_dates.copy()
rng.shuffle(shuffled)  # ランダムシャッフル
train_dates = shuffled[:n_train]
test_dates = shuffled[n_train:]
```

**具体例：**
- train: [2023-01-31, 2020-02-28, 2024-03-31, ...]  # 時系列が混ざる
- test: [2021-01-31, 2025-02-28, 2022-03-31, ...]  # 時系列が混ざる
- trainに2024年のデータ、testに2021年のデータが含まれる可能性

**修正後：**
```python
# 修正後のコード
unique_dates = sorted(list(dict.fromkeys(rebalance_dates)))  # 時系列順にソート
if time_series_split:
    train_dates = unique_dates[:n_train]  # 前80%
    test_dates = unique_dates[n_train:]   # 後20%
```

**確認方法：**
実行ログで以下を確認：
```
学習データ: 36日 (80.0%)
  最初: 2020-01-31
  最後: 2022-12-30
テストデータ: 9日 (20.0%)
  最初: 2023-01-31
  最後: 2023-12-29
```
- trainの最後の日付 < testの最初の日付 になっているか

## 修正内容の詳細

### 1. `calculate_longterm_performance()`の修正

**変更点：**
1. `as_of_date`パラメータを追加（評価の打ち切り日を明示的に指定）
2. `horizon_months`を必須パラメータに変更
3. `latest_date = MAX(date) FROM prices_daily`を削除
4. 各リバランス日の評価終了日を`eval_end_date = rebalance_date + horizon_months`で計算
5. `require_full_horizon=True`の場合、`eval_end_date <= as_of_date`を満たさないものは除外
6. ログ出力を追加（`rebalance_date`, `eval_end_date`, `holding_years`）

**コード変更箇所：**
```python
# 修正前
latest_date = pd.read_sql_query("SELECT MAX(date) FROM prices_daily", conn)
eval_date = latest_date

# 修正後
if as_of_date is None:
    as_of_date = pd.read_sql_query("SELECT MAX(date) FROM prices_daily", conn)  # 警告を出力
    print(f"⚠️  as_of_dateが指定されていません。DBの最新日({as_of_date})を使用します。")

eval_end_date = rebalance_date + relativedelta(months=horizon_months)
if require_full_horizon and eval_end_date > as_of_date:
    continue  # 除外
eval_date = min(eval_end_date, as_of_date)

# ログ出力
holding_years = (datetime.strptime(eval_date, "%Y-%m-%d") - rebalance_dt).days / 365.25
print(f"{rebalance_date} → eval_end={eval_date} (holding={holding_years:.2f}年, horizon={horizon_months}M)")
```

### 2. `split_rebalance_dates()`の修正

**変更点：**
1. `time_series_split`パラメータを追加（デフォルト: `True`）
2. 時系列順にソートしてから分割
3. ランダム分割は研究用途のみ（`time_series_split=False`で有効化可能）

**コード変更箇所：**
```python
# 修正前
shuffled = rebalance_dates.copy()
rng.shuffle(shuffled)
train_dates = sorted(shuffled[:n_train])
test_dates = sorted(shuffled[n_train:])

# 修正後
unique_dates = sorted(list(dict.fromkeys(rebalance_dates)))  # 時系列順にソート
if time_series_split:
    train_dates = unique_dates[:n_train]  # 前80%
    test_dates = unique_dates[n_train:]   # 後20%
else:
    # ランダム分割（研究用途のみ）
    shuffled = unique_dates.copy()
    rng.shuffle(shuffled)
    train_dates = sorted(shuffled[:n_train])
    test_dates = sorted(shuffled[n_train:])
```

### 3. 24Mと12Mで異なるend_dateを使用

**変更点：**
1. 24Mの最適化は、24Mホライズンが完走できるように`end_date`を自動調整
2. `end_date_24m = end_date - 24ヶ月`

**コード変更箇所：**
```python
# reoptimize_all_candidates.py内
end_date_24m = end_date
if not skip_24m:
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    end_dt_24m = end_dt - relativedelta(months=24)
    end_date_24m = end_dt_24m.strftime("%Y-%m-%d")
    print(f"24M最適化用のend_dateを調整: {end_date} → {end_date_24m}")

# 24M最適化
results["operational_24M"] = optimize_and_save(
    ...
    end_date=end_date_24m,  # 24M用に調整
    ...
)

# 12M最適化
results["12M_momentum"] = optimize_and_save(
    ...
    end_date=end_date,  # 12Mはそのまま
    ...
)
```

## 実行フロー

### 1. operational_24Mの最適化

```
入力:
  start_date: 2020-01-01
  end_date: 2025-12-31
  → end_date_24m: 2023-12-31 (自動調整)

処理:
  1. リバランス日を取得: 2020-01-31 ～ 2023-12-31
  2. 時系列分割:
     - train: 2020-01-31 ～ 2022-12-30 (80%)
     - test: 2023-01-31 ～ 2023-12-29 (20%)
  3. trainで最適化:
     - 各リバランス日について:
       - eval_end_date = rebalance_date + 24M
       - eval_end_date <= as_of_date を満たすもののみ評価
  4. testで評価
  5. パラメータファイルを保存
  6. レジストリを更新
```

### 2. 12M_momentumの最適化

```
入力:
  start_date: 2020-01-01
  end_date: 2025-12-31 (そのまま)

処理:
  1. リバランス日を取得: 2020-01-31 ～ 2025-12-31
  2. 時系列分割:
     - train: 2020-01-31 ～ 2022-12-30 (80%)
     - test: 2023-01-31 ～ 2023-12-29 (20%)
  3. trainで最適化:
     - 各リバランス日について:
       - eval_end_date = rebalance_date + 12M
       - eval_end_date <= as_of_date を満たすもののみ評価
  4. testで評価
  5. パラメータファイルを保存
  6. レジストリを更新
```

### 3. 12M_reversalの最適化

12M_momentumと同様（StudyタイプがB）

## 確認チェックリスト

### 未来参照リークの確認

- [ ] 実行ログで`eval_end_date`が`rebalance_date + horizon_months`になっているか
- [ ] `eval_end_date <= as_of_date`を満たしているか
- [ ] DBの最新日（2026-01-08など）が使われていないか
- [ ] `as_of_date`が明示的に指定されているか（警告が出ていないか）

### 時系列分割の確認

- [ ] trainの最後の日付 < testの最初の日付 になっているか
- [ ] 時系列順に分割されているか
- [ ] ランダムシャッフルが使われていないか

### 評価窓の確認

- [ ] 24M最適化で`end_date_24m = end_date - 24ヶ月`になっているか
- [ ] 24M最適化ですべてのリバランス日が24Mホライズン完走可能か
- [ ] 12M最適化ですべてのリバランス日が12Mホライズン完走可能か

## 期待される結果

### 修正前の問題

1. **未来参照リーク**
   - 2021-01-31のリバランスを2026-01-08まで評価
   - 異常に高い年率リターン（例：28933%）

2. **時系列リーク**
   - trainに2024年のデータ、testに2021年のデータ
   - 一般化性能の見積りが甘い

3. **評価窓の不一致**
   - 24M: 48期間、12M: 60期間
   - 比較が不公平

### 修正後の期待

1. **未来参照リークの排除**
   - 各リバランス日が固定ホライズンで評価される
   - より現実的な年率リターン

2. **時系列リークの排除**
   - train/testが時系列順に分割される
   - より現実的な一般化性能の見積り

3. **比較可能性の向上**
   - 24Mと12Mで有効サンプル数を揃える
   - 公平な比較が可能

## 技術的な実装詳細

### パラメータの流れ

```
reoptimize_all_candidates.py
  ↓
optimize_longterm_main()
  ↓
objective_longterm()
  ↓
calculate_longterm_performance()
  ↓
各リバランス日について:
  - eval_end_date = rebalance_date + horizon_months
  - eval_end_date <= as_of_date をチェック
  - calculate_portfolio_performance(rebalance_date, eval_end_date)
```

### ログ出力の例

```
[calculate_longterm_performance] 評価の打ち切り日: 2025-12-31
[calculate_longterm_performance] 2020-01-31 → eval_end=2022-01-31 (holding=2.00年, horizon=24M)
[calculate_longterm_performance] 2020-02-28 → eval_end=2022-02-28 (holding=2.00年, horizon=24M)
...
[calculate_longterm_performance] ⚠️  2024-01-31はホライズン未達（24M、eval_end=2026-01-31 > as_of=2025-12-31）のため除外
```

## 次のステップ

再最適化完了後：

1. **Step 2: A-1比較を共通のrebalance_date集合で再集計**
   - 24Mを含める比較 → 全戦略が評価できる月（積集合）だけで集計
   - 12Mだけの比較 → 12M同士で比較

2. **Step 3: レジームポリシーのrangeを見直す**
   - range → 12M_momentum
   - range → 前回のparams_idを維持（ヒステリシス）
   - range → 24Mのまま（現状）


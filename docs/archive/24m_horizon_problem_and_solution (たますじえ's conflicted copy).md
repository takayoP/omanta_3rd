# 24Mホライズンの「ホライズン未達」問題と解決策

## 問題の背景

### 24Mホライズンとは

24Mホライズンは、**リバランス日から24ヶ月後の評価終了日まで保有する戦略**です。

例：
- リバランス日: 2023-01-31
- 評価終了日: 2025-01-31（2023-01-31 + 24ヶ月）

### なぜ問題が発生するのか

**設定例**：
- `as_of_date`（評価の打ち切り日）: 2023-12-31
- `train_end_date`（学習期間の終了日）: 2022-12-31
- `test期間`（比較評価に使う期間）: 2023-01-31 ～ 2023-12-29

**24Mホライズンの場合**：
- 2023-01-31のポートフォリオの評価終了日: 2025-01-31
- しかし、`as_of_date`は2023-12-31までしかデータがない
- 2025-01-31 > 2023-12-31 なので、「ホライズン未達」として除外される

**結果**：
- test期間のすべてのポートフォリオ（2023-01-31 ～ 2023-12-29）が「ホライズン未達」として除外される
- test期間のポートフォリオが0件になり、エラーが発生する

### 図解

```
リバランス日        評価終了日（24ヶ月後）    as_of_date
  ↓                        ↓                      ↓
2023-01-31 ────────────→ 2025-01-31          2023-12-31
  ↑                                           ↑
test期間開始                                データがここまで
                                            （2025-01-31 > 2023-12-31 なので「ホライズン未達」）
```

## 解決策の検討

### 案1: `require_full_horizon=False`にする（❌ 不適切）

**内容**：
- `require_full_horizon=False`に設定して、ホライズン未達のポートフォリオも評価に含める

**問題点**：
1. **設計意図を崩す**: 24Mホライズンは「24ヶ月間保有」を前提としているのに、実際には約11ヶ月（2023-01-31 ～ 2023-12-31）しか評価しない
2. **比較の公平性が損なわれる**: 12Mホライズンは完全な12ヶ月で評価されるのに対し、24Mホライズンは短縮期間で評価される
3. **最適化との整合性**: train期間では`require_full_horizon=True`なのに、test期間では`require_full_horizon=False`では条件が異なる

**結論**: この案は「動かすための暫定回避策」としては成立するが、評価・意思決定には使えない

### 案2: test期間を手前にずらす（✅ 推奨）

**内容**：
- `require_full_horizon=True`を維持
- test期間を`as_of_date - 24ヶ月`以前に設定する
- これにより、`eval_end <= as_of_date`を満たすrebalanceのみが評価対象となる

**メリット**：
1. **設計意図を維持**: 24Mホライズンは「24ヶ月間保有」を前提として維持される
2. **比較の公平性**: 完全な24ヶ月間で評価される
3. **最適化との整合性**: train期間もtest期間も`require_full_horizon=True`で統一

**デメリット**：
- test期間が古くなる（例：2021年のみ）
- testサンプル数が減る（12ヶ月分のみ）

**結論**: この案が推奨される

## 解決策の詳細（案2）

### 基本的な考え方

24Mホライズンで`require_full_horizon=True`を守ると：
- `eval_end = rebalance_date + 24M`
- `eval_end <= as_of_date`を満たすrebalanceのみが評価対象
- つまり、`rebalance_date <= as_of_date - 24M`のrebalanceのみが評価可能

### 境界条件の設定

**重要なポイント**: test期間とtrain期間が重複しないようにする必要がある

1. **`train_max_rb`（train期間の最終rebalance日）**
   - `train_max_rb = train_end_date - 24M`
   - train期間で使用されるrebalanceの最終日（`eval_end <= train_end_date`を満たす）

2. **`test_max_rb`（test期間の最終rebalance日）**
   - `test_max_rb = as_of_date - 24M`
   - test期間で使用されるrebalanceの最終日（`eval_end <= as_of_date`を満たす）

3. **`test_rb`（test期間）**
   - `test_rb = (train_max_rb, test_max_rb]`
   - train期間より後で、test_max_rb以下のrebalanceのみをtest期間とする

### 具体例

**設定**：
- `as_of_date`: 2023-12-31
- `train_end_date`: 2022-12-31

**計算**：
- `test_max_rb = 2023-12-31 - 24ヶ月 = 2021-12-31`
- `train_max_rb = 2022-12-31 - 24ヶ月 = 2020-12-31`
- `test_rb = (2020-12-31, 2021-12-31]` → **2021年のみがtest期間**

**図解**：

```
rebalance日          eval_end (24M後)       as_of_date    train_end_date
   ↓                      ↓                    ↓              ↓
2020-12-31 ──────────→ 2022-12-31                           2022-12-31
  ↑                                                        ↑
train_max_rb                                            train_end_date
(training期間の最終rebalance)                            (training期間終了)

2021-01-31 ──────────→ 2023-01-31
2021-02-28 ──────────→ 2023-02-28
  ...                    ...
2021-12-31 ──────────→ 2023-12-31          2023-12-31
  ↑                                        ↑
test_max_rb                                as_of_date
(test期間の最終rebalance)                   (データの打ち切り日)

2022-01-31 ──────────→ 2024-01-31
  ↑
train_end_dateより後なので、本来のtest期間（ただし24Mだと未達）
```

**結果**：
- train期間: 2020-12-31以前のrebalance（`eval_end <= 2022-12-31`を満たす）
- test期間: 2021-01-31 ～ 2021-12-31のrebalance（`eval_end <= 2023-12-31`を満たす）
- 2022年以降: `eval_end`が2024年以降になるため、`as_of_date=2023-12-31`では評価できない

## 実装のポイント

### コード実装

```python
if horizon_months == 24:
    # test_max_rb: as_of_date - 24M（test期間の最終rebalance日）
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    test_max_dt = as_of_dt - relativedelta(months=24)
    test_max_date = test_max_dt.strftime("%Y-%m-%d")
    
    # train_max_rb: train_end_date - 24M（train期間の最終rebalance日）
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
```

### 重要なポイント

1. **`train_max_rb`より後のrebalanceのみをtest期間とする**
   - これにより、train期間とtest期間が重複しない

2. **`test_max_rb`以下のrebalanceのみをtest期間とする**
   - これにより、`eval_end <= as_of_date`を満たすrebalanceのみが評価対象となる

3. **`require_full_horizon=True`を維持**
   - 設計意図（24M=24ヶ月保有）を維持する

## 確認ポイント

実行時に、以下のログ出力を確認してください：

### A. 日付集合が意図通りか

- `train_max_rb` が **2020年末**（例：2020-12-31近辺）
- `test_first_rb` が **2021年初**（例：2021-01-31）
- `test_last_rb` が **2021年末**（例：2021-12-31）
- `num_test_periods == 12`（2021年の12ヶ月分）

### B. ホライズン未達がゼロになっているか

`require_full_horizon=True`のままなので、すべてのtest期間のポートフォリオが`eval_end <= as_of_date`を満たし、ホライズン未達で除外されるポートフォリオは0になるはずです。

## まとめ

### 問題

- 24Mホライズンで`require_full_horizon=True`の場合、`as_of_date=2023-12-31`だと、test期間（2023年）のすべてのポートフォリオが「ホライズン未達」として除外される

### 解決策

- test期間を`as_of_date - 24ヶ月`以前（例：2021年）に設定する
- `train_max_rb = train_end_date - 24M`より後のrebalanceのみをtest期間とする（train期間と重複しないように）
- `require_full_horizon=True`を維持（設計意図を維持）

### 結果

- test期間: 2021-01-31 ～ 2021-12-31（12ヶ月分）
- すべてのポートフォリオが`eval_end <= as_of_date`を満たす
- 完全な24ヶ月間で評価される
- 設計意図（24M=24ヶ月保有）が維持される

### トレードオフ

- test期間が古くなる（2021年のみ）
- testサンプル数が減る（12ヶ月分のみ）
- しかし、設計意図を維持し、完全な24ヶ月間で評価できる

## 参考資料

- `docs/lambda_comparison_24m_horizon_fix.md`: 初期の問題分析と代替案の検討
- `docs/lambda_comparison_24m_horizon_solution.md`: 解決策の詳細な説明と実装コード
- `src/omanta_3rd/jobs/compare_lambda_penalties.py`: 実装コード
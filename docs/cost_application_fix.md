# コスト適用の修正

## 問題

長期保有型（24ヶ月ホライズン）のパフォーマンス計算で、コスト（cost_bps）が適用されていませんでした。

## 原因

`calculate_portfolio_performance`関数にコストパラメータがなく、コストが適用されていませんでした。

## 修正内容

### 1. `calculate_portfolio_performance`関数にコストパラメータを追加

```python
def calculate_portfolio_performance(
    rebalance_date: str,
    as_of_date: Optional[str] = None,
    portfolio_table: str = "portfolio_monthly",
    cost_bps: float = 0.0,  # 追加
) -> Dict[str, Any]:
```

### 2. コスト計算ロジックを追加

長期保有型の場合、リバランスが1回だけなので、購入と売却が1回ずつ発生します。

- **購入コスト率（パーセント）**: `cost_bps / 100.0`
- **売却コスト率（パーセント）**: `(1.0 + total_return_gross / 100.0) × cost_bps / 100.0`
- **合計コスト（パーセント）**: `購入コスト率 + 売却コスト率`

```python
if not pd.isna(total_return_gross) and cost_bps > 0:
    # 正確なコスト計算
    buy_cost_pct = cost_bps / 100.0  # bps → パーセント
    sell_cost_pct = (1.0 + total_return_gross / 100.0) * cost_bps / 100.0
    total_cost_pct = buy_cost_pct + sell_cost_pct
    total_return = total_return_gross - total_cost_pct
else:
    total_return = total_return_gross
```

### 3. `_calculate_performance_single_longterm`関数にコストパラメータを追加

並列実行時にコストを渡せるように、`_calculate_performance_single_longterm`関数に`cost_bps`パラメータを追加しました。

### 4. コスト情報をデバッグ用に追加

`portfolio_topix_comparison`に`cost_info`を追加し、コストの詳細を確認できるようにしました。

## 検証方法

修正後、以下のコマンドでコストが正しく適用されているか確認できます：

```powershell
python scripts/verify_cost_application.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json `
  --test-period 2022 `
  --cost-bps-list "0,10,25,50"
```

期待される結果：
- 0bpsと25bpsで**明確な差分**が発生する
- コストが大きくなるほど、リターンが減少する

## 注意事項

- 長期保有型（24ヶ月ホライズン）では、リバランスが1回だけなので、コストの影響は比較的小さい
- ただし、25bpsの場合、約0.5%ポイント程度の影響があるはず
- 0bpsと25bpsで同じ結果が出る場合は、コストが適用されていない可能性がある

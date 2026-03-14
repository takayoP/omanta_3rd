# 同じパラメータでの両ルート比較結果（まとめ）

## 実行結果

同じパラメータファイル（`params_operational_24M_lambda0.00_best_20260111_154617.json`）を使用して、2023-01-31の結果を比較しました。

## パフォーマンスの比較

| 項目 | compare側 | optimize側 | 差 |
|------|-----------|-----------|-----|
| **avg_annualized_excess_return_pct** | **9.60%** | **6.25%** | **+3.35%pt** |
| **mean_annual_excess_return_pct** | N/A | **6.25%** | - |
| **total_return_pct** | **64.27%** | **55.77%** | **+8.50%pt** |

## optimize側の詳細（[DEBUG]出力から）

```json
{
  "rebalance_date": "2023-01-31",
  "entry_date": "2023-01-31",
  "exit_date": "2025-01-31",
  "selected_codes": [1669, 1424, 285, 1667, 1668, 621, 1138, 1125, 705, 156, 438, 165],
  "weights": [0.0880, 0.0865, 0.0861, 0.0856, 0.0838, 0.0837, 0.0822, 0.0821, 0.0819, 0.0813, 0.0794, 0.0794],
  "total_return_pct": 55.77%,
  "topix_return_pct": 40.55%,
  "excess_return_pct": 15.22%,
  "annualized_total_return_pct": 24.79%,
  "annualized_topix_return_pct": 18.54%,
  "annualized_excess_return_pct": 6.25%,
  "holding_years": 2.0014年
}
```

## 重要な発見

### ⚠️ **同じパラメータでもパフォーマンスが異なる**

同じパラメータファイルを使用しているにもかかわらず、パフォーマンスに差があります：

- **total_return_pct**: compare側 64.27% vs optimize側 55.77%（差: +8.50%pt）
- **avg_annualized_excess_return_pct**: compare側 9.60% vs optimize側 6.25%（差: +3.35%pt）

### 考えられる原因

1. **評価日が異なる可能性**
   - compare側: 評価日が異なる可能性（確認が必要）
   - optimize側: 2025-01-31（固定ホライズン）

2. **計算方法の違い**
   - compare側: `avg_annualized_excess_return_pct`（各ポートフォリオの年率超過を平均）
   - optimize側: `mean_annual_excess_return_pct`（各ポートフォリオの年率超過を平均）

3. **ポートフォリオ生成の違い**
   - 同じパラメータでも、実装の違いによりポートフォリオが異なる可能性

## 次のステップ

1. **compare側の詳細情報（selected_codes、weights、exit_date）を取得**
2. **両ルートのポートフォリオが一致しているか確認**
3. **評価日が一致しているか確認**
4. **計算方法の違いを詳細に比較**

## 結論

同じパラメータを使用しているにもかかわらず、パフォーマンスに差があることが確認されました。これは、実装の違いや評価方法の違いによる可能性があります。

詳細な調査が必要です。





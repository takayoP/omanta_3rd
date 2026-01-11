# 2023-01-31の両ルート比較結果（デバッグ出力比較）

## 実行結果

同じパラメータファイル（`params_operational_24M_lambda0.00_best_20260111_154617.json`）を使用して、2023-01-31の結果を比較しました。

## optimize側のデバッグ出力

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

## compare側のデバッグ出力

```json
{
  "rebalance_date": "2023-01-31",
  "entry_date": "2023-01-31",
  "exit_date": "2025-01-31",
  "selected_codes": [1716, 621, 568, 512, 1669, 1245, 1828, 793, 1424, 744, 1555, 1667],
  "weights": [0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833, 0.0833],
  "total_return_pct": 64.27%,
  "topix_return_pct": 40.55%,
  "excess_return_pct": 23.72%,
  "annualized_total_return_pct": 28.14%,
  "annualized_topix_return_pct": 18.54%,
  "annualized_excess_return_pct": 9.60%,
  "holding_years": 2.0014年,
  "params_hash": "b1f763b3",
  "portfolio_hash": "458c5408"
}
```

## 重要な発見

### ⚠️ **ポートフォリオが完全に異なる（パターンA）**

| 項目 | optimize側 | compare側 | 一致？ |
|------|-----------|----------|--------|
| **selected_codes** | [1669, 1424, 285, 1667, 1668, 621, 1138, 1125, 705, 156, 438, 165] | [1716, 621, 568, 512, 1669, 1245, 1828, 793, 1424, 744, 1555, 1667] | ❌ **完全に異なる** |
| **重み** | 不均等（7.94%～8.80%） | 等権重（8.33%） | ❌ **異なる** |
| **exit_date** | 2025-01-31 | 2025-01-31 | ✅ **一致** |
| **topix_return_pct** | 40.55% | 40.55% | ✅ **一致** |
| **total_return_pct** | 55.77% | 64.27% | ❌ **+8.50%ptの差** |
| **annualized_excess_return_pct** | 6.25% | 9.60% | ❌ **+3.35%ptの差** |

### 結論

**パターンA（ポートフォリオ生成の違い）が確定しました。**

- **selected_codesが完全に異なる**
- **重みも異なる**（optimize側: 不均等、compare側: 等権重）
- **exit_dateとtopix_return_pctは一致**しているため、評価日やTOPIX計算は同じ
- **total_return_pctが8.50%pt違う**のは、ポートフォリオ（銘柄）が異なるため

### 考えられる原因

1. **ポートフォリオ生成のロジックが異なる**
   - optimize側: 不均等な重み
   - compare側: 等権重（8.33%ずつ）

2. **選択アルゴリズムの違い**
   - optimize側とcompare側で、同じパラメータでも異なるポートフォリオを生成している

### 次のステップ

1. **ポートフォリオ生成のコードを比較**
   - optimize側の`select_portfolio`とcompare側の`select_portfolio`が同じか確認
   - 重みの計算方法が異なる可能性

2. **params_hashを比較**
   - optimize側にもparams_hashを追加して、同じパラメータが使用されているか確認

3. **ポートフォリオ生成の実装を統一**
   - 同じパラメータで同じポートフォリオが生成されるように実装を統一


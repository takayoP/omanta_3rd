# 2023-01-31の両ルート比較結果（ハッシュ比較・確定版）

## 実行結果

同じパラメータファイル（`params_operational_24M_lambda0.00_best_20260111_154617.json`）を使用して、2023-01-31の結果を比較しました。

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

**関数情報:**
- `select_portfolio` module: `src.omanta_3rd.jobs.longterm_run`
- `build_features` module: `src.omanta_3rd.jobs.longterm_run`

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
  "holding_years": 2.0014年,
  "params_hash": "b1f763b3",
  "portfolio_hash": "5e833876"
}
```

## 重要な発見

### ✅ **params_hashが一致**

| 項目 | compare側 | optimize側 | 一致？ |
|------|-----------|-----------|--------|
| **params_hash** | `b1f763b3` | `b1f763b3` | ✅ **一致** |
| **portfolio_hash** | `458c5408` | `5e833876` | ❌ **不一致** |
| **selected_codes** | [1716, 621, 568, ...] | [1669, 1424, 285, ...] | ❌ **完全に異なる** |
| **重み** | 等権重（0.0833） | 不均等（0.0879～0.0794） | ❌ **異なる** |

### 結論

1. **原因3（effective params差）は除外**
   - `params_hash`が一致しているため、パラメータは同じ

2. **原因1/2（生成ロジック差）が確定**
   - `portfolio_hash`が不一致
   - 同じ`select_portfolio`関数を呼んでいるが、結果が異なる
   - compare側の重みが完全等分（0.0833）になっている

### 考えられる原因

1. **等ウェイト強制が入っている**
   - compare側で`select_portfolio`の結果を上書きしている可能性
   - `weights = [1.0/len(selected)] * len(selected)`のような処理が入っている

2. **`select_portfolio`の呼び出し方法が異なる**
   - 同じ関数でも、引数の渡し方や前処理が異なる可能性

### 次のステップ

1. **`select_portfolio`の実装を確認**
   - 重みの計算方法を確認
   - 等ウェイト強制が入っていないか確認

2. **compare側で重みが上書きされていないか確認**
   - `run_backtest_with_params_file`内で重みを上書きしている箇所を探す
   - `1.0/len`、`equal`、`weight =`などのキーワードで検索

3. **`select_portfolio`の呼び出し前後で重みをログ出力**
   - `select_portfolio`の戻り値の重みを確認
   - compare側で上書きされているか確認





# 2023-01-31の両ルート比較結果（ハッシュ比較）

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

## optimize側のデバッグ出力（予定）

optimize側にも`params_hash`と`portfolio_hash`を追加しました。次回実行時に取得予定です。

## 重要な発見

### 関数のモジュール名は一致

- compare側: `src.omanta_3rd.jobs.longterm_run.select_portfolio`
- optimize側: 同じモジュールを使用しているはず

### 次のステップ

1. **optimize側の`params_hash`を確認**
   - `params_hash`が一致していない → 原因3（effective params差）
   - `params_hash`一致、`portfolio_hash`不一致 → 原因1/2（生成ロジック差）

2. **等ウェイト強制の確認**
   - compare側の重みが完全等分（0.0833）になっている原因を調査
   - `select_portfolio`の実装を確認


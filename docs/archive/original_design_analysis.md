# 元々の設計の確認

## コードの使用状況

### `select_portfolio`（longterm_run.py） - 等ウェイト

**使用箇所:**
1. `batch_longterm_run.py`: 131行目（本番運用）
2. `longterm_run.py`: 2055行目（`main`関数内）
3. `batch_longterm_run_with_regime.py`: 253行目（レジーム切替）
4. `compare_lambda_penalties.py`: 256行目（比較スクリプト）

**実装:**
```python
# src/omanta_3rd/jobs/longterm_run.py:1978
sel["weight"] = 1.0 / n  # 等ウェイト強制
```

### `_select_portfolio_with_params`（optimize.py） - スコアベースの重み

**使用箇所:**
1. `optimize.py`: 366行目（`_run_single_backtest`内）
2. `optimize_timeseries.py`: 344行目（時系列最適化）

**実装:**
```python
# src/omanta_3rd/jobs/optimize.py:307-312
total_score = sel_df["core_score"].sum()
if total_score > 0:
    sel_df["weight"] = sel_df["core_score"] / total_score  # スコアベースの重み
else:
    sel_df["weight"] = 1.0 / len(sel_df)
```

## ドキュメントの記載

`chat/No1_cursor_investment_algorithm_folder_stru.md`の9081-9177行目によると：

> **現在の実装では**等加重（Equal Weight）方式を使用

> `portfolio_monthly`テーブルの`weight`について：
> - 現在の実装: 等加重方式（選定銘柄数で1.0を均等に分割）

## 結論

**元々の設計は「等ウェイト（`select_portfolio`）」です。**

1. **元々の実装**: `select_portfolio`（longterm_run.py）
   - 等ウェイト強制（`sel["weight"] = 1.0 / n`）
   - 本番運用で使用（`batch_longterm_run.py`など）
   - ドキュメントでも「現在の実装では等加重方式を使用」と記載

2. **最適化用に追加された実装**: `_select_portfolio_with_params`（optimize.py）
   - スコアベースの重み（`sel_df["weight"] = sel_df["core_score"] / total_score`）
   - 関数名に`_`がついている = 内部関数（private）
   - 最適化専用（`optimize.py`、`optimize_timeseries.py`で使用）

### 影響

- **compare側**: 元々の実装（`select_portfolio`）を使用 → 等ウェイト
- **optimize側**: 最適化用の実装（`_select_portfolio_with_params`）を使用 → スコアベースの重み

この不一致が、今回の問題の原因です。





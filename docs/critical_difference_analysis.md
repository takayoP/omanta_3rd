# 重要な違いの分析：`select_portfolio` vs `_select_portfolio_with_params`

## 重要な発見

### `_select_portfolio_with_params`は`core_score`を再計算している

`_select_portfolio_with_params`（optimize.py）の217-265行目を見ると：

```python
# Value score
df["forward_per_pct"] = df.groupby("sector33")["forward_per"].transform(...)
df["pbr_pct"] = df.groupby("sector33")["pbr"].transform(...)
df["value_score"] = ...

# Size score
df["log_mcap"] = df["market_cap"].apply(_log_safe)
df["size_score"] = _pct_rank(df["log_mcap"], ascending=True)

# Quality score
df["roe_score"] = _pct_rank(df["roe"], ascending=True)
df["quality_score"] = df["roe_score"]

# Growth score
df["op_growth_score"] = _pct_rank(df["op_growth"], ascending=True).fillna(0.5)
df["profit_growth_score"] = _pct_rank(df["profit_growth"], ascending=True).fillna(0.5)
df["op_trend_score"] = _pct_rank(df["op_trend"], ascending=True).fillna(0.5)
df["growth_score"] = ...

# Record-high score
df["record_high_score"] = df["record_high_forecast_flag"].astype(float)

# Core score
df["core_score"] = (
    strategy_params.w_quality * df["quality_score"]
    + strategy_params.w_value * df["value_score"]
    + strategy_params.w_growth * df["growth_score"]
    + strategy_params.w_record_high * df["record_high_score"]
    + strategy_params.w_size * df["size_score"]
)
```

**`_select_portfolio_with_params`は`core_score`を再計算しています！**

### `select_portfolio`は`core_score`が既に計算済みである前提

`select_portfolio`（longterm_run.py）は：

```python
# Pool by core score
pool = f.sort_values("core_score", ascending=False).head(params.pool_size).copy()
```

**`core_score`が既に`feat`に含まれている前提**です。

### 問題点

`build_features`が`core_score`を計算しているかどうかを確認する必要があります。

もし`build_features`が`core_score`を計算していない場合：
- `select_portfolio`は動作しない（`core_score`カラムが存在しない）
- しかし、実際には動作しているということは、`build_features`が`core_score`を計算している

もし`build_features`が`core_score`を計算している場合：
- `_select_portfolio_with_params`は再計算しているが、パラメータが同じなら結果は同じ
- ただし、`_select_portfolio_with_params`は`core_score`を再計算しているため、`build_features`で計算された`core_score`は使用されない

## 次のステップ

`build_features`がどのカラムを返しているか確認する必要があります。





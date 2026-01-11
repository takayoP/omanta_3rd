# 関数比較分析：`select_portfolio` vs `_select_portfolio_with_params`

## 比較目的

optimize側を等ウェイトに統一するために、どちらの方法が適切か判断する：
- 案B: optimize側を`select_portfolio`（longterm_run.py）に寄せるだけ
- 案A: 共通関数化が必要か

## 比較項目

### 1. フィルタリング処理

#### `select_portfolio`（longterm_run.py）
```python
# liquidity filter
q = f["liquidity_60d"].quantile(params.liquidity_quantile_cut)
f = f[(f["liquidity_60d"].notna()) & (f["liquidity_60d"] >= q)]

# ROE threshold
f = f[(f["roe"].notna()) & (f["roe"] >= params.roe_min)]
```

#### `_select_portfolio_with_params`（optimize.py）
```python
# Liquidity filter
if strategy_params.liquidity_quantile_cut > 0:
    q = df["liquidity_60d"].quantile(strategy_params.liquidity_quantile_cut)
    df = df[df["liquidity_60d"] >= q]

# ROE filter
df = df[df["roe"] >= strategy_params.roe_min]
```

**結論**: 同じ処理

### 2. スコア計算

#### `select_portfolio`（longterm_run.py）
- `core_score`は既に`feat`に含まれている（`build_features`で計算済み）
- `entry_score`も既に`feat`に含まれている（`build_features`で計算済み）

#### `_select_portfolio_with_params`（optimize.py）
- `core_score`を再計算（value_score、growth_score、quality_score、record_high_score、size_scoreを計算してから）
- `entry_score`を再計算（`_calculate_entry_score_with_params`を呼び出す）

**結論**: `_select_portfolio_with_params`はスコアを再計算しているが、`select_portfolio`は既存のスコアを使用

### 3. プール選択

#### `select_portfolio`（longterm_run.py）
```python
pool = f.sort_values("core_score", ascending=False).head(params.pool_size).copy()
```

#### `_select_portfolio_with_params`（optimize.py）
```python
pool = df.nlargest(strategy_params.pool_size, "core_score")
```

**結論**: 同じ処理（`core_score`で上位`pool_size`を選択）

### 4. エントリースコアでのソート

#### `select_portfolio`（longterm_run.py）
```python
if params.use_entry_score:
    pool = pool.sort_values(["entry_score", "core_score"], ascending=[False, False])
```

#### `_select_portfolio_with_params`（optimize.py）
```python
if strategy_params.use_entry_score:
    pool = pool.sort_values(
        ["entry_score", "core_score"], ascending=[False, False]
    )
```

**結論**: 同じ処理

### 5. セクターキャップ

#### `select_portfolio`（longterm_run.py）
```python
for _, r in pool.iterrows():
    sec = r.get("sector33") or "UNKNOWN"
    if sector_counts.get(sec, 0) >= params.sector_cap:
        continue
    sector_counts[sec] = sector_counts.get(sec, 0) + 1
    selected_rows.append(r)
    if len(selected_rows) >= params.target_max:
        break
```

#### `_select_portfolio_with_params`（optimize.py）
```python
for _, row in pool.iterrows():
    sector = row["sector33"]
    if sector_counts.get(sector, 0) < strategy_params.sector_cap:
        selected.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= strategy_params.target_max:
            break
```

**結論**: 同じ処理（セクターキャップとtarget_maxで選択）

### 6. 最小銘柄数チェック

#### `select_portfolio`（longterm_run.py）
```python
if len(selected_rows) < params.target_min:
    selected_rows = pool.head(params.target_max).to_dict("records")
```

#### `_select_portfolio_with_params`（optimize.py）
```python
if len(selected) < strategy_params.target_min:
    # セクター制限を緩和
    selected_indices = [...]
    remaining = pool[~pool.index.isin(selected_indices)]
    for _, row in remaining.iterrows():
        selected.append(row)
        if len(selected) >= strategy_params.target_min:
            break
```

**結論**: 同じ目的だが、実装が微妙に異なる（`select_portfolio`の方がシンプル）

### 7. 重みの計算

#### `select_portfolio`（longterm_run.py）
```python
n = len(sel)
sel["weight"] = 1.0 / n  # 等ウェイト
```

#### `_select_portfolio_with_params`（optimize.py）
```python
total_score = sel_df["core_score"].sum()
if total_score > 0:
    sel_df["weight"] = sel_df["core_score"] / total_score  # スコアベース
else:
    sel_df["weight"] = 1.0 / len(sel_df)  # フォールバック: 等ウェイト
```

**結論**: **これが唯一の違い**（重みの計算方法）

## 総合判断

### 結論：**案B（最小変更）で対応可能**

理由：
1. **銘柄選定ロジックはほぼ同じ**
   - フィルタリング、プール選択、エントリースコアでのソート、セクターキャップ、最小銘柄数チェックは同じ
   - 唯一の違いは「重みの計算方法」だけ

2. **スコア計算の違いは問題にならない**
   - `select_portfolio`は`build_features`で計算済みのスコアを使用
   - `_select_portfolio_with_params`は再計算しているが、`build_features`で既に計算済みなら結果は同じ

3. **最小銘柄数チェックの実装の違いも問題にならない**
   - 目的は同じ（最小銘柄数に満たない場合はセクター制限を緩和）
   - `select_portfolio`の方がシンプルで問題なし

### 推奨対応：案B（最小変更）

optimize側で`_select_portfolio_with_params`の代わりに`select_portfolio`を使用する。

ただし、以下の点に注意：
1. `build_features`で`entry_score`が計算済みか確認（計算済みなら問題なし）
2. `select_portfolio`は`build_features`で計算済みのスコアを使用する前提


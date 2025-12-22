# PER/PBR/Forward PER計算ロジック修正実装計画

## 概要

ChatGPTの提案に基づき、標準的なPER/PBR/Forward PER計算ロジックに修正します。

## 修正箇所

### 1. 価格データの取得（1020-1022行目）

**現行**:
```python
# 調整後終値（adj_close）を使用（以前のロジックに戻す）
px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "adj_close"]].copy()
px_today = px_today.rename(columns={"adj_close": "price"})
```

**修正後**:
```python
# 未調整終値（close）を使用（標準的なロジック）
px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "close"]].copy()
px_today = px_today.rename(columns={"close": "price"})
```

### 2. FY実績データの取得確認（1032行目）

`_load_latest_fy`関数が`shares_outstanding`と`treasury_shares`を返していることを確認。
既に返している場合は変更不要。

### 3. 標準EPS/BPS/予想EPSの計算とPER/PBR/Forward PERの再計算（1084-1144行目）

**現行コード（1084-1144行目）**:
```python
# 以前のロジックでは、EPS/BPSの調整は行わない（そのまま使用）

# 最新株数ベースの発行済み株式数を計算（以前のロジックに戻す）
# net_shares_adjusted(d) = net_shares_raw(d) / CAF(d)
def _get_latest_basis_shares_for_price_date(row):
    """
    評価日時点の発行済み株式数を計算（以前のCAFベースの方法に戻す）
    
    以前のロジック：
    - 評価日時点の実際の株数を取得（shares_raw）
    - CAF（累積調整係数）を計算
    - shares_adjusted = shares_raw / caf
    
    これにより、評価日より後に発生した分割・併合を考慮して調整します。
    """
    code = row.get("code")
    
    if not code:
        return np.nan
    
    # 評価日時点の実際の発行済み株式数を取得
    shares_raw, _ = _get_shares_at_date(conn, code, price_date)
    if pd.isna(shares_raw) or shares_raw <= 0:
        return np.nan
    
    # 累積調整係数（CAF）を計算（評価日より後のAdjustmentFactorの累積積）
    # 警告を抑制してCAFを計算（以前のロジックに戻すため）
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, price_date)
    
    if pd.isna(caf) or caf <= 0:
        return np.nan
    
    # 調整後株数 = 実際の株数 / CAF
    shares_adjusted = shares_raw / caf
    
    return shares_adjusted

# 以前のロジックに戻す: 時価総額ベースではなく、直接PER/PBRを計算
# PBR from latest FY (price / bvps)
df["pbr"] = df.apply(lambda r: _safe_div(r.get("price"), r.get("bvps")), axis=1)

# Forward PER from forecast_eps (price / forecast_eps)
# 以前のロジックでは、forecast_eps_fcを直接使用（調整なし）
df["forward_per"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("forecast_eps_fc"))
    if pd.notna(r.get("forecast_eps_fc")) and r.get("forecast_eps_fc") > 0
    else np.nan,
    axis=1
)

# PER from actual eps (price / eps)
# 以前のロジックでは、epsを直接使用（調整なし）
df["per"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("eps"))
    if pd.notna(r.get("eps")) and r.get("eps") > 0
    else np.nan,
    axis=1
)
```

**修正後コード（性能最適化版）**:
```python
# 標準的なロジック: EPS/BPS/予想EPSを自前で計算
# 1. FY期末のネット株数を計算
# 注意: treasury_sharesがnp.nanの場合は0扱い（明示的に処理）
def _calculate_net_shares_fy(row):
    """FY期末のネット株数を計算"""
    so = row.get("shares_outstanding")
    ts = row.get("treasury_shares")
    
    if pd.isna(so) or so <= 0:
        return np.nan
    
    # treasury_sharesがnp.nanの場合は0扱い（明示的に処理）
    if pd.isna(ts):
        ts = 0.0
    elif ts < 0:
        ts = 0.0
    
    net_shares = so - ts
    return net_shares if net_shares > 0 else np.nan

df["net_shares_fy"] = df.apply(_calculate_net_shares_fy, axis=1)

# 2. FY期末から評価日までの分割倍率を計算（性能最適化: 一括取得）
# 銘柄ごとに1回だけSQLを実行するように最適化
unique_codes = df["code"].unique()
split_mult_dict = {}

for code in unique_codes:
    code_rows = df[df["code"] == code]
    if code_rows.empty:
        continue
    
    # 同じ銘柄の最初の行からfy_endを取得（同じ銘柄は同じfy_endのはず）
    fy_end = code_rows.iloc[0].get("current_period_end")
    
    if pd.isna(fy_end):
        split_mult_dict[code] = 1.0
        continue
    
    # datetime型に変換
    if hasattr(fy_end, 'strftime'):
        fy_end_str = fy_end.strftime("%Y-%m-%d")
    else:
        fy_end_str = str(fy_end)
    
    # fy_end >= price_date の防御（異常な将来日付の場合は倍率=1.0）
    if fy_end_str >= price_date:
        split_mult_dict[code] = 1.0
        continue
    
    split_mult_dict[code] = _split_multiplier_between(conn, code, fy_end_str, price_date)

# dictからmapで流し込む
df["split_mult_fy_to_price"] = df["code"].map(split_mult_dict).fillna(1.0)

# 3. 評価日時点のネット株数（補正後）を計算
df["net_shares_at_price"] = df.apply(
    lambda r: r.get("net_shares_fy") * r.get("split_mult_fy_to_price")
    if pd.notna(r.get("net_shares_fy")) and pd.notna(r.get("split_mult_fy_to_price")) and r.get("net_shares_fy") > 0
    else np.nan,
    axis=1
)

    # 4. 標準EPS/BPS/予想EPSを計算
    # 標準EPS（実績）
    # 注意: profit <= 0 の場合はNaN（負のPERは意味がないため、スクリーニング用途として妥当）
    df["eps_std"] = df.apply(
        lambda r: _safe_div(r.get("profit"), r.get("net_shares_at_price"))
        if pd.notna(r.get("profit")) and pd.notna(r.get("net_shares_at_price")) and r.get("profit") > 0
        else np.nan,
        axis=1
    )

# 標準BPS（実績）
df["bps_std"] = df.apply(
    lambda r: _safe_div(r.get("equity"), r.get("net_shares_at_price"))
    if pd.notna(r.get("equity")) and pd.notna(r.get("net_shares_at_price")) and r.get("equity") > 0
    else np.nan,
    axis=1
)

    # 標準予想EPS（予想）
    # 列名の存在チェック（merge後の列名を確認）
    forecast_profit_col = None
    forecast_eps_col = None
    
    # forecast_profit_fc を優先、なければ forecast_profit も確認
    if "forecast_profit_fc" in df.columns:
        forecast_profit_col = "forecast_profit_fc"
    elif "forecast_profit" in df.columns:
        forecast_profit_col = "forecast_profit"
        print("[warning] forecast_profit_fc not found, using forecast_profit instead")
    else:
        print("[warning] forecast_profit_fc and forecast_profit not found")
    
    # forecast_eps_fc を優先、なければ forecast_eps も確認
    if "forecast_eps_fc" in df.columns:
        forecast_eps_col = "forecast_eps_fc"
    elif "forecast_eps" in df.columns:
        forecast_eps_col = "forecast_eps"
        print("[warning] forecast_eps_fc not found, using forecast_eps instead")
    
    # 第一優先: forecast_profitから計算
    if forecast_profit_col:
        df["forecast_eps_std"] = df.apply(
            lambda r: _safe_div(r.get(forecast_profit_col), r.get("net_shares_at_price"))
            if pd.notna(r.get(forecast_profit_col)) and pd.notna(r.get("net_shares_at_price")) and r.get(forecast_profit_col) > 0
            else np.nan,
            axis=1
        )
    else:
        df["forecast_eps_std"] = np.nan
    
    # フォールバック: forecast_eps（J-Quants）を使う
    # forecast_profitが欠損している場合のみ
    if forecast_eps_col:
        df["forecast_eps_std"] = df.apply(
            lambda r: r.get(forecast_eps_col)
            if pd.isna(r.get("forecast_eps_std")) and pd.notna(r.get(forecast_eps_col)) and r.get(forecast_eps_col) > 0
            else r.get("forecast_eps_std"),
            axis=1
        )

# 5. PER/PBR/Forward PERを標準的な方法で計算
# 実績PER（Trailing PER）
df["per"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("eps_std"))
    if pd.notna(r.get("eps_std")) and r.get("eps_std") > 0
    else np.nan,
    axis=1
)

# 実績PBR
df["pbr"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("bps_std"))
    if pd.notna(r.get("bps_std")) and r.get("bps_std") > 0
    else np.nan,
    axis=1
)

# 予想PER（Forward PER）
df["forward_per"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("forecast_eps_std"))
    if pd.notna(r.get("forecast_eps_std")) and r.get("forecast_eps_std") > 0
    else np.nan,
    axis=1
)

# 時価総額も計算（他の用途で使用される可能性があるため）
df["market_cap_latest_basis"] = df.apply(
    lambda r: r.get("price") * r.get("net_shares_at_price")
    if pd.notna(r.get("price")) and pd.notna(r.get("net_shares_at_price")) and r.get("net_shares_at_price") > 0
    else np.nan,
    axis=1
)
```

## 実装手順

1. **価格データの取得を修正**（1020-1022行目）
   - `adj_close`を`close`に変更

2. **標準EPS/BPS/予想EPSの計算を追加**（1084行目以降）
   - FY期末のネット株数を計算
   - 分割倍率を計算（既存の`_split_multiplier_between`関数を使用）
   - 評価日時点のネット株数を計算
   - 標準EPS/BPS/予想EPSを計算

3. **PER/PBR/Forward PERの計算を修正**（1124-1144行目）
   - 新しい標準EPS/BPS/予想EPSを使用して計算

4. **時価総額の計算を修正**（1146-1153行目）
   - `net_shares_at_price`を使用

## 注意事項

1. **既存の`_split_multiplier_between`関数を使用**: 既に実装されているため、新規作成不要
2. **フォールバック処理**: `forecast_profit_fc`が欠損している場合のみ`forecast_eps_fc`を使用
3. **デバッグ用カラム**: `net_shares_fy`, `split_mult_fy_to_price`, `net_shares_at_price`, `eps_std`, `bps_std`, `forecast_eps_std`を保持
4. **後方互換性**: 必要に応じて、旧ロジックの結果も併存して比較ログを出す

## テスト

修正後、以下の銘柄で計算結果を確認：
- 1605, 6005, 8136, 9202, 8725, 4507, 8111

標準的なロジックに修正されていることを確認します。

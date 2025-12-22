# PER/PBR/Forward PER計算ロジック仕様書

## 概要

本仕様書は、株式のPER（株価収益率）、PBR（株価純資産倍率）、Forward PER（予想PER）の計算ロジックを詳細に説明します。
このロジックは、J-Quants APIから取得したデータを使用し、株式分割・併合を適切に考慮した計算方法です。

## データベーススキーマ

### prices_dailyテーブル
- `date`: 日付（YYYY-MM-DD）
- `code`: 銘柄コード（4桁文字列）
- `adj_close`: 調整後終値（株式分割・併合を調整した終値）**← 本ロジックで使用**
- `close`: 未調整終値（株式分割・併合を調整していない終値）
- `adjustment_factor`: 調整係数（株式分割・併合の調整係数、例: 1:3分割の場合0.333333）
- `turnover_value`: 売買代金

### fins_statementsテーブル
- `code`: 銘柄コード（4桁文字列）
- `disclosed_date`: 開示日（YYYY-MM-DD）
- `current_period_end`: 期末日（YYYY-MM-DD）
- `type_of_current_period`: 期間種別（'FY'=通期、'Q1'=第1四半期、'Q2'=第2四半期、'Q3'=第3四半期）
- `profit`: 当期純利益
- `equity`: 純資産
- `eps`: 1株当たり当期純利益（EPS）
- `bvps`: 1株当たり純資産（BPS）
- `forecast_eps`: 予想EPS
- `forecast_profit`: 予想利益
- `forecast_operating_profit`: 予想営業利益
- `shares_outstanding`: 発行済み株式数
- `treasury_shares`: 自己株式数

## 計算フロー

### ステップ1: 評価日の確定

評価日（`asof`）を受け取り、実際の価格データが存在する営業日を取得します。

```python
def _snap_price_date(conn, asof: str) -> str:
    """
    評価日を営業日にスナップ（価格データが存在する最新の日付を取得）
    """
    df = pd.read_sql_query(
        "SELECT MAX(date) AS d FROM prices_daily WHERE date <= ?",
        conn,
        params=(asof,),
    )
    if df.empty or pd.isna(df.iloc[0]["d"]):
        raise RuntimeError(f"No prices_daily.date <= {asof}. Load prices first.")
    return str(df.iloc[0]["d"])
```

### ステップ2: 価格データの取得

評価日の調整後終値（`adj_close`）を取得します。

```python
# 価格データを取得（過去200日分）
prices_win = _load_prices_window(conn, price_date, lookback_days=200)

# 評価日の調整後終値を取得
px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "adj_close"]].copy()
px_today = px_today.rename(columns={"adj_close": "price"})
```

**重要**: 
- `close`（未調整終値）ではなく、`adj_close`（調整後終値）を使用します
- これにより、株式分割・併合が発生した場合でも、時系列で一貫した価格を使用できます

### ステップ3: 最新のFY実績データの取得

`disclosed_date <= 評価日` かつ `type_of_current_period = 'FY'` の条件で、銘柄ごとに最新の財務データを取得します。

```sql
WITH ranked AS (
  SELECT
    code, current_period_end, disclosed_date,
    profit, equity, eps, bvps,
    shares_outstanding, treasury_shares,
    ROW_NUMBER() OVER (
      PARTITION BY code
      ORDER BY current_period_end DESC, disclosed_date DESC
    ) AS rn
  FROM fins_statements
  WHERE disclosed_date <= ?
    AND type_of_current_period = 'FY'
)
SELECT *
FROM ranked
WHERE rn = 1
```

**ポイント**:
- `ROW_NUMBER() OVER (PARTITION BY code ORDER BY ...)` を使用して、銘柄ごとに最新のデータを取得
- `current_period_end DESC, disclosed_date DESC` でソートし、最新の期末データを優先
- 同じ`current_period_end`のデータが複数ある場合、最新の`disclosed_date`を優先

### ステップ4: 最新の予想データの取得

`disclosed_date <= 評価日` の条件で、銘柄ごとに最新の予想データを取得します。
FYを優先し、同じ開示日の場合FYを優先します。

```sql
WITH ranked AS (
  SELECT
    code, disclosed_date, type_of_current_period,
    forecast_operating_profit, forecast_profit, forecast_eps,
    next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
    ROW_NUMBER() OVER (
      PARTITION BY code
      ORDER BY disclosed_date DESC,
               CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END
    ) AS rn
  FROM fins_statements
  WHERE disclosed_date <= ?
    AND (forecast_operating_profit IS NOT NULL 
         OR forecast_profit IS NOT NULL 
         OR forecast_eps IS NOT NULL)
)
SELECT *
FROM ranked
WHERE rn = 1
```

**ポイント**:
- FYを優先: `CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END` でFYを優先
- 四半期データも含める: FYデータがない場合や、FYデータに予想がない場合は、四半期データからも取得
- 予想データが存在する条件: `forecast_operating_profit`、`forecast_profit`、`forecast_eps`のいずれかがNULLでない

### ステップ5: データのマージ

以下の順序でデータをマージします：

```python
df = universe.merge(px_today, on="code", how="inner")  # 価格データ
df = df.merge(liq, on="code", how="left")              # 流動性データ（60日平均売買代金）
df = df.merge(fy_latest, on="code", how="left", suffixes=("", "_fy"))  # FY実績データ
df = df.merge(fc_latest, on="code", how="left", suffixes=("", "_fc"))  # 予想データ
```

**マージ後のカラム名**:
- FY実績データ: `profit`, `equity`, `eps`, `bvps`, `shares_outstanding`, `treasury_shares`など
- 予想データ: `forecast_eps_fc`, `forecast_profit_fc`, `forecast_operating_profit_fc`など（`_fc`サフィックス）

### ステップ6: PER/PBR/Forward PERの計算

#### 6-1. PER（株価収益率）の計算

```python
df["per"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("eps"))
    if pd.notna(r.get("eps")) and r.get("eps") > 0
    else np.nan,
    axis=1
)
```

**計算式**: `PER = price / eps`

- `price`: 調整後終値（`adj_close`）
- `eps`: 最新FYのEPS（財務データに記録されている値をそのまま使用、調整なし）

**条件**:
- `eps`がNULLまたは0以下の場合、PERは`NaN`になります

#### 6-2. PBR（株価純資産倍率）の計算

```python
df["pbr"] = df.apply(lambda r: _safe_div(r.get("price"), r.get("bvps")), axis=1)
```

**計算式**: `PBR = price / bvps`

- `price`: 調整後終値（`adj_close`）
- `bvps`: 最新FYのBPS（財務データに記録されている値をそのまま使用、調整なし）

#### 6-3. Forward PER（予想PER）の計算

```python
df["forward_per"] = df.apply(
    lambda r: _safe_div(r.get("price"), r.get("forecast_eps_fc"))
    if pd.notna(r.get("forecast_eps_fc")) and r.get("forecast_eps_fc") > 0
    else np.nan,
    axis=1
)
```

**計算式**: `Forward PER = price / forecast_eps_fc`

- `price`: 調整後終値（`adj_close`）
- `forecast_eps_fc`: 最新の予想EPS（財務データに記録されている値をそのまま使用、調整なし）

**条件**:
- `forecast_eps_fc`がNULLまたは0以下の場合、Forward PERは`NaN`になります

### ステップ7: 時価総額の計算（参考用）

時価総額は他の用途で使用される可能性があるため、計算します。
ただし、PER/PBR/Forward PERの計算には使用しません。

#### 7-1. 評価日時点の調整後株数の計算

```python
def _get_latest_basis_shares_for_price_date(row):
    """
    評価日時点の発行済み株式数を計算（CAFベースの方法）
    """
    code = row.get("code")
    price_date = "2025-12-19"  # 評価日
    
    # 評価日時点の実際の発行済み株式数を取得
    shares_raw, _ = _get_shares_at_date(conn, code, price_date)
    
    # CAF（累積調整係数）を計算
    # CAF = 評価日より後に発生したAdjustmentFactorの累積積
    caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, price_date)
    
    # 調整後株数 = 実際の株数 / CAF
    shares_adjusted = shares_raw / caf
    
    return shares_adjusted
```

**CAFの計算方法**:
```sql
SELECT date, adjustment_factor
FROM prices_daily
WHERE code = ?
  AND date > ?  -- 評価日より後
  AND adjustment_factor IS NOT NULL
  AND adjustment_factor != 1.0
ORDER BY date ASC
```

CAF = 評価日より後に発生した`adjustment_factor`の累積積

**例**:
- 1:3分割（`adjustment_factor = 0.333333`）が評価日より後に発生した場合、CAF = 0.333333
- 1:2分割（`adjustment_factor = 0.5`）が評価日より後に発生した場合、CAF = 0.5

#### 7-2. 時価総額の計算

```python
df["shares_latest_basis"] = df.apply(_get_latest_basis_shares_for_price_date, axis=1)
df["market_cap_latest_basis"] = df.apply(
    lambda r: r.get("price") * r.get("shares_latest_basis")
    if pd.notna(r.get("price")) and pd.notna(r.get("shares_latest_basis")) and r.get("shares_latest_basis") > 0
    else np.nan,
    axis=1
)
```

**計算式**: `market_cap = price * shares_adjusted`

- `price`: 調整後終値（`adj_close`）
- `shares_adjusted`: 調整後株数（CAFで調整済み）

## 重要な設計方針

### 1. 価格データの選択

- **`adj_close`（調整後終値）を使用**: 株式分割・併合を調整した終値を使用することで、時系列で一貫した比較が可能です
- `close`（未調整終値）は使用しません

### 2. EPS/BPS/予想EPSの調整

- **EPS/BPS/予想EPSは調整しません**: 財務データに記録されている値をそのまま使用します
- 以前の実装では、発行済み株式数の変化に基づいてEPS/BPSを調整していましたが、本ロジックでは調整しません
- 理由: `adj_close`を使用しているため、価格は既に分割・併合を考慮して調整されています。EPS/BPSも分割後の基準で記録されているため、そのまま使用できます

### 3. 予想データの取得

- **FYを優先**: 予想データはFY（通期）を優先して取得します
- **四半期データも含める**: FYデータがない場合や、FYデータに予想がない場合は、四半期データからも取得します
- これにより、予想データのカバレッジが向上します

### 4. 時価総額の計算

- 時価総額は参考用に計算しますが、PER/PBR/Forward PERの計算には使用しません
- 時価総額の計算には、CAF（累積調整係数）を使用して株数を調整します

## 計算例

### 例1: コード7419（ノジマ）

- 評価日: 2025-12-19
- 価格（adj_close）: 1,000円
- EPS: 100円
- BPS: 500円
- 予想EPS: 120円

計算結果:
- PER = 1,000 / 100 = 10.0
- PBR = 1,000 / 500 = 2.0
- Forward PER = 1,000 / 120 = 8.33

### 例2: 株式分割が発生した場合

- 評価日: 2025-12-19
- 価格（adj_close）: 500円（分割後、既に調整済み）
- EPS: 50円（分割後の基準で記録されている）
- BPS: 250円（分割後の基準で記録されている）
- 予想EPS: 60円（分割後の基準で記録されている）

計算結果:
- PER = 500 / 50 = 10.0
- PBR = 500 / 250 = 2.0
- Forward PER = 500 / 60 = 8.33

**重要**: 
- `adj_close`を使用しているため、分割前の価格と分割後の価格は自動的に調整されています
- EPS/BPS/予想EPSも分割後の基準で記録されているため、そのまま使用できます
- そのため、分割前と分割後で同じPER/PBR/Forward PERが計算されます（理論的には）

## 実装上の注意点

### 1. データの欠損値処理

- `price`、`eps`、`bvps`、`forecast_eps_fc`が欠損している場合、対応するPER/PBR/Forward PERは`NaN`になります
- `profit <= 0`または`forecast_profit <= 0`の場合、PER/Forward PERは`NaN`になります（負のPERは意味がないため）

### 2. SQLクエリの最適化

- `ROW_NUMBER() OVER (PARTITION BY code ORDER BY ...)`を使用して、銘柄ごとに最新のデータを取得します
- これにより、`IN (...)`を使った場合のクロスジョイン問題を回避できます

### 3. 予想データの取得ロジック

- FYを優先し、同じ開示日の場合FYを優先するため、`ORDER BY disclosed_date DESC, CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END`を使用します

### 4. 安全な除算関数

```python
def _safe_div(numerator, denominator):
    """
    安全な除算（0除算を回避）
    """
    if pd.isna(numerator) or pd.isna(denominator):
        return np.nan
    if denominator == 0:
        return np.nan
    return numerator / denominator
```

## 計算結果の実例

評価日: 2025-12-19

| コード | PER | PBR | Forward PER |
|--------|-----|-----|-------------|
| 1605 | 9.12 | 0.78 | 9.60 |
| 6005 | 14.23 | 1.66 | 12.52 |
| 8136 | 28.26 | 11.07 | 24.44 |
| 9202 | 9.37 | 1.27 | 9.85 |
| 8725 | 8.42 | 1.42 | 9.50 |
| 4507 | 13.56 | 1.70 | 12.29 |
| 8111 | 4.97 | 1.09 | 14.35 |

## まとめ

本ロジックは、以下の特徴があります:

1. **`adj_close`（調整後終値）を使用**: 株式分割・併合を自動的に考慮
2. **EPS/BPS/予想EPSは調整しない**: 財務データに記録されている値をそのまま使用
3. **予想データはFYを優先**: 四半期データも含めて取得
4. **時価総額は参考用**: PER/PBR/Forward PERの計算には使用しない

このロジックにより、株式分割・併合が発生した場合でも、一貫したPER/PBR/Forward PERの計算が可能です。

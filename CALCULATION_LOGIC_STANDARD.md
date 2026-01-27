# PER/PBR/Forward PER計算ロジック（標準版）仕様書

## 概要

本仕様書は、標準的（一般的）なPER（株価収益率）、PBR（株価純資産倍率）、Forward PER（予想PER）の計算ロジックを定義します。
株式分割・併合を適切に考慮し、時価総額が倍率で崩れる問題を防ぐ設計です。

## 方針（重要）

1. **指標は「評価日（asof）時点の株価」と「その時点の株数ベースの1株指標」で計算する**
2. **株式分割・併合は adjustment_factor を用いて FY期末→評価日までの株数を前進補正し、株価（未調整 close）と同じベースに揃える**
3. **EPS/BPS/予想EPSは、原則 profit/equity/forecast_profit と補正後株数から再計算する**（J-Quantsの eps/bvps/forecast_eps は「参考」＝フォールバック）
4. **目的：分割/併合があっても「時価総額が倍率で崩れる」「price と per-share 指標の基準がズレる」事故を防ぐ**

## 使用するデータ

### prices_dailyテーブル
- `date`: 日付（YYYY-MM-DD）
- `code`: 銘柄コード（4桁文字列）
- **`close`**: 未調整終値 **← 本ロジックで使用**
- `adj_close`: 調整後終値（参考用、本ロジックでは使用しない）
- `adjustment_factor`: 調整係数（株式分割・併合の調整係数、例: 1:3分割の場合0.333333）

### fins_statementsテーブル
- `code`: 銘柄コード（4桁文字列）
- `disclosed_date`: 開示日（YYYY-MM-DD）
- `current_period_end`: 期末日（YYYY-MM-DD）
- `type_of_current_period`: 期間種別（'FY'=通期、'Q1'=第1四半期など）
- `profit`: 当期純利益
- `equity`: 純資産
- `forecast_profit`: 予想利益（予想PER用に最優先で使用）
- `shares_outstanding`: 発行済み株式数
- `treasury_shares`: 自己株式数
- （フォールバック用）`eps`, `bvps`, `forecast_eps`: J-Quantsが計算した1株指標（参考用）

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

評価日の**未調整終値（`close`）**を取得します。

```python
# 価格データを取得（過去200日分）
prices_win = _load_prices_window(conn, price_date, lookback_days=200)

# 評価日の未調整終値を取得
px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "close"]].copy()
px_today = px_today.rename(columns={"close": "price"})
```

**重要**: 
- **`close`（未調整終値）を使用**: 評価日時点の「市場で見える株価」に一致しやすく、バックテストでも「将来の分割」が混入しにくい
- `adj_close`（調整後終値）は使用しません（ただし保存してもOK）

### ステップ3: 最新のFY実績データの取得

`disclosed_date <= 評価日` かつ `type_of_current_period = 'FY'` の条件で、銘柄ごとに最新の財務データを取得します。

```sql
WITH ranked AS (
  SELECT
    code, current_period_end, disclosed_date,
    profit, equity, shares_outstanding, treasury_shares,
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

**取得する列**:
- `profit`: 当期純利益
- `equity`: 純資産
- `shares_outstanding`: 発行済み株式数
- `treasury_shares`: 自己株式数
- `current_period_end`: 期末日

### ステップ4: 最新の予想データの取得

`disclosed_date <= 評価日` の条件で、銘柄ごとに最新の予想データを取得します。
**FYを優先**し、同じ開示日の場合FYを優先します。

```sql
WITH ranked AS (
  SELECT
    code, disclosed_date, type_of_current_period,
    forecast_profit, forecast_eps,
    ROW_NUMBER() OVER (
      PARTITION BY code
      ORDER BY disclosed_date DESC,
               CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END
    ) AS rn
  FROM fins_statements
  WHERE disclosed_date <= ?
    AND type_of_current_period = 'FY'
    AND (forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
)
SELECT *
FROM ranked
WHERE rn = 1
```

**使用するデータ**:
- **第一優先**: `forecast_profit`（予想利益）
- **フォールバック**: `forecast_profit`が無い場合のみ`forecast_eps`を使用

**注意**: FYのみで十分なら、四半期予想を混ぜない方が標準的・安定です。

### ステップ5: 分割・併合を株数に反映（FY期末 → 評価日）

#### 5-1. ベース株数（FY期末のネット株数）

```python
net_shares_fy = shares_outstanding - treasury_shares
```

- `treasury_shares`がNULLの場合は0扱い
- `net_shares_fy <= 0`の場合は`NaN`

#### 5-2. 分割倍率（FY期末→評価日）

`prices_daily`の`(fy_end, price_date]`の範囲で、`adjustment_factor != 1`を拾います。

```python
def _split_multiplier_between(conn, code: str, start_date: str, end_date: str) -> float:
    """
    FY期末から評価日までの分割・併合による株数倍率を計算
    
    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。
    
    例: 1:3分割（adjustment_factor = 0.333333）の場合、
    株数倍率 = 1 / 0.333333 ≈ 3.0
    """
    df = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > ?
          AND date <= ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, start_date, end_date),
    )
    
    if df.empty:
        return 1.0
    
    mult = 1.0
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        if pd.notna(adj_factor) and adj_factor > 0:
            mult *= (1.0 / float(adj_factor))
    
    return mult
```

**計算式**: `split_mult = ∏(1 / adjustment_factor)`

**例**:
- 1:3分割（`adjustment_factor = 0.333333`）の場合、`split_mult = 1 / 0.333333 ≈ 3.0`
- 1:2分割（`adjustment_factor = 0.5`）の場合、`split_mult = 1 / 0.5 = 2.0`

#### 5-3. 評価日時点のネット株数（近似）

```python
net_shares_at_price = net_shares_fy * split_mult
```

これで「期末後に分割したのに株数が増えてない」問題を解消します。

### ステップ6: 標準EPS / 標準BPS / 標準予想EPS の作成

#### 6-1. 標準EPS（実績）

```python
eps_std = profit / net_shares_at_price
```

**条件**:
- `profit <= 0`または`net_shares_at_price <= 0`の場合は`NaN`
- `profit`が`NaN`の場合は`NaN`

#### 6-2. 標準BPS（実績）

```python
bps_std = equity / net_shares_at_price
```

**条件**:
- `equity <= 0`または`net_shares_at_price <= 0`の場合は`NaN`
- `equity`が`NaN`の場合は`NaN`

#### 6-3. 標準予想EPS（予想）

**第一優先**: `forecast_profit`から作る

```python
forecast_eps_std = forecast_profit / net_shares_at_price
```

**条件**:
- `forecast_profit <= 0`の場合は`NaN`
- `forecast_profit`が`NaN`の場合は`NaN`

**フォールバック**: `forecast_eps`（J-Quants）を使う

```python
if pd.isna(forecast_eps_std) and pd.notna(forecast_eps) and forecast_eps > 0:
    forecast_eps_std = forecast_eps
```

**注意**: `forecast_eps`の株数基準が不明確な場合があるため、ログで「fallback使用率」を出すことを推奨します。

### ステップ7: PER / 予想PER / PBR の定義（標準）

#### 7-1. 実績PER（Trailing PER）

```python
per = price / eps_std
```

**条件**:
- `eps_std`が`NaN`または`eps_std <= 0`の場合は`NaN`
- `price`が`NaN`の場合は`NaN`

#### 7-2. 予想PER（Forward PER）

```python
forward_per = price / forecast_eps_std
```

**条件**:
- `forecast_eps_std`が`NaN`または`forecast_eps_std <= 0`の場合は`NaN`
- `price`が`NaN`の場合は`NaN`

#### 7-3. 実績PBR

```python
pbr = price / bps_std
```

**条件**:
- `bps_std`が`NaN`または`bps_std <= 0`の場合は`NaN`
- `price`が`NaN`の場合は`NaN`

## 実装上の推奨

### 1. 計算列（中間）を残す

デバッグ用に`features_monthly`等に以下を保持推奨：

- `price_close`: 未調整終値
- `net_shares_fy`: FY期末のネット株数
- `split_mult_fy_to_price`: FY期末→評価日の分割倍率
- `net_shares_at_price`: 評価日時点のネット株数（補正後）
- `eps_std`: 標準EPS
- `bps_std`: 標準BPS
- `forecast_eps_std`: 標準予想EPS
- `per`: 実績PER
- `forward_per`: 予想PER
- `pbr`: 実績PBR

### 2. 増資・自己株取得の限界（注記）

この仕様は分割/併合は評価日まで反映するが、増資や自己株取得など「期末と評価日の間の株数変動」は`fins_statements`の更新粒度次第で取り切れない（必要なら別ソースで補完）。

### 3. 安全な除算関数

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

## 既存仕様からの差分（要点）

| 項目 | 現行仕様 | 標準版仕様 |
|------|----------|------------|
| 価格 | `adj_close`（調整後終値） | `close`（未調整終値） |
| EPS | DBの`eps`をそのまま使用 | `profit / net_shares_at_price`で再計算 |
| BPS | DBの`bvps`をそのまま使用 | `equity / net_shares_at_price`で再計算 |
| 予想EPS | DBの`forecast_eps`をそのまま使用 | `forecast_profit / net_shares_at_price`で再計算（フォールバックあり） |
| 分割・併合の考慮 | 価格側（`adj_close`）で吸収 | 株数側（`split_mult`）で補正 |

## 実装手順（Cursor実装への最短の作業単位）

1. `px_today`を`adj_close`ではなく`close`で取得する
2. `fy_latest`取得に`current_period_end`と`shares_outstanding`/`treasury_shares`を必ず含める
3. `_split_multiplier_between(code, fy_end, price_date)`関数を作る（既存の関数を活用）
4. `eps_std` / `bps_std` / `forecast_eps_std`を作って`per`/`pbr`/`forward_per`を計算
5. 旧`per`/`pbr`/`forward_per`を置換（または併存して比較ログを出す）

## まとめ

本仕様は、標準的（一般的）なPER/PBR/Forward PERの計算方法を定義しています。
株式分割・併合を適切に考慮し、時価総額が倍率で崩れる問題を防ぐ設計です。

**重要なポイント**:
1. **`close`（未調整終値）を使用**: 評価日時点の市場価格に一致
2. **EPS/BPS/予想EPSを自前で計算**: `profit/equity/forecast_profit`と補正後株数から再計算
3. **分割・併合を株数側で補正**: FY期末→評価日までの分割倍率を計算して株数を補正
4. **標準的な定義**: 四季報等の一般的な指標と一致しやすい



























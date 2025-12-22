# PER/PBR/Forward PER計算ロジック（最終版）

## 概要

本ドキュメントは、株式のPER（株価収益率）、PBR（株価純資産倍率）、Forward PER（予想PER）の計算ロジックを説明します。
このロジックは、以前の実装で精度が良かった部分を採用し、株式分割・併合を適切に考慮した計算方法です。

## 計算対象銘柄の実例

評価日: 2025-12-19

実際に計算した結果:

| コード | PER | PBR | Forward PER |
|--------|-----|-----|-------------|
| 1605 | 9.12 | 0.78 | 9.60 |
| 6005 | 14.23 | 1.66 | 12.52 |
| 8136 | 28.26 | 11.07 | 24.44 |
| 9202 | 9.37 | 1.27 | 9.85 |
| 8725 | 8.42 | 1.42 | 9.50 |
| 4507 | 13.56 | 1.70 | 12.29 |
| 8111 | 4.97 | 1.09 | 14.35 |

これらの値は、以下のロジックで計算されています。

## 使用するデータソース

### 1. 価格データ（prices_dailyテーブル）

- **`adj_close`（調整後終値）**: 株式分割・併合を調整した終値。本ロジックでは**この値を使用**します。
- `close`（未調整終値）: 株式分割・併合を調整していない終値。本ロジックでは使用しません。
- `adjustment_factor`: 株式分割・併合の調整係数（例: 1:3分割の場合、0.333333）

### 2. 財務データ（fins_statementsテーブル）

- `profit`: 当期純利益
- `equity`: 純資産
- `eps`: 1株当たり当期純利益（EPS）
- `bvps`: 1株当たり純資産（BPS）
- `forecast_eps`: 予想EPS
- `forecast_profit`: 予想利益
- `shares_outstanding`: 発行済み株式数
- `treasury_shares`: 自己株式数
- `current_period_end`: 期末日
- `disclosed_date`: 開示日
- `type_of_current_period`: 期間種別（'FY'=通期、'Q1'=第1四半期など）

## 計算ロジック

### ステップ1: 価格データの取得

評価日（`asof`）の調整後終値（`adj_close`）を取得します。

```python
px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "adj_close"]].copy()
px_today = px_today.rename(columns={"adj_close": "price"})
```

**重要**: `close`（未調整終値）ではなく、`adj_close`（調整後終値）を使用します。

### ステップ2: 最新の財務データの取得

#### 2-1. 最新のFY実績データの取得

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
  WHERE disclosed_date <= :asof
    AND type_of_current_period = 'FY'
)
SELECT *
FROM ranked
WHERE rn = 1
```

#### 2-2. 最新の予想データの取得

`disclosed_date <= 評価日` の条件で、銘柄ごとに最新の予想データを取得します。
FYを優先し、同じ開示日の場合FYを優先します。

```sql
WITH ranked AS (
  SELECT
    code, disclosed_date, type_of_current_period,
    forecast_operating_profit, forecast_profit, forecast_eps,
    ROW_NUMBER() OVER (
      PARTITION BY code
      ORDER BY disclosed_date DESC,
               CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END
    ) AS rn
  FROM fins_statements
  WHERE disclosed_date <= :asof
    AND (forecast_operating_profit IS NOT NULL 
         OR forecast_profit IS NOT NULL 
         OR forecast_eps IS NOT NULL)
)
SELECT *
FROM ranked
WHERE rn = 1
```

### ステップ3: PER/PBR/Forward PERの計算

#### 3-1. PER（株価収益率）の計算

```python
PER = price / eps
```

- `price`: 調整後終値（`adj_close`）
- `eps`: 最新FYのEPS（調整なし）

**注意**: EPSは調整しません。財務データに記録されているEPSをそのまま使用します。

#### 3-2. PBR（株価純資産倍率）の計算

```python
PBR = price / bvps
```

- `price`: 調整後終値（`adj_close`）
- `bvps`: 最新FYのBPS（調整なし）

**注意**: BPSは調整しません。財務データに記録されているBPSをそのまま使用します。

#### 3-3. Forward PER（予想PER）の計算

```python
Forward PER = price / forecast_eps_fc
```

- `price`: 調整後終値（`adj_close`）
- `forecast_eps_fc`: 最新の予想EPS（調整なし）

**注意**: 予想EPSは調整しません。財務データに記録されている予想EPSをそのまま使用します。

### ステップ4: 時価総額の計算（参考用）

時価総額は他の用途で使用される可能性があるため、計算します。

#### 4-1. 評価日時点の調整後株数の計算

評価日時点の実際の発行済み株式数を取得し、CAF（累積調整係数）で調整します。

```python
# 評価日時点の実際の発行済み株式数を取得
shares_raw, _ = _get_shares_at_date(conn, code, price_date)

# CAF（累積調整係数）を計算
# CAF = 評価日より後に発生したAdjustmentFactorの累積積
caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, price_date)

# 調整後株数 = 実際の株数 / CAF
shares_adjusted = shares_raw / caf
```

**CAFの計算方法**:
- 評価日より後に発生した`adjustment_factor`の累積積を計算
- 例: 1:3分割（`adjustment_factor = 0.333333`）が評価日より後に発生した場合、CAF = 0.333333
- 例: 1:2分割（`adjustment_factor = 0.5`）が評価日より後に発生した場合、CAF = 0.5

#### 4-2. 時価総額の計算

```python
market_cap = price * shares_adjusted
```

- `price`: 調整後終値（`adj_close`）
- `shares_adjusted`: 調整後株数（CAFで調整済み）

## 重要なポイント

### 1. 価格データの選択

- **`adj_close`（調整後終値）を使用**: 株式分割・併合を調整した終値を使用することで、時系列で一貫した比較が可能です。
- `close`（未調整終値）は使用しません。

### 2. EPS/BPS/予想EPSの調整

- **EPS/BPS/予想EPSは調整しません**: 財務データに記録されている値をそのまま使用します。
- 以前の実装では、発行済み株式数の変化に基づいてEPS/BPSを調整していましたが、本ロジックでは調整しません。

### 3. 予想データの取得

- **FYを優先**: 予想データはFY（通期）を優先して取得します。
- **四半期データも含める**: FYデータがない場合や、FYデータに予想がない場合は、四半期データからも取得します。

### 4. 時価総額の計算

- 時価総額は参考用に計算しますが、PER/PBR/Forward PERの計算には使用しません。
- 時価総額の計算には、CAF（累積調整係数）を使用して株数を調整します。

## 計算例

### 例1: コード7419（ノジマ）

- 評価日: 2025-12-19
- 価格（adj_close）: 仮に1,000円
- EPS: 仮に100円
- BPS: 仮に500円
- 予想EPS: 仮に120円

計算結果:
- PER = 1,000 / 100 = 10.0
- PBR = 1,000 / 500 = 2.0
- Forward PER = 1,000 / 120 = 8.33

### 例2: 株式分割が発生した場合

- 評価日: 2025-12-19
- 価格（adj_close）: 500円（分割後）
- EPS: 50円（分割後の基準で記録されている）
- BPS: 250円（分割後の基準で記録されている）
- 予想EPS: 60円（分割後の基準で記録されている）

計算結果:
- PER = 500 / 50 = 10.0
- PBR = 500 / 250 = 2.0
- Forward PER = 500 / 60 = 8.33

**重要**: `adj_close`を使用しているため、分割前の価格と分割後の価格は自動的に調整されています。EPS/BPS/予想EPSも分割後の基準で記録されているため、そのまま使用できます。

## 実装上の注意点

### 1. データの欠損値処理

- `price`、`eps`、`bvps`、`forecast_eps_fc`が欠損している場合、対応するPER/PBR/Forward PERは`NaN`になります。
- `profit <= 0`または`forecast_profit <= 0`の場合、PER/Forward PERは`NaN`になります（負のPERは意味がないため）。

### 2. SQLクエリの最適化

- `ROW_NUMBER() OVER (PARTITION BY code ORDER BY ...)`を使用して、銘柄ごとに最新のデータを取得します。
- これにより、`IN (...)`を使った場合のクロスジョイン問題を回避できます。

### 3. 予想データの取得ロジック

- FYを優先し、同じ開示日の場合FYを優先するため、`ORDER BY disclosed_date DESC, CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END`を使用します。

## まとめ

本ロジックは、以前の実装で精度が良かった部分を採用し、以下の特徴があります:

1. **`adj_close`（調整後終値）を使用**: 株式分割・併合を自動的に考慮
2. **EPS/BPS/予想EPSは調整しない**: 財務データに記録されている値をそのまま使用
3. **予想データはFYを優先**: 四半期データも含めて取得
4. **時価総額は参考用**: PER/PBR/Forward PERの計算には使用しない

このロジックにより、株式分割・併合が発生した場合でも、一貫したPER/PBR/Forward PERの計算が可能です。

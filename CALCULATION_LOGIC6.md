# PER、予想PER、PBRの計算ロジック（現在の実装）

## 概要

現在の実装では、J-Quants APIの`AdjustmentFactor`を使用して、全期間にわたって調整済みのPER、予想PER、PBRを計算しています。

## 使用するデータ

### 1. 価格データ（prices_dailyテーブル）

- **`close`（未調整終値）**: 評価日時点の実際の終値（分割・併合の調整なし）
  - 取得元: J-Quants API `/prices/daily_quotes` の `Close`
  - **用途: 時価総額の計算に使用**（バックテストでも安定した計算が可能）

- **`adj_close`（調整後終値）**: 株式分割・併合を考慮して調整された終値
  - 取得元: J-Quants API `/prices/daily_quotes` の `AdjustmentClose`
  - 用途: 参考/保持用（指標計算には使用しない）

- **`adjustment_factor`（調整係数）**: 株式分割・併合が発生した日の調整係数
  - 取得元: J-Quants API `/prices/daily_quotes` の `AdjustmentFactor`
  - 例: 1:2分割の場合、`adjustment_factor = 0.5`
  - 例: 1:3分割の場合、`adjustment_factor = 0.333333`
  - 用途: FY期末→評価日の分割倍率計算に使用（`_split_multiplier_between`関数）

### 2. 財務データ（fins_statementsテーブル）

- **`profit`（当期純利益）**: 最新のFY実績データから取得
  - 取得方法: `disclosed_date <= 評価日` の条件で、`current_period_end`が最新のFYレコードから取得
  - 定義: 親会社株主に帰属する当期純利益（連結ベース）
  - 用途: PERの計算に使用
  - 注意: `profit <= 0`の場合はPERをNULLとする（負のPERは意味がない）

- **`equity`（純資産）**: 最新のFY実績データから取得
  - 取得方法: `profit`と同じレコードから取得
  - 用途: PBRの計算に使用

- **`forecast_profit`（予想利益）**: 最新の予想データから取得
  - 取得方法: `disclosed_date <= 評価日` の条件で、最新の予想レコードから取得
  - 定義: 親会社株主に帰属する当期純利益の予想（連結ベース、`profit`と同じ定義）
  - 用途: Forward PERの計算に使用
  - 注意: `forecast_profit <= 0`の場合はForward PERをNULLとする（負のForward PERは意味がない）

- **`shares_outstanding`（期末発行済株式数）**: 最新のFY実績データから取得
  - 取得方法: `profit`と同じレコードから取得
  - 用途: 時価総額の計算に使用

- **`treasury_shares`（期末自己株式数）**: 最新のFY実績データから取得
  - 取得方法: `profit`と同じレコードから取得
  - 用途: 発行済み株式数の計算に使用（`shares_outstanding - treasury_shares`）

## 計算ロジック

**注意: 現実装ではCAF（累積調整係数）は使用していません**

現在の実装では、時価総額計算に未調整終値（`close`）を使用し、
株数はFY期末→評価日の分割倍率（`_split_multiplier_between`）で補正しているため、
CAF（評価日より後の累積積）は不要です。CAFを使用すると二重補正（株数も増やしたのに価格も調整）
が発生する可能性があります。

### ステップ1: 評価日時点の株数の計算（FY期末→評価日の分割・併合を考慮）

```python
def _split_multiplier_between(conn, code, start_date, end_date):
    """
    FY期末から評価日までの分割・併合による株数倍率を計算
    
    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。
    """
    # start_dateより後、end_date以下のAdjustmentFactorを取得
    # split_mult = ∏(1 / adjustment_factor)
    return split_mult

def _get_latest_basis_shares_for_price_date(row):
    """
    評価日時点の発行済み株式数を計算（FY期末→評価日の分割・併合を考慮）
    
    計算式:
    - shares_base: FY期末時点の発行済み株式数（財務データから取得）
    - split_mult: FY期末から評価日までの分割・併合による株数倍率
    - shares_at_price_date = shares_base * split_mult
    """
    shares_base = shares_outstanding - treasury_shares  # FY期末株数
    split_mult = _split_multiplier_between(conn, code, fy_end, price_date)
    shares_at_price_date = shares_base * split_mult
    return shares_at_price_date
```

**重要なポイント:**
- **修正の理由**: 従来の実装では「評価日より後」のCAFを計算していたが、FY期末より後、評価日より前に分割が発生した場合、財務データの`shares_outstanding`は「期末株数」のままなので、分割後の株数が反映されない
- `shares_base`はFY期末時点の発行済み株式数（`shares_outstanding - treasury_shares`）
- `split_mult`はFY期末から評価日までの分割・併合による株数倍率
  - 1:3分割（adjustment_factor = 0.333333）の場合、`split_mult = 1 / 0.333333 = 3.0`
- `shares_at_price_date = shares_base * split_mult`で、評価日時点の株数を計算

**実際の計算例（コード7419、評価日2025-12-19）:**
- 評価日: 2025-12-19
- 財務データの期末日: 2025-03-31（最新のFY実績データ）
- 2025-10-09に1:3分割が発生（adjustment_factor = 0.333333）
- `shares_base` = 31,928,266株（FY期末2025-03-31時点の株数）
- `split_mult` = 1 / 0.333333 = 3.0（2025-03-31から2025-12-19までの分割倍率）
- `shares_at_price_date` = 31,928,266 × 3.0 = 95,784,798株

### ステップ2: 時価総額の計算

```python
market_cap = close * shares_at_price_date
```

**重要なポイント:**
- **未調整終値（`close`）を使用**: バックテストでも安定した計算が可能
  - `adj_close`は「その日より後に起きた分割・併合」も織り込んだ価格になり得るため、評価日が過去だと時価総額が崩れる可能性がある
  - `close`は評価日時点の実際の終値なので、評価日より後の分割の影響を受けない
- `shares_at_price_date`は評価日時点の株数（FY期末株数 × FY期末→評価日の分割倍率）
- 時価総額 = 未調整終値 × 評価日時点の株数

**例:**
- `close` = 1,179円（未調整終値）
- `shares_at_price_date` = 95,784,798株（FY期末株数 × 分割倍率）
- `market_cap` = 1,179 × 95,784,798 = 112,930,276,842円

### ステップ3: PERの計算

```python
per = market_cap / profit if profit > 0 else np.nan
```

**重要なポイント:**
- `profit`は最新のFY実績データから取得（分割とは無関係）
- **`profit <= 0`の場合はNULL**: 負のPERは意味がないため
- PER = 時価総額 / 利益

**例:**
- `market_cap` = 112,930,276,842円
- `profit` = 32,292,000,000円
- `per` = 112,930,276,842 / 32,292,000,000 = 3.50

### ステップ4: PBRの計算

```python
pbr = market_cap / equity
```

**重要なポイント:**
- `equity`は最新のFY実績データから取得（分割とは無関係）
- PBR = 時価総額 / 純資産

**例:**
- `market_cap` = 112,930,276,842円
- `equity` = 208,307,000,000円
- `pbr` = 112,930,276,842 / 208,307,000,000 = 0.54

### ステップ5: Forward PERの計算

```python
forward_per = market_cap / forecast_profit if forecast_profit > 0 else np.nan
```

**重要なポイント:**
- `forecast_profit`は最新の予想データから取得（分割とは無関係）
- **`forecast_profit <= 0`の場合はNULL**: 負のForward PERは意味がないため
- **`forecast_profit`の定義**: `profit`と同じ定義（親会社株主に帰属する当期純利益、連結ベース）
- Forward PER = 時価総額 / 予想利益

**例:**
- `market_cap` = 112,930,276,842円
- `forecast_profit` = 40,000,000,000円
- `forward_per` = 112,930,276,842 / 40,000,000,000 = 2.82

## データの取得方法の詳細

### 財務データの取得（`_load_latest_fy`関数）

**Step 1: 銘柄ごとに最新のcurrent_period_endを選ぶ（SQL側で確定）**

```sql
WITH ranked AS (
  SELECT
    code, current_period_end,
    ROW_NUMBER() OVER (
      PARTITION BY code
      ORDER BY current_period_end DESC, disclosed_date DESC
    ) AS rn
  FROM fins_statements
  WHERE disclosed_date <= 評価日
    AND type_of_current_period = 'FY'
    AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
         OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
)
SELECT code, current_period_end
FROM ranked
WHERE rn = 1
```

**Step 2: 最新のcurrent_period_endに該当するレコードを全て取得（相互補完のため）**

```sql
SELECT disclosed_date, disclosed_time, code, type_of_current_period, current_period_end,
       operating_profit, profit, equity, eps, bvps,
       forecast_operating_profit, forecast_profit, forecast_eps,
       next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
       shares_outstanding, treasury_shares
FROM fins_statements
WHERE code IN (...)
  AND current_period_end IN (...)
  AND disclosed_date <= 評価日
  AND type_of_current_period = 'FY'
  AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
       OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
```

**重要なポイント:**
- **`ROW_NUMBER() OVER (PARTITION BY code ORDER BY current_period_end DESC, disclosed_date DESC)`**: 銘柄ごとに最新1件をSQLで確定
- `disclosed_date <= 評価日`の条件で、評価日以前に開示されたデータのみを使用
- `current_period_end DESC`で、最新の期末日を優先
- 同じ`current_period_end`の複数レコードがある場合、`disclosed_date DESC`で最新の開示日を優先
- その後、Python側で同じ`current_period_end`のデータを集約して相互補完を行う
- 最終的に銘柄ごとに最新1件を返す（別銘柄のFYが混ざることを防止）

### 予想データの取得（`_load_latest_forecast`関数）

```sql
WITH ranked AS (
  SELECT
    code, disclosed_date, type_of_current_period,
    forecast_operating_profit, forecast_profit, forecast_eps,
    next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
    ROW_NUMBER() OVER (
      PARTITION BY code
      ORDER BY disclosed_date DESC
    ) AS rn
  FROM fins_statements
  WHERE disclosed_date <= 評価日
    AND type_of_current_period = 'FY'
)
SELECT code, disclosed_date, type_of_current_period,
       forecast_operating_profit, forecast_profit, forecast_eps,
       next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
FROM ranked
WHERE rn = 1
```

**重要なポイント:**
- `disclosed_date <= 評価日`の条件で、評価日以前に開示されたデータのみを使用
- **`type_of_current_period = 'FY'`を明示**: forward_perを通期会社予想で統一するため
- **`ROW_NUMBER() OVER (PARTITION BY code ORDER BY disclosed_date DESC)`**: 銘柄ごとに最新1件をSQLで確定
- `disclosed_date DESC`で最新の開示日を優先
- 四半期予想が紛れ込むことを防止
- 別銘柄のFYが混ざることを防止

## 修正内容（2025年1月）

### 問題点1: FY期末→評価日の分割が反映されない

従来の実装では、CAFを「評価日より後」の累積積として計算していましたが、**FY期末より後、評価日より前に分割が発生した場合**に問題が発生していました。

**原因:**
- `shares_outstanding`と`treasury_shares`は「期末株数」なので、FY期末より後に分割が起きても期末株数は増えない
- 一方、価格は分割後（評価日時点の株価）になっている
- その結果、時価総額が分割倍率ぶん小さくなる（1:3分割なら約1/3）

**症状:**
- 期待値（Forward PER=8.95, PER=7.9, PBR=1.52）と計算値が大きく異なる
- 計算値（時価総額 = 112,930,275,663円）は、期待値の約1/3

### 修正内容1: FY期末→評価日の分割倍率を適用

**変更の肝:**
- CAFを「評価日より後」ではなく、「FY期末（current_period_end）→評価日（price_date）」の間に起きた分割・併合で株数を前進補正

**実装:**
1. `_split_multiplier_between`関数を新規作成
   - FY期末から評価日までの分割・併合による株数倍率を計算
   - `split_mult = ∏_{t ∈ (fy_end, price_date]} (1 / AdjustmentFactor(t))`
   - 注意: 丸めは行わない（端数が出る比率や制度変更・権利関係などで綺麗な逆整数にならないケースに対応）
2. `_get_latest_basis_shares_for_price_date`関数を修正
   - FY期末株数（`shares_base`）を取得
   - FY期末→評価日の分割倍率（`split_mult`）を計算
   - 評価日時点の株数 = `shares_base * split_mult`

### 問題点2: adj_closeを使うとバックテストでズレる

**原因:**
- `adj_close`は「その日より後に起きた分割・併合」も織り込んだ価格になり得る
- 評価日が過去だと、`adj_close`は将来の分割でさらに調整されるのに、`shares_at_price_date`は「FY期末→評価日」までしか補正していない
- その結果、バックテストで時価総額が崩れる

### 修正内容2: 未調整終値（close）を使用

**変更の肝:**
- 時価総額の計算に未調整終値（`close`）を使用
- `adj_close`ではなく`close`を使うことで、評価日より後の分割の影響を受けない

**実装:**
- `px_today`の取得で`adj_close`を`close`に変更
- 時価総額 = `close * shares_at_price_date`

**期待される効果:**
- FY期末より後、評価日より前に発生した分割・併合を正しく反映
- バックテストでも安定した計算が可能
- 時価総額が分割倍率ぶん小さくなる問題を解消
- PER、PBR、Forward PERが期待値に近づく

## 実装上の注意点

### 1. CAF（累積調整係数）は使用しない

**現実装ではCAFは使用していません（封印関数）**

現在の実装では、時価総額計算に未調整終値（`close`）を使用し、
株数はFY期末→評価日の分割倍率（`_split_multiplier_between`）で補正しているため、
CAF（評価日より後の累積積）は不要です。

`_calculate_cumulative_adjustment_factor`関数は古いロジックの残骸であり、
使用すると二重補正（株数も増やしたのに価格も調整）が発生する可能性があります。

### 2. 丸め誤差対策について

**丸めは行いません**

`_split_multiplier_between`関数では、1/af を整数に丸める処理は行いません。
理由：
- 端数が出る比率（例：1:1.1のようなものは通常ないが、制度変更・権利関係などで見かけの係数が綺麗な逆整数にならないケース）に対応
- 将来、J-Quants側が別種の調整を混ぜた場合に対応

### 3. 増資・自己株取得の限界

**期中の増資・自己株取得は反映されません**

今回のロジックは分割・併合には強いですが、`shares_outstanding` / `treasury_shares`を
「最新FYレコード」から持ってくるので、期中の増資・自己株取得があると
「評価日時点の株数」からズレます。

これはJ-Quantsの`fins_statements`を株数の真の日次系列として使えないことによる限界です。

**現実解:**
- 月次リバランス用途なら：許容しつつ「ズレうる」と注記（多くの実務ではここで十分）
- 精度を上げたいなら：増資・自己株は別ソース（TDnet/EDINET等）でイベント反映

### 4. 予想データの取得条件

**`type_of_current_period='FY'`を明示**

`_load_latest_forecast`関数では、`forward_per`を通期会社予想で統一するため、
`type_of_current_period='FY'`を明示しています。

これにより、四半期予想が紛れ込むことを防止します。

**SQLで銘柄ごとに最新1件を確定**

`_load_latest_forecast`関数では、`ROW_NUMBER() OVER (PARTITION BY code ORDER BY disclosed_date DESC)`を使用して、
SQL側で銘柄ごとに最新1件を確定しています。

これにより、別銘柄のFYが混ざることを防止し、merge時の重複を防ぎます。

### 5. shares_baseのNULL/異常値ガード

**treasury_sharesのNULL処理**

`_get_latest_basis_shares_for_price_date`関数では、以下のガードを実装しています：

- `treasury_shares`がNULLの場合は0扱い
- `treasury_shares`が負の値の場合は0扱い（異常値）
- `shares_base <= 0`の場合は`np.nan`を返す

これにより、実データでのNULL/異常値に対応します。

### 6. 日付型の統一

**文字列（YYYY-MM-DD形式）で統一**

`_split_multiplier_between`関数では、`fy_end`と`price_date`を文字列（YYYY-MM-DD形式）に統一しています。

- `fy_end`: datetime型から`strftime("%Y-%m-%d")`で文字列に変換
- `price_date`: `_snap_price_date`関数から文字列（YYYY-MM-DD形式）で取得

SQLでの日付比較が意図どおりに動作するよう、日付型を統一しています。

### 7. AdjustmentFactorの浮動小数誤差の警告

**異常値検出ログ**

`_split_multiplier_between`関数では、分割倍率が極端におかしい場合（`mult > 100`または`mult < 0.01`）に
警告ログを出力します。

これにより、異常データ混入に早く気づけます。

### 8. PER/Forward PERの分母（利益）の定義と負の値の処理

**利益の定義を統一**

- `profit`: 親会社株主に帰属する当期純利益（連結ベース）
- `forecast_profit`: 親会社株主に帰属する当期純利益の予想（連結ベース、`profit`と同じ定義）

**負のPER/Forward PERの処理**

- `profit <= 0`の場合はPERをNULLとする（負のPERは意味がない）
- `forecast_profit <= 0`の場合はForward PERをNULLとする（負のForward PERは意味がない）

月次スクリーニングでは「負のPERをどう扱うか」が結果に影響するため、明示的に処理しています。

### 9. _load_latest_fyのSQLで銘柄ごとに最新1件を確定

**ROW_NUMBER()を使用**

`_load_latest_fy`関数では、`ROW_NUMBER() OVER (PARTITION BY code ORDER BY current_period_end DESC, disclosed_date DESC)`を使用して、
SQL側で銘柄ごとに最新1件を確定しています。

これにより、別銘柄のFYが混ざることを防止し、merge時の重複を防ぎます。

**相互補完のロジックは維持**

SQL側で最新の`current_period_end`を選んだ後、Python側で同じ`current_period_end`のデータを集約して相互補完を行います。

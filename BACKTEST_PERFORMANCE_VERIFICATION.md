# バックテストパフォーマンス計算の検証資料

## 概要

この資料は、バックテストにおけるポートフォリオパフォーマンス計算ロジックの検証のために作成されました。実装ファイル: `src/omanta_3rd/backtest/performance.py`

**使用方法**: この資料をChatGPT ProなどのAIに渡して、計算ロジックの正確性を検証してもらってください。

**サンプルデータ抽出**: `extract_verification_samples.py` を実行すると、実際のデータベースから検証用のサンプルデータを抽出できます。

---

## 1. 計算フロー全体

```
1. ポートフォリオ取得（portfolio_monthlyテーブル）
   ↓
2. リバランス日の翌営業日を取得
   ↓
3. 各銘柄の購入価格取得（翌営業日の始値）
   ↓
4. 各銘柄の評価価格取得（評価日の終値）
   ↓
5. 分割倍率の計算（リバランス日以降の分割を考慮）
   ↓
6. 個別銘柄のリターン計算（分割調整済み）
   ↓
7. ポートフォリオ全体のリターン計算（weight加重平均）
   ↓
8. TOPIXリターン計算（比較用）
   ↓
9. 超過リターン計算（ポートフォリオ - TOPIX）
```

---

## 2. 詳細な計算ロジック

### 2.1 リバランス日の翌営業日の取得

**関数**: `_get_next_trading_day(conn, date: str)`

**ロジック**:
```sql
SELECT MIN(date) AS next_date
FROM prices_daily
WHERE date > ?
```

**目的**: リバランス日の直後の最初の営業日を取得。この日が実際の購入日となる。

**重要ポイント**:
- リバランス日当日ではなく、**翌営業日**を使用
- これは実際の取引を反映するため（当日中に注文を出しても翌日執行される想定）

---

### 2.2 購入価格の取得

**取得方法**: リバランス日の**翌営業日の始値（open）**

```sql
SELECT open
FROM prices_daily
WHERE code = ? AND date = ?  -- next_trading_day
```

**重要ポイント**:
- **始値（open）**を使用する理由: 実際の取引では、当日の始値で購入すると想定
- 終値ではなく始値を使用することで、より実践的なシミュレーション

---

### 2.3 評価価格の取得

**取得方法**: 評価日（as_of_date）の**終値（close）**

```sql
SELECT close
FROM prices_daily
WHERE code = ? AND date <= ?
ORDER BY date DESC
LIMIT 1
```

**重要ポイント**:
- **終値（close）**を使用: 評価時点での時価を表す
- `date <= ?`で、評価日が営業日でない場合でも、直近の営業日の価格を取得

---

### 2.4 分割倍率の計算

**関数**: `_split_multiplier_between(conn, code, start_date, end_date)`

**ロジック**:

1. 期間内の分割・併合を取得:
```sql
SELECT date, adjustment_factor
FROM prices_daily
WHERE code = ?
  AND date > ?  -- next_trading_day（購入日）
  AND date <= ?  -- as_of_date（評価日）
  AND adjustment_factor IS NOT NULL
  AND adjustment_factor != 1.0
ORDER BY date ASC
```

2. 株数倍率を計算:
```
split_multiplier = ∏(1 / adjustment_factor)
```

**具体例**:

**例1: 1:3分割の場合**
- adjustment_factor = 0.333333
- split_multiplier = 1 / 0.333333 = 3.0
- 意味: 1株が3株になるため、株数は3倍になる

**例2: 複数回の分割**
- 2022-06-01: 1:2分割（adjustment_factor = 0.5）→ 倍率 = 2.0
- 2023-06-01: 1:3分割（adjustment_factor = 0.333333）→ 倍率 = 3.0
- 合計倍率 = 2.0 × 3.0 = 6.0

**重要ポイント**:
- `date > start_date`: 購入日**以降**の分割のみを考慮（購入日の分割は購入価格に既に反映されている想定）
- `date <= end_date`: 評価日**以前**の分割を考慮

---

### 2.5 個別銘柄のリターン計算

**計算式**:

```python
adjusted_current_price = current_price * split_multiplier
return_pct = (adjusted_current_price - rebalance_price) / rebalance_price * 100.0
```

**具体例**:

**ケース1: 分割なし**
- 購入価格（rebalance_price）: 1,000円（翌営業日の始値）
- 評価価格（current_price）: 1,200円（評価日の終値）
- split_multiplier: 1.0
- adjusted_current_price: 1,200 × 1.0 = 1,200円
- return_pct: (1,200 - 1,000) / 1,000 × 100 = 20.0%

**ケース2: 1:3分割が発生**
- 購入価格: 1,000円
- 評価価格: 400円（分割後なので1/3になっている）
- split_multiplier: 3.0
- adjusted_current_price: 400 × 3.0 = 1,200円（分割前の価格に戻す）
- return_pct: (1,200 - 1,000) / 1,000 × 100 = 20.0%

**重要ポイント**:
- **価格調整方式**を使用: 評価価格を分割前の基準に戻して計算
- これにより、分割が発生しても正しいリターンが計算できる
- 注意: 実際の保有銘柄では**株数調整方式**を使用することもあるが、バックテストでは価格調整方式を使用

---

### 2.6 ポートフォリオ全体のリターン計算

**計算式**:

```python
weighted_return = weight * return_pct  # 各銘柄
total_return = weighted_return.sum()  # ポートフォリオ全体
```

**具体例**:

| 銘柄 | weight | return_pct | weighted_return |
|------|--------|------------|-----------------|
| A    | 0.05   | 10.0%      | 0.5%            |
| B    | 0.10   | 20.0%      | 2.0%            |
| C    | 0.15   | -5.0%      | -0.75%          |
| ...  | ...    | ...        | ...             |
| **合計** | **1.00** | - | **15.25%** |

**重要ポイント**:
- **weight加重平均**を使用
- weightはポートフォリオ内での配分比率（合計=1.0）
- 単純平均ではなく、投資額に応じた加重平均

---

### 2.7 TOPIXリターンの計算

**購入日**: リバランス日の翌営業日の**始値（open）**
**売却日**: 評価日の**終値（close）**

```python
topix_buy_price = _get_topix_price(conn, next_trading_day, use_open=True)
topix_sell_price = _get_topix_price(conn, as_of_date, use_open=False)
topix_return_pct = (topix_sell_price - topix_buy_price) / topix_buy_price * 100.0
```

**重要ポイント**:
- 個別株と同じタイミングを使用（翌営業日始値で購入、評価日終値で評価）
- これにより、公平な比較が可能

---

### 2.8 超過リターンの計算

```python
excess_return_pct = total_return_pct - topix_return_pct
```

**意味**: ポートフォリオがTOPIXをどれだけ上回ったか（または下回ったか）

---

## 3. データベーススキーマ

### 3.1 backtest_performance テーブル

| カラム名 | 型 | 説明 |
|---------|-----|------|
| rebalance_date | TEXT | リバランス日（YYYY-MM-DD） |
| as_of_date | TEXT | 評価日（YYYY-MM-DD） |
| total_return_pct | REAL | ポートフォリオ全体の総リターン（%） |
| num_stocks | INTEGER | 銘柄数 |
| num_stocks_with_price | INTEGER | 価格データがある銘柄数 |
| avg_return_pct | REAL | 平均リターン（%） |
| min_return_pct | REAL | 最小リターン（%） |
| max_return_pct | REAL | 最大リターン（%） |
| topix_return_pct | REAL | TOPIXリターン（%） |
| excess_return_pct | REAL | 超過リターン（%）= total_return_pct - topix_return_pct |
| created_at | TEXT | 作成日時 |

### 3.2 backtest_stock_performance テーブル

| カラム名 | 型 | 説明 |
|---------|-----|------|
| rebalance_date | TEXT | リバランス日 |
| as_of_date | TEXT | 評価日 |
| code | TEXT | 銘柄コード |
| weight | REAL | ポートフォリオ内の重み |
| rebalance_price | REAL | 購入価格（翌営業日の始値） |
| current_price | REAL | 評価価格（評価日の終値） |
| split_multiplier | REAL | 分割倍率 |
| adjusted_current_price | REAL | 調整済み評価価格（current_price × split_multiplier） |
| return_pct | REAL | リターン（%） |
| investment_amount | REAL | 投資金額（比較用の仮想金額） |
| topix_return_pct | REAL | TOPIXリターン（%） |
| excess_return_pct | REAL | 超過リターン（%） |

---

## 4. 検証すべきポイント

### 4.1 基本的な計算の正確性

1. **購入価格**: リバランス日の翌営業日の始値が正しく取得されているか
2. **評価価格**: 評価日の終値（または直近営業日の終値）が正しく取得されているか
3. **リターン計算**: `(adjusted_current_price - rebalance_price) / rebalance_price * 100`が正しいか

### 4.2 分割処理の正確性

1. **分割倍率の計算**: `∏(1 / adjustment_factor)`が正しいか
2. **期間の範囲**: 購入日**以降**、評価日**以前**の分割のみを考慮しているか
3. **調整後の価格**: `current_price × split_multiplier`が正しく計算されているか

**検証方法**:
- 分割が発生した銘柄について、手計算で確認
- 分割前の価格に戻した値が正しいか確認

### 4.3 ポートフォリオ全体の計算

1. **weight加重平均**: `total_return = Σ(weight × return_pct)`が正しいか
2. **weightの合計**: ポートフォリオ内のweightの合計が1.0に近いか（丸め誤差を考慮）

### 4.4 TOPIX比較の正確性

1. **購入タイミング**: 個別株と同じく翌営業日始値を使用しているか
2. **評価タイミング**: 個別株と同じく評価日終値を使用しているか
3. **超過リターン**: `excess_return = portfolio_return - topix_return`が正しいか

### 4.5 エッジケース

1. **価格データがない銘柄**: 正しく処理されているか（NaNやNone）
2. **評価日が営業日でない場合**: 直近営業日の価格を取得しているか
3. **分割が複数回発生**: すべての分割が正しく反映されているか
4. **購入価格がない銘柄**: 翌営業日の始値が存在しない場合の処理

---

## 5. 検証用のサンプルクエリ

### 5.1 特定のポートフォリオの詳細を確認

```sql
-- ポートフォリオ全体のパフォーマンス
SELECT 
    rebalance_date,
    as_of_date,
    total_return_pct,
    topix_return_pct,
    excess_return_pct,
    num_stocks,
    avg_return_pct
FROM backtest_performance
WHERE rebalance_date = '2022-01-31'
ORDER BY as_of_date;
```

### 5.2 銘柄別の詳細を確認

```sql
-- 銘柄別のパフォーマンス（分割が発生した銘柄を確認）
SELECT 
    code,
    weight,
    rebalance_price,
    current_price,
    split_multiplier,
    adjusted_current_price,
    return_pct,
    topix_return_pct,
    excess_return_pct
FROM backtest_stock_performance
WHERE rebalance_date = '2022-01-31'
  AND as_of_date = '2025-12-26'
ORDER BY return_pct DESC;
```

### 5.3 分割が発生した銘柄を確認

```sql
-- 分割が発生した銘柄（split_multiplier != 1.0）
SELECT 
    code,
    rebalance_price,
    current_price,
    split_multiplier,
    adjusted_current_price,
    return_pct
FROM backtest_stock_performance
WHERE rebalance_date = '2022-01-31'
  AND as_of_date = '2025-12-26'
  AND split_multiplier != 1.0
ORDER BY split_multiplier DESC;
```

### 5.4 weightの合計を確認

```sql
-- ポートフォリオ内のweightの合計（1.0に近いはず）
SELECT 
    rebalance_date,
    as_of_date,
    SUM(weight) as total_weight,
    COUNT(*) as num_stocks
FROM backtest_stock_performance
WHERE rebalance_date = '2022-01-31'
  AND as_of_date = '2025-12-26'
GROUP BY rebalance_date, as_of_date;
```

---

## 6. 手動検証の手順

### 6.1 個別銘柄の検証

1. **データ取得**: 特定の銘柄について以下を取得
   - rebalance_date
   - next_trading_day（翌営業日）
   - 購入価格（next_trading_dayの始値）
   - as_of_date
   - 評価価格（as_of_dateの終値）
   - 分割履歴（next_trading_day以降、as_of_date以前）

2. **分割倍率の計算**: 手動で計算
   ```
   split_multiplier = ∏(1 / adjustment_factor)
   ```

3. **調整後の価格**: 手動で計算
   ```
   adjusted_current_price = current_price × split_multiplier
   ```

4. **リターン**: 手動で計算
   ```
   return_pct = (adjusted_current_price - rebalance_price) / rebalance_price × 100
   ```

5. **比較**: 計算結果とデータベースの値を比較

### 6.2 ポートフォリオ全体の検証

1. **各銘柄のweighted_return**: 手動で計算
   ```
   weighted_return[i] = weight[i] × return_pct[i]
   ```

2. **total_return**: 手動で計算
   ```
   total_return = Σ(weighted_return[i])
   ```

3. **比較**: 計算結果とデータベースの値を比較

---

## 7. 潜在的な問題点と注意事項

### 7.1 分割処理について

**現在の実装**: 価格調整方式（評価価格を分割前の基準に戻す）

**代替手法**: 株数調整方式（購入価格を分割後の基準に調整）

**どちらが正しいか**: 
- バックテストでは**価格調整方式**が一般的
- ただし、実際の保有銘柄では**株数調整方式**を使用することが多い

**現在の実装が適切か**: 検証が必要

### 7.2 購入価格のタイミング

**現在の実装**: 翌営業日の始値

**代替手法**: 
- リバランス日当日の終値
- 翌営業日の終値

**現在の実装が適切か**: 
- 実際の取引では、リバランス日の終値で注文を出し、翌営業日の始値で執行されることが多い
- したがって、現在の実装（翌営業日始値）は合理的

### 7.3 TOPIX比較のタイミング

**現在の実装**: 
- 購入: 翌営業日始値
- 評価: 評価日終値

**個別株と同じタイミングを使用**: 公平な比較のため適切

---

## 8. 検証チェックリスト

- [ ] 購入価格が翌営業日の始値であることを確認
- [ ] 評価価格が評価日の終値（または直近営業日の終値）であることを確認
- [ ] 分割倍率が正しく計算されているか確認（手動計算と比較）
- [ ] 調整後の価格が正しく計算されているか確認
- [ ] 個別銘柄のリターンが正しく計算されているか確認
- [ ] ポートフォリオ全体のリターンがweight加重平均であることを確認
- [ ] weightの合計が1.0に近いことを確認
- [ ] TOPIXリターンが正しく計算されているか確認
- [ ] 超過リターンが正しく計算されているか確認
- [ ] エッジケース（価格データなし、分割複数回など）が正しく処理されているか確認

---

## 9. 参考資料

- 実装ファイル: `src/omanta_3rd/backtest/performance.py`
- データベーススキーマ: `sql/schema.sql` (backtest_performance, backtest_stock_performance)
- ポートフォリオテーブル: `portfolio_monthly`

---

## 10. 質問事項（ChatGPT Proへの質問例）

1. **分割処理の妥当性**: 現在の価格調整方式（評価価格を分割前の基準に戻す）は正しいか？株数調整方式と比較してどちらが適切か？

2. **購入価格のタイミング**: リバランス日の翌営業日の始値を使用することは適切か？実際の取引を反映しているか？

3. **計算式の正確性**: 以下の計算式は正しいか？
   ```
   adjusted_current_price = current_price × split_multiplier
   return_pct = (adjusted_current_price - rebalance_price) / rebalance_price × 100
   ```

4. **ポートフォリオ全体の計算**: weight加重平均による計算は正しいか？単純平均との違いは何か？

5. **TOPIX比較の妥当性**: 個別株と同じタイミング（翌営業日始値で購入、評価日終値で評価）を使用することは適切か？

6. **エッジケースの処理**: 価格データがない銘柄、評価日が営業日でない場合の処理は適切か？


# バックテストパフォーマンス計算の改善内容

## 修正日: 2025-12-28

## 修正内容

### 1. 評価日が非営業日のときのズレ問題を修正

**問題点**:
- 評価日が非営業日の場合、現在価格は直近営業日の価格を取得できるが、分割倍率の計算は評価日（非営業日）までで計算される
- もし休場日にもcorporate action行が立つ実装だと、価格と分割の基準日がズレる可能性がある

**修正内容**:
- 現在価格取得時に`date`も取得し、実際に評価に使った価格の日付（`effective_asof_date`）を保持
- 分割倍率計算時に`effective_asof_date`を使用することで、価格と分割の基準日を必ず一致させる

**変更箇所**:
```python
# 修正前
SELECT close FROM prices_daily WHERE code = ? AND date <= ? ORDER BY date DESC LIMIT 1
split_mult = _split_multiplier_between(conn, code, next_trading_day, as_of_date)

# 修正後
SELECT date, close FROM prices_daily WHERE code = ? AND date <= ? ORDER BY date DESC LIMIT 1
effective_asof_date = str(price_row["date"].iloc[0])  # 実際に評価に使った価格の日付
split_mult = _split_multiplier_between(conn, code, next_trading_day, effective_asof_date)
```

---

### 2. ポートフォリオ全体のリターン計算での欠損値処理を改善

**問題点**:
- `return_pct`がNaNの場合、`weighted_return`もNaNになり、`sum()`でNaNがスキップされる
- これにより、欠損銘柄のweight部分が暗黙に無視される
- 全銘柄NaNでも`sum()`が0.0を返し得る（pandasの挙動）ので、最悪「データがないのに0%」になる

**修正内容**:
- `sum(min_count=1)`を使用: 全部NaNならNaNを維持
- 有効銘柄のweight合計（coverage）を計算
- 欠損値の扱い方針を明示（方針C: 品質管理）
  - `weight_coverage`（有効weight割合）を結果に含める
  - 呼び出し側で品質を判断できるようにする

**変更箇所**:
```python
# 修正前
portfolio["weighted_return"] = portfolio["weight"] * portfolio["return_pct"]
total_return = portfolio["weighted_return"].sum()

# 修正後
portfolio["weighted_return"] = portfolio["weight"] * portfolio["return_pct"]

# 有効銘柄（return_pctがNaNでない）のweight合計を計算（coverage）
valid_mask = portfolio["return_pct"].notna()
valid_weight_sum = portfolio.loc[valid_mask, "weight"].sum()
total_weight = portfolio["weight"].sum()
coverage = valid_weight_sum / total_weight if total_weight > 0 else 0.0

# sum(min_count=1)を使用: 全部NaNならNaNを維持
total_return = portfolio["weighted_return"].sum(min_count=1)
```

**追加された結果フィールド**:
- `num_stocks_with_return`: 有効なリターンがある銘柄数
- `weight_coverage`: 有効weight割合（品質指標、0.0-1.0）

---

## データベースマイグレーション

新しいカラムを追加するマイグレーションスクリプト:
- `sql/migration_add_backtest_coverage.sql`

**実行方法**:
```sql
-- バックテストパフォーマンステーブルに品質指標カラムを追加
ALTER TABLE backtest_performance 
ADD COLUMN num_stocks_with_return INTEGER;

ALTER TABLE backtest_performance 
ADD COLUMN weight_coverage REAL;
```

---

## 検証方法

### 1. 評価日が非営業日のケース

```python
# 評価日を非営業日（例: 2025-12-28が日曜日）に設定
perf = calculate_portfolio_performance("2022-01-31", "2025-12-28")

# 各銘柄について、effective_asof_dateが実際の価格データの日付と一致しているか確認
# split_multiplierがeffective_asof_dateまでで計算されているか確認
```

### 2. 欠損値があるケース

```python
# 一部の銘柄で価格データがない場合
perf = calculate_portfolio_performance("2022-01-31", "2025-12-26")

# weight_coverageを確認
print(f"weight_coverage: {perf['weight_coverage']}")  # 0.98以上が理想

# num_stocks_with_returnを確認
print(f"有効銘柄数: {perf['num_stocks_with_return']}/{perf['num_stocks']}")

# total_return_pctがNaNでないか確認（全部NaNの場合はNaNになる）
print(f"total_return_pct: {perf['total_return_pct']}")
```

---

## 注意事項

1. **既存のデータ**: 既存の`backtest_performance`テーブルには`num_stocks_with_return`と`weight_coverage`がNULLになります
2. **マイグレーション**: 新しいカラムを追加する前に、既存データのバックアップを推奨
3. **後方互換性**: 既存のコードは引き続き動作しますが、新しいフィールドを活用することで品質管理が向上します

---

## 改善効果

1. **正確性の向上**: 評価日が非営業日でも、価格と分割の基準日が必ず一致する
2. **品質管理の向上**: `weight_coverage`により、欠損値の影響を可視化できる
3. **エラー検出の向上**: 全部NaNの場合はNaNを返すことで、誤った結果を防ぐ
4. **データ品質の可視化**: 不正なadjustment_factorや欠損価格を警告として出力

---

## 追加改善（2025-12-28）

### 3. 分割倍率の不正値検出と警告

**問題点**:
- `adjustment_factor`が0や負の値の場合、静かに無視されてバグが埋め込まれる可能性がある

**修正内容**:
- 不正値（NULL、0、負の値）を検出し、警告を出力
- 不正値は無視して計算を続行（既存の挙動を維持）

**変更箇所**:
```python
# 不正値の検出と警告
if adj_factor <= 0:
    invalid_factors.append((split_date, f"invalid_value={adj_factor}"))
    print(f"警告: 銘柄{code}の分割データに不正値があります。日付={split_date}, adjustment_factor={adj_factor}")
    continue
```

### 4. 欠損価格の警告出力

**修正内容**:
- 購入価格が取得できない銘柄を検出し、警告を出力
- 評価価格が取得できない銘柄を検出し、警告を出力

**変更箇所**:
```python
if missing_buy_prices:
    print(f"警告: {len(missing_buy_prices)}銘柄で購入価格が取得できませんでした。")

if missing_sell_prices:
    print(f"警告: {len(missing_sell_prices)}銘柄で評価価格が取得できませんでした。")
```

### 5. 欠損値の扱い方針の明文化

**修正内容**:
- コメントで欠損値の扱い方針を明示
- 方針C（品質管理）を採用: coverageを返し、呼び出し側で判断
- 警告メッセージを詳細化（欠損銘柄数、欠損weight、coverageを表示）

**変更箇所**:
```python
# 欠損値の警告（品質管理）
if coverage < MIN_COVERAGE:
    print(
        f"警告: ポートフォリオの品質が低い可能性があります。"
        f"欠損銘柄数={missing_count}/{num_total}, "
        f"欠損weight={missing_weight:.4f}/{total_weight:.4f}, "
        f"coverage={coverage:.4f}"
    )
```


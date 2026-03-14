# 最高益フラグのデータリーク修正

## 発見された問題

### 1. `check_record_high()`関数のデータリーク

**問題点：**
- `check_record_high()`関数で、リバランス日以前に開示されたデータのみを参照する条件（`disclosed_date <= as_of_date`）が欠けていました
- これにより、リバランス日時点でまだ開示されていない未来のデータも参照する可能性がありました

**修正前：**
```python
# 最新の実績利益を取得
sql = """
    SELECT profit
    FROM fins_statements
    WHERE code = ? AND type_of_current_period = 'FY'
    ORDER BY current_period_end DESC
    LIMIT 1
"""
# ❌ disclosed_date <= as_of_date の条件がない
```

**修正後：**
```python
# 最新の実績利益を取得（リバランス日以前に開示されたデータのみ）
sql = """
    SELECT profit
    FROM fins_statements
    WHERE code = ? 
      AND type_of_current_period = 'FY'
      AND disclosed_date <= ?
      AND current_period_end <= ?
    ORDER BY current_period_end DESC, disclosed_date DESC
    LIMIT 1
"""
params=(code, as_of_date, as_of_date)
# ✅ disclosed_date <= as_of_date と current_period_end <= as_of_date の両方の条件を追加
```

### 2. `scoring.py`の`calculate_entry_score()`関数のデータリーク

**問題点：**
- `current_period_end`を取得する際に`disclosed_date <= as_of_date`の条件がない
- PER/PBRを計算する際にも`disclosed_date <= as_of_date`の条件がない

**修正内容：**
- `check_record_high()`の呼び出しに`as_of_date`パラメータを追加
- `current_period_end`取得時に`disclosed_date <= as_of_date`と`current_period_end <= as_of_date`の条件を追加
- PER/PBR計算時に`disclosed_date <= as_of_date`と`current_period_end <= as_of_date`の条件を追加

## 修正内容の詳細

### 1. `src/omanta_3rd/features/fundamentals.py`の`check_record_high()`

**変更点：**
- `rebalance_date`パラメータを追加（必須、リバランス日（ポートフォリオ作成日）を指定）
- すべてのSQLクエリに`disclosed_date <= rebalance_date`と`current_period_end <= rebalance_date`の条件を追加
- データリークを防ぐため、リバランス日以前に開示されたデータのみを参照

### 2. `src/omanta_3rd/strategy/scoring.py`の`calculate_entry_score()`

**変更点：**
- `current_period_end`取得時に`disclosed_date <= as_of_date`と`current_period_end <= as_of_date`の条件を追加（`as_of_date`はリバランス日）
- `check_record_high()`の呼び出しに`rebalance_date`パラメータ（`as_of_date`を渡す）を追加
- PER/PBR計算時に`disclosed_date <= as_of_date`と`current_period_end <= as_of_date`の条件を追加（`as_of_date`はリバランス日）

### 3. `src/omanta_3rd/jobs/longterm_run.py`の`build_features()`

**確認結果：**
- ✅ 既に正しく実装されています
- `op_max_df`取得時に`disclosed_date <= price_date`と`current_period_end <= price_date`の条件があります
- `forecast_operating_profit`は`fy_latest`または`fc_latest`から取得され、これらは`disclosed_date <= price_date`でフィルタリングされています

## データリークの有無

### 修正前

**❌ データリークあり：**
- `check_record_high()`で`disclosed_date <= as_of_date`の条件がない
- `scoring.py`で`disclosed_date <= as_of_date`の条件がない
- リバランス日時点でまだ開示されていない未来のデータも参照する可能性がある

### 修正後

**✅ データリークなし：**
- すべてのSQLクエリに`disclosed_date <= rebalance_date`（リバランス日）と`current_period_end <= rebalance_date`の条件を追加
- リバランス日（ポートフォリオ作成日）以前に開示されたデータのみを参照
- ポートフォリオ作成時に、それ以前に公表された全ての利益情報を利用して最高益を判定する形になっています

## 確認チェックリスト

- [x] `check_record_high()`に`rebalance_date`パラメータを追加（リバランス日（ポートフォリオ作成日）を指定）
- [x] すべてのSQLクエリに`disclosed_date <= rebalance_date`の条件を追加
- [x] すべてのSQLクエリに`current_period_end <= rebalance_date`の条件を追加
- [x] `scoring.py`の`calculate_entry_score()`を修正
- [x] `longterm_run.py`の`build_features()`は既に正しく実装されていることを確認


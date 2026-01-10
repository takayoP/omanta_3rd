# ChatGPTのアドバイスに対する対応

## 確認結果と修正方針

### ✅ 修正済みの点

1. **`as_of_date`未指定でDBのMAX(date)を使わない**
   - `optimize_longterm_main()`側で`as_of_date=None`のとき`end_date`を使用
   - `calculate_longterm_performance()`は`None`を許さない（エラー）

2. **24Mの`rebalance_end_date_24m`と`as_of_date`を分離**
   - 「リバランス日を列挙する終端」と「評価で見てよい最終日」を分離
   - 24Mで`rebalance_end_date_24m = end_date - 24ヶ月`、`as_of_date = end_date`を明示

### ⚠️ 修正が必要な点

#### 1. DB MAX(date) fallbackの完全除去

**問題点：**
- `calculate_portfolio_performance()`で`as_of_date=None`の場合、DB MAX(date)を使用
- `compare_regime_switching.py`でも同様の問題

**対応方針：**
- 最適化系の呼び出しでは必ず`as_of_date`を指定
- `calculate_portfolio_performance()`は他の呼び出し元もあるため、警告を出しつつ、最適化系では必ず指定することをドキュメントに明記

#### 2. 価格データの物理的な切り取り（未実装）

**問題点：**
- `calculate_portfolio_performance()`内で価格データを取得する際に`WHERE date <= as_of_date`を強制していない

**対応方針：**
- すべての価格データ取得SQLクエリに`WHERE date <= as_of_date`を追加

#### 3. 非営業日の丸め規約（未実装）

**問題点：**
- `eval_end_date`が非営業日の場合の処理が未定義

**対応方針：**
- `eval_end_date`を営業日にスナップする規約を固定（前営業日または翌営業日）

## 修正箇所の詳細

### 1. `calculate_portfolio_performance()`の修正

**現在の問題：**
```python
if as_of_date is None:
    latest_date_df = pd.read_sql_query(
        "SELECT MAX(date) as max_date FROM prices_daily",
        conn
    )
    as_of_date = str(latest_date_df["max_date"].iloc[0])
```

**修正方針：**
- 最適化系では`as_of_date`を必須にする
- 他の呼び出し元への影響を考慮し、警告を出す

### 2. 価格データの物理的な切り取り

**修正箇所：**
- `calculate_portfolio_performance()`内のすべての価格データ取得SQLクエリに`WHERE date <= as_of_date`を追加

### 3. `compare_regime_switching.py`の修正

**現在の問題：**
```python
if as_of_date is None:
    latest_date_df = pd.read_sql_query(
        "SELECT MAX(date) as max_date FROM prices_daily",
        conn
    )
    as_of_date = str(latest_date_df["max_date"].iloc[0])
```

**修正方針：**
- `as_of_date`がNoneの場合は`end_date`を使用（DB MAX(date)は使わない）

### 4. ファンダ窓変更（5年→3年）の扱い

**推奨：**
- 再テストはまず「日付系修正だけ」で1回回す
- 次に、ファンダ窓変更も入れて2回目を回す
- こうすると原因が切り分けできる

## 確認チェックリスト

### 修正前の確認

- [ ] `calculate_longterm_performance()`で`as_of_date`がNoneの場合にエラーになることを確認
- [ ] 24Mで`rebalance_end_date_24m`と`as_of_date`が分離されていることを確認
- [ ] `optimize_longterm_main()`で`as_of_date=None`のとき`end_date`を使用することを確認

### 修正後の確認

- [ ] `calculate_portfolio_performance()`の価格データ取得に`WHERE date <= as_of_date`を追加
- [ ] `compare_regime_switching.py`でDB MAX(date)を使わないように修正
- [ ] `eval_end_date`が非営業日の場合の処理を固定（営業日にスナップ）
- [ ] ドキュメントの更新（`calculate_longterm_performance()`のドキュメント）

## 再テストの推奨手順

1. **1回目: 日付系修正だけ**
   - ファンダ窓変更（5年→3年）は行わない
   - 日付系修正（`as_of_date`分離、DB MAX(date)除去、価格データの物理的切り取り）のみを適用
   - 結果を記録

2. **2回目: ファンダ窓変更も適用**
   - 日付系修正 + ファンダ窓変更（5年→3年）を適用
   - 結果を記録
   - 1回目と比較して、ファンダ窓変更の影響を切り分け


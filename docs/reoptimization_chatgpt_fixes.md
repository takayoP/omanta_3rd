# ChatGPTの指摘に対する修正内容

## 修正した問題点

### 1. as_of_dateのデフォルト挙動の修正

**問題：**
- `as_of_date`が未指定の場合、DBの`MAX(date)`を使用していた
- これにより、`--as-of-date`を付け忘れた瞬間に未来参照リークに戻る

**修正：**
- `as_of_date`が未指定の場合、`end_date`（CLIの`--end`）を使用
- DBの`MAX(date)`は使用しない（エラーで止める）

**修正箇所：**
- `src/omanta_3rd/jobs/optimize_longterm.py`:
  - `calculate_longterm_performance()`: `as_of_date`がNoneの場合はエラー
  - `optimize_longterm_main()`: `as_of_date`がNoneの場合は`end_date`を使用

### 2. 24Mのrebalance_end_date_24mとas_of_dateの分離

**問題：**
- 24M最適化で`end_date_24m`と`as_of_date`が混同される可能性
- `end_date_24m`を`as_of_date`として渡すと、24M評価が短くなる

**修正：**
- 変数名を`rebalance_end_date_24m`に変更（混同防止）
- `rebalance_end_date_24m`（リバランス日の取得範囲）と`as_of_date`（評価の打ち切り日）を分離
- 24M最適化時：
  - `rebalance_end_date_24m = end_date - 24ヶ月`
  - `as_of_date = end_date`（元のend_dateを使用）

**修正箇所：**
- `src/omanta_3rd/jobs/reoptimize_all_candidates.py`:
  - `end_date_24m` → `rebalance_end_date_24m`に変更
  - 24M最適化時に`rebalance_end_date_24m`と`as_of_date`を分離して渡す

### 3. 営業利益トレンドと最高益フラグを5年→3年に変更

**問題：**
- サンプル数が少なくなってしまうため、過去5年のデータを使っていた

**修正：**
- `calculate_roe_trend()`のデフォルト`periods=4` → `periods=3`（3期=3年）
- `check_record_high()`に過去3年の制限を追加
- `longterm_run.py`の`_load_fy_history()`呼び出しで`years=10` → `years=3`
- 営業利益トレンドの計算で`tail(5)` → `tail(3)`

**修正箇所：**
- `src/omanta_3rd/features/fundamentals.py`:
  - `calculate_roe_trend()`: `periods=3`に変更
  - `check_record_high()`: 過去3年の制限を追加
- `src/omanta_3rd/jobs/longterm_run.py`:
  - `_load_fy_history()`: `years=3`に変更
  - 営業利益トレンド: `tail(3)`に変更

## 未実装の改善点（今後の検討事項）

### 1. 価格データの物理的な切り取り

**推奨：**
- `calculate_longterm_performance()`冒頭で`prices_daily = prices_daily[date <= as_of_date]`を入れる
- またはSQL取得段階で`WHERE date <= as_of_date`を強制

**現状：**
- `calculate_portfolio_performance()`は既に`as_of_date`パラメータを持っており、内部で実装されている可能性
- 確認が必要

### 2. eval_end_dateが非営業日のときの日付合わせ規約

**推奨：**
- `rebalance_date`は当日（営業日）確定
- `eval_end_date`は翌営業日（on or after）に丸める、または前営業日に丸める
- どちらでも良いが、一貫して固定する

**現状：**
- `calculate_portfolio_performance()`は既に`as_of_date`パラメータを持っており、内部で営業日にスナップしている可能性
- 確認が必要

### 3. purge/embargo split（重なり排除）

**推奨：**
- testの開始日`rb_test_start`に対して、trainに入れる`rb`は`rb <= rb_test_start - horizon_months`に制限
- またはサンプルの時刻を`eval_end_date`と見なして、`eval_end_date`で時系列分割する

**現状：**
- 時系列分割は実装済み
- purge/embargo splitは未実装（今後の検討事項）

## 確認チェックリスト

### 未来参照リークの確認

- [x] `as_of_date`が`end_date`（CLIの`--end`）になっているか（DB MAX(date)ではない）
- [x] `eval_end_date`が常に`rebalance_date + horizon_months`になっているか
- [x] `eval_end_date <= as_of_date`を満たしているか
- [x] 24M最適化で`rebalance_end_date_24m`と`as_of_date`が分離されているか

### 時系列分割の確認

- [x] trainの最後の日付 < testの最初の日付 になっているか
- [x] 時系列順に分割されているか

### 評価窓の確認

- [x] 24M最適化で`rebalance_end_date_24m = end_date - 24ヶ月`になっているか
- [x] 24M最適化で`as_of_date = end_date`（元のend_date）になっているか
- [x] すべてのリバランス日が24Mホライズン完走可能か

### 営業利益トレンドと最高益フラグの確認

- [x] `calculate_roe_trend()`のデフォルト`periods=3`になっているか
- [x] `check_record_high()`に過去3年の制限が追加されているか
- [x] `_load_fy_history()`で`years=3`になっているか
- [x] 営業利益トレンドの計算で`tail(3)`になっているか


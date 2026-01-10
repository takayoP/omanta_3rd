# 再最適化の最終確認チェックリスト

## ChatGPTのアドバイスに基づく確認結果

### ✅ 修正済みの点

#### 1. `as_of_date`未指定でDBのMAX(date)を使わない
- ✅ `optimize_longterm_main()`側で`as_of_date=None`のとき`end_date`を使用
- ✅ `calculate_longterm_performance()`は`None`を許さない（エラー）
- ✅ `calculate_portfolio_performance()`も`as_of_date=None`の場合はエラー（DB MAX(date)は使わない）
- ✅ `compare_regime_switching.py`も`as_of_date=None`のとき`end_date`を使用（DB MAX(date)は使わない）

#### 2. 24Mの`rebalance_end_date_24m`と`as_of_date`を分離
- ✅ 「リバランス日を列挙する終端」と「評価で見てよい最終日」を分離
- ✅ 24Mで`rebalance_end_date_24m = end_date - 24ヶ月`、`as_of_date = end_date`を明示
- ✅ 変数名を`rebalance_end_date_24m`に変更（混同防止）

#### 3. 価格データの物理的な切り取り（部分実装）
- ✅ `calculate_portfolio_performance()`内の価格データ取得SQLに`WHERE date <= as_of_date`を追加
- ✅ `_get_next_trading_day()`に`max_date`パラメータを追加（オプショナル、後方互換性を保持）
- ✅ `_get_next_trading_day()`呼び出し時に`max_date=as_of_date`を指定

#### 4. 非営業日の丸め規約（実装済み）
- ✅ `eval_end_date`を営業日にスナップする処理を追加（`_snap_price_date()`を使用）
- ✅ 規約: `eval_end_date`が非営業日の場合は、その日以前の最新の営業日を使用

#### 5. 最高益フラグのデータリーク修正
- ✅ `check_record_high()`に`rebalance_date`パラメータを追加（リバランス日以前に開示されたデータのみを参照）
- ✅ すべてのSQLクエリに`disclosed_date <= rebalance_date`と`current_period_end <= rebalance_date`の条件を追加
- ✅ `longterm_run.py`の`build_features()`では、全期間のデータを直接取得（`fy_hist`の制限を回避）

### ⚠️ 確認が必要な点

#### 1. DB MAX(date) fallbackの完全除去

**確認方法：**
```bash
grep -r "SELECT MAX(date).*FROM prices_daily" src/omanta_3rd/jobs/optimize*.py
grep -r "SELECT MAX(date).*FROM prices_daily" src/omanta_3rd/backtest/performance.py
```

**確認結果：**
- ✅ `optimize_longterm.py`: DB MAX(date)を使用していない
- ✅ `calculate_longterm_performance()`: `as_of_date`がNoneの場合はエラー
- ✅ `calculate_portfolio_performance()`: `as_of_date`がNoneの場合はエラー
- ✅ `compare_regime_switching.py`: DB MAX(date)は使わない（`end_date`を使用）

**注意：**
- 他のファイル（`longterm_run.py`の`_snap_price_date()`など）で`SELECT MAX(date) FROM prices_daily WHERE date <= ?`を使っているが、これは「指定日以前の最新日」を取得するためのもので、データリークではない

#### 2. 24M呼び出し部分の確認

**`reoptimize_all_candidates.py`の24M呼び出し部分：**
```python
results["operational_24M"] = optimize_and_save(
    params_id="operational_24M",
    horizon_months=24,
    study_type="C",
    start_date=start_date,
    end_date=rebalance_end_date_24m,  # 24M用のリバランス日取得範囲
    n_trials=n_trials,
    n_jobs=n_jobs,
    bt_workers=bt_workers,
    version=version,
    as_of_date=as_of_date,  # 評価の打ち切り日（元のend_dateを使用）
)
```

**確認ポイント：**
- ✅ `end_date=rebalance_end_date_24m`（リバランス日取得範囲）
- ✅ `as_of_date=as_of_date`（評価の打ち切り日、元の`end_date`）
- ✅ これらが分離されている

**`calculate_longterm_performance()`の冒頭部分：**
```python
# 評価の打ち切り日を決定（必須）
if as_of_date is None:
    raise ValueError(
        "as_of_dateは必須です。未来参照リークを防ぐため、"
        "必ず明示的に指定してください（例: end_dateを渡す）。"
    )
print(f"      [calculate_longterm_performance] 評価の打ち切り日: {as_of_date}")
```

**確認ポイント：**
- ✅ `as_of_date`がNoneの場合はエラー
- ✅ DB MAX(date)は使用しない

### ファンダ窓変更（5年→3年）の扱い

**推奨：**
再テストは2段階で実施することを推奨：

1. **1回目: 日付系修正だけ**
   - ファンダ窓変更（5年→3年）は行わない
   - 日付系修正（`as_of_date`分離、DB MAX(date)除去、価格データの物理的切り取り、非営業日の丸め規約）のみを適用
   - 結果を記録

2. **2回目: ファンダ窓変更も適用**
   - 日付系修正 + ファンダ窓変更（5年→3年）を適用
   - 結果を記録
   - 1回目と比較して、ファンダ窓変更の影響を切り分け

**実装上の注意：**
- 現在、ファンダ窓変更（5年→3年）は既に適用されている
- 1回目を実行するには、ファンダ窓変更を一時的に戻す必要がある
- または、ファンダ窓変更の影響を認識した上で、2回目のみを実行する

### 未実装の改善点（オプション）

#### 1. 価格データの物理的な切り取り（完全実装）

**現状：**
- `calculate_portfolio_performance()`内の価格データ取得SQLに`WHERE date <= as_of_date`を追加済み
- ただし、`calculate_longterm_performance()`内で価格データを取得する際にも同様の処理が必要

**推奨：**
- すべての価格データ取得SQLに`WHERE date <= as_of_date`を追加
- または、価格データ取得関数に`as_of_date`パラメータを追加

#### 2. purge/embargo split（重なり排除）

**現状：**
- 時系列分割は実装済み
- ただし、train/test間で評価期間が重なる可能性がある

**推奨（今後の検討事項）：**
- testの開始日`rb_test_start`に対して、trainに入れる`rb`は`rb <= rb_test_start - horizon_months`に制限
- または、サンプルの時刻を`eval_end_date`と見なして、`eval_end_date`で時系列分割

## 再テスト開始OKの最終チェックリスト

### 必須確認項目

- [x] 24Mで`rebalance_end_date_24m`と`as_of_date`が別引数として渡っている（ログで確認可能）
- [x] 評価系でDB MAX(date)を参照するコードが残っていない（`optimize_longterm.py`、`calculate_longterm_performance()`、`calculate_portfolio_performance()`）
- [x] `compare_regime_switching.py`でDB MAX(date)を使わない（`end_date`を使用）
- [x] `calculate_longterm_performance()`で`as_of_date`がNoneの場合はエラー
- [x] `eval_end_date`を営業日にスナップする処理を追加
- [x] `_get_next_trading_day()`で`max_date`を考慮
- [x] `calculate_portfolio_performance()`内の価格データ取得に`WHERE date <= as_of_date`を追加
- [x] 最高益フラグの計算でリバランス日以前に開示されたデータのみを参照

### 推奨確認項目

- [ ] ファンダ窓変更（5年→3年）を一時的に戻して、日付系修正だけの1回目を実行（原因切り分けのため）
- [ ] または、ファンダ窓変更の影響を認識した上で、2回目のみを実行

### 実行時のログ確認ポイント

以下をログで確認してください：

1. **24M最適化時：**
   ```
   24M最適化用のrebalance_end_dateを調整: 2025-12-31 → 2023-12-31
   24Mのas_of_date（評価の打ち切り日）: 2025-12-31 (元のend_dateを使用)
   ```
   - ✅ `rebalance_end_date_24m`と`as_of_date`が分離されている

2. **`calculate_longterm_performance()`実行時：**
   ```
   [calculate_longterm_performance] 評価の打ち切り日: 2025-12-31
   [calculate_longterm_performance] 2020-01-31 → eval_end=2022-01-31 (holding=2.00年, horizon=24M)
   ```
   - ✅ `eval_end_date`が`rebalance_date + horizon_months`になっている
   - ✅ DBの最新日（2026-01-08など）が使われていない
   - ✅ `eval_date`が営業日にスナップされている

3. **価格データ取得時：**
   - ✅ すべてのSQLクエリで`WHERE date <= as_of_date`が使われている

## コード確認用の抜粋

### `reoptimize_all_candidates.py`の24M呼び出し部分

```python
# 1. operational_24Mを最適化
if not skip_24m:
    results["operational_24M"] = optimize_and_save(
        params_id="operational_24M",
        horizon_months=24,
        study_type="C",  # 広範囲探索
        start_date=start_date,
        end_date=rebalance_end_date_24m,  # 24M用のリバランス日取得範囲
        n_trials=n_trials,
        n_jobs=n_jobs,
        bt_workers=bt_workers,
        version=version,
        as_of_date=as_of_date,  # 評価の打ち切り日（元のend_dateを使用）
    )
```

**確認ポイント：**
- `end_date=rebalance_end_date_24m`（リバランス日取得範囲）
- `as_of_date=as_of_date`（評価の打ち切り日、元の`end_date`）
- ✅ これらが分離されている

### `calculate_longterm_performance()`の冒頭部分

```python
performances = []
with connect_db() as conn:
    # 評価の打ち切り日を決定（必須）
    if as_of_date is None:
        raise ValueError(
            "as_of_dateは必須です。未来参照リークを防ぐため、"
            "必ず明示的に指定してください（例: end_dateを渡す）。"
        )
    print(f"      [calculate_longterm_performance] 評価の打ち切り日: {as_of_date}")
    
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    
    # horizon_monthsは必須
    if horizon_months is None:
        raise ValueError("horizon_monthsは必須です。未来参照リークを防ぐため、明示的に指定してください。")
    
    # 評価日を決定（固定ホライズン評価）
    for rebalance_date in sorted(portfolios.keys()):
        # ...
        # 評価終了日を計算（固定ホライズン）
        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
        eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
        eval_end_date = eval_end_dt.strftime("%Y-%m-%d")
        
        # require_full_horizonがTrueの場合、eval_end_dateがas_of_dateより後の場合は除外
        if require_full_horizon:
            if eval_end_dt > as_of_dt:
                print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}はホライズン未達（{horizon_months}M、eval_end={eval_end_date} > as_of={as_of_date}）のため除外")
                continue
        
        # eval_end_dateとas_of_dateのうち、早い方を使用（安全のため）
        eval_date = min(eval_end_date, as_of_date)
        
        # eval_dateを営業日にスナップ（非営業日の場合は前営業日を使用）
        try:
            eval_date_snapped = _snap_price_date(conn, eval_date)
            if eval_date_snapped != eval_date:
                print(f"      [calculate_longterm_performance] eval_dateを営業日にスナップ: {eval_date} → {eval_date_snapped}")
            eval_date = eval_date_snapped
        except RuntimeError as e:
            print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}のeval_date({eval_date})以前に営業日が見つかりません: {e}")
            continue
```

**確認ポイント：**
- ✅ `as_of_date`がNoneの場合はエラー
- ✅ DB MAX(date)は使用しない
- ✅ `eval_end_date = rebalance_date + horizon_months`で計算
- ✅ `eval_date`を営業日にスナップ

### `calculate_portfolio_performance()`の修正部分

```python
# 評価日を決定（必須）
# 重要: データリークを防ぐため、as_of_dateは必須とする
#       DB MAX(date)は使用しない（未来参照リーク防止）
if as_of_date is None:
    return {
        "rebalance_date": rebalance_date,
        "as_of_date": None,
        "error": "as_of_dateは必須です。データリークを防ぐため、リバランス日以前の日付を明示的に指定してください。",
    }

# リバランス日の翌営業日を取得
# 重要: as_of_date以前のデータのみを参照（データリーク防止）
next_trading_day = _get_next_trading_day(conn, rebalance_date, max_date=as_of_date)

# 価格データ取得（as_of_date以前のデータのみ）
price_row = pd.read_sql_query(
    """
    SELECT date, close
    FROM prices_daily
    WHERE code = ? AND date <= ?
    ORDER BY date DESC
    LIMIT 1
    """,
    conn,
    params=(code, as_of_date),  # ✅ WHERE date <= as_of_date
)
```

**確認ポイント：**
- ✅ `as_of_date`がNoneの場合はエラー（DB MAX(date)は使わない）
- ✅ `_get_next_trading_day()`で`max_date=as_of_date`を指定
- ✅ 価格データ取得SQLに`WHERE date <= as_of_date`を追加

## 結論

### 修正完了 ✅

ChatGPTのアドバイスに基づいて、以下の修正を完了しました：

1. ✅ DB MAX(date) fallbackの完全除去
2. ✅ 24Mの`rebalance_end_date_24m`と`as_of_date`の分離
3. ✅ 価格データの物理的な切り取り（部分的に実装）
4. ✅ 非営業日の丸め規約の固定
5. ✅ 最高益フラグのデータリーク修正

### 推奨される再テスト手順

1. **ファンダ窓変更の影響を認識した上で、再最適化を実行**
2. **実行ログで上記の確認ポイントをチェック**
3. **結果を分析し、必要に応じて追加の修正を行う**

### 実行コマンド

```bash
python -m omanta_3rd.jobs.reoptimize_all_candidates \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --n-trials 200
```

実行時に、上記のログ確認ポイントをチェックしてください。


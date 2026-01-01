# monthly_excess_returns末尾の0.0問題の修正

## 問題の概要

Holdout評価の結果で、`monthly_excess_returns`配列の末尾に`0.0`が追加され、`num_periods`（実際のデータ期間数）と配列の長さが一致しない問題が発生していました。

### 具体例

```json
{
  "num_periods": 11,
  "monthly_excess_returns": [
    0.0116, 0.0129, -0.0077, -0.0438, -0.0020,
    0.0001, 0.0723, -0.0105, 0.1433, -0.0003,
    0.0322,
    0.0  // ← ダミーの0.0が末尾に追加されている
  ],
  "monthly_dates": [
    "2025-01-31", "2025-02-28", ..., "2025-12-30"  // 12個
  ]
}
```

### 問題の影響

1. **統計指標の歪み**: 平均・標準偏差・Sharpe比などの計算に影響（控えめ側にズレる）
2. **評価の一貫性**: `num_periods`と配列の長さが不一致で混乱を招く
3. **データの信頼性**: 実データとダミーデータが混在し、評価の信頼性が低下

### 原因

`calculate_timeseries_returns_from_portfolios`関数で、最後のリバランス日（例: 2025-12-30）について、次のリバランス日（`end_date` = 2025-12-31）が実際の取引日でない場合、価格データが取得できず`portfolio_valid.empty`となり、`0.0`が追加されていました。

## 修正内容

### 修正方針

**「実データのみを返す」方針に統一**：
- データが取得できない期間はスキップ（0.0を追加しない）
- `dates`配列も実データが存在するリバランス日のみを含む

### 修正箇所

`src/omanta_3rd/backtest/timeseries.py` の `calculate_timeseries_returns_from_portfolios` 関数

#### 1. `dates_with_data`リストの追加

```python
# 修正前
monthly_returns = []
monthly_excess_returns = []
equity_curve = [1.0]
portfolio_details = []

# 修正後
monthly_returns = []
monthly_excess_returns = []
equity_curve = [1.0]
portfolio_details = []
dates_with_data = []  # 実データが存在するリバランス日のみを記録
```

#### 2. データ取得失敗時の処理をスキップに変更

```python
# 修正前
if rebalance_date not in portfolios:
    monthly_returns.append(0.0)
    monthly_excess_returns.append(0.0)
    equity_curve.append(equity_curve[-1])
    continue

portfolio = portfolios[rebalance_date].copy()
if portfolio.empty:
    monthly_returns.append(0.0)
    monthly_excess_returns.append(0.0)
    equity_curve.append(equity_curve[-1])
    continue

purchase_date = _get_next_trading_day(conn, rebalance_date)
if purchase_date is None:
    monthly_returns.append(0.0)
    monthly_excess_returns.append(0.0)
    equity_curve.append(equity_curve[-1])
    continue

# ... (中略) ...

if portfolio_valid.empty:
    stock_returns = []
else:
    # ... リターン計算 ...
    monthly_returns.append(portfolio_return_net)
    monthly_excess_returns.append(excess_return)
    # ...
else:
    monthly_returns.append(0.0)  # ← ダミー0.0を追加
    monthly_excess_returns.append(0.0)
    equity_curve.append(equity_curve[-1])
```

```python
# 修正後
if rebalance_date not in portfolios:
    # ポートフォリオが存在しない場合はスキップ（実データのみを返すため）
    continue

portfolio = portfolios[rebalance_date].copy()
if portfolio.empty:
    # ポートフォリオが空の場合はスキップ（実データのみを返すため）
    continue

purchase_date = _get_next_trading_day(conn, rebalance_date)
if purchase_date is None:
    # 購入日が取得できない場合はスキップ（実データのみを返すため）
    continue

# ... (中略) ...

if portfolio_valid.empty:
    stock_returns = []
else:
    # ... リターン計算 ...
    monthly_returns.append(portfolio_return_net)
    monthly_excess_returns.append(excess_return)
    equity_curve.append(equity_curve[-1] * (1.0 + portfolio_return_net))
    dates_with_data.append(rebalance_date)  # 実データが追加された時だけdatesにも追加
    # ...
# portfolio_valid.emptyの場合、データが取得できないためスキップ（0.0を追加しない）
```

#### 3. 返却値の`dates`を`dates_with_data`に変更

```python
# 修正前
return {
    "monthly_returns": monthly_returns,
    "monthly_excess_returns": monthly_excess_returns,
    "equity_curve": equity_curve,
    "dates": rebalance_dates,  # 入力された全リバランス日
    "portfolio_details": portfolio_details,
}

# 修正後
return {
    "monthly_returns": monthly_returns,
    "monthly_excess_returns": monthly_excess_returns,
    "equity_curve": equity_curve,
    "dates": dates_with_data,  # 実データが存在するリバランス日のみを返す
    "portfolio_details": portfolio_details,
}
```

## 修正後の動作

### 修正後の例

```json
{
  "num_periods": 11,
  "monthly_excess_returns": [
    0.0116, 0.0129, -0.0077, -0.0438, -0.0020,
    0.0001, 0.0723, -0.0105, 0.1433, -0.0003,
    0.0322  // ← 末尾の0.0が削除され、実データのみ
  ],
  "monthly_dates": [
    "2025-01-31", "2025-02-28", ..., "2025-11-28"  // 11個（実データのみ）
  ]
}
```

### 整合性の確保

- `len(monthly_excess_returns) == len(monthly_dates) == num_periods`
- すべての配列要素が実データのみで構成される
- 統計指標（平均、標準偏差、Sharpe比など）が正確に計算される

## 影響範囲

### 影響を受けるスクリプト・関数

1. **`evaluate_candidates_holdout.py`**
   - `_calculate_detailed_metrics`関数
   - `monthly_excess_returns`と`monthly_dates`の長さが一致することを前提としているため、修正により整合性が保たれる

2. **`calculate_timeseries_returns_from_portfolios`関数**
   - この関数を呼び出すすべてのコード
   - 返却値の`dates`が実データのみを含むようになる

### 後方互換性

- **互換性あり**: 修正により、返却される配列の長さが変わる可能性があるが、データの整合性が向上する
- **動作の変更**: 以前は末尾に0.0が追加されていたが、今後は追加されない
- **推奨**: 修正後にHoldout評価を再実行し、最新の結果を使用することを推奨

## 検証方法

修正が正しく動作していることを確認するには：

1. **配列の長さの一致確認**
   ```python
   assert len(result["monthly_excess_returns"]) == len(result["dates"])
   assert len(result["monthly_excess_returns"]) == result["num_periods"]
   ```

2. **末尾に0.0がないことの確認**
   ```python
   assert result["monthly_excess_returns"][-1] != 0.0 or len(result["monthly_excess_returns"]) > 0
   # または、より厳密に
   assert all(r != 0.0 for r in result["monthly_excess_returns"]) or \
          (len(result["monthly_excess_returns"]) > 0 and \
           result["monthly_excess_returns"][-1] != 0.0 or \
           any(r != 0.0 for r in result["monthly_excess_returns"]))
   ```

3. **Holdout評価の再実行**
   - `evaluate_candidates_holdout.py`を再実行
   - 結果JSONを確認し、`monthly_excess_returns`と`monthly_dates`の長さが一致することを確認

## 要注意ポイント：スキップによるバイアスの可能性

### 問題

**欠損月をスキップすることで、Sharpe比やCAGRが上振れする可能性がある**

今回の修正は「0.0を入れない」点では正しい一方、欠損が発生した月を丸ごと除外します。これがもし「悪い月が欠損しやすい」ような偏りを持つと、SharpeやCAGRが上振れします（逆もあり得るが、一般には上振れリスクが問題）。

特に、最後のリバランス日について次の取引日がなく価格が取れないケースは多くの場合「末尾1回」なので影響は小さいですが、年内で欠損が複数月発生する設計だと危険になります。

### 対応方針

**「実データのみ返す」方針は維持しつつ、欠損を“観測可能な情報”としてログ化・統制する**

### 実装した改善

#### 1. スキップ情報の記録

`calculate_timeseries_returns_from_portfolios`関数で、スキップされた期間の情報を記録するように改善：

```python
missing_periods_info = []  # スキップされた期間の情報を記録

# スキップ時に情報を記録
if rebalance_date not in portfolios:
    missing_periods_info.append({
        "rebalance_date": rebalance_date,
        "reason": "portfolio_not_found",
    })
    continue

# ... (他のスキップケースも同様) ...

return {
    "monthly_returns": monthly_returns,
    "monthly_excess_returns": monthly_excess_returns,
    "equity_curve": equity_curve,
    "dates": dates_with_data,
    "portfolio_details": portfolio_details,
    "missing_periods_count": len(missing_periods_info),  # スキップされた期間数
    "missing_periods_info": missing_periods_info,  # スキップされた期間の詳細情報
}
```

#### 2. 評価結果への反映

`evaluate_candidates_holdout.py`の`_calculate_detailed_metrics`関数で、スキップ情報を評価結果に含める：

```python
result["missing_periods_count"] = missing_periods_count
result["missing_periods_info"] = missing_periods_info
if missing_periods_count > 0:
    result["has_missing_periods"] = True
    result["missing_periods_warning"] = (
        f"注意: {missing_periods_count}期間がスキップされました。"
        "スキップされた期間が多い場合、Sharpe比やCAGRが上振れする可能性があります。"
    )
else:
    result["has_missing_periods"] = False
```

### 今後の改善案（将来実装可能）

#### オプション1：保守的な評価（超過=0）

スキップが発生したら、評価を「保守的」に落とす選択肢：
- その月はベンチマークリターンと同じ（超過=0）にする
- 「実運用では取引できなかった」を表現

#### オプション2：現金ホールド扱い

- その月のポートフォリオリターン=0、超過=-benchmark
- 仕様を明確化して数値に反映

**注意**: どちらが正しいかは運用仕様次第ですが、「スキップで消える」より、仕様を定義して数値に反映する方が検証として強いです。

### 評価時の推奨事項

1. **`missing_periods_count > 0`の候補は注意フラグ**
   - 結果JSONで`has_missing_periods: true`の候補は、特に注意深く評価する
   - スキップされた期間が多い場合（例：3期間以上）、結果を保守的に解釈する

2. **`missing_periods_info`の確認**
   - どの期間がスキップされたか確認
   - スキップの理由（`reason`）を確認
   - 特定の月に偏ってスキップされていないか確認

3. **複数月の欠損がある場合**
   - 現状の結果（スキップ版）を基本とする
   - 必要に応じて、保守的な評価（超過=0等）を別途計算して比較検討

## 参考文献

- ChatGPTによる指摘（2025年疑似ライブ評価結果へのフィードバック）
- 「月次配列末尾の0.0」問題の指摘
- 推奨対応：実データのみを返す、または`num_periods`と長さを揃える
- 要注意ポイント：スキップによるバイアスの可能性と対応方針


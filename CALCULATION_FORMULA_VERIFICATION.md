# Holdout検証における計算式の検証資料

この資料は、Holdout検証で使用している計算式をChatGPTに検証してもらうためのものです。
各計算式の数学的な定義、実装コード、検証すべきポイントを記載しています。

---

## 1. Sharpe Ratio（超過リターンの年率化Sharpe比率）

### 数学的定義

**Sharpe_excess（超過リターンのSharpe比率）:**

```
Sharpe_excess = (mean(r_excess) - r_f / 12) / std(r_excess) * √12
```

ここで:
- `r_excess`: 月次超過リターン（小数、0.01 = 1%）
- `mean(r_excess)`: 月次超過リターンの平均
- `std(r_excess)`: 月次超過リターンの標準偏差（不偏標準偏差、ddof=1）
- `r_f`: リスクフリーレート（年率、小数、本実装では0.0）
- `√12`: 年率化係数

**注意点:**
- 月次リターンから年率化する際は、標準偏差に√12を掛ける（分散ではなく標準偏差）
- **重要**: `monthly_excess_returns`が指定された場合（ベンチマーク超過リターン）、RFは引かない
  - これはTOPIX超過Sharpe（情報比率IR相当）を計算するため
  - RFを引くと「無リスク超過Sharpe」になるが、TOPIX超過とは異なる
  - 通常リターン（`monthly_returns`のみ）の場合のみRFを引く

### 実装コード

```python
# src/omanta_3rd/backtest/metrics.py:37-76
def calculate_sharpe_ratio(
    monthly_returns: List[float],
    monthly_excess_returns: Optional[List[float]] = None,
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> Optional[float]:
    if monthly_excess_returns is not None:
        returns_array = np.array(monthly_excess_returns)
    else:
        returns_array = np.array(monthly_returns)
    
    if len(returns_array) < 2:
        return None
    
    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array, ddof=1)  # 不偏標準偏差
    
    if std_return == 0:
        return None
    
    # 月次リターンから計算
    if monthly_excess_returns is not None:
        # ベンチマーク超過リターンの場合、RFは引かない（TOPIX超過Sharpe = IR相当）
        sharpe = mean_return / std_return
    else:
        # 通常リターンの場合はRFを引く
        sharpe = (mean_return - risk_free_rate / 12.0) / std_return
    
    # 年率化
    if annualize:
        sharpe *= np.sqrt(12.0)
    
    return float(sharpe)
```

### 検証ポイント

1. **年率化の方法**: 標準偏差に√12を掛けるのは正しいか？ ✅ 正しい
2. **リスクフリーレートの扱い**: 
   - `monthly_excess_returns`使用時（ベンチマーク超過）: RFは引かない ✅ 修正済み
   - `monthly_returns`のみ使用時: 年率を月次に換算（÷12）して差し引く ✅ 正しい
3. **不偏標準偏差**: `ddof=1`を使用しているのは適切か？ ✅ 正しい
4. **超過リターンの使用**: `monthly_excess_returns`が指定された場合は、それを使用するのは正しいか？ ✅ 正しい

### ChatGPT検証結果

✅ **定義と実装は整合しています**
✅ **年率化（√12）は標準的です**
⚠️ **改善済み**: ベンチマーク超過リターン使用時はRFを引かないように修正

---

## 2. CAGR（年率複利成長率）

### 数学的定義

**CAGR（超過リターンの年率複利成長率）:**

```
CAGR_excess = ((1 + Total_Return) ^ (12 / N) - 1) * 100
```

ここで:
- `Total_Return = ∏(1 + r_excess_i) - 1`: 全期間の複利累積超過リターン
- `r_excess_i`: 各月の超過リターン（小数）
- `N`: 月数
- `12 / N`: 年率換算の指数

**年別CAGR_excessの場合:**

```
CAGR_excess_year = ((1 + Cumulative_Return_year) ^ (12 / N_year) - 1) * 100
```

### 実装コード

**全体期間のCAGR:**

```python
# src/omanta_3rd/backtest/metrics.py:263-280
def calculate_cagr(equity_curve: List[float], num_months: int) -> Optional[float]:
    if not equity_curve or num_months == 0:
        return None
    
    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    cagr = (1.0 + total_return) ** (12.0 / num_months) - 1.0
    
    return float(cagr)
```

**年別CAGR_excess（Holdout検証での実装）:**

```python
# evaluate_candidates_holdout.py:356-364
if len(year_excess) > 0:
    # 複利で累積リターンを計算
    cumulative_return = np.prod([1.0 + r for r in year_excess]) - 1.0
    periods = len(year_excess)
    # 年率換算（月次データから年率に変換）
    cagr_excess = ((1.0 + cumulative_return) ** (12.0 / periods) - 1.0) * 100.0 if periods > 0 else None
```

### 検証ポイント

1. **複利計算**: `np.prod([1.0 + r for r in year_excess])`で複利累積を計算するのは正しいか？
2. **年率換算**: 指数が`12.0 / periods`（月数）で正しいか？
3. **エクイティカーブからの計算**: 全体期間のCAGRは`equity_curve[-1] / equity_curve[0] - 1.0`から計算するのは正しいか？

---

## 3. 平均超過リターンとボラティリティ（年率換算）

### 数学的定義

**月次平均超過リターン:**

```
mean_excess_monthly = (1/N) * Σ r_excess_i
```

**年率平均超過リターン:**

```
mean_excess_annual = mean_excess_monthly * 12 * 100
```

**月次標準偏差（不偏）:**

```
vol_excess_monthly = sqrt((1/(N-1)) * Σ (r_excess_i - mean_excess_monthly)^2)
```

**年率標準偏差:**

```
vol_excess_annual = vol_excess_monthly * √12 * 100
```

### 実装コード

```python
# evaluate_candidates_holdout.py:373-384
mean_excess_monthly = np.mean(monthly_excess_returns) if monthly_excess_returns else 0.0
vol_excess_monthly = np.std(monthly_excess_returns, ddof=1) if len(monthly_excess_returns) > 1 else 0.0

# 年率換算
mean_excess_annual = mean_excess_monthly * 12.0 * 100.0  # %換算
vol_excess_annual = vol_excess_monthly * np.sqrt(12.0) * 100.0  # %換算
```

### 検証ポイント

1. **平均の年率換算**: 月次平均に12を掛けるのは正しいか？
2. **標準偏差の年率換算**: 月次標準偏差に√12を掛けるのは正しいか？（分散ではなく標準偏差）
3. **不偏標準偏差**: `ddof=1`を使用しているのは適切か？

---

## 4. MaxDD（最大ドローダウン）

### 数学的定義

**MaxDD（最大ドローダウン）:**

```
peak_t = max(equity_0, equity_1, ..., equity_t)  # 累積最大値
drawdown_t = (equity_t - peak_t) / peak_t
MaxDD = min(drawdown_t)  # 最小値（最も負の値）
```

### 実装コード

```python
# src/omanta_3rd/backtest/metrics.py:11-34
def calculate_max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    # エクイティカーブをnumpy配列に変換
    values = np.array(equity_curve)
    
    # ピークを計算（累積最大値）
    peak = np.maximum.accumulate(values)
    
    # ドローダウンを計算（ピークからの下落率）
    drawdown = (values - peak) / peak
    
    max_dd = np.min(drawdown)
    return float(max_dd)
```

### 検証ポイント

1. **累積最大値**: `np.maximum.accumulate(values)`でピークを計算するのは正しいか？
2. **ドローダウンの計算**: `(values - peak) / peak`の式は正しいか？
3. **TOPIXのMaxDD**: TOPIXのエクイティカーブから同様に計算するのは正しいか？

---

## 5. ターンオーバー（売買回転率）

### 数学的定義

**実売買ベースのターンオーバー:**

```
executed_turnover = executed_sell_notional + executed_buy_notional
```

本実装では、毎回100%売却して100%購入するため:
- `executed_sell_notional = 1.0`（100%売却）
- `executed_buy_notional = 1.0`（100%購入）
- `executed_turnover = 2.0`（200%）

**年間ターンオーバー:**

```
turnover_annual = mean(executed_turnover_monthly) * 12
```

### 実装コード

```python
# src/omanta_3rd/backtest/timeseries.py:224-254
def _calculate_turnover(
    current_portfolio: pd.DataFrame,
    previous_portfolio: Optional[pd.DataFrame],
) -> Dict[str, float]:
    # 実売買ベースのターンオーバー（毎回100%売って100%買う）
    executed_sell_notional = 1.0
    executed_buy_notional = 1.0
    executed_turnover = executed_sell_notional + executed_buy_notional  # 2.0
    ...
```

**Holdout検証での使用:**

```python
# evaluate_candidates_holdout.py:408-423
turnovers = []
for detail in portfolio_details:
    if "executed_turnover" in detail:
        turnovers.append(detail["executed_turnover"])

avg_turnover_monthly = np.mean(turnovers) if turnovers else None
avg_turnover_annual = avg_turnover_monthly * 12.0 if avg_turnover_monthly is not None else None
```

### 検証ポイント

1. **実売買ベースの計算**: 毎回100%売却・100%購入の場合、ターンオーバーが2.0（200%）になるのは正しいか？
2. **年間換算**: 月次平均に12を掛けるのは正しいか？

---

## 6. コスト考慮後のSharpe Ratio

### 数学的定義

**年間コスト（bps）:**

```
annual_cost = turnover_annual * cost_bps / 10000
```

**コスト考慮後の月次平均超過リターン:**

```
mean_excess_after_cost = mean_excess_monthly - (annual_cost / 12)
```

**コスト考慮後のSharpe Ratio:**

```
sharpe_after_cost = (mean_excess_after_cost * 12) / (vol_excess_monthly * √12)
```

**注意**: この実装は簡易版で、ボラティリティは変更なしと仮定しています。

### 実装コード（改善版）

```python
# evaluate_candidates_holdout.py:425-460（改善後）
if cost_bps > 0:
    # 月次コストを計算（portfolio_detailsから取得）
    monthly_costs = []
    for detail in portfolio_details:
        if "cost_frac" in detail:
            # cost_fracは既に月次コスト（小数）として計算済み
            monthly_costs.append(detail["cost_frac"])
    
    if monthly_costs:
        # 月次超過リターンから月次コストを控除（推奨方法）
        monthly_excess_after_cost = [
            r - c for r, c in zip(monthly_excess_returns, monthly_costs)
        ]
        
        # コスト控除後の統計を再計算
        mean_excess_after_cost_monthly = np.mean(monthly_excess_after_cost)
        vol_excess_after_cost_monthly = np.std(monthly_excess_after_cost, ddof=1)
        
        # コスト控除後のSharpe Ratioを計算
        sharpe_after_cost = (
            (mean_excess_after_cost_monthly * 12.0) / (vol_excess_after_cost_monthly * np.sqrt(12.0))
            if vol_excess_after_cost_monthly > 0 else None
        )
```

### 検証ポイント

1. **コストの計算**: `turnover_annual * cost_bps / 10000`は正しいか？（bpsは1/10000） ✅ 正しい
2. **月次コストの計算**: `annual_cost / 12`で月次コストを計算するのは正しいか？ ✅ 正しい
3. **計算方法の改善**: 
   - ❌ **旧実装（簡易版）**: 平均からコストを引くだけ → ボラティリティが反映されない
   - ✅ **新実装（推奨）**: 月次系列からコストを控除して再計算 → ボラティリティも正しく反映 ✅ 改善済み

### ChatGPT検証結果

⚠️ **改善済み**: 簡易版（平均からコストを引く）から、月次系列から控除して再計算する方法に変更
- これにより、ボラティリティも正しく反映され、「コストがある月だけ下がる」効果も入る

---

## 7. 年別分解の計算

### 数学的定義

**年別Sharpe_excess:**

年ごとの月次リターンから、Sharpe Ratioを計算（上記1と同じ方法）

**年別CAGR_excess:**

年ごとの月次超過リターンから、複利累積リターンを計算し、年率換算（上記2と同じ方法）

### 実装コード

```python
# evaluate_candidates_holdout.py:339-367
for year in [2023, 2024]:
    year_df = df[df["year"] == year]
    if len(year_df) == 0:
        continue
    
    year_excess = year_df["excess_return"].tolist()
    year_returns = year_df["return"].tolist()
    
    # Sharpe_excess
    sharpe_excess = calculate_sharpe_ratio(
        year_returns,
        year_excess,
        risk_free_rate=0.0,
        annualize=True,
    )
    
    # CAGR_excess（複利計算）
    if len(year_excess) > 0:
        cumulative_return = np.prod([1.0 + r for r in year_excess]) - 1.0
        periods = len(year_excess)
        cagr_excess = ((1.0 + cumulative_return) ** (12.0 / periods) - 1.0) * 100.0 if periods > 0 else None
```

### 検証ポイント

1. **年別のフィルタリング**: 日付から年を抽出してフィルタリングするのは正しいか？
2. **年別Sharpe**: 年ごとの月次リターンから計算するのは正しいか？（年率化係数は同じ√12で良いか？）
3. **年別CAGR**: 年ごとの月次超過リターンから計算するのは正しいか？

---

## 8. 総合的な検証ポイント

### 単位の一貫性

- リターン: 小数（0.01 = 1%）で計算し、出力時に%換算（×100）する
- Sharpe Ratio: 無次元（年率化済み）
- CAGR: 小数で計算し、出力時に%換算（×100）する
- MaxDD: 小数で計算し、出力時に%換算（×100）する
- ボラティリティ: 小数で計算し、出力時に%換算（×100）する

### 年率化の一貫性

- **平均リターン**: 月次平均 × 12
- **標準偏差**: 月次標準偏差 × √12
- **Sharpe Ratio**: 月次Sharpe × √12

### 検証すべき全体的なポイント

1. **計算式の数学的正確性**: 各計算式が標準的な定義と一致しているか？
2. **年率化の方法**: 月次データから年率に換算する方法が正しいか？
3. **不偏標準偏差の使用**: `ddof=1`を使用するのは適切か？
4. **複利計算**: CAGRの計算で複利を正しく考慮しているか？
5. **単位変換**: 小数と%の変換が正しく行われているか？
6. **エッジケース**: データが少ない場合や、標準偏差が0の場合の処理は適切か？

---

## 参考: 実装ファイル

- `src/omanta_3rd/backtest/metrics.py`: 基本メトリクス計算
- `src/omanta_3rd/backtest/eval_common.py`: 時系列データからのメトリクス計算
- `src/omanta_3rd/backtest/timeseries.py`: 時系列リターン計算、ターンオーバー計算
- `evaluate_candidates_holdout.py`: Holdout検証での詳細メトリクス計算

---

**検証依頼**: 上記の計算式が数学的に正しいか、標準的な定義と一致しているか、実装に誤りがないかを確認してください。


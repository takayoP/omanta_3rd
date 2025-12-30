# パフォーマンス計算方法の比較

このドキュメントでは、2つの異なるパフォーマンス計算方法について説明します。

---

## 1. 既存版（累積リターン計算）

### ファイル
- `calculate_performance_metrics.py`
- `src/omanta_3rd/backtest/performance.py` の `calculate_portfolio_performance()`

### 計算方法
各リバランス日 `ti` から**最終評価日（as_of_date）**までの累積リターンを計算します。

```
リバランス日 ti → 最終評価日（例: 2025-12-26）
```

### 特徴
- **用途**: 特定時点でのポートフォリオの累積パフォーマンスを評価
- **期間**: 各ポートフォリオごとに異なる期間（tiから最終日まで）
- **指標**: 銘柄間の平均・分散を計算（時系列指標ではない）

### 使用例
```python
from omanta_3rd.backtest.performance import calculate_portfolio_performance

# 特定のリバランス日のパフォーマンスを計算
perf = calculate_portfolio_performance(
    rebalance_date="2022-01-31",
    as_of_date="2025-12-26"  # Noneの場合は最新日
)
```

### 出力
- `total_return_pct`: ポートフォリオ全体の累積リターン（%）
- `avg_return_pct`: 銘柄間の平均リターン（%）
- `stocks`: 各銘柄の個別リターン

### 注意点
- 各ポートフォリオの期間が異なるため、時系列指標（Sharpe、Sortino、MaxDD）として解釈できない
- 銘柄間の平均・分散を計算しているため、標準的なバックテスト指標とは異なる

---

## 2. 時系列版（月次リターン計算）

### ファイル
- `calculate_performance_metrics_timeseries.py`
- `src/omanta_3rd/backtest/timeseries.py`
- `src/omanta_3rd/backtest/metrics.py`

### 計算方法
各リバランス日 `ti` から**次のリバランス日 `ti+1`**までの月次リターンを計算します。

```
リバランス日 t0 → リバランス日 t1
リバランス日 t1 → リバランス日 t2
...
リバランス日 tN-1 → リバランス日 tN
```

### 特徴
- **用途**: 月次リバランス戦略としての標準的なバックテスト指標を計算
- **期間**: 各ポートフォリオは1ヶ月間（ti→ti+1）
- **指標**: 時系列リターン系列から標準的な指標を計算

### 使用例
```python
from omanta_3rd.backtest.timeseries import calculate_timeseries_returns
from omanta_3rd.backtest.metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)

# 時系列P/Lを計算
timeseries_data = calculate_timeseries_returns(
    start_date="2022-01-01",
    end_date="2025-12-31",
    cost_bps=0.0,
)

# 指標を計算
max_dd = calculate_max_drawdown(timeseries_data["equity_curve"])
sharpe = calculate_sharpe_ratio(
    timeseries_data["monthly_returns"],
    timeseries_data["monthly_excess_returns"],
)
```

### 出力
- `monthly_returns`: 月次リターン系列（小数）
- `monthly_excess_returns`: 月次超過リターン系列（小数）
- `equity_curve`: エクイティカーブ（初期値1.0からの累積）
- `metrics`: 標準的なバックテスト指標
  - CAGR（年率リターン）
  - MaxDD（最大ドローダウン）
  - Sharpe Ratio（年率化）
  - Sortino Ratio（年率化）
  - Calmar Ratio
  - Win Rate（月次勝率）
  - Profit Factor

### 注意点
- 標準的なバックテスト指標として解釈可能
- エクイティカーブからMaxDDを計算
- 月次リターン系列からSharpe/Sortinoを計算（年率化）

---

## 3. 比較表

| 項目 | 既存版（累積リターン） | 時系列版（月次リターン） |
|------|---------------------|----------------------|
| **計算期間** | ti → 最終日 | ti → ti+1 |
| **期間の長さ** | 各ポートフォリオで異なる | 各ポートフォリオで1ヶ月 |
| **指標の種類** | 銘柄間の平均・分散 | 時系列指標 |
| **MaxDD** | 計算不可（時系列がない） | エクイティカーブから計算 |
| **Sharpe/Sortino** | 銘柄間の統計（時系列ではない） | 月次リターン系列から計算（年率化） |
| **用途** | 特定時点での累積パフォーマンス評価 | 標準的なバックテスト指標 |
| **最適化** | 不適切（期間が異なる） | 適切（時系列指標） |

---

## 4. 使い分け

### 既存版を使用する場合
- 特定のリバランス日時点での累積パフォーマンスを確認したい
- 各銘柄の個別リターンを詳細に分析したい
- 既存のデータベース構造との互換性を保ちたい
- 既存の最適化結果との互換性を保ちたい

### 時系列版を使用する場合
- 標準的なバックテスト指標（Sharpe、Sortino、MaxDD）を計算したい
- 最適化の目的関数として使用したい（推奨）
- エクイティカーブを可視化したい
- 月次リバランス戦略としてのパフォーマンスを評価したい
- 正しい時系列指標で最適化を行いたい

---

## 5. 実装ファイル一覧

### 既存版
- `src/omanta_3rd/backtest/performance.py`
  - `calculate_portfolio_performance()` - 単一ポートフォリオのパフォーマンス計算
  - `calculate_all_portfolios_performance()` - 全ポートフォリオのパフォーマンス計算
  - `save_performance_to_db()` - データベースへの保存
- `calculate_performance_metrics.py` - 運用評価指標の計算（銘柄間統計）
- `src/omanta_3rd/jobs/optimize.py` - パラメータ最適化（累積リターン計算を使用）

### 時系列版
- `src/omanta_3rd/backtest/timeseries.py`
  - `calculate_timeseries_returns()` - 時系列P/L計算
- `src/omanta_3rd/backtest/metrics.py`
  - `calculate_max_drawdown()` - 最大ドローダウン
  - `calculate_sharpe_ratio()` - シャープレシオ
  - `calculate_sortino_ratio()` - ソルティノレシオ
  - `calculate_calmar_ratio()` - カルマーレシオ
  - `calculate_profit_factor_timeseries()` - プロフィットファクタ
  - `calculate_win_rate_timeseries()` - 勝率
  - `calculate_cagr()` - 年率リターン
  - `calculate_volatility_timeseries()` - ボラティリティ
- `calculate_performance_metrics_timeseries.py` - 運用評価指標の計算（時系列版）
- `src/omanta_3rd/jobs/optimize_timeseries.py` - パラメータ最適化（時系列P/L計算を使用）

---

## 6. 移行ガイド

### 既存版から時系列版への移行

1. **最適化の目的関数を修正**
   ```python
   # 旧: calculate_all_portfolios_performance(as_of_date=end_date)
   # 新: calculate_timeseries_returns(start_date, end_date)
   ```

2. **指標計算を修正**
   ```python
   # 旧: 銘柄間の平均・分散
   # 新: 月次リターン系列から計算
   ```

3. **エクイティカーブの使用**
   ```python
   # 新: equity_curveからMaxDDを計算
   max_dd = calculate_max_drawdown(equity_curve)
   ```

---

**最終更新日**: 2025-12-29  
**バージョン**: 1.0


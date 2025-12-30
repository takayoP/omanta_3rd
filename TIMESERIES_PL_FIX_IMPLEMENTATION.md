# 時系列P/L計算の修正実装計画

## 概要

ChatGPTの分析に基づき、現状の「リバランス日→最終日」の累積リターン計算を、「ti→ti+1」の月次リターン系列に修正します。

---

## 1. 現状の問題点の特定

### 1.1 問題箇所の特定

**問題のあるコード**:
- `src/omanta_3rd/backtest/performance.py` の `calculate_all_portfolios_performance()` 関数
- `calculate_performance_metrics.py` の `calculate_performance_metrics()` 関数

**問題の原因**:
```python
# calculate_all_portfolios_performance() の呼び出し
performance_results = calculate_all_portfolios_performance(as_of_date=end_date)
# → as_of_dateがNoneの場合、最新の価格データを使用
# → 各リバランス日から「最終日」までの累積リターンを計算

# calculate_portfolio_performance() 内
if as_of_date is None:
    latest_date_df = pd.read_sql_query(
        "SELECT MAX(date) as max_date FROM prices_daily",
        conn
    )
    as_of_date = str(latest_date_df["max_date"].iloc[0])  # ← ここが問題
```

**結果**:
- 各リバランス日 `ti` のポートフォリオリターンが「ti→最終日」の累積リターンになっている
- 月次リターン系列が作られていない
- エクイティカーブが作られていない
- MaxDD、Sharpe、Sortinoが正しく計算されていない

### 1.2 確認方法

`performance_metrics.json` を確認すると：
- 同一ポートフォリオ内の各銘柄で `returns - excess_returns` が一定（TOPIXリターン）
- その差が89%など、月次としては異常に大きい（累積リターンである証拠）

---

## 2. 修正方針

### 2.1 基本方針

1. **月次リターン系列を作成**: ti→ti+1のポートフォリオリターンを計算
2. **エクイティカーブを作成**: 月次リターンから累積資産曲線を計算
3. **標準的な指標を計算**: エクイティカーブと月次リターン系列から指標を計算

### 2.2 実装アプローチ

**新規作成**:
- `src/omanta_3rd/backtest/timeseries.py` - 時系列P/L計算モジュール
- `src/omanta_3rd/backtest/metrics.py` - 時系列指標計算モジュール

**修正**:
- `calculate_performance_metrics.py` - 新しい時系列計算を使用
- `src/omanta_3rd/jobs/optimize.py` - 目的関数を時系列指標に変更

---

## 3. 実装詳細

### 3.1 時系列P/L計算モジュール（新規作成）

**ファイル**: `src/omanta_3rd/backtest/timeseries.py`

```python
"""
時系列P/L計算モジュール

月次リバランス戦略としての正しい時系列リターンを計算します。
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from ..infra.db import connect_db
from .performance import _get_next_trading_day, _get_previous_trading_day, _split_multiplier_between, _get_topix_price


def calculate_timeseries_returns(
    start_date: str,
    end_date: str,
    rebalance_dates: Optional[List[str]] = None,
    cost_bps: float = 0.0,
) -> Dict[str, Any]:
    """
    時系列P/Lを計算
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        rebalance_dates: リバランス日のリスト（Noneの場合は自動取得）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
    
    Returns:
        時系列P/L情報の辞書:
        - monthly_returns: 月次リターンのリスト（小数、0.01 = 1%）
        - monthly_excess_returns: 月次超過リターンのリスト（小数）
        - equity_curve: エクイティカーブ（初期値1.0）
        - dates: リバランス日のリスト
        - portfolio_details: 各リバランス日のポートフォリオ詳細
    """
    with connect_db() as conn:
        # リバランス日のリストを取得
        if rebalance_dates is None:
            rebalance_dates = _get_rebalance_dates(conn, start_date, end_date)
        
        monthly_returns = []
        monthly_excess_returns = []
        equity_curve = [1.0]  # 初期値1.0
        portfolio_details = []
        
        for i, rebalance_date in enumerate(rebalance_dates):
            # 次のリバランス日を取得（最後の場合はend_date）
            if i + 1 < len(rebalance_dates):
                next_rebalance_date = rebalance_dates[i + 1]
            else:
                next_rebalance_date = end_date
            
            # ポートフォリオを取得
            portfolio = _get_portfolio(conn, rebalance_date)
            if portfolio.empty:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # リバランス日の翌営業日を取得（購入日）
            purchase_date = _get_next_trading_day(conn, rebalance_date)
            if purchase_date is None:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 次のリバランス日の前営業日を取得（売却日）
            # 注意: 次のリバランス日の価格は使わない（リバランス前の価格を使用）
            sell_date = _get_previous_trading_day(conn, next_rebalance_date)
            if sell_date is None:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 各銘柄のリターンを計算
            stock_returns = []
            for _, row in portfolio.iterrows():
                code = row["code"]
                weight = row["weight"]
                
                # 購入価格（リバランス日の翌営業日の始値）
                purchase_price = _get_price(conn, code, purchase_date, use_open=True)
                if purchase_price is None:
                    continue
                
                # 売却価格（次のリバランス日の前営業日の終値）
                sell_price = _get_price(conn, code, sell_date, use_open=False)
                if sell_price is None:
                    continue
                
                # 株式分割を考慮
                split_mult = _split_multiplier_between(conn, code, purchase_date, sell_date)
                
                # リターン計算（分割を考慮）
                # 分割が発生した場合、購入価格を分割後の基準に調整
                adjusted_purchase_price = purchase_price / split_mult
                return_decimal = (sell_price / adjusted_purchase_price - 1.0)
                
                stock_returns.append({
                    "code": code,
                    "weight": weight,
                    "return_decimal": return_decimal,
                })
            
            # ポートフォリオ全体のグロスリターン（等加重平均）
            if stock_returns:
                portfolio_return_gross = sum(
                    r["weight"] * r["return_decimal"] 
                    for r in stock_returns
                )
                
                # 取引コストを控除（簡易版：ターンオーバーは後で計算）
                portfolio_return_net = portfolio_return_gross - (cost_bps / 1e4)
                
                # TOPIXリターンを計算
                topix_purchase = _get_topix_price(conn, purchase_date, use_open=False)
                topix_sell = _get_topix_price(conn, sell_date, use_open=False)
                
                if topix_purchase is not None and topix_sell is not None and topix_purchase > 0:
                    topix_return = (topix_sell / topix_purchase - 1.0)
                    excess_return = portfolio_return_net - topix_return
                else:
                    topix_return = 0.0
                    excess_return = portfolio_return_net
                
                monthly_returns.append(portfolio_return_net)
                monthly_excess_returns.append(excess_return)
                equity_curve.append(equity_curve[-1] * (1.0 + portfolio_return_net))
                
                portfolio_details.append({
                    "rebalance_date": rebalance_date,
                    "purchase_date": purchase_date,
                    "sell_date": sell_date,
                    "next_rebalance_date": next_rebalance_date,
                    "num_stocks": len(stock_returns),
                    "portfolio_return_gross": portfolio_return_gross,
                    "portfolio_return_net": portfolio_return_net,
                    "topix_return": topix_return,
                    "excess_return": excess_return,
                })
            else:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
        
        return {
            "monthly_returns": monthly_returns,  # 小数（0.01 = 1%）
            "monthly_excess_returns": monthly_excess_returns,  # 小数
            "equity_curve": equity_curve,  # 初期値1.0からの累積
            "dates": rebalance_dates,
            "portfolio_details": portfolio_details,
        }


def _get_rebalance_dates(conn, start_date: str, end_date: str) -> List[str]:
    """
    リバランス日のリストを取得
    """
    df = pd.read_sql_query(
        """
        SELECT DISTINCT rebalance_date
        FROM portfolio_monthly
        WHERE rebalance_date >= ? AND rebalance_date <= ?
        ORDER BY rebalance_date ASC
        """,
        conn,
        params=(start_date, end_date),
    )
    return df["rebalance_date"].tolist()


def _get_portfolio(conn, rebalance_date: str) -> pd.DataFrame:
    """
    指定日のポートフォリオを取得
    """
    return pd.read_sql_query(
        """
        SELECT code, weight
        FROM portfolio_monthly
        WHERE rebalance_date = ?
        """,
        conn,
        params=(rebalance_date,),
    )


def _get_previous_trading_day(conn, date: str) -> Optional[str]:
    """
    指定日付の前営業日を取得
    """
    prev_date_df = pd.read_sql_query(
        """
        SELECT MAX(date) AS prev_date
        FROM prices_daily
        WHERE date < ?
        """,
        conn,
        params=(date,),
    )
    
    if prev_date_df.empty or pd.isna(prev_date_df["prev_date"].iloc[0]):
        return None
    
    return str(prev_date_df["prev_date"].iloc[0])


def _get_price(conn, code: str, date: str, use_open: bool = False) -> Optional[float]:
    """
    指定日の価格を取得
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        date: 日付（YYYY-MM-DD）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        価格、存在しない場合はNone
    """
    price_column = "open" if use_open else "close"
    price_df = pd.read_sql_query(
        f"""
        SELECT {price_column}
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """,
        conn,
        params=(code, date),
    )
    
    if price_df.empty or pd.isna(price_df[price_column].iloc[0]):
        return None
    
    return float(price_df[price_column].iloc[0])
```

### 3.2 時系列指標計算モジュール（新規作成）

**ファイル**: `src/omanta_3rd/backtest/metrics.py`

```python
"""
時系列指標計算モジュール

エクイティカーブと月次リターンから、標準的なバックテスト指標を計算します。
"""

from typing import List, Optional
import numpy as np


def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """
    最大ドローダウンを計算
    
    Args:
        equity_curve: エクイティカーブ（初期値1.0からの累積）
    
    Returns:
        最大ドローダウン（小数、-0.1 = -10%）
    """
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


def calculate_sharpe_ratio(
    monthly_returns: List[float],
    monthly_excess_returns: Optional[List[float]] = None,
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> Optional[float]:
    """
    シャープレシオを計算
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        monthly_excess_returns: 月次超過リターンのリスト（小数、Noneの場合はmonthly_returnsを使用）
        risk_free_rate: リスクフリーレート（年率、小数、デフォルト: 0.0）
        annualize: 年率化するかどうか
    
    Returns:
        シャープレシオ（None if 計算不可）
    """
    if monthly_excess_returns is not None:
        returns_array = np.array(monthly_excess_returns)
    else:
        returns_array = np.array(monthly_returns)
    
    if len(returns_array) < 2:
        return None
    
    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array, ddof=1)
    
    if std_return == 0:
        return None
    
    # 月次リターンから計算
    sharpe = (mean_return - risk_free_rate / 12.0) / std_return
    
    # 年率化
    if annualize:
        sharpe *= np.sqrt(12.0)
    
    return float(sharpe)


def calculate_sortino_ratio(
    monthly_returns: List[float],
    monthly_excess_returns: Optional[List[float]] = None,
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> Optional[float]:
    """
    ソルティノレシオを計算
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        monthly_excess_returns: 月次超過リターンのリスト（小数、Noneの場合はmonthly_returnsを使用）
        risk_free_rate: リスクフリーレート（年率、小数、デフォルト: 0.0）
        annualize: 年率化するかどうか
    
    Returns:
        ソルティノレシオ（None if 計算不可）
    """
    if monthly_excess_returns is not None:
        returns_array = np.array(monthly_excess_returns)
    else:
        returns_array = np.array(monthly_returns)
    
    if len(returns_array) < 2:
        return None
    
    mean_return = np.mean(returns_array)
    
    # 下方リスク（負のリターンのみの標準偏差）
    negative_returns = returns_array[returns_array < 0]
    
    if len(negative_returns) == 0:
        # 負のリターンがない場合
        if mean_return > risk_free_rate / 12.0:
            return None  # または非常に大きな値（999.0など）
        else:
            return None
    
    downside_std = np.std(negative_returns, ddof=1)
    
    if downside_std == 0:
        return None
    
    # 月次リターンから計算
    sortino = (mean_return - risk_free_rate / 12.0) / downside_std
    
    # 年率化
    if annualize:
        sortino *= np.sqrt(12.0)
    
    return float(sortino)


def calculate_calmar_ratio(
    equity_curve: List[float],
    monthly_returns: List[float],
) -> Optional[float]:
    """
    カルマーレシオを計算
    
    カルマーレシオ = 年率リターン / 最大ドローダウン（絶対値）
    
    Args:
        equity_curve: エクイティカーブ
        monthly_returns: 月次リターンのリスト（小数）
    
    Returns:
        カルマーレシオ（None if 計算不可）
    """
    if not monthly_returns or not equity_curve:
        return None
    
    # 年率リターンを計算
    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    num_months = len(monthly_returns)
    if num_months == 0:
        return None
    
    annual_return = ((1.0 + total_return) ** (12.0 / num_months) - 1.0)
    
    # 最大ドローダウンを計算
    max_dd = abs(calculate_max_drawdown(equity_curve))
    
    if max_dd == 0:
        return None
    
    return annual_return / max_dd


def calculate_profit_factor_timeseries(monthly_returns: List[float]) -> Optional[float]:
    """
    プロフィットファクタを計算（時系列リターンから）
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
    
    Returns:
        プロフィットファクタ（None if 計算不可）
    """
    if not monthly_returns:
        return None
    
    gains = [r for r in monthly_returns if r > 0]
    losses = [abs(r) for r in monthly_returns if r < 0]
    
    total_gains = sum(gains) if gains else 0.0
    total_losses = sum(losses) if losses else 0.0
    
    if total_losses == 0:
        return None if total_gains == 0 else float('inf')
    
    return total_gains / total_losses


def calculate_win_rate_timeseries(
    monthly_returns: List[float],
    use_excess: bool = False,
    monthly_excess_returns: Optional[List[float]] = None,
) -> Optional[float]:
    """
    勝率を計算（時系列リターンから）
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        use_excess: 超過リターンを使用するかどうか
        monthly_excess_returns: 月次超過リターンのリスト（小数）
    
    Returns:
        勝率（0.0-1.0、None if 計算不可）
    """
    if not monthly_returns:
        return None
    
    if use_excess and monthly_excess_returns is not None:
        returns_array = np.array(monthly_excess_returns)
    else:
        returns_array = np.array(monthly_returns)
    
    wins = (returns_array > 0).sum()
    total = len(returns_array)
    
    if total == 0:
        return None
    
    return float(wins / total)


def calculate_cagr(equity_curve: List[float], num_months: int) -> Optional[float]:
    """
    年率リターン（CAGR）を計算
    
    Args:
        equity_curve: エクイティカーブ
        num_months: 月数
    
    Returns:
        CAGR（小数、0.1 = 10%）
    """
    if not equity_curve or num_months == 0:
        return None
    
    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    cagr = (1.0 + total_return) ** (12.0 / num_months) - 1.0
    
    return float(cagr)


def calculate_volatility_timeseries(
    monthly_returns: List[float],
    annualize: bool = True,
) -> Optional[float]:
    """
    ボラティリティを計算（時系列リターンから）
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        annualize: 年率換算するか（デフォルト: True）
    
    Returns:
        ボラティリティ（小数、0.1 = 10%）
    """
    if not monthly_returns or len(monthly_returns) < 2:
        return None
    
    returns_array = np.array(monthly_returns)
    std_return = np.std(returns_array, ddof=1)
    
    if annualize:
        # 月次リターンから年率換算（√12倍）
        std_return *= np.sqrt(12.0)
    
    return float(std_return)
```

---

## 4. 既存コードの修正

### 4.1 calculate_performance_metrics.py の修正

**修正方針**:
- 時系列P/L計算を使用
- 月次リターン系列から指標を計算
- エクイティカーブからMaxDDを計算

**主要な変更点**:
```python
# 旧: calculate_all_portfolios_performance(as_of_date=end_date)
# 新: calculate_timeseries_returns(start_date, end_date)

from omanta_3rd.backtest.timeseries import calculate_timeseries_returns
from omanta_3rd.backtest.metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_profit_factor_timeseries,
    calculate_win_rate_timeseries,
    calculate_cagr,
    calculate_volatility_timeseries,
)

# 時系列P/Lを計算
timeseries_data = calculate_timeseries_returns(
    start_date=start_date or "2021-01-01",
    end_date=end_date or "2025-12-31",
    cost_bps=0.0,  # 取引コスト（後で調整可能）
)

# 指標を計算
max_dd = calculate_max_drawdown(timeseries_data["equity_curve"])
sharpe = calculate_sharpe_ratio(
    timeseries_data["monthly_returns"],
    timeseries_data["monthly_excess_returns"],
)
sortino = calculate_sortino_ratio(
    timeseries_data["monthly_returns"],
    timeseries_data["monthly_excess_returns"],
)
```

### 4.2 optimize.py の目的関数の修正

**修正方針**:
- 時系列指標を使用
- 月次超過リターン系列の平均を使用
- 月次勝率を使用
- 月次超過リターン系列のSharpeを使用

**主要な変更点**:
```python
# 旧: 個別ポートフォリオのパフォーマンスから計算
# 新: 時系列P/Lから計算

from omanta_3rd.backtest.timeseries import calculate_timeseries_returns
from omanta_3rd.backtest.metrics import (
    calculate_sharpe_ratio,
    calculate_win_rate_timeseries,
)

# 時系列P/Lを計算
timeseries_data = calculate_timeseries_returns(
    start_date=rebalance_dates[0],
    end_date=rebalance_dates[-1],
    rebalance_dates=rebalance_dates,
    cost_bps=0.0,
)

# 目的関数の値を計算
monthly_excess_returns = timeseries_data["monthly_excess_returns"]
mean_excess_return = np.mean(monthly_excess_returns) * 100.0  # %換算
win_rate = calculate_win_rate_timeseries(
    timeseries_data["monthly_returns"],
    use_excess=True,
    monthly_excess_returns=monthly_excess_returns,
)
sharpe_ratio = calculate_sharpe_ratio(
    timeseries_data["monthly_returns"],
    monthly_excess_returns,
)

objective_value = (
    mean_excess_return * 0.7
    + win_rate * 10.0 * 0.2
    + sharpe_ratio * 0.1
)
```

---

## 5. サニティチェック

### 5.1 チェック項目

1. **TOPIXの月次リターン分布が常識的**
   - 平均：±数％ / 月
   - 最小：-20% / 月以下（リーマン級）
   - 最大：+20% / 月以下

2. **個別銘柄の月次リターンに +300% が頻発しない**
   - 出るなら、株式分割・併合・データ欠損・調整前価格を疑う

3. **equity curve が上下し、MaxDD が0にならない**
   - 普通は0にはなりません

4. **Sharpe/Sortinoが“桁違い”に大きくならない**
   - 月次で Sortino 165 は通常あり得ない水準

### 5.2 チェックスクリプト

実装後に実行するチェックスクリプトを作成予定。

---

## 6. 実装手順

### Phase 1: 新規モジュールの作成 ✅ 完了

1. ✅ `src/omanta_3rd/backtest/timeseries.py` を作成
2. ✅ `src/omanta_3rd/backtest/metrics.py` を作成
3. ⏳ 単体テストを実行（次のステップ）

### Phase 2: 既存コードの修正 ✅ 完了

1. ✅ `calculate_performance_metrics.py` - 既存版として保持（コメント追加済み）
2. ✅ `calculate_performance_metrics_timeseries.py` - 時系列版を新規作成
3. ✅ `src/omanta_3rd/jobs/optimize.py` - 既存版として保持
4. ✅ `src/omanta_3rd/jobs/optimize_timeseries.py` - 時系列版を新規作成
5. ⏳ 統合テストを実行

### Phase 3: 検証 ⏳ 未実装

1. ⏳ サニティチェックを実行
2. ⏳ 既存のバックテスト結果と比較
3. ⏳ 指標の妥当性を確認

---

## 7. 実装状況

### 完了した実装

- ✅ `src/omanta_3rd/backtest/timeseries.py` - 時系列P/L計算モジュール
  - `calculate_timeseries_returns()` - 月次リターン系列を計算
  - `_get_previous_trading_day()` - 前営業日を取得
  - `_get_price()` - 指定日の価格を取得
  - `_get_rebalance_dates()` - リバランス日のリストを取得
  - `_get_portfolio()` - ポートフォリオを取得

- ✅ `src/omanta_3rd/backtest/metrics.py` - 時系列指標計算モジュール
  - `calculate_max_drawdown()` - 最大ドローダウンを計算
  - `calculate_sharpe_ratio()` - シャープレシオを計算
  - `calculate_sortino_ratio()` - ソルティノレシオを計算
  - `calculate_calmar_ratio()` - カルマーレシオを計算
  - `calculate_profit_factor_timeseries()` - プロフィットファクタを計算
  - `calculate_win_rate_timeseries()` - 勝率を計算
  - `calculate_cagr()` - 年率リターンを計算
  - `calculate_volatility_timeseries()` - ボラティリティを計算

- ✅ `calculate_performance_metrics_timeseries.py` - 時系列版の運用評価指標計算スクリプト
  - `calculate_performance_metrics_timeseries()` - 時系列指標を計算

- ✅ `src/omanta_3rd/jobs/optimize_timeseries.py` - 時系列版の最適化スクリプト
  - `run_backtest_for_optimization_timeseries()` - 時系列P/L計算を使用したバックテスト実行
  - `objective_timeseries()` - 時系列指標ベースの目的関数
  - `main()` - 最適化のメイン処理

### 次のステップ

1. ✅ `calculate_performance_metrics_timeseries.py` を作成（完了）
2. ✅ `src/omanta_3rd/jobs/optimize_timeseries.py` を作成（完了）
3. ⏳ サニティチェックスクリプトを作成
4. ⏳ 既存のバックテスト結果と比較して検証
5. ⏳ 時系列版の動作確認

---

**最終更新日**: 2025-12-29  
**バージョン**: 1.1


# 時系列P/L計算の実装計画

## 概要

ChatGPT評価で指摘された「評価系の妥当性」問題に対応するため、月次リバランス戦略としての正しい時系列P/Lを計算する機能を実装します。

---

## 1. 現状の問題点

### 1.1 指標計算の問題

**現状**:
- MaxDD=0.00%（計算方法の制約で0表示）
- Sortino=999.0（下方偏差がほぼ0）
- Profit Factor=Infinity（損失ゼロ）
- 指標定義が「時系列バックテスト」になっていない可能性

**原因**:
- 各ポートフォリオごとの個別リターンを集計している
- 時系列のエクイティカーブを作成していない
- 月次リバランスの連続性を考慮していない

---

## 2. 実装方針

### 2.1 時系列P/Lの計算フロー

```
1. リバランス日のリストを取得（月次）
   - 例: 2021-01-29, 2021-02-26, ..., 2025-11-28

2. 各リバランス日tで以下を実行:
   a. ポートフォリオを取得（12銘柄、等加重）
   b. リバランス日tの翌営業日の価格を取得（購入価格）
   c. リバランス日t+1の価格を取得（売却価格）
   d. 各銘柄のリターンを計算（株式分割を考慮）
   e. ポートフォリオ全体のリターンを計算（等加重平均）

3. 時系列リターンを連結:
   - portfolio_returns = [r1, r2, ..., rn]  # 月次リターン
   - equity_curve = [100, 100*(1+r1), 100*(1+r1)*(1+r2), ...]  # エクイティカーブ

4. エクイティカーブから指標を計算:
   - MaxDD: ピークからの最大下落率
   - Sharpe: 月次リターンの平均/標準偏差 × √12（年率化）
   - Sortino: 月次リターンの平均/下方偏差 × √12（年率化）
   - Calmar: 年率リターン / MaxDD
```

### 2.2 実装ファイル構成

```
src/omanta_3rd/backtest/
├── time_series.py          # 新規作成: 時系列P/L計算
├── performance.py          # 既存: 個別ポートフォリオのパフォーマンス計算
└── metrics.py              # 新規作成: 時系列指標の計算
```

---

## 3. 実装詳細

### 3.1 time_series.py の実装

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
from .performance import _get_next_trading_day, _split_multiplier_between


def calculate_timeseries_returns(
    start_date: str,
    end_date: str,
    rebalance_dates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    時系列P/Lを計算
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        rebalance_dates: リバランス日のリスト（Noneの場合は自動取得）
    
    Returns:
        時系列P/L情報の辞書:
        - monthly_returns: 月次リターンのリスト（%）
        - equity_curve: エクイティカーブ（初期値100）
        - dates: リバランス日のリスト
        - portfolio_details: 各リバランス日のポートフォリオ詳細
    """
    with connect_db() as conn:
        # リバランス日のリストを取得
        if rebalance_dates is None:
            rebalance_dates = _get_rebalance_dates(conn, start_date, end_date)
        
        monthly_returns = []
        equity_curve = [100.0]  # 初期値100
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
                equity_curve.append(equity_curve[-1])
                continue
            
            # リバランス日の翌営業日を取得（購入日）
            purchase_date = _get_next_trading_day(conn, rebalance_date)
            if purchase_date is None:
                monthly_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 次のリバランス日の価格を取得（売却日）
            # 注意: 次のリバランス日の前営業日を使用（リバランス日の価格は使わない）
            sell_date = _get_previous_trading_day(conn, next_rebalance_date)
            if sell_date is None:
                monthly_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 各銘柄のリターンを計算
            returns = []
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
                return_pct = (sell_price / adjusted_purchase_price - 1.0) * 100.0
                
                returns.append({
                    "code": code,
                    "weight": weight,
                    "return_pct": return_pct,
                })
            
            # ポートフォリオ全体のリターン（等加重平均）
            if returns:
                portfolio_return = sum(r["weight"] * r["return_pct"] for r in returns)
                monthly_returns.append(portfolio_return)
                equity_curve.append(equity_curve[-1] * (1.0 + portfolio_return / 100.0))
            else:
                monthly_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
            
            portfolio_details.append({
                "rebalance_date": rebalance_date,
                "purchase_date": purchase_date,
                "sell_date": sell_date,
                "num_stocks": len(returns),
                "portfolio_return": portfolio_return if returns else 0.0,
            })
        
        return {
            "monthly_returns": monthly_returns,
            "equity_curve": equity_curve,
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

### 3.2 metrics.py の実装

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
        equity_curve: エクイティカーブ（初期値100からの増減率、%）
    
    Returns:
        最大ドローダウン（%）
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    # エクイティカーブを絶対値に変換（初期値100 + 増減率%）
    values = np.array([100.0 + v for v in equity_curve])
    
    # ピークを計算（累積最大値）
    peak = np.maximum.accumulate(values)
    
    # ドローダウンを計算（ピークからの下落率）
    drawdown = (values - peak) / peak * 100.0
    
    max_dd = np.min(drawdown)
    return float(max_dd)


def calculate_sharpe_ratio(
    monthly_returns: List[float],
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> Optional[float]:
    """
    シャープレシオを計算
    
    Args:
        monthly_returns: 月次リターンのリスト（%）
        risk_free_rate: リスクフリーレート（年率、%）
        annualize: 年率化するかどうか
    
    Returns:
        シャープレシオ（None if 計算不可）
    """
    if not monthly_returns or len(monthly_returns) < 2:
        return None
    
    returns_array = np.array(monthly_returns)
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
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> Optional[float]:
    """
    ソルティノレシオを計算
    
    Args:
        monthly_returns: 月次リターンのリスト（%）
        risk_free_rate: リスクフリーレート（年率、%）
        annualize: 年率化するかどうか
    
    Returns:
        ソルティノレシオ（None if 計算不可）
    """
    if not monthly_returns or len(monthly_returns) < 2:
        return None
    
    returns_array = np.array(monthly_returns)
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
    
    カルマーレシオ = 年率リターン / 最大ドローダウン
    
    Args:
        equity_curve: エクイティカーブ
        monthly_returns: 月次リターンのリスト（%）
    
    Returns:
        カルマーレシオ（None if 計算不可）
    """
    if not monthly_returns:
        return None
    
    # 年率リターンを計算
    total_return = (equity_curve[-1] / equity_curve[0] - 1.0) * 100.0
    num_months = len(monthly_returns)
    if num_months == 0:
        return None
    
    annual_return = ((1.0 + total_return / 100.0) ** (12.0 / num_months) - 1.0) * 100.0
    
    # 最大ドローダウンを計算
    max_dd = abs(calculate_max_drawdown(equity_curve))
    
    if max_dd == 0:
        return None
    
    return annual_return / max_dd


def calculate_profit_factor_timeseries(monthly_returns: List[float]) -> Optional[float]:
    """
    プロフィットファクタを計算（時系列リターンから）
    
    Args:
        monthly_returns: 月次リターンのリスト（%）
    
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
```

---

## 4. 実装手順

### 4.1 Phase 1: 時系列P/L計算の実装

1. `src/omanta_3rd/backtest/time_series.py`を作成
2. `calculate_timeseries_returns`関数を実装
3. テスト: 2021-01-29 ～ 2025-11-28の時系列P/Lを計算

### 4.2 Phase 2: 指標計算の実装

1. `src/omanta_3rd/backtest/metrics.py`を作成
2. MaxDD、Sharpe、Sortino、Calmar、PFの計算関数を実装
3. テスト: 時系列P/Lから指標を計算

### 4.3 Phase 3: 既存コードの統合

1. `calculate_performance_metrics.py`を修正
2. 時系列P/L計算を使用するように変更
3. 指標計算を新しい関数に置き換え

---

## 5. テスト計画

### 5.1 単体テスト

- 時系列P/L計算の正確性
- 指標計算の正確性
- エッジケース（欠損データ、分割発生など）

### 5.2 統合テスト

- 既存のバックテスト結果との整合性確認
- 時系列P/Lと個別ポートフォリオの整合性確認

---

## 6. 期待される改善

### 6.1 指標の正確性

- MaxDD: エクイティカーブから正確に計算
- Sortino: 時系列リターンから下方偏差を計算
- Profit Factor: 時系列P/Lから計算
- Sharpe: 時系列リターンから計算（年率化）

### 6.2 評価の信頼性

- 標準的なバックテスト指標として解釈可能
- 過学習検証の前提条件を満たす
- 将来のパフォーマンス予測に使用可能

---

**最終更新日**: 2025-12-29  
**バージョン**: 1.0








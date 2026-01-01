"""
時系列バックテスト評価の共通関数

メトリクス計算を共通化し、WFA/holdout評価で使用します。
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import numpy as np

from ..backtest.timeseries import calculate_timeseries_returns
from ..backtest.metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_cagr,
    calculate_volatility_timeseries,
    calculate_profit_factor_timeseries,
    calculate_win_rate_timeseries,
)


def calculate_metrics_from_timeseries_data(
    timeseries_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    時系列データからメトリクスを計算（共通関数）
    
    Args:
        timeseries_data: calculate_timeseries_returns()の戻り値
    
    Returns:
        メトリクスの辞書
    """
    monthly_returns = timeseries_data.get("monthly_returns", [])
    monthly_excess_returns = timeseries_data.get("monthly_excess_returns", [])
    equity_curve = timeseries_data.get("equity_curve", [])
    portfolio_details = timeseries_data.get("portfolio_details", [])
    
    if not monthly_returns:
        return {
            "error": "月次リターンデータがありません",
        }
    
    # 基本統計
    mean_return = np.mean(monthly_returns) if monthly_returns else 0.0
    mean_excess_return = np.mean(monthly_excess_returns) if monthly_excess_returns else 0.0
    
    # エクイティカーブから計算
    max_dd = calculate_max_drawdown(equity_curve) if equity_curve else 0.0
    cagr = calculate_cagr(equity_curve, len(monthly_returns)) if equity_curve else None
    volatility = calculate_volatility_timeseries(monthly_returns, annualize=True)
    
    # リスク調整後リターン
    # 注意: monthly_excess_returnsが指定された場合、これはベンチマーク超過リターン
    # そのため、risk_free_rate=0.0を指定（TOPIX超過Sharpe = 情報比率IR相当）
    sharpe = calculate_sharpe_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,  # 超過リターン使用時はRF=0（TOPIX超過Sharpeを計算）
        annualize=True,
    )
    sortino = calculate_sortino_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )
    
    # 勝率・Profit Factor
    win_rate = calculate_win_rate_timeseries(
        monthly_returns,
        use_excess=True,
        monthly_excess_returns=monthly_excess_returns,
    )
    profit_factor = calculate_profit_factor_timeseries(monthly_returns, equity_curve)
    
    # 総リターン
    total_return = None
    if equity_curve and len(equity_curve) > 0:
        total_return = (equity_curve[-1] / equity_curve[0] - 1.0) * 100.0
    
    # 欠損銘柄数
    total_missing_count = sum(
        detail.get("num_missing_stocks", 0) for detail in portfolio_details
    )
    
    return {
        # リターン指標
        "cagr": cagr * 100.0 if cagr is not None else None,  # %換算
        "mean_return": mean_return * 100.0,  # %換算
        "mean_excess_return": mean_excess_return * 100.0,  # %換算
        "total_return": total_return,  # %換算
        "volatility": volatility * 100.0 if volatility is not None else None,  # %換算
        
        # リスク指標
        "max_drawdown": max_dd * 100.0,  # %換算
        
        # リスク調整後リターン
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        
        # 勝率・Profit Factor
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        
        # その他
        "num_periods": len(monthly_returns),
        "num_missing_stocks": total_missing_count,
    }


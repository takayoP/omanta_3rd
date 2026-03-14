"""
ポートフォリオ評価の単一入口。
時系列リターンとターンオーバーから指標を計算し、目的関数（sharpe_excess - lambda_turnover * avg_turnover）を返す。
"""

from __future__ import annotations

from typing import Dict, Any, List
import pandas as pd

from ..infra.db import connect_db
from .timeseries import calculate_timeseries_returns_from_portfolios
from .metrics import (
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_calmar_ratio,
)


def evaluate_portfolio(
    portfolios: Dict[str, pd.DataFrame],
    start_date: str,
    end_date: str,
    cost_bps: float = 0.0,
    lambda_turnover: float = 0.0,
) -> Dict[str, Any]:
    """
    ポートフォリオ時系列を評価し、指標と目的関数を返す。

    Args:
        portfolios: {rebalance_date: portfolio_df}。各 portfolio_df は code, weight 列を持つ。
        start_date: 評価開始日 (YYYY-MM-DD)
        end_date: 評価終了日 (YYYY-MM-DD)
        cost_bps: 取引コスト (bps)
        lambda_turnover: ターンオーバーペナルティ。objective = sharpe_excess - lambda_turnover * avg_turnover

    Returns:
        sharpe_excess, cagr, maxdd, calmar, avg_turnover, objective, monthly_excess_returns, equity_curve, ...
    """
    result = calculate_timeseries_returns_from_portfolios(
        portfolios=portfolios,
        start_date=start_date,
        end_date=end_date,
        cost_bps=cost_bps,
    )

    monthly_returns = result["monthly_returns"]
    monthly_excess_returns = result["monthly_excess_returns"]
    equity_curve = result["equity_curve"]
    portfolio_details = result.get("portfolio_details", [])

    if len(monthly_excess_returns) < 2:
        return {
            "sharpe_excess": None,
            "cagr": None,
            "maxdd": None,
            "calmar": None,
            "avg_turnover": 0.0,
            "objective": None,
            "monthly_returns": monthly_returns,
            "monthly_excess_returns": monthly_excess_returns,
            "equity_curve": equity_curve,
            "dates": result.get("dates", []),
            "error": "insufficient_periods",
        }

    sharpe_excess = calculate_sharpe_ratio(
        monthly_returns=monthly_returns,
        monthly_excess_returns=monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )

    # CAGR (超過リターン基準の簡易年率)
    n_months = len(monthly_excess_returns)
    if n_months > 0 and equity_curve:
        total_return = equity_curve[-1] / equity_curve[0] - 1.0
        cagr = (1.0 + total_return) ** (12.0 / n_months) - 1.0 if n_months > 0 else None
    else:
        cagr = None

    maxdd = calculate_max_drawdown(equity_curve) if equity_curve else None
    calmar = calculate_calmar_ratio(equity_curve, monthly_returns) if equity_curve and monthly_returns else None

    # 平均ターンオーバー (paper_turnover の平均。0〜1)
    if portfolio_details:
        turnovers = [d.get("paper_turnover", 0.0) for d in portfolio_details]
        avg_turnover = sum(turnovers) / len(turnovers) if turnovers else 0.0
    else:
        avg_turnover = 0.0

    objective = None
    if sharpe_excess is not None:
        objective = sharpe_excess - lambda_turnover * avg_turnover

    return {
        "sharpe_excess": sharpe_excess,
        "cagr": cagr,
        "maxdd": maxdd,
        "calmar": calmar,
        "avg_turnover": avg_turnover,
        "objective": objective,
        "monthly_returns": monthly_returns,
        "monthly_excess_returns": monthly_excess_returns,
        "equity_curve": equity_curve,
        "dates": result.get("dates", []),
        "portfolio_details": portfolio_details,
    }

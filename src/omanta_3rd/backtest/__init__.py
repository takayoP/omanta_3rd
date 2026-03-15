"""バックテスト機能"""

from .metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_cagr,
    calculate_volatility_timeseries,
    calculate_profit_factor_timeseries,
    calculate_win_rate_timeseries,
    calculate_annualized_return_from_period,
    calculate_percentile,
)
from .performance import (
    calculate_portfolio_performance,
    calculate_all_portfolios_performance,
    save_performance_to_db,
)
from .timeseries import (
    calculate_timeseries_returns,
    calculate_timeseries_returns_from_portfolios,
)
from .performance_from_dataframe import calculate_portfolio_performance_from_dataframe
from .eval_common import calculate_metrics_from_timeseries_data, get_git_commit_hash
from .feature_cache import FeatureCache

__all__ = [
    # metrics
    "calculate_max_drawdown",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_calmar_ratio",
    "calculate_cagr",
    "calculate_volatility_timeseries",
    "calculate_profit_factor_timeseries",
    "calculate_win_rate_timeseries",
    "calculate_annualized_return_from_period",
    "calculate_percentile",
    # performance
    "calculate_portfolio_performance",
    "calculate_all_portfolios_performance",
    "save_performance_to_db",
    # timeseries
    "calculate_timeseries_returns",
    "calculate_timeseries_returns_from_portfolios",
    # misc
    "calculate_portfolio_performance_from_dataframe",
    "calculate_metrics_from_timeseries_data",
    "get_git_commit_hash",
    "FeatureCache",
]

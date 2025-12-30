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


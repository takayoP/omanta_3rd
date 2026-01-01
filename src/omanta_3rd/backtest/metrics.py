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
    
    【重要】monthly_excess_returnsが指定された場合（ベンチマーク超過リターン）:
    - 通常、これは既にベンチマーク（TOPIX等）を控除済み
    - この場合、risk_free_rateは引かない（TOPIX超過Sharpe = 情報比率IR相当）
    - risk_free_rateを引くと「無リスク超過Sharpe」になるが、TOPIX超過とは異なる
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        monthly_excess_returns: 月次超過リターンのリスト（小数、Noneの場合はmonthly_returnsを使用）
            ※ ベンチマーク超過リターンの場合、risk_free_rateは通常0.0に設定
        risk_free_rate: リスクフリーレート（年率、小数、デフォルト: 0.0）
            ※ monthly_excess_returns使用時は通常0.0（TOPIX超過Sharpeを計算するため）
        annualize: 年率化するかどうか
    
    Returns:
        シャープレシオ（None if 計算不可）
    """
    if monthly_excess_returns is not None:
        returns_array = np.array(monthly_excess_returns)
        # ベンチマーク超過リターンの場合、RFは引かない（TOPIX超過Sharpe = IR相当）
        # 将来RF≠0にする場合は、関数を分離するか、引数で明示的に指定する必要がある
        use_rf = False  # 超過リターン使用時はRFを引かない
    else:
        returns_array = np.array(monthly_returns)
        use_rf = True  # 通常リターンの場合はRFを引く
    
    if len(returns_array) < 2:
        return None
    
    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array, ddof=1)
    
    if std_return == 0:
        return None
    
    # 月次リターンから計算
    if use_rf:
        sharpe = (mean_return - risk_free_rate / 12.0) / std_return
    else:
        # 超過リターンの場合、RFは引かない（TOPIX超過Sharpe = 情報比率IR相当）
        sharpe = mean_return / std_return
    
    # 年率化
    if annualize:
        sharpe *= np.sqrt(12.0)
    
    return float(sharpe)


def calculate_sortino_ratio(
    monthly_returns: List[float],
    monthly_excess_returns: Optional[List[float]] = None,
    risk_free_rate: float = 0.0,
    annualize: bool = True,
    target: float = 0.0,
) -> Optional[float]:
    """
    ソルティノレシオを計算（標準定義）
    
    【標準定義】
    - downside = min(0, r - target) を全期間に適用
    - downside_dev = sqrt(mean(downside^2))
    - Sortino = (mean(r) - target) / downside_dev
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        monthly_excess_returns: 月次超過リターンのリスト（小数、Noneの場合はmonthly_returnsを使用）
        risk_free_rate: リスクフリーレート（年率、小数、デフォルト: 0.0）
        annualize: 年率化するかどうか
        target: 目標リターン（月次、小数、デフォルト: 0.0）
    
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
    
    # 下方リスク（標準定義）
    # downside = min(0, r - target) を全期間に適用
    downside = np.minimum(0.0, returns_array - target)
    
    # downside_dev = sqrt(mean(downside^2))
    downside_dev = np.sqrt(np.mean(downside ** 2))
    
    if downside_dev == 0:
        # 下方偏差が0の場合（すべてのリターンがtarget以上）
        if mean_return > target:
            return None  # 計算不可（無限大に近い）
        else:
            return None  # 計算不可
    
    # 月次リターンから計算
    sortino = (mean_return - target) / downside_dev
    
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


def calculate_profit_factor_timeseries(
    monthly_returns: List[float],
    equity_curve: Optional[List[float]] = None,
) -> Optional[float]:
    """
    プロフィットファクタを計算（時系列リターンから、標準定義）
    
    【標準定義】
    - pnl_t = equity_{t-1} * r_t（通貨建て損益）
    - PF = sum(pnl_pos) / abs(sum(pnl_neg))
    - 損失ゼロなら None を返す（np.inf ではなく）
    
    Args:
        monthly_returns: 月次リターンのリスト（小数）
        equity_curve: エクイティカーブ（初期値1.0からの累積、Noneの場合は簡易版を使用）
    
    Returns:
        プロフィットファクタ（None if 計算不可）
    """
    if not monthly_returns:
        return None
    
    # エクイティカーブが提供されている場合は標準定義を使用
    if equity_curve is not None and len(equity_curve) == len(monthly_returns) + 1:
        # pnl_t = equity_{t-1} * r_t（通貨建て損益）
        pnl_list = []
        for i, r in enumerate(monthly_returns):
            equity_prev = equity_curve[i]
            pnl = equity_prev * r
            pnl_list.append(pnl)
        
        pnl_array = np.array(pnl_list)
        pnl_pos = pnl_array[pnl_array > 0]
        pnl_neg = pnl_array[pnl_array < 0]
        
        total_pnl_pos = np.sum(pnl_pos) if len(pnl_pos) > 0 else 0.0
        total_pnl_neg = np.sum(pnl_neg) if len(pnl_neg) > 0 else 0.0
        
        if total_pnl_neg == 0:
            return None  # 損失ゼロなら None（np.inf ではなく）
        
        return float(total_pnl_pos / abs(total_pnl_neg))
    else:
        # 簡易版: 月次リターンの正負を単純合計（後方互換性のため）
        gains = [r for r in monthly_returns if r > 0]
        losses = [abs(r) for r in monthly_returns if r < 0]
        
        total_gains = sum(gains) if gains else 0.0
        total_losses = sum(losses) if losses else 0.0
        
        if total_losses == 0:
            return None  # 損失ゼロなら None（np.inf ではなく）
        
        return float(total_gains / total_losses)


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


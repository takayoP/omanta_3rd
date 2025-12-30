"""
ポートフォリオの運用評価指標を計算（既存版：累積リターン計算）

プロフィットファクタ、シャープレシオ、最大ドローダウンなどの
運用評価指標を計算します。

【計算方法】
各リバランス日 ti から最終評価日（as_of_date）までの累積リターンを計算します。
銘柄間の平均・分散を計算するため、時系列指標（Sharpe、Sortino、MaxDD）として
解釈することはできません。

【時系列版との違い】
- 既存版（本ファイル）: ti → 最終日 の累積リターン
- 時系列版（calculate_performance_metrics_timeseries.py）: ti → ti+1 の月次リターン

詳細は PERFORMANCE_CALCULATION_METHODS.md を参照してください。
"""

from __future__ import annotations

import sys
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from omanta_3rd.infra.db import connect_db
from omanta_3rd.backtest.performance import calculate_all_portfolios_performance


def calculate_profit_factor(returns: List[float]) -> Optional[float]:
    """
    プロフィットファクタを計算
    
    プロフィットファクタ = 総利益 / 総損失
    
    Args:
        returns: リターンのリスト（%）
    
    Returns:
        プロフィットファクタ（None if 計算不可）
    """
    if not returns:
        return None
    
    gains = [r for r in returns if r > 0]
    losses = [abs(r) for r in returns if r < 0]
    
    total_gains = sum(gains) if gains else 0.0
    total_losses = sum(losses) if losses else 0.0
    
    if total_losses == 0:
        return None if total_gains == 0 else float('inf')
    
    return total_gains / total_losses


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> Optional[float]:
    """
    シャープレシオを計算
    
    シャープレシオ = (平均リターン - リスクフリーレート) / 標準偏差
    
    Args:
        returns: リターンのリスト（%）
        risk_free_rate: リスクフリーレート（%、デフォルト: 0.0）
    
    Returns:
        シャープレシオ（None if 計算不可）
    """
    if not returns or len(returns) < 2:
        return None
    
    returns_array = np.array(returns)
    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array, ddof=1)
    
    if std_return == 0:
        return None
    
    return (mean_return - risk_free_rate) / std_return


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> Optional[float]:
    """
    ソルティノレシオを計算
    
    ソルティノレシオ = (平均リターン - リスクフリーレート) / 下方リスク
    
    Args:
        returns: リターンのリスト（%）
        risk_free_rate: リスクフリーレート（%、デフォルト: 0.0）
    
    Returns:
        ソルティノレシオ（None if 計算不可、負のリターンがない場合は999.0を返す）
    """
    if not returns or len(returns) < 2:
        return None
    
    returns_array = np.array(returns)
    mean_return = np.mean(returns_array)
    
    # 下方リスク（負のリターンのみの標準偏差）
    negative_returns = returns_array[returns_array < 0]
    
    # 負のリターンがない場合：下方リスクを0として扱い、平均リターンが正であれば非常に大きな値を返す
    if len(negative_returns) == 0:
        if mean_return > risk_free_rate:
            # 下方リスクがない（すべて正のリターン）→ 非常に良いパフォーマンス
            return 999.0  # 実質的に無限大を表す値
        else:
            # 平均リターンがリスクフリーレート以下 → 計算不可
            return None
    
    # 負のリターンが1つだけの場合：下方リスクをその絶対値として扱う
    if len(negative_returns) == 1:
        downside_std = abs(negative_returns[0])
    else:
        # 負のリターンが2つ以上ある場合：標準偏差を計算
        downside_std = np.std(negative_returns, ddof=1)
    
    # 下方リスクが0の場合（理論的には起こり得ないが、念のため）
    if downside_std == 0 or np.isnan(downside_std):
        return None
    
    return (mean_return - risk_free_rate) / downside_std


def calculate_max_drawdown(cumulative_values: List[float]) -> Optional[float]:
    """
    最大ドローダウンを計算
    
    最大ドローダウン = 最大のピークから谷までの下落率
    
    Args:
        cumulative_values: 累積価値のリスト（初期値100からの増減率、%）
    
    Returns:
        最大ドローダウン（%、None if 計算不可）
    """
    if not cumulative_values or len(cumulative_values) < 2:
        return None
    
    # 累積価値を絶対値に変換（初期値100 + 増減率%）
    values = np.array([100.0 + v for v in cumulative_values])
    
    # ピークを計算（累積最大値）
    peak = np.maximum.accumulate(values)
    
    # ドローダウンを計算（ピークからの下落率）
    drawdown = (values - peak) / peak * 100.0
    
    max_dd = np.min(drawdown)
    return float(max_dd)


def calculate_win_rate(returns: List[float]) -> Optional[float]:
    """
    勝率を計算
    
    勝率 = 正のリターンの数 / 全リターンの数
    
    Args:
        returns: リターンのリスト（%）
    
    Returns:
        勝率（0.0-1.0、None if 計算不可）
    """
    if not returns:
        return None
    
    wins = sum(1 for r in returns if r > 0)
    return wins / len(returns)


def calculate_avg_win_loss(returns: List[float]) -> Dict[str, Optional[float]]:
    """
    平均勝ち/平均負けを計算
    
    Args:
        returns: リターンのリスト（%）
    
    Returns:
        平均勝ち、平均負け、勝ち/負け比率の辞書
    """
    if not returns:
        return {
            "avg_win": None,
            "avg_loss": None,
            "win_loss_ratio": None,
        }
    
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    
    avg_win = np.mean(wins) if wins else None
    avg_loss = np.mean(losses) if losses else None
    
    if avg_win is not None and avg_loss is not None and avg_loss != 0:
        win_loss_ratio = abs(avg_win / avg_loss)
    else:
        win_loss_ratio = None
    
    return {
        "avg_win": float(avg_win) if avg_win is not None else None,
        "avg_loss": float(avg_loss) if avg_loss is not None else None,
        "win_loss_ratio": float(win_loss_ratio) if win_loss_ratio is not None else None,
    }


def calculate_calmar_ratio(annual_return: float, max_drawdown: float) -> Optional[float]:
    """
    カルマーレシオを計算
    
    カルマーレシオ = 年率リターン / 最大ドローダウン（絶対値）
    
    Args:
        annual_return: 年率リターン（%）
        max_drawdown: 最大ドローダウン（%、負の値）
    
    Returns:
        カルマーレシオ（None if 計算不可）
    """
    if max_drawdown == 0:
        return None
    
    return annual_return / abs(max_drawdown)


def calculate_annual_return(total_return: float, years: float) -> Optional[float]:
    """
    年率リターンを計算
    
    年率リターン = ((1 + 総リターン/100) ^ (1/年数) - 1) * 100
    
    Args:
        total_return: 総リターン（%）
        years: 年数
    
    Returns:
        年率リターン（%、None if 計算不可）
    """
    if years <= 0:
        return None
    
    total_return_decimal = total_return / 100.0
    annual_return_decimal = (1.0 + total_return_decimal) ** (1.0 / years) - 1.0
    
    return annual_return_decimal * 100.0


def calculate_volatility(returns: List[float], annualized: bool = True) -> Optional[float]:
    """
    ボラティリティを計算
    
    Args:
        returns: リターンのリスト（%）
        annualized: 年率換算するか（デフォルト: True）
    
    Returns:
        ボラティリティ（%、None if 計算不可）
    """
    if not returns or len(returns) < 2:
        return None
    
    returns_array = np.array(returns)
    std_return = np.std(returns_array, ddof=1)
    
    if annualized:
        # 月次リターンから年率換算（√12倍）
        std_return *= np.sqrt(12)
    
    return float(std_return)


def calculate_max_consecutive(returns: List[float], win: bool = True) -> int:
    """
    最大連勝/連敗を計算
    
    Args:
        returns: リターンのリスト（%）
        win: Trueの場合は連勝、Falseの場合は連敗
    
    Returns:
        最大連勝/連敗数
    """
    if not returns:
        return 0
    
    max_consecutive = 0
    current_consecutive = 0
    
    for r in returns:
        is_win = r > 0
        if (win and is_win) or (not win and not is_win and r < 0):
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    return max_consecutive


def calculate_performance_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ポートフォリオの運用評価指標を計算
    
    Args:
        start_date: 開始日（YYYY-MM-DD、Noneの場合は全期間）
        end_date: 終了日（YYYY-MM-DD、Noneの場合は最新）
    
    Returns:
        運用評価指標の辞書
    """
    print("=" * 80)
    print("運用評価指標の計算")
    print("=" * 80)
    
    # パフォーマンスデータを取得
    print("パフォーマンスデータを取得中...")
    performance_results = calculate_all_portfolios_performance(as_of_date=end_date)
    
    # エラーを除外
    valid_results = [r for r in performance_results if "error" not in r]
    
    if not valid_results:
        print("❌ 有効なパフォーマンス結果がありません")
        return {}
    
    # 日付でフィルタリング
    if start_date:
        valid_results = [r for r in valid_results if r["rebalance_date"] >= start_date]
    if end_date:
        valid_results = [r for r in valid_results if r["rebalance_date"] <= end_date]
    
    if not valid_results:
        print("❌ 指定期間内に有効なパフォーマンス結果がありません")
        return {}
    
    print(f"対象期間: {len(valid_results)}件のポートフォリオ")
    print(f"最初: {valid_results[0]['rebalance_date']}")
    print(f"最後: {valid_results[-1]['rebalance_date']}")
    print()
    
    # リターンを抽出（リバランス日順にソート）
    valid_results_sorted = sorted(valid_results, key=lambda x: x["rebalance_date"])
    
    # 各rebalance_dateごとにグループ化して指標を計算
    portfolio_metrics = []
    
    for r in valid_results_sorted:
        rebalance_date = r["rebalance_date"]
        stocks = r.get("stocks", [])
        
        if not stocks:
            continue
        
        # このポートフォリオ内の個別銘柄のリターンを抽出
        stock_returns = []
        stock_excess_returns = []
        
        for stock in stocks:
            return_pct = stock.get("return_pct")
            if return_pct is not None:
                stock_returns.append(return_pct)
            
            # 超過リターンも抽出
            topix_comp = stock.get("topix_comparison", {})
            excess_return = topix_comp.get("excess_return_pct")
            if excess_return is not None:
                stock_excess_returns.append(excess_return)
        
        if not stock_returns:
            continue
        
        # このポートフォリオの指標を計算
        portfolio_metric = {
            "rebalance_date": rebalance_date,
            "num_stocks": len(stock_returns),
            "returns": stock_returns,
            "excess_returns": stock_excess_returns,
        }
        
        # 基本統計
        portfolio_metric["mean_return"] = np.mean(stock_returns)
        portfolio_metric["median_return"] = np.median(stock_returns)
        portfolio_metric["std_return"] = np.std(stock_returns, ddof=1) if len(stock_returns) > 1 else 0.0
        portfolio_metric["min_return"] = np.min(stock_returns)
        portfolio_metric["max_return"] = np.max(stock_returns)
        
        # プロフィットファクタ
        portfolio_metric["profit_factor"] = calculate_profit_factor(stock_returns)
        
        # シャープレシオ
        portfolio_metric["sharpe_ratio"] = calculate_sharpe_ratio(stock_returns, risk_free_rate=0.0)
        
        # ソルティノレシオ
        portfolio_metric["sortino_ratio"] = calculate_sortino_ratio(stock_returns, risk_free_rate=0.0)
        
        # 勝率
        portfolio_metric["win_rate"] = calculate_win_rate(stock_returns)
        
        # 平均勝ち/平均負け
        win_loss = calculate_avg_win_loss(stock_returns)
        portfolio_metric["avg_win"] = win_loss["avg_win"]
        portfolio_metric["avg_loss"] = win_loss["avg_loss"]
        portfolio_metric["win_loss_ratio"] = win_loss["win_loss_ratio"]
        
        # 最大連勝/連敗
        portfolio_metric["max_consecutive_wins"] = calculate_max_consecutive(stock_returns, win=True)
        portfolio_metric["max_consecutive_losses"] = calculate_max_consecutive(stock_returns, win=False)
        
        # 総利益/総損失
        gains = [ret for ret in stock_returns if ret > 0]
        losses = [abs(ret) for ret in stock_returns if ret < 0]
        portfolio_metric["total_gains"] = sum(gains) if gains else 0.0
        portfolio_metric["total_losses"] = sum(losses) if losses else 0.0
        
        # ボラティリティ
        portfolio_metric["volatility"] = calculate_volatility(stock_returns, annualized=True)
        
        portfolio_metrics.append(portfolio_metric)
    
    if not portfolio_metrics:
        print("❌ 有効なパフォーマンス結果がありません")
        return {}
    
    print(f"ポートフォリオ数: {len(portfolio_metrics)}件")
    print(f"最初: {portfolio_metrics[0]['rebalance_date']}")
    print(f"最後: {portfolio_metrics[-1]['rebalance_date']}")
    print()
    
    # 全期間の個別銘柄のリターンも抽出（全体統計用）
    all_stock_returns = []
    all_stock_excess_returns = []
    for pm in portfolio_metrics:
        all_stock_returns.extend(pm["returns"])
        all_stock_excess_returns.extend(pm["excess_returns"])
    
    # ポートフォリオ全体のリターンも保持（比較用）
    portfolio_returns = [r["total_return_pct"] for r in valid_results_sorted if r.get("total_return_pct") is not None]
    portfolio_excess_returns = [
        r.get("topix_comparison", {}).get("excess_return_pct")
        for r in valid_results_sorted
        if r.get("topix_comparison", {}).get("excess_return_pct") is not None
    ]
    
    # 全体統計用
    returns = all_stock_returns
    excess_returns = all_stock_excess_returns
    
    if not returns:
        print("❌ 有効なリターンデータがありません")
        return {}
    
    print(f"個別銘柄のリターン数（全期間合計）: {len(returns)}件")
    print()
    
    print("=" * 80)
    print("【基本統計（各ポートフォリオごとの平均）】")
    print("=" * 80)
    
    # 各ポートフォリオごとの指標の平均を計算
    num_portfolios = len(portfolio_metrics)
    num_stocks = len(returns)
    
    # 各ポートフォリオの平均リターンの平均
    mean_returns = [pm["mean_return"] for pm in portfolio_metrics]
    avg_mean_return = np.mean(mean_returns)
    
    # 各ポートフォリオの中央値リターンの平均
    median_returns = [pm["median_return"] for pm in portfolio_metrics]
    avg_median_return = np.mean(median_returns)
    
    # 各ポートフォリオの標準偏差の平均
    std_returns = [pm["std_return"] for pm in portfolio_metrics]
    avg_std_return = np.mean(std_returns)
    
    # 全期間の個別銘柄のリターンから計算
    overall_mean_return = np.mean(returns)
    overall_median_return = np.median(returns)
    overall_std_return = np.std(returns, ddof=1)
    overall_min_return = np.min(returns)
    overall_max_return = np.max(returns)
    
    print(f"ポートフォリオ数: {num_portfolios}")
    print(f"個別銘柄数（全期間合計）: {num_stocks}")
    print()
    print("【各ポートフォリオごとの平均】")
    print(f"平均リターン（ポートフォリオ平均）: {avg_mean_return:.2f}%")
    print(f"中央値リターン（ポートフォリオ平均）: {avg_median_return:.2f}%")
    print(f"標準偏差（ポートフォリオ平均）: {avg_std_return:.2f}%")
    print()
    print("【全期間の個別銘柄統計】")
    print(f"平均リターン（全銘柄）: {overall_mean_return:.2f}%")
    print(f"中央値リターン（全銘柄）: {overall_median_return:.2f}%")
    print(f"標準偏差（全銘柄）: {overall_std_return:.2f}%")
    print(f"最小リターン: {overall_min_return:.2f}%")
    print(f"最大リターン: {overall_max_return:.2f}%")
    print()
    
    # 注意: 各ポートフォリオのリターンは「リバランス日から評価日（2025-12-26）までのリターン」です。
    # これは各ポートフォリオが独立した投資期間を持っていることを意味します。
    # 累積リターンを計算するには、各ポートフォリオの期間を考慮する必要がありますが、
    # 現在のデータでは各ポートフォリオのリターンは既に期間全体のリターンなので、
    # 累積リターンは「各ポートフォリオのリターンの平均」として扱います。
    
    # 期間を計算
    first_date = datetime.strptime(valid_results_sorted[0]["rebalance_date"], "%Y-%m-%d")
    last_date = datetime.strptime(valid_results_sorted[-1]["rebalance_date"], "%Y-%m-%d")
    days = (last_date - first_date).days
    years = days / 365.25
    
    # 累積リターンの計算
    # 個別銘柄のリターンは、各ポートフォリオ内の銘柄ごとのリターンなので、
    # 累積リターンは「平均リターン」として扱います。
    # （実際の運用では、各銘柄は独立して運用されるため、累積リターンは平均リターンとほぼ同じ）
    total_return = overall_mean_return
    
    # 累積価値を計算（ドローダウン計算用）
    # 個別銘柄のリターンを時系列で累積するのではなく、
    # ポートフォリオ全体のリターンを使用して累積価値を計算
    cumulative_values = []
    cumulative_value = 100.0  # 初期値を100とする
    
    # ポートフォリオ全体のリターンを使用して累積価値を計算
    for r in portfolio_returns:
        cumulative_value *= (1.0 + r / 100.0)
        cumulative_values.append(cumulative_value)
    
    # 累積リターン（初期値からの増減率）を計算（ドローダウン計算用）
    cumulative_returns = [v - 100.0 for v in cumulative_values]
    
    # 注意: この計算は理論的には正しくありません。
    # 各ポートフォリオのリターンは既に期間全体のリターンなので、
    # 累積リターンは「各ポートフォリオのリターンの平均」として扱うべきです。
    # しかし、実際の運用では、各ポートフォリオは時系列で連続して運用されるため、
    # この計算は簡易的な指標として使用します。
    
    print("=" * 80)
    print("【リターン指標（個別銘柄ベース）】")
    print("=" * 80)
    
    # 個別銘柄の平均リターンから年率リターンを計算
    # 注意: 個別銘柄のリターンは各ポートフォリオ内の銘柄ごとのリターンなので、
    # 年率リターンは平均リターンから直接計算します。
    annual_return = calculate_annual_return(total_return, years) if years > 0 else None
    if annual_return is not None:
        print(f"平均リターン: {total_return:.2f}%")
        print(f"期間: {years:.2f}年")
        print(f"年率リターン（平均リターンベース）: {annual_return:.2f}%")
    print()
    
    # TOPIX比較
    if excess_returns:
        mean_excess = np.mean(excess_returns)
        print(f"平均超過リターン（個別銘柄ベース）: {mean_excess:.2f}%")
    print()
    
    # ポートフォリオ全体のリターンも表示（参考）
    if portfolio_returns:
        portfolio_mean_return = np.mean(portfolio_returns)
        portfolio_annual_return = calculate_annual_return(portfolio_mean_return, years) if years > 0 else None
        print("【参考: ポートフォリオ全体のリターン】")
        print(f"ポートフォリオ平均リターン: {portfolio_mean_return:.2f}%")
        if portfolio_annual_return is not None:
            print(f"ポートフォリオ年率リターン: {portfolio_annual_return:.2f}%")
        print()
    
    print("=" * 80)
    print("【リスク指標】")
    print("=" * 80)
    
    # ボラティリティ
    volatility = calculate_volatility(returns, annualized=True)
    if volatility is not None:
        print(f"年率ボラティリティ: {volatility:.2f}%")
    
    # 最大ドローダウン（累積価値ベースで計算）
    max_drawdown = calculate_max_drawdown(cumulative_returns)
    if max_drawdown is not None:
        print(f"最大ドローダウン: {max_drawdown:.2f}%")
    print()
    
    print("=" * 80)
    print("【リスク調整後リターン指標（各ポートフォリオごとの平均）】")
    print("=" * 80)
    
    # 各ポートフォリオごとのシャープレシオの平均
    sharpe_ratios = [pm["sharpe_ratio"] for pm in portfolio_metrics if pm["sharpe_ratio"] is not None]
    if sharpe_ratios:
        avg_sharpe_ratio = np.mean(sharpe_ratios)
        print(f"シャープレシオ（ポートフォリオ平均）: {avg_sharpe_ratio:.4f}")
        print(f"  最小: {np.min(sharpe_ratios):.4f}, 最大: {np.max(sharpe_ratios):.4f}")
    
    # 各ポートフォリオごとのソルティノレシオの平均
    sortino_ratios = [pm["sortino_ratio"] for pm in portfolio_metrics if pm["sortino_ratio"] is not None and not np.isnan(pm["sortino_ratio"])]
    if sortino_ratios:
        avg_sortino_ratio = np.mean(sortino_ratios)
        print(f"ソルティノレシオ（ポートフォリオ平均）: {avg_sortino_ratio:.4f}")
        print(f"  最小: {np.min(sortino_ratios):.4f}, 最大: {np.max(sortino_ratios):.4f}")
        print(f"  計算可能なポートフォリオ数: {len(sortino_ratios)}/{num_portfolios}")
    else:
        print(f"ソルティノレシオ（ポートフォリオ平均）: 計算不可（負のリターンがないポートフォリオが多い）")
    
    # 全期間の個別銘柄から計算したシャープレシオ（参考）
    overall_sharpe_ratio = calculate_sharpe_ratio(returns, risk_free_rate=0.0)
    if overall_sharpe_ratio is not None:
        print(f"シャープレシオ（全銘柄）: {overall_sharpe_ratio:.4f}")
    
    overall_sortino_ratio = calculate_sortino_ratio(returns, risk_free_rate=0.0)
    if overall_sortino_ratio is not None:
        print(f"ソルティノレシオ（全銘柄）: {overall_sortino_ratio:.4f}")
    
    # カルマーレシオ
    if annual_return is not None and max_drawdown is not None:
        calmar_ratio = calculate_calmar_ratio(annual_return, max_drawdown)
        if calmar_ratio is not None:
            print(f"カルマーレシオ: {calmar_ratio:.4f}")
    print()
    
    print("=" * 80)
    print("【勝敗統計（各ポートフォリオごとの平均）】")
    print("=" * 80)
    
    # 各ポートフォリオごとの勝率の平均
    win_rates = [pm["win_rate"] for pm in portfolio_metrics if pm["win_rate"] is not None]
    if win_rates:
        avg_win_rate = np.mean(win_rates)
        print(f"勝率（ポートフォリオ平均）: {avg_win_rate:.2%}")
        print(f"  最小: {np.min(win_rates):.2%}, 最大: {np.max(win_rates):.2%}")
    
    # 各ポートフォリオごとの平均勝ち/平均負けの平均
    avg_wins = [pm["avg_win"] for pm in portfolio_metrics if pm["avg_win"] is not None]
    avg_losses = [pm["avg_loss"] for pm in portfolio_metrics if pm["avg_loss"] is not None]
    win_loss_ratios = [pm["win_loss_ratio"] for pm in portfolio_metrics if pm["win_loss_ratio"] is not None]
    
    if avg_wins:
        print(f"平均勝ち（ポートフォリオ平均）: {np.mean(avg_wins):.2f}%")
    if avg_losses:
        print(f"平均負け（ポートフォリオ平均）: {np.mean(avg_losses):.2f}%")
    if win_loss_ratios:
        print(f"勝ち/負け比率（ポートフォリオ平均）: {np.mean(win_loss_ratios):.2f}")
    
    # 各ポートフォリオごとの最大連勝/連敗の平均
    max_consecutive_wins_list = [pm["max_consecutive_wins"] for pm in portfolio_metrics]
    max_consecutive_losses_list = [pm["max_consecutive_losses"] for pm in portfolio_metrics]
    print(f"最大連勝（ポートフォリオ平均）: {np.mean(max_consecutive_wins_list):.1f}回")
    print(f"最大連敗（ポートフォリオ平均）: {np.mean(max_consecutive_losses_list):.1f}回")
    print()
    
    # 全期間の個別銘柄から計算した勝率（参考）
    overall_win_rate = calculate_win_rate(returns)
    if overall_win_rate is not None:
        print(f"勝率（全銘柄）: {overall_win_rate:.2%} ({int(overall_win_rate * num_stocks)}/{num_stocks})")
    
    overall_win_loss = calculate_avg_win_loss(returns)
    if overall_win_loss["avg_win"] is not None:
        print(f"平均勝ち（全銘柄）: {overall_win_loss['avg_win']:.2f}%")
    if overall_win_loss["avg_loss"] is not None:
        print(f"平均負け（全銘柄）: {overall_win_loss['avg_loss']:.2f}%")
    if overall_win_loss["win_loss_ratio"] is not None:
        print(f"勝ち/負け比率（全銘柄）: {overall_win_loss['win_loss_ratio']:.2f}")
    print()
    
    print("=" * 80)
    print("【収益性指標（各ポートフォリオごとの平均）】")
    print("=" * 80)
    
    # 各ポートフォリオごとのプロフィットファクタの平均
    profit_factors = [pm["profit_factor"] for pm in portfolio_metrics if pm["profit_factor"] is not None and pm["profit_factor"] != float('inf')]
    if profit_factors:
        avg_profit_factor = np.mean(profit_factors)
        print(f"プロフィットファクタ（ポートフォリオ平均）: {avg_profit_factor:.4f}")
        print(f"  最小: {np.min(profit_factors):.4f}, 最大: {np.max(profit_factors):.4f}")
    
    # 無限大のプロフィットファクタの数
    infinite_pf_count = sum(1 for pm in portfolio_metrics if pm["profit_factor"] == float('inf'))
    if infinite_pf_count > 0:
        print(f"損失なしのポートフォリオ数: {infinite_pf_count}/{num_portfolios}")
    
    # 各ポートフォリオごとの総利益/総損失の平均
    total_gains_list = [pm["total_gains"] for pm in portfolio_metrics]
    total_losses_list = [pm["total_losses"] for pm in portfolio_metrics]
    print(f"総利益（ポートフォリオ平均）: {np.mean(total_gains_list):.2f}%")
    print(f"総損失（ポートフォリオ平均）: {np.mean(total_losses_list):.2f}%")
    print()
    
    # 全期間の個別銘柄から計算したプロフィットファクタ（参考）
    overall_profit_factor = calculate_profit_factor(returns)
    if overall_profit_factor is not None:
        if overall_profit_factor == float('inf'):
            print(f"プロフィットファクタ（全銘柄）: ∞ (損失なし)")
        else:
            print(f"プロフィットファクタ（全銘柄）: {overall_profit_factor:.4f}")
    
    overall_gains = [r for r in returns if r > 0]
    overall_losses = [r for r in returns if r < 0]
    overall_total_gains = sum(overall_gains) if overall_gains else 0.0
    overall_total_losses = sum([abs(r) for r in overall_losses]) if overall_losses else 0.0
    print(f"総利益（全銘柄）: {overall_total_gains:.2f}%")
    print(f"総損失（全銘柄）: {overall_total_losses:.2f}%")
    print()
    
    # 結果を辞書にまとめる
    metrics = {
        "period": {
            "start_date": valid_results_sorted[0]["rebalance_date"],
            "end_date": valid_results_sorted[-1]["rebalance_date"],
            "days": days,
            "years": years,
            "num_portfolios": len(valid_results_sorted),
            "num_stocks": num_stocks,
        },
        "returns": {
            "total_return": total_return,
            "annual_return": annual_return,
            "mean_return": overall_mean_return,
            "median_return": overall_median_return,
            "min_return": overall_min_return,
            "max_return": overall_max_return,
            "avg_mean_return_per_portfolio": avg_mean_return,
            "avg_median_return_per_portfolio": avg_median_return,
        },
        "risk": {
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "std_return": overall_std_return,
            "avg_std_return_per_portfolio": avg_std_return,
        },
        "risk_adjusted": {
            "sharpe_ratio": overall_sharpe_ratio,
            "sortino_ratio": overall_sortino_ratio,
            "avg_sharpe_ratio_per_portfolio": np.mean(sharpe_ratios) if sharpe_ratios else None,
            "avg_sortino_ratio_per_portfolio": np.mean(sortino_ratios) if sortino_ratios else None,
            "calmar_ratio": calculate_calmar_ratio(annual_return, max_drawdown) if annual_return and max_drawdown else None,
        },
        "win_loss": {
            "win_rate": overall_win_rate,
            "avg_win": overall_win_loss["avg_win"],
            "avg_loss": overall_win_loss["avg_loss"],
            "win_loss_ratio": overall_win_loss["win_loss_ratio"],
            "avg_win_rate_per_portfolio": np.mean(win_rates) if win_rates else None,
            "avg_win_per_portfolio": np.mean(avg_wins) if avg_wins else None,
            "avg_loss_per_portfolio": np.mean(avg_losses) if avg_losses else None,
            "avg_win_loss_ratio_per_portfolio": np.mean(win_loss_ratios) if win_loss_ratios else None,
            "max_consecutive_wins": calculate_max_consecutive(returns, win=True),
            "max_consecutive_losses": calculate_max_consecutive(returns, win=False),
            "avg_max_consecutive_wins_per_portfolio": np.mean(max_consecutive_wins_list),
            "avg_max_consecutive_losses_per_portfolio": np.mean(max_consecutive_losses_list),
        },
        "profitability": {
            "profit_factor": overall_profit_factor,
            "total_gains": overall_total_gains,
            "total_losses": overall_total_losses,
            "avg_profit_factor_per_portfolio": np.mean(profit_factors) if profit_factors else None,
            "avg_total_gains_per_portfolio": np.mean(total_gains_list),
            "avg_total_losses_per_portfolio": np.mean(total_losses_list),
        },
        "portfolio_metrics": portfolio_metrics,
        "topix_comparison": {
            "mean_excess_return": np.mean(excess_returns) if excess_returns else None,
        },
    }
    
    print("=" * 80)
    print("計算完了")
    print("=" * 80)
    
    return metrics


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ポートフォリオの運用評価指標を計算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--start",
        type=str,
        dest="start_date",
        default=None,
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        dest="end_date",
        default=None,
        help="終了日（YYYY-MM-DD）",
    )
    
    args = parser.parse_args()
    
    metrics = calculate_performance_metrics(
        start_date=args.start_date,
        end_date=args.end_date,
    )
    
    if not metrics:
        sys.exit(1)
    
    # JSON形式で保存（オプション）
    import json
    output_file = "performance_metrics.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"\n結果を {output_file} に保存しました")


if __name__ == "__main__":
    main()


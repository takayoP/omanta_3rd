"""候補群のHoldout検証スクリプト

200 trialで選定された候補群を、Holdout期間（2023-2024）で評価します。

Usage:
    python evaluate_candidates_holdout.py --candidates candidates_studyB_20251231_174014.json --holdout-start 2023-01-01 --holdout-end 2024-12-31
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import replace, fields
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

import pandas as pd

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.omanta_3rd.jobs.monthly_run import StrategyParams, build_features
from src.omanta_3rd.jobs.optimize import (
    EntryScoreParams,
    _calculate_entry_score_with_params,
    _select_portfolio_with_params,
    _entry_score_with_params,
)
from src.omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates
from src.omanta_3rd.backtest.timeseries import calculate_timeseries_returns_from_portfolios
from src.omanta_3rd.backtest.eval_common import calculate_metrics_from_timeseries_data
from src.omanta_3rd.backtest.feature_cache import FeatureCache
from src.omanta_3rd.backtest.metrics import (
    calculate_sharpe_ratio,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_volatility_timeseries,
)
from src.omanta_3rd.infra.db import connect_db
import sqlite3
import numpy as np
from datetime import datetime


def _generate_single_portfolio(
    rebalance_date: str,
    strategy_params_dict: dict,
    entry_params_dict: dict,
    features_dict: Dict[str, pd.DataFrame] = None,
    prices_dict: Dict[str, Dict[str, List[float]]] = None,
) -> tuple:
    """
    単一のリバランス日でポートフォリオを生成（並列化用）
    
    Args:
        rebalance_date: リバランス日
        strategy_params_dict: StrategyParamsを辞書化したもの
        entry_params_dict: EntryScoreParamsを辞書化したもの
        features_dict: 特徴量辞書（キャッシュ、Noneの場合はDBから取得）
        prices_dict: 価格データ辞書（キャッシュ、Noneの場合はDBから取得）
    
    Returns:
        (rebalance_date, portfolio_df) のタプル（エラー時は (rebalance_date, None)）
    """
    try:
        # 辞書からdataclassに復元
        strategy_params = StrategyParams(**strategy_params_dict)
        entry_params = EntryScoreParams(**entry_params_dict)
        
        # 特徴量を取得（キャッシュ優先）
        if features_dict is not None and rebalance_date in features_dict:
            feat = features_dict[rebalance_date].copy()
        else:
            # DBから取得
            try:
                with connect_db(read_only=True) as conn:
                    feat = build_features(conn, rebalance_date)
            except sqlite3.OperationalError as e:
                if "readonly" in str(e).lower() or "read-only" in str(e).lower():
                    with connect_db(read_only=False) as conn:
                        feat = build_features(conn, rebalance_date)
                else:
                    raise
        
        if feat is None or feat.empty:
            return (rebalance_date, None)
        
        # entry_scoreを計算
        if prices_dict is not None and rebalance_date in prices_dict:
            # キャッシュから価格データを取得
            close_map = {
                code: pd.Series(prices)
                for code, prices in prices_dict[rebalance_date].items()
            }
            feat["entry_score"] = feat["code"].apply(
                lambda c: _entry_score_with_params(close_map.get(c), entry_params)
                if c in close_map
                else pd.NA
            )
        else:
            # DBから価格データを取得
            price_date = feat["as_of_date"].iloc[0]
            with connect_db(read_only=True) as conn:
                prices_win = pd.read_sql_query(
                    """
                    SELECT code, date, adj_close
                    FROM prices_daily
                    WHERE date <= ?
                    ORDER BY code, date
                    """,
                    conn,
                    params=(price_date,),
                )
            feat = _calculate_entry_score_with_params(feat, prices_win, entry_params)
        
        # ポートフォリオを選択
        portfolio = _select_portfolio_with_params(
            feat, strategy_params, entry_params
        )
        
        if portfolio is None or portfolio.empty:
            return (rebalance_date, None)
        
        return (rebalance_date, portfolio)
    except Exception as e:
        # エラー情報を返す（デバッグ用、ただし並列実行時の出力は避ける）
        # エラーは呼び出し元で処理される
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        # tracebackは返さない（並列実行時のオーバーヘッドを避ける）
        return (rebalance_date, None)


def evaluate_candidate_holdout(
    candidate: Dict[str, Any],
    holdout_start_date: str,
    holdout_end_date: str,
    cost_bps: float = 0.0,
    features_dict: Dict[str, pd.DataFrame] = None,
    prices_dict: Dict[str, Dict[str, List[float]]] = None,
    n_jobs: int = 1,
) -> Dict[str, Any]:
    """
    候補のパラメータでHoldout期間を評価
    
    Args:
        candidate: 候補の辞書（trial_number, value, paramsを含む）
        holdout_start_date: Holdout期間の開始日
        holdout_end_date: Holdout期間の終了日
        cost_bps: 取引コスト（bps）
        features_dict: 特徴量辞書（キャッシュ、Noneの場合はDBから取得）
        prices_dict: 価格データ辞書（キャッシュ、Noneの場合はDBから取得）
        n_jobs: 並列実行数（-1でCPU数、1で逐次実行）
    
    Returns:
        評価結果の辞書
    """
    params = candidate["params"]
    
    # リバランス日を取得
    holdout_dates = get_monthly_rebalance_dates(holdout_start_date, holdout_end_date)
    
    if not holdout_dates:
        return {
            "trial_number": candidate["trial_number"],
            "error": "Holdout期間のリバランス日が見つかりませんでした",
        }
    
    # StrategyParamsを構築
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
        w_quality=params.get("w_quality", 0.0),
        w_value=params.get("w_value", 0.0),
        w_growth=params.get("w_growth", 0.0),
        w_record_high=params.get("w_record_high", 0.0),
        w_size=params.get("w_size", 0.0),
        w_forward_per=params.get("w_forward_per", 0.5),
        w_pbr=1.0 - params.get("w_forward_per", 0.5),
        roe_min=params.get("roe_min", 0.08),
        liquidity_quantile_cut=params.get("liquidity_quantile_cut", 0.25),
    )
    
    # EntryScoreParamsを構築
    bb_weight = params.get("bb_weight", 0.6)
    entry_params = EntryScoreParams(
        rsi_base=params.get("rsi_base", 50.0),
        rsi_max=params.get("rsi_max", 75.0),
        bb_z_base=params.get("bb_z_base", -1.0),
        bb_z_max=params.get("bb_z_max", 2.0),
        bb_weight=bb_weight,
        rsi_weight=1.0 - bb_weight,
    )
    
    # StrategyParamsとEntryScoreParamsを辞書に変換（pickle可能にするため）
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    # ポートフォリオを生成（並列化）
    portfolios = {}  # {rebalance_date: portfolio_df}
    
    # 並列実行数の決定
    if n_jobs == -1:
        n_jobs = min(len(holdout_dates), mp.cpu_count())
    elif n_jobs <= 0:
        n_jobs = 1
    
    # 並列実行: ポートフォリオ生成
    if n_jobs > 1 and len(holdout_dates) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {
                executor.submit(
                    _generate_single_portfolio,
                    rebalance_date,
                    strategy_params_dict,
                    entry_params_dict,
                    features_dict,
                    prices_dict,
                ): rebalance_date
                for rebalance_date in holdout_dates
            }
            
            for future in as_completed(futures):
                rebalance_date = futures[future]
                try:
                    result_date, portfolio = future.result()
                    if portfolio is not None and not portfolio.empty:
                        portfolios[result_date] = portfolio
                    elif portfolio is None:
                        # エラーが発生した場合（_generate_single_portfolioがNoneを返した場合）
                        print(f"  警告: {rebalance_date}のポートフォリオ生成に失敗しました（データが存在しない可能性があります）")
                except Exception as e:
                    print(f"  警告: {rebalance_date}の処理で例外が発生: {type(e).__name__}: {e}")
    else:
        # 逐次実行
        for rebalance_date in holdout_dates:
            _, portfolio = _generate_single_portfolio(
                rebalance_date,
                strategy_params_dict,
                entry_params_dict,
                features_dict,
                prices_dict,
            )
            if portfolio is not None and not portfolio.empty:
                portfolios[rebalance_date] = portfolio
    
    if not portfolios:
        return {
            "trial_number": candidate["trial_number"],
            "error": "ポートフォリオが生成されませんでした",
        }
    
    # 時系列リターンを計算（ポートフォリオを直接渡す）
    timeseries_data = calculate_timeseries_returns_from_portfolios(
        portfolios=portfolios,
        start_date=holdout_start_date,
        end_date=holdout_end_date,
        rebalance_dates=holdout_dates,
        cost_bps=cost_bps,
        buy_cost_bps=cost_bps,
        sell_cost_bps=cost_bps,
    )
    
    # メトリクスを計算
    metrics = calculate_metrics_from_timeseries_data(timeseries_data)
    
    # 詳細メトリクスを計算
    detailed_metrics = _calculate_detailed_metrics(
        timeseries_data,
        holdout_start_date,
        holdout_end_date,
        cost_bps,
    )
    
    # メトリクスに詳細情報を統合
    metrics.update(detailed_metrics)
    
    # ポートフォリオ情報と保有銘柄詳細を取得
    portfolio_holdings = _extract_portfolio_holdings(timeseries_data, portfolios)
    
    return {
        "trial_number": candidate["trial_number"],
        "train_sharpe": candidate.get("value", None),
        "holdout_metrics": metrics,
        "params": params,
        "portfolio_holdings": portfolio_holdings,  # 追加: ポートフォリオ情報と保有銘柄詳細
    }


def _extract_portfolio_holdings(
    timeseries_data: Dict[str, Any],
    portfolios: Dict[str, pd.DataFrame],
    initial_investment: float = 1000000.0,  # 初期投資額（円、デフォルト100万円）
) -> Dict[str, Any]:
    """
    ポートフォリオ情報と保有銘柄詳細を抽出
    
    Args:
        timeseries_data: calculate_timeseries_returns_from_portfolios()の戻り値
        portfolios: {rebalance_date: portfolio_df} の辞書
        initial_investment: 初期投資額（円、保有株数計算に使用）
    
    Returns:
        ポートフォリオ情報と保有銘柄詳細の辞書
    """
    portfolio_details = timeseries_data.get("portfolio_details", [])
    dates = timeseries_data.get("dates", [])
    
    holdings_by_period = []
    
    # 各リバランス期間の保有銘柄情報を構築
    for i, rebalance_date in enumerate(dates):
        period_detail = next(
            (d for d in portfolio_details if d.get("rebalance_date") == rebalance_date),
            None
        )
        
        if period_detail is None:
            continue
        
        # 各銘柄の詳細情報を取得（timeseries.pyから取得）
        stock_details = period_detail.get("stock_details", [])
        
        # 基本ポートフォリオ情報
        holdings_info = {
            "rebalance_date": rebalance_date,
            "purchase_date": period_detail.get("purchase_date"),
            "sell_date": period_detail.get("sell_date"),
            "stocks": []
        }
        
        # 各銘柄の詳細情報を構築
        for stock_detail in stock_details:
            code = stock_detail.get("code")
            weight = stock_detail.get("weight", 0.0)
            purchase_price = stock_detail.get("purchase_price")
            sell_price = stock_detail.get("sell_price")
            return_pct = stock_detail.get("return_pct", 0.0)
            
            # 保有株数を計算（初期投資額 × ウェイト / 購入価格）
            shares = None
            investment_amount = None
            profit_loss = None
            profit_loss_pct = return_pct
            
            if purchase_price is not None and purchase_price > 0:
                investment_amount = initial_investment * weight
                shares = investment_amount / purchase_price
                
                # 損益を計算（売却価格 - 購入価格）× 株数
                if sell_price is not None:
                    profit_loss = (sell_price - purchase_price) * shares
            
            stock_info = {
                "code": code,
                "weight": weight,
                "purchase_date": period_detail.get("purchase_date"),
                "sell_date": period_detail.get("sell_date"),
                "purchase_price": purchase_price,
                "sell_price": sell_price,
                "shares": shares,
                "investment_amount": investment_amount,  # 投資額（円）
                "return_pct": return_pct,  # 損益率（%）
                "profit_loss": profit_loss,  # 損益（円）
                "split_multiplier": stock_detail.get("split_multiplier", 1.0),
            }
            
            holdings_info["stocks"].append(stock_info)
        
        holdings_by_period.append(holdings_info)
    
    return {
        "holdings_by_period": holdings_by_period,
        "initial_investment": initial_investment,
    }


def _calculate_detailed_metrics(
    timeseries_data: Dict[str, Any],
    holdout_start_date: str,
    holdout_end_date: str,
    cost_bps: float,
) -> Dict[str, Any]:
    """
    詳細メトリクスを計算（年別分解、時系列、MaxDD、ターンオーバー等）
    
    Args:
        timeseries_data: calculate_timeseries_returns_from_portfolios()の戻り値
        holdout_start_date: Holdout期間の開始日
        holdout_end_date: Holdout期間の終了日
        cost_bps: 取引コスト（bps）
    
    Returns:
        詳細メトリクスの辞書
    """
    monthly_returns = timeseries_data.get("monthly_returns", [])
    monthly_excess_returns = timeseries_data.get("monthly_excess_returns", [])
    equity_curve = timeseries_data.get("equity_curve", [])
    dates = timeseries_data.get("dates", [])
    portfolio_details = timeseries_data.get("portfolio_details", [])
    missing_periods_count = timeseries_data.get("missing_periods_count", 0)
    missing_periods_info = timeseries_data.get("missing_periods_info", [])
    
    if not monthly_excess_returns or not dates:
        return {}
    
    # 日付とリターンをDataFrameに変換（年でフィルタリングするため）
    # datesが文字列リストの場合とdatetimeリストの場合に対応
    if dates and isinstance(dates[0], str):
        dates_parsed = pd.to_datetime(dates)
    else:
        dates_parsed = dates if dates else []
    
    df = pd.DataFrame({
        "date": dates_parsed,
        "excess_return": monthly_excess_returns,
        "return": monthly_returns,
    })
    if len(df) > 0:
        df["year"] = pd.to_datetime(df["date"]).dt.year
    
    result = {}
    
    # 1. 年別（2023/2024）に分解した指標
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
            # 複利で累積リターンを計算
            cumulative_return = np.prod([1.0 + r for r in year_excess]) - 1.0
            periods = len(year_excess)
            # 年率換算（月次データから年率に変換）
            cagr_excess = ((1.0 + cumulative_return) ** (12.0 / periods) - 1.0) * 100.0 if periods > 0 else None
        else:
            cagr_excess = None
        
        result[f"sharpe_excess_{year}"] = sharpe_excess
        result[f"cagr_excess_{year}"] = cagr_excess
    
    # 2. Holdout期間の超過リターン時系列（月次）
    result["monthly_excess_returns"] = monthly_excess_returns
    result["monthly_dates"] = dates
    
    # 3. Holdoutの年超過ボラと平均超過リターン
    mean_excess_monthly = np.mean(monthly_excess_returns) if monthly_excess_returns else 0.0
    vol_excess_monthly = np.std(monthly_excess_returns, ddof=1) if len(monthly_excess_returns) > 1 else 0.0
    
    # 年率換算
    mean_excess_annual = mean_excess_monthly * 12.0 * 100.0  # %換算
    vol_excess_annual = vol_excess_monthly * np.sqrt(12.0) * 100.0  # %換算
    
    result["mean_excess_return_monthly"] = mean_excess_monthly * 100.0  # %換算
    result["mean_excess_return_annual"] = mean_excess_annual
    result["vol_excess_monthly"] = vol_excess_monthly * 100.0  # %換算
    result["vol_excess_annual"] = vol_excess_annual
    
    # 4. MaxDD（ポートフォリオ）とTOPIX比
    max_dd = calculate_max_drawdown(equity_curve) if equity_curve else 0.0
    
    # TOPIXのエクイティカーブを計算（portfolio_detailsから）
    topix_equity_curve = [1.0]
    topix_returns = []
    for detail in portfolio_details:
        if "topix_return" in detail:
            topix_return = detail["topix_return"]
            topix_returns.append(topix_return)
            topix_equity_curve.append(topix_equity_curve[-1] * (1.0 + topix_return))
    
    max_dd_topix = None
    max_dd_diff = None
    if len(topix_equity_curve) > 1:
        max_dd_topix = calculate_max_drawdown(topix_equity_curve)
        max_dd_diff = (max_dd - max_dd_topix) * 100.0  # %換算
    
    result["max_drawdown"] = max_dd * 100.0  # %換算
    result["max_drawdown_topix"] = max_dd_topix * 100.0 if max_dd_topix is not None else None
    result["max_drawdown_diff"] = max_dd_diff
    
    # 5. 売買回転（ターンオーバー）
    # portfolio_detailsからターンオーバー情報を取得
    turnovers = []
    for detail in portfolio_details:
        # executed_turnover が最も正確な指標
        if "executed_turnover" in detail:
            turnovers.append(detail["executed_turnover"])
        elif "turnover" in detail:
            turnovers.append(detail["turnover"])
    
    # 年間ターンオーバー（月次ターンオーバーの平均を年率換算）
    avg_turnover_monthly = np.mean(turnovers) if turnovers else None
    avg_turnover_annual = avg_turnover_monthly * 12.0 if avg_turnover_monthly is not None else None
    
    result["turnover_monthly"] = avg_turnover_monthly
    result["turnover_annual"] = avg_turnover_annual
    
    # コストを考慮したSharpe_excess（推奨方法: 月次系列から控除して再計算）
    if cost_bps > 0:
        # 月次コストを計算（portfolio_detailsから取得）
        monthly_costs = []
        for detail in portfolio_details:
            if "cost_frac" in detail:
                # cost_fracは既に月次コスト（小数）として計算済み
                monthly_costs.append(detail["cost_frac"])
            elif avg_turnover_monthly is not None:
                # フォールバック: 平均ターンオーバーから推定
                monthly_cost_frac = (avg_turnover_monthly * cost_bps / 10000.0)
                monthly_costs.append(monthly_cost_frac)
        
        if monthly_costs:
            # 月次超過リターンから月次コストを控除
            monthly_excess_after_cost = [
                r - c for r, c in zip(monthly_excess_returns, monthly_costs)
            ]
            
            # コスト控除後の統計を再計算
            mean_excess_after_cost_monthly = np.mean(monthly_excess_after_cost) if monthly_excess_after_cost else 0.0
            vol_excess_after_cost_monthly = np.std(monthly_excess_after_cost, ddof=1) if len(monthly_excess_after_cost) > 1 else 0.0
            
            # コスト控除後のSharpe Ratioを計算
            if vol_excess_after_cost_monthly > 0:
                sharpe_after_cost = (
                    (mean_excess_after_cost_monthly * 12.0) / (vol_excess_after_cost_monthly * np.sqrt(12.0))
                )
            else:
                sharpe_after_cost = None
            
            result["sharpe_excess_after_cost"] = sharpe_after_cost
            result["mean_excess_return_after_cost_monthly"] = mean_excess_after_cost_monthly * 100.0  # %換算
            result["mean_excess_return_after_cost_annual"] = mean_excess_after_cost_monthly * 12.0 * 100.0  # %換算
            result["vol_excess_after_cost_monthly"] = vol_excess_after_cost_monthly * 100.0  # %換算
            result["vol_excess_after_cost_annual"] = vol_excess_after_cost_monthly * np.sqrt(12.0) * 100.0  # %換算
            
            # 年間コスト（参考値）
            if avg_turnover_annual is not None:
                annual_cost = avg_turnover_annual * cost_bps / 10000.0
                result["annual_cost_bps"] = annual_cost * 10000.0  # bps換算
                result["annual_cost_pct"] = annual_cost * 100.0  # %換算
    
    # 6. 価格欠損の扱い情報
    total_missing_count = sum(
        detail.get("num_missing_stocks", 0) for detail in portfolio_details
    )
    result["num_missing_stocks_total"] = total_missing_count
    result["num_periods"] = len(portfolio_details)
    result["missing_stocks_per_period"] = (
        total_missing_count / len(portfolio_details) if portfolio_details else 0.0
    )
    
    # 欠損処理の仕様（説明用）
    result["missing_handling"] = "欠損銘柄は除外（ウェイト再正規化）"
    
    # スキップされた期間の情報（バイアス検出のため）
    result["missing_periods_count"] = missing_periods_count
    result["missing_periods_info"] = missing_periods_info
    if missing_periods_count > 0:
        # スキップされた期間がある場合、注意フラグを追加
        result["has_missing_periods"] = True
        result["missing_periods_warning"] = (
            f"注意: {missing_periods_count}期間がスキップされました。"
            "スキップされた期間が多い場合、Sharpe比やCAGRが上振れする可能性があります。"
        )
    else:
        result["has_missing_periods"] = False
    
    return result


def _evaluate_single_candidate_wrapper(args_tuple):
    """
    単一候補の評価を実行（並列化用のラッパー）
    
    Args:
        args_tuple: (candidate, holdout_start_date, holdout_end_date, cost_bps, features_dict, prices_dict, n_jobs) のタプル
    
    Returns:
        評価結果の辞書
    """
    candidate, holdout_start_date, holdout_end_date, cost_bps, features_dict, prices_dict, n_jobs = args_tuple
    return evaluate_candidate_holdout(
        candidate,
        holdout_start_date,
        holdout_end_date,
        cost_bps=cost_bps,
        features_dict=features_dict,
        prices_dict=prices_dict,
        n_jobs=n_jobs,
    )


def main():
    parser = argparse.ArgumentParser(description="候補群のHoldout検証")
    parser.add_argument("--candidates", type=str, required=True, help="候補群のJSONファイルパス")
    parser.add_argument("--holdout-start", type=str, default="2023-01-01", help="Holdout期間の開始日（YYYY-MM-DD）")
    parser.add_argument("--holdout-end", type=str, default="2024-12-31", help="Holdout期間の終了日（YYYY-MM-DD）")
    parser.add_argument("--cost-bps", type=float, default=0.0, help="取引コスト（bps）")
    parser.add_argument("--output", type=str, help="結果を保存するJSONファイルパス")
    parser.add_argument("--top-n", type=int, help="上位N件のみ評価（デフォルト: 全件）")
    parser.add_argument("--n-jobs", type=int, default=-1, help="並列実行数（-1でCPU数、1で逐次実行、デフォルト: -1）")
    parser.add_argument("--use-cache", action="store_true", help="FeatureCacheを使用して特徴量と価格データを事前計算（推奨）")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="キャッシュディレクトリ（デフォルト: cache/features）")
    
    args = parser.parse_args()
    
    # 候補群を読み込み
    with open(args.candidates, "r", encoding="utf-8") as f:
        candidates_data = json.load(f)
    
    candidates = candidates_data.get("candidates", [])
    
    # 出力ファイル名が指定されていない場合、候補ファイル名から自動生成
    if not args.output:
        candidates_path = Path(args.candidates)
        candidates_stem = candidates_path.stem  # 例: "candidates_studyB_20251231_174014"
        # "candidates_" を "holdout_results_" に置換
        if candidates_stem.startswith("candidates_"):
            output_stem = candidates_stem.replace("candidates_", "holdout_results_", 1)
        else:
            output_stem = f"holdout_results_{candidates_stem}"
        args.output = str(candidates_path.parent / f"{output_stem}.json")
        print(f"出力ファイル名が指定されていないため、自動生成しました: {args.output}")
        print()
    
    if args.top_n:
        candidates = candidates[:args.top_n]
    
    # リバランス日を取得（並列実行数の決定に必要）
    holdout_dates = get_monthly_rebalance_dates(args.holdout_start, args.holdout_end)
    n_rebalance_dates = len(holdout_dates)
    
    # 並列実行数の決定（最適化コードのロジックを参考）
    cpu_count = mp.cpu_count()
    
    if args.n_jobs == -1:
        # 最適化コードと同じロジックを適用（リソース不足を防ぐため）
        # 候補レベルの並列実行数（控えめに設定）
        candidate_n_jobs = min(len(candidates), min(2, max(1, cpu_count // 8)))
        
        # 各候補内のリバランス日レベルの並列実行数
        # 最適化コードと同様に上限を4に制限（リソース不足を防ぐため）
        available_cpus = max(1, cpu_count - candidate_n_jobs)
        rebalance_n_jobs = max(1, min(n_rebalance_dates, available_cpus))
        # リバランス日が4以上でCPUが2以上ある場合は、上限4で並列化
        if n_rebalance_dates >= 4 and available_cpus >= 2:
            rebalance_n_jobs = max(2, min(n_rebalance_dates, min(4, available_cpus)))
        
        # 総プロセス数の上限チェック（CPU数を超えないように）
        # candidate_n_jobs × rebalance_n_jobs がcpu_countを超える場合は調整
        total_procs = candidate_n_jobs * rebalance_n_jobs
        if total_procs > cpu_count:
            # 総プロセス数がCPU数を超える場合は、リバランス日レベルの並列実行数を削減
            rebalance_n_jobs = max(1, cpu_count // candidate_n_jobs)
    else:
        # n_jobsが指定された場合は、それを候補レベルの並列実行数として使用
        # リバランス日レベルの並列化は無効化（候補レベルのみ並列化）
        candidate_n_jobs = args.n_jobs
        rebalance_n_jobs = 1
    
    print("=" * 80)
    print("候補群のHoldout検証")
    print("=" * 80)
    print(f"候補数: {len(candidates)}")
    print(f"Holdout期間: {args.holdout_start} ～ {args.holdout_end}")
    print(f"取引コスト: {args.cost_bps} bps")
    print(f"CPU数: {cpu_count}")
    print(f"候補レベルの並列実行数: {candidate_n_jobs}")
    print(f"リバランス日レベルの並列実行数: {rebalance_n_jobs}")
    total_parallel_procs = candidate_n_jobs * rebalance_n_jobs
    print(f"推定最大総プロセス数: {total_parallel_procs} (候補並列 × リバランス日並列)")
    if total_parallel_procs > cpu_count:
        print(f"警告: 総プロセス数がCPU数を超えています")
    print("=" * 80)
    print()
    
    # FeatureCacheを使用して特徴量と価格データを事前計算
    features_dict = None
    prices_dict = None
    if args.use_cache:
        print("特徴量と価格データのキャッシュを構築中...")
        try:
            feature_cache = FeatureCache(cache_dir=args.cache_dir)
            # キャッシュ構築時は利用可能なCPUを最大限使用（評価時とは別プロセス）
            cache_workers = max(1, min(n_rebalance_dates, cpu_count))
            features_dict, prices_dict = feature_cache.warm(
                holdout_dates,
                n_jobs=cache_workers if cache_workers > 1 else -1
            )
            print(f"✅ キャッシュ構築完了: 特徴量 {len(features_dict)}日分、価格データ {len(prices_dict)}日分")
            print()
        except Exception as e:
            print(f"⚠️ キャッシュの構築に失敗しました: {e}")
            print("  キャッシュなしで続行します（処理は遅くなりますが、動作します）")
            print()
            import traceback
            traceback.print_exc()
            # キャッシュなしで続行
            features_dict = None
            prices_dict = None
    
    # 各候補を評価（並列化）
    results = []
    
    if candidate_n_jobs > 1 and len(candidates) > 1:
        # 並列実行
        print(f"候補の評価を並列実行中（{candidate_n_jobs}並列）...")
        print()
        
        with ProcessPoolExecutor(max_workers=candidate_n_jobs) as executor:
            futures = {
                executor.submit(
                    _evaluate_single_candidate_wrapper,
                    (candidate, args.holdout_start, args.holdout_end, args.cost_bps, features_dict, prices_dict, rebalance_n_jobs)
                ): candidate["trial_number"]
                for candidate in candidates
            }
            
            completed = 0
            for future in as_completed(futures):
                trial_number = futures[future]
                completed += 1
                try:
                    result = future.result()
                    results.append(result)
                    
                    if "error" in result:
                        print(f"[{completed}/{len(candidates)}] Trial #{trial_number}: ❌ エラー: {result['error']}")
                    else:
                        holdout_sharpe = result["holdout_metrics"].get("sharpe_ratio", None)
                        train_sharpe = result.get("train_sharpe", None)
                        if holdout_sharpe is not None:
                            print(f"[{completed}/{len(candidates)}] Trial #{trial_number}: Train Sharpe: {train_sharpe:.4f} → Holdout Sharpe: {holdout_sharpe:.4f}")
                        else:
                            print(f"[{completed}/{len(candidates)}] Trial #{trial_number}: ⚠️ メトリクスの計算に失敗しました")
                except Exception as e:
                    print(f"[{completed}/{len(candidates)}] Trial #{trial_number}: ❌ 例外が発生: {e}")
                    results.append({
                        "trial_number": trial_number,
                        "error": str(e),
                    })
    else:
        # 逐次実行
        for i, candidate in enumerate(candidates, 1):
            print(f"[{i}/{len(candidates)}] Trial #{candidate['trial_number']} を評価中...")
            result = evaluate_candidate_holdout(
                candidate,
                args.holdout_start,
                args.holdout_end,
                cost_bps=args.cost_bps,
                features_dict=features_dict,
                prices_dict=prices_dict,
                n_jobs=rebalance_n_jobs,
            )
            results.append(result)
            
            if "error" in result:
                print(f"  ❌ エラー: {result['error']}")
            else:
                holdout_sharpe = result["holdout_metrics"].get("sharpe_ratio", None)
                train_sharpe = result.get("train_sharpe", None)
                if holdout_sharpe is not None:
                    print(f"  Train Sharpe: {train_sharpe:.4f} → Holdout Sharpe: {holdout_sharpe:.4f}")
                else:
                    print(f"  ⚠️ メトリクスの計算に失敗しました")
            print()
    
    # 結果をtrial_numberでソート（元の順序を保持）
    results.sort(key=lambda x: next((c["trial_number"] for c in candidates if c["trial_number"] == x.get("trial_number", -1)), -1))
    
    # 結果をまとめる
    summary = {
        "config": {
            "candidates_file": args.candidates,
            "holdout_start": args.holdout_start,
            "holdout_end": args.holdout_end,
            "cost_bps": args.cost_bps,
            "n_candidates": len(candidates),
        },
        "results": results,
    }
    
    # 結果を表示
    print("=" * 80)
    print("評価結果サマリー")
    print("=" * 80)
    print()
    print("| Trial # | Train Sharpe | Holdout Sharpe | ギャップ |")
    print("|---------|--------------|----------------|----------|")
    
    for result in results:
        if "error" in result:
            continue
        
        trial_num = result["trial_number"]
        train_sharpe = result.get("train_sharpe", None)
        holdout_sharpe = result["holdout_metrics"].get("sharpe_ratio", None)
        
        if train_sharpe is not None and holdout_sharpe is not None:
            gap = train_sharpe - holdout_sharpe
            print(f"| #{trial_num} | {train_sharpe:.4f} | {holdout_sharpe:.4f} | {gap:.4f} |")
    
    print()
    
    # 統計
    valid_results = [r for r in results if "error" not in r and r["holdout_metrics"].get("sharpe_ratio") is not None]
    if valid_results:
        holdout_sharpes = [r["holdout_metrics"]["sharpe_ratio"] for r in valid_results]
        train_sharpes = [r.get("train_sharpe", 0) for r in valid_results]
        
        print("統計:")
        print(f"  Holdout Sharpe - 平均: {pd.Series(holdout_sharpes).mean():.4f}")
        print(f"  Holdout Sharpe - 中央値: {pd.Series(holdout_sharpes).median():.4f}")
        print(f"  Holdout Sharpe - 最小値: {min(holdout_sharpes):.4f}")
        print(f"  Holdout Sharpe - 最大値: {max(holdout_sharpes):.4f}")
        print(f"  Holdout Sharpe > 0.10 の候補数: {sum(1 for s in holdout_sharpes if s > 0.10)}/{len(holdout_sharpes)}")
        print(f"  Holdout Sharpe > 0.20 の候補数: {sum(1 for s in holdout_sharpes if s > 0.20)}/{len(holdout_sharpes)}")
        print()
        
        gaps = [t - h for t, h in zip(train_sharpes, holdout_sharpes)]
        print(f"  Train - Holdout ギャップ - 平均: {pd.Series(gaps).mean():.4f}")
        print(f"  Train - Holdout ギャップ - 中央値: {pd.Series(gaps).median():.4f}")
        print()
    
    # 結果を保存（args.outputは既に設定されているはず）
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"✅ 結果を {output_path} に保存しました")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


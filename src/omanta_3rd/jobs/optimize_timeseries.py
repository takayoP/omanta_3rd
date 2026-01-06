"""パラメータ最適化システム（Optuna使用、並列計算対応、時系列版）【月次リバランス型用】

月次リバランス型のパラメータ最適化スクリプト。

時系列P/L計算を使用して、標準的なバックテスト指標を最適化します。
月次リバランス戦略として、ti→ti+1の月次リターン系列から指標を計算します。

【既存版との違い】
- 既存版（optimize.py）: 各リバランス日から最終日までの累積リターンを使用
- 時系列版（本ファイル）: 各リバランス日から次のリバランス日までの月次リターンを使用

【注意】このスクリプトは月次リバランス型専用です。
長期保有型の最適化には optimize_longterm.py を使用してください。

詳細は PERFORMANCE_CALCULATION_METHODS.md を参照してください。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, replace, fields
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import optuna
from optuna.visualization import plot_optimization_history, plot_param_importances
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
import multiprocessing as mp
import sqlite3
import threading
import time

try:
    import tkinter as tk
    from tkinter import ttk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

from ..infra.db import connect_db
from ..jobs.longterm_run import (
    StrategyParams,
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
    save_portfolio_for_rebalance,
)
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..backtest.timeseries import calculate_timeseries_returns, calculate_timeseries_returns_from_portfolios
from ..backtest.metrics import (
    calculate_sharpe_ratio,
    calculate_win_rate_timeseries,
)
from ..backtest.feature_cache import FeatureCache

# 既存のoptimize.pyから必要な関数をインポート
from .optimize import (
    EntryScoreParams,
    _entry_score_with_params,
    _calculate_entry_score_with_params,
    _select_portfolio_with_params,
    ProgressWindow,
)


def run_backtest_for_optimization_timeseries(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    enable_timing: bool = False,
    trial: Optional[optuna.Trial] = None,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
    save_to_db: bool = True,
) -> Dict[str, Any]:
    """
    最適化用のバックテスト実行（時系列版、並列計算対応、キャッシュ対応）
    
    設計: 並列ワーカーは「ポートフォリオ選定だけ」を返し、
          保存後に時系列P/Lを計算する
    
    Args:
        rebalance_dates: リバランス日のリスト
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数、1で逐次実行）
        enable_timing: 時間計測を有効にするか
        trial: OptunaのTrialオブジェクト
        features_dict: 特徴量辞書（{rebalance_date: features_df}、Noneの場合はDBから取得）
        prices_dict: 価格データ辞書（{rebalance_date: {code: [adj_close, ...]}}、Noneの場合はDBから取得）
        save_to_db: ポートフォリオをDBに保存するか（デフォルト: True）
    
    Returns:
        パフォーマンス指標の辞書（時系列指標）とタイミング情報
    """
    trial_start_time = time.time()
    timing_info = {}
    
    # dataclassを辞書に変換（pickle可能にするため）
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    # 並列実行数の決定
    if n_jobs == -1:
        n_jobs = min(len(rebalance_dates), mp.cpu_count())
    elif n_jobs <= 0:
        n_jobs = 1
    
    portfolios = {}  # {rebalance_date: portfolio_df}
    
    # データ取得・ポートフォリオ選定（時間計測）
    data_start_time = time.time()
    
    # 並列実行: ポートフォリオ選定のみ
    if n_jobs > 1 and len(rebalance_dates) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {
                executor.submit(
                    _run_single_backtest_portfolio_only,
                    rebalance_date,
                    strategy_params_dict,
                    entry_params_dict,
                    features_dict.get(rebalance_date) if features_dict else None,
                    prices_dict.get(rebalance_date) if prices_dict else None,
                ): rebalance_date
                for rebalance_date in rebalance_dates
            }
            
            for future in as_completed(futures):
                rebalance_date = futures[future]
                try:
                    portfolio = future.result()
                    if portfolio is not None and not portfolio.empty:
                        portfolios[rebalance_date] = portfolio
                except Exception as e:
                    print(f"エラー ({rebalance_date}): {e}")
    else:
        # 逐次実行
        for rebalance_date in rebalance_dates:
            portfolio = _run_single_backtest_portfolio_only(
                rebalance_date,
                strategy_params_dict,
                entry_params_dict,
                features_dict.get(rebalance_date) if features_dict else None,
                prices_dict.get(rebalance_date) if prices_dict else None,
            )
            if portfolio is not None and not portfolio.empty:
                portfolios[rebalance_date] = portfolio
    
    data_end_time = time.time()
    timing_info["data_fetch_time"] = data_end_time - data_start_time
    
    # デバッグ: 結果が空なら例外を投げる
    if not portfolios:
        raise RuntimeError(
            f"No portfolios were generated for any rebalance dates. "
            f"Check worker errors, feature building, or portfolio selection logic."
        )
    
    # ポートフォリオをDBに保存（オプション）
    save_start_time = time.time()
    if save_to_db:
        with connect_db() as conn:
            for rebalance_date, portfolio_df in portfolios.items():
                save_portfolio_for_rebalance(conn, portfolio_df)
    save_end_time = time.time()
    timing_info["save_time"] = save_end_time - save_start_time if save_to_db else 0.0
    
    # 時系列P/Lを計算（portfoliosを直接渡す）
    if not rebalance_dates:
        raise RuntimeError("No rebalance dates provided")
    
    start_date = rebalance_dates[0]
    end_date = rebalance_dates[-1]
    
    timeseries_start_time = time.time()
    # portfoliosを直接渡すことで、DBへの保存を回避（SQLiteロック待ちを削減）
    timeseries_data = calculate_timeseries_returns_from_portfolios(
        portfolios=portfolios,
        start_date=start_date,
        end_date=end_date,
        rebalance_dates=rebalance_dates,
        cost_bps=cost_bps,
    )
    timeseries_end_time = time.time()
    timing_info["timeseries_calc_time"] = timeseries_end_time - timeseries_start_time
    
    monthly_returns = timeseries_data["monthly_returns"]
    monthly_excess_returns = timeseries_data["monthly_excess_returns"]
    
    if not monthly_returns:
        raise RuntimeError(
            f"No monthly returns were calculated. "
            f"Check calculate_timeseries_returns() logic."
        )
    
    # 時系列指標を計算
    metrics_start_time = time.time()
    mean_excess_return = np.mean(monthly_excess_returns) * 100.0  # %換算
    mean_return = np.mean(monthly_returns) * 100.0  # %換算
    
    # 月次勝率（超過リターン基準）
    win_rate = calculate_win_rate_timeseries(
        monthly_returns,
        use_excess=True,
        monthly_excess_returns=monthly_excess_returns,
    )
    if win_rate is None:
        win_rate = 0.0
    
    # シャープレシオ（月次超過リターン系列から計算、年率化）
    sharpe_ratio = calculate_sharpe_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )
    if sharpe_ratio is None:
        sharpe_ratio = 0.0
    metrics_end_time = time.time()
    timing_info["metrics_calc_time"] = metrics_end_time - metrics_start_time
    
    trial_end_time = time.time()
    timing_info["total_time"] = trial_end_time - trial_start_time
    
    result = {
        "mean_excess_return": mean_excess_return,  # %
        "mean_return": mean_return,  # %
        "win_rate": win_rate,  # 0.0-1.0
        "sharpe_ratio": sharpe_ratio,  # 年率化済み
        "num_portfolios": len(portfolios),
        "num_monthly_returns": len(monthly_returns),
    }
    
    if enable_timing:
        result["timing"] = timing_info
        # trialのuser_attrsにtiming情報を保存（後で集計用）
        if trial is not None:
            trial.set_user_attr("timing", timing_info)
    
    return result


def _run_single_backtest_portfolio_only(
    rebalance_date: str,
    strategy_params_dict: dict,
    entry_params_dict: dict,
    feat: Optional[pd.DataFrame] = None,
    prices_data: Optional[Dict[str, List[float]]] = None,
) -> Optional[pd.DataFrame]:
    """
    単一のリバランス日に対するポートフォリオ選定のみ（並列化用、キャッシュ対応）
    
    Args:
        rebalance_date: リバランス日
        strategy_params_dict: StrategyParamsを辞書化したもの
        entry_params_dict: EntryScoreParamsを辞書化したもの
        feat: 特徴量DataFrame（Noneの場合はDBから取得）
        prices_data: 価格データ（{code: [adj_close, ...]}、Noneの場合はDBから取得）
    
    Returns:
        ポートフォリオDataFrame（エラー時はNone）
    """
    try:
        import sys
        print(f"        [_run_single_backtest] 開始: {rebalance_date}")
        sys.stdout.flush()
        
        # 辞書からdataclassに復元
        strategy_params = StrategyParams(**strategy_params_dict)
        entry_params = EntryScoreParams(**entry_params_dict)
        
        # 特徴量を取得（キャッシュ優先）
        if feat is None:
            print(f"        [_run_single_backtest] DBから特徴量を取得: {rebalance_date}")
            sys.stdout.flush()
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
            print(f"        [_run_single_backtest] ⚠️  特徴量が空: {rebalance_date}")
            sys.stdout.flush()
            return None
        
        print(f"        [_run_single_backtest] 特徴量取得完了: {rebalance_date} (銘柄数: {len(feat)})")
        sys.stdout.flush()
        
        # entry_scoreを計算（パラメータ化版、価格データはキャッシュから取得）
        if prices_data is not None:
            print(f"        [_run_single_backtest] entry_score計算開始 (キャッシュ使用): {rebalance_date}")
            sys.stdout.flush()
            # キャッシュから価格データを取得
            close_map = {
                code: pd.Series(prices)
                for code, prices in prices_data.items()
            }
            feat["entry_score"] = feat["code"].apply(
                lambda c: _entry_score_with_params(close_map.get(c), entry_params)
                if c in close_map
                else np.nan
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
        
        # ポートフォリオを選択（パラメータ化版）
        print(f"        [_run_single_backtest] ポートフォリオ選択開始: {rebalance_date}")
        sys.stdout.flush()
        portfolio = _select_portfolio_with_params(
            feat, strategy_params, entry_params
        )
        
        if portfolio is None or portfolio.empty:
            print(f"        [_run_single_backtest] ⚠️  ポートフォリオが空: {rebalance_date}")
            sys.stdout.flush()
            return None
        
        print(f"        [_run_single_backtest] ✓ 完了: {rebalance_date} (選択銘柄数: {len(portfolio)})")
        sys.stdout.flush()
        return portfolio
    except Exception as e:
        print(f"エラー ({rebalance_date}): {e}")
        import traceback
        traceback.print_exc()
        return None


def objective_timeseries(
    trial: optuna.Trial,
    rebalance_dates: List[str],
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    enable_timing: bool = False,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
    save_to_db: bool = True,
    entry_mode: str = "free",
) -> float:
    """
    Optunaの目的関数（時系列版）
    
    Args:
        trial: OptunaのTrialオブジェクト
        rebalance_dates: リバランス日のリスト
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        enable_timing: 時間計測を有効にするか
    
    Returns:
        最適化対象の値（時系列指標ベース）
    """
    """
    Optunaの目的関数（時系列版）
    
    Args:
        trial: OptunaのTrialオブジェクト
        rebalance_dates: リバランス日のリスト
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        enable_timing: 時間計測を有効にするか
    
    Returns:
        最適化対象の値（時系列指標ベース）
    """
    # StrategyParamsのパラメータ（既存版と同じ範囲）
    w_quality = trial.suggest_float("w_quality", 0.15, 0.35)
    w_value = trial.suggest_float("w_value", 0.20, 0.40)
    w_growth = trial.suggest_float("w_growth", 0.05, 0.20)
    w_record_high = trial.suggest_float("w_record_high", 0.03, 0.15)
    w_size = trial.suggest_float("w_size", 0.10, 0.25)
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
    w_forward_per = trial.suggest_float("w_forward_per", 0.35, 0.65)
    w_pbr = 1.0 - w_forward_per
    
    roe_min = trial.suggest_float("roe_min", 0.05, 0.12)
    liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.15, 0.35)
    
    # StrategyParamsはfrozenなので、replaceを使用
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
        w_quality=w_quality,
        w_value=w_value,
        w_growth=w_growth,
        w_record_high=w_record_high,
        w_size=w_size,
        w_forward_per=w_forward_per,
        w_pbr=w_pbr,
        roe_min=roe_min,
        liquidity_quantile_cut=liquidity_quantile_cut,
    )
    
    # EntryScoreParamsのパラメータ（順張り/逆張りを対称に探索）
    RSI_LOW, RSI_HIGH = 15.0, 85.0
    rsi_min_width = 10.0  # 最小幅制約（緩和: 20.0 → 10.0）
    
    # baseを先にサンプリング
    rsi_base = trial.suggest_float("rsi_base", RSI_LOW, RSI_HIGH)
    
    # baseに対して制約を満たすmaxの範囲を計算
    # maxは base ± min_width の範囲外から選ぶ必要がある
    max_low = max(RSI_LOW, rsi_base + rsi_min_width)  # 順張り方向の下限: base + min_width 以上
    max_high = min(RSI_HIGH, rsi_base - rsi_min_width)  # 逆張り方向の上限: base - min_width 以下
    
    # 制約を満たす範囲が存在するかチェック
    can_long = (max_low <= RSI_HIGH)  # 順張り方向が可能か
    can_short = (max_high >= RSI_LOW)  # 逆張り方向が可能か
    
    # entry_modeに応じた制約
    if entry_mode == "mom":
        # 順張り方向を強制
        if not can_long:
            trial.set_user_attr("prune_reason", "rsi_mom_not_possible")
            raise optuna.TrialPruned(f"RSI: base={rsi_base:.2f}に対して順張り方向が不可能です")
        rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)
    elif entry_mode == "rev":
        # 逆張り方向を強制
        if not can_short:
            trial.set_user_attr("prune_reason", "rsi_rev_not_possible")
            raise optuna.TrialPruned(f"RSI: base={rsi_base:.2f}に対して逆張り方向が不可能です")
        rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)
    else:
        # freeモード: 両方向を探索
        if can_long and can_short:
            # 両方向が可能な場合: trial番号の偶奇で方向を選ぶ（パラメータ空間を増やさない）
            # 順張り方向: [base + min_width, RSI_HIGH]
            # 逆張り方向: [RSI_LOW, base - min_width]
            # 実質的にはコイン投げと同じだが、Optunaのサンプラーに学習させない
            if trial.number % 2 == 0:
                rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)
            else:
                rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)
        elif can_long:
            # 順張り方向のみ可能: [base + min_width, RSI_HIGH]
            rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)
        elif can_short:
            # 逆張り方向のみ可能: [RSI_LOW, base - min_width]
            rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)
        else:
            # 制約を満たす範囲が存在しない（通常は発生しない）
            trial.set_user_attr("prune_reason", "rsi_no_valid_range")
            raise optuna.TrialPruned(f"RSI: base={rsi_base:.2f}に対して制約を満たすmaxの範囲が存在しません")
    
    # BB Z-scoreパラメータ（順張り/逆張りを対称に探索）
    BB_LOW, BB_HIGH = -3.5, 3.5
    bb_z_min_width = 0.5  # 最小幅制約（緩和: 1.0 → 0.5）
    
    # baseを先にサンプリング
    bb_z_base = trial.suggest_float("bb_z_base", BB_LOW, BB_HIGH)
    
    # baseに対して制約を満たすmaxの範囲を計算
    # maxは base ± min_width の範囲外から選ぶ必要がある
    bb_max_low = max(BB_LOW, bb_z_base + bb_z_min_width)  # 順張り方向の下限: base + min_width 以上
    bb_max_high = min(BB_HIGH, bb_z_base - bb_z_min_width)  # 逆張り方向の上限: base - min_width 以下
    
    # 制約を満たす範囲が存在するかチェック
    bb_can_long = (bb_max_low <= BB_HIGH)  # 順張り方向が可能か
    bb_can_short = (bb_max_high >= BB_LOW)  # 逆張り方向が可能か
    
    # entry_modeに応じた制約
    if entry_mode == "mom":
        # 順張り方向を強制
        if not bb_can_long:
            trial.set_user_attr("prune_reason", "bb_mom_not_possible")
            raise optuna.TrialPruned(f"BB Z-score: base={bb_z_base:.2f}に対して順張り方向が不可能です")
        bb_z_max = trial.suggest_float("bb_z_max", bb_max_low, BB_HIGH)
    elif entry_mode == "rev":
        # 逆張り方向を強制
        if not bb_can_short:
            trial.set_user_attr("prune_reason", "bb_rev_not_possible")
            raise optuna.TrialPruned(f"BB Z-score: base={bb_z_base:.2f}に対して逆張り方向が不可能です")
        bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, bb_max_high)
    else:
        # freeモード: 両方向を探索
        if bb_can_long and bb_can_short:
            # 両方向が可能な場合: trial番号の偶奇で方向を選ぶ（パラメータ空間を増やさない）
            # 順張り方向: [base + min_width, BB_HIGH]
            # 逆張り方向: [BB_LOW, base - min_width]
            # 実質的にはコイン投げと同じだが、Optunaのサンプラーに学習させない
            if trial.number % 2 == 0:
                bb_z_max = trial.suggest_float("bb_z_max", bb_max_low, BB_HIGH)
            else:
                bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, bb_max_high)
        elif bb_can_long:
            # 順張り方向のみ可能: [base + min_width, BB_HIGH]
            bb_z_max = trial.suggest_float("bb_z_max", bb_max_low, BB_HIGH)
        elif bb_can_short:
            # 逆張り方向のみ可能: [BB_LOW, base - min_width]
            bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, bb_max_high)
        else:
            # 制約を満たす範囲が存在しない（通常は発生しない）
            trial.set_user_attr("prune_reason", "bb_no_valid_range")
            raise optuna.TrialPruned(f"BB Z-score: base={bb_z_base:.2f}に対して制約を満たすmaxの範囲が存在しません")
    
    bb_weight = trial.suggest_float("bb_weight", 0.45, 0.75)
    rsi_weight = 1.0 - bb_weight
    
    entry_params = EntryScoreParams(
        rsi_base=rsi_base,
        rsi_max=rsi_max,
        bb_z_base=bb_z_base,
        bb_z_max=bb_z_max,
        bb_weight=bb_weight,
        rsi_weight=rsi_weight,
        rsi_min_width=rsi_min_width,
        bb_z_min_width=bb_z_min_width,
    )
    
    # 順張り/逆張りの方向と幅をログに記録
    rsi_direction = "順張り" if rsi_max > rsi_base else "逆張り"
    bb_direction = "順張り" if bb_z_max > bb_z_base else "逆張り"
    trial.set_user_attr("rsi_direction", rsi_direction)
    trial.set_user_attr("bb_direction", bb_direction)
    trial.set_user_attr("rsi_width", abs(rsi_max - rsi_base))
    trial.set_user_attr("bb_z_width", abs(bb_z_max - bb_z_base))
    
    # バックテスト実行（時系列版）
    perf = run_backtest_for_optimization_timeseries(
        rebalance_dates,
        strategy_params,
        entry_params,
        cost_bps=cost_bps,
        n_jobs=n_jobs,
        enable_timing=enable_timing,
        trial=trial,
        features_dict=features_dict,
        prices_dict=prices_dict,
        save_to_db=save_to_db,
    )
    
    # 目的関数: 超過リターン系列のIR（=Sharpe_excess）を主軸に
    # sharpe_ratio: 月次超過リターン系列のSharpe（年率化済み）= IR
    # 必要なら微調整: sharpe_excess + 0.1*mean_excess - 0.05*turnover_penalty - 0.1*missing_penalty
    # 勝率項は入れる場合でも小さく（または撤去）
    objective_value = perf["sharpe_ratio"]  # 主軸: Sharpe_excess（=IR）
    
    # 微調整（必要に応じて有効化）
    # objective_value = (
    #     perf["sharpe_ratio"] * 1.0  # 主軸
    #     + perf["mean_excess_return"] * 0.1  # 平均超過リターン（小さく）
    #     # 勝率は撤去（または非常に小さく）
    # )
    
    # デバッグ用ログ出力
    log_msg = (
        f"[Trial {trial.number}] "
        f"objective={objective_value:.4f}, "
        f"excess_return={perf['mean_excess_return']:.4f}%, "
        f"win_rate={perf['win_rate']:.4f}, "
        f"sharpe={perf['sharpe_ratio']:.4f}"
    )
    
    if enable_timing and "timing" in perf:
        timing = perf["timing"]
        log_msg += (
            f" | time={timing['total_time']:.2f}s "
            f"(data={timing['data_fetch_time']:.2f}s, "
            f"save={timing['save_time']:.2f}s, "
            f"timeseries={timing['timeseries_calc_time']:.2f}s, "
            f"metrics={timing['metrics_calc_time']:.2f}s)"
        )
    
    print(log_msg)
    
    return objective_value


def _setup_blas_threads():
    """BLASスレッドを1に設定（プロセス並列時の過負荷を防ぐ）"""
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")


def main(
    start_date: str,
    end_date: str,
    n_trials: int = 50,
    study_name: Optional[str] = None,
    n_jobs: int = -1,
    bt_workers: int = -1,  # デフォルトで自動設定（-1）
    parallel_mode: str = "trial",
    cost_bps: float = 0.0,
    show_progress_window: bool = True,
    storage: Optional[str] = None,
    no_db_write: bool = False,
    cache_dir: str = "cache/features",
    entry_mode: str = "free",
):
    """
    最適化を実行（時系列版、特徴量キャッシュ対応）
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        n_trials: 試行回数
        study_name: スタディ名（Noneの場合は自動生成）
        n_jobs: trial並列数（-1でCPU数、parallel_mode='trial'の場合に使用）
        bt_workers: trial内バックテストの並列数（デフォルト: 1）
        parallel_mode: 並列化モード（'trial', 'backtest', 'hybrid'）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        show_progress_window: 進捗ウィンドウを表示するか
        storage: Optunaストレージ（Noneの場合はSQLite、例: 'postgresql://...'）
        no_db_write: 最適化中にDBに書き込まない（デフォルト: False）
        cache_dir: キャッシュディレクトリ（デフォルト: "cache/features"）
    """
    # BLASスレッドを1に設定
    _setup_blas_threads()
    
    print("=" * 80)
    print("パラメータ最適化システム（並列計算対応、時系列版）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"取引コスト: {cost_bps} bps")
    print(f"並列化モード: {parallel_mode}")
    print(f"Entry mode: {entry_mode}")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print(f"最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築します...")
    print("=" * 80)
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(rebalance_dates, n_jobs=bt_workers if bt_workers > 0 else -1)
    print(f"[FeatureCache] 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # Optunaスタディを作成
    if study_name is None:
        study_name = f"optimization_timeseries_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # ストレージの設定
    if storage is None:
        storage = f"sqlite:///optuna_{study_name}.db"
    
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
    )
    
    # 並列化設定を先に計算（進捗ウィンドウの表示判定に使用）
    cpu_count = mp.cpu_count()
    
    # 並列数の事前計算（進捗ウィンドウの表示判定用）
    if parallel_mode == "trial":
        if n_jobs == -1:
            if storage.startswith("sqlite"):
                optuna_n_jobs_preview = min(4, max(2, min(4, cpu_count // 8)))
            else:
                optuna_n_jobs_preview = min(8, max(1, cpu_count // 2))
        else:
            optuna_n_jobs_preview = n_jobs
    elif parallel_mode == "backtest":
        optuna_n_jobs_preview = 1
    elif parallel_mode == "hybrid":
        if n_jobs == -1:
            if storage.startswith("sqlite"):
                optuna_n_jobs_preview = max(2, min(cpu_count - 1, int(cpu_count * 0.6)))
            else:
                optuna_n_jobs_preview = min(4, max(2, cpu_count // 2))
        else:
            optuna_n_jobs_preview = n_jobs
    else:
        optuna_n_jobs_preview = 1
    
    # 進捗ウィンドウを作成（並列実行時は無効化）
    progress_window = None
    # 並列実行時（n_jobs > 1）は進捗ウィンドウを表示しない（tkinterのスレッドセーフ問題を回避）
    if show_progress_window and TKINTER_AVAILABLE and optuna_n_jobs_preview == 1:
        progress_window = ProgressWindow(n_trials)
        progress_window.run()
        print("進捗ウィンドウを表示しました")
    elif show_progress_window and optuna_n_jobs_preview > 1:
        print("並列実行のため、進捗ウィンドウは表示しません（tkinterのスレッドセーフ問題を回避）")
    
    # コールバック関数（並列実行時は進捗ウィンドウを更新しない）
    def callback(study: optuna.Study, trial: optuna.Trial):
        """最適化の進捗を更新"""
        # 並列実行時（n_jobs > 1）はtkinterの更新がスレッドセーフでないため無効化
        if progress_window and optuna_n_jobs_preview == 1:
            try:
                current_value = trial.value if trial.value is not None else None
                best_value = None
                try:
                    best_value = study.best_value
                except ValueError:
                    if len(study.trials) > 0:
                        completed_trials = [
                            t for t in study.trials 
                            if t.state == optuna.trial.TrialState.COMPLETE
                        ]
                        if completed_trials:
                            best_trial = max(
                                completed_trials,
                                key=lambda t: t.value if t.value is not None else float('-inf')
                            )
                            best_value = best_trial.value if best_trial.value is not None else None
                
                params = trial.params if hasattr(trial, 'params') else None
                
                if best_value is not None:
                    progress_window.update(trial.number + 1, best_value, params)
                elif current_value is not None:
                    progress_window.update(trial.number + 1, current_value, params)
            except RuntimeError:
                # tkinterのエラー（メインスレッド以外からの更新）は無視
                pass
    
    # 並列化設定
    enable_timing = True  # 時間計測を有効化
    
    if parallel_mode == "trial":
        # trial並列のみ（推奨）
        if n_jobs == -1:
            # SQLiteの場合は控えめに（2-4程度）競合を避ける
            # SQLiteのWALモードでも、Optunaのtrial並列が多すぎるとロック待ちが発生
            if storage.startswith("sqlite"):
                # 2-4に制限（競合を最小化）
                optuna_n_jobs = min(4, max(2, min(4, cpu_count // 8)))
            else:
                optuna_n_jobs = min(8, max(1, cpu_count // 2))
        else:
            optuna_n_jobs = n_jobs
        # バックテスト内の並列化も有効化（リバランス日ごとに並列処理）
        if bt_workers == -1:
            # リバランス日数とCPU数を考慮して適切な並列数を決定
            # 各trial内でリバランス日ごとに並列処理するため、残りのCPUリソースを活用
            # trial並列数がCPU数の70%程度なので、残り30%をバックテスト並列に割り当て
            # ただし、リバランス日数が少ない場合はそれに合わせる
            available_cpus = max(1, cpu_count - optuna_n_jobs)
            backtest_n_jobs = max(1, min(len(rebalance_dates), available_cpus))
            # 最低でも2-4並列は確保（リバランス日数が十分にある場合）
            if len(rebalance_dates) >= 4 and available_cpus >= 2:
                backtest_n_jobs = max(2, min(len(rebalance_dates), min(4, available_cpus)))
        else:
            backtest_n_jobs = bt_workers
        print("最適化を開始します...")
        print(f"CPU数: {cpu_count}")
        print(f"Optuna試行並列数: {optuna_n_jobs}")
        print(f"各試行内のバックテスト並列数: {backtest_n_jobs}")
        print()
    elif parallel_mode == "backtest":
        # trial逐次、trial内並列
        optuna_n_jobs = 1
        if bt_workers == -1:
            backtest_n_jobs = min(len(rebalance_dates), cpu_count)
        else:
            backtest_n_jobs = bt_workers
        print("最適化を開始します...")
        print(f"CPU数: {cpu_count}")
        print(f"Optuna試行並列数: {optuna_n_jobs} (逐次)")
        print(f"各試行内のバックテスト並列数: {backtest_n_jobs}")
        print()
    elif parallel_mode == "hybrid":
        # 二重並列（条件付き）
        if n_jobs == -1:
            # SQLiteでも積極的に並列化
            if storage.startswith("sqlite"):
                optuna_n_jobs = max(2, min(cpu_count - 1, int(cpu_count * 0.6)))
            else:
                optuna_n_jobs = min(4, max(2, cpu_count // 2))
        else:
            optuna_n_jobs = n_jobs
        if bt_workers == -1:
            backtest_n_jobs = max(1, cpu_count // optuna_n_jobs)
        else:
            backtest_n_jobs = bt_workers
        # オーバーサブスクライブを防ぐ
        if optuna_n_jobs * backtest_n_jobs > cpu_count:
            print(f"警告: 並列度がCPU数を超えています。調整します。")
            backtest_n_jobs = max(1, cpu_count // optuna_n_jobs)
        print("最適化を開始します...")
        print(f"CPU数: {cpu_count}")
        print(f"Optuna試行並列数: {optuna_n_jobs}")
        print(f"各試行内のバックテスト並列数: {backtest_n_jobs}")
        print(f"理論上の最大並列度: {optuna_n_jobs * backtest_n_jobs}")
        print()
    else:
        raise ValueError(f"不明な並列化モード: {parallel_mode}")
    
    # 時間計測用のリスト
    trial_times = []
    
    # 最適化実行
    study.optimize(
        lambda trial: objective_timeseries(
            trial,
            rebalance_dates,
            cost_bps,
            backtest_n_jobs,
            enable_timing=enable_timing,
            features_dict=features_dict,
            prices_dict=prices_dict,
            save_to_db=not no_db_write,
            entry_mode=entry_mode,
        ),
        n_trials=n_trials,
        show_progress_bar=True,
        n_jobs=optuna_n_jobs,
        callbacks=[callback] if progress_window else None,
    )
    
    # 完了したtrialのtiming情報を収集・集計
    timing_summary = {
        "data_fetch_times": [],
        "save_times": [],
        "timeseries_calc_times": [],
        "metrics_calc_times": [],
        "total_times": [],
    }
    
    for trial in study.trials:
        if trial.state == optuna.trial.TrialState.COMPLETE and trial.value is not None:
            # trialのuser_attrsからtiming情報を取得
            if hasattr(trial, 'user_attrs') and 'timing' in trial.user_attrs:
                timing = trial.user_attrs['timing']
                if isinstance(timing, dict):
                    timing_summary["data_fetch_times"].append(timing.get("data_fetch_time", 0.0))
                    timing_summary["save_times"].append(timing.get("save_time", 0.0))
                    timing_summary["timeseries_calc_times"].append(timing.get("timeseries_calc_time", 0.0))
                    timing_summary["metrics_calc_times"].append(timing.get("metrics_calc_time", 0.0))
                    timing_summary["total_times"].append(timing.get("total_time", 0.0))
    
    # 進捗ウィンドウを閉じる
    if progress_window:
        progress_window.close()
    
    # 結果表示
    print()
    print("=" * 80)
    print("【最適化結果】")
    print("=" * 80)
    print(f"最良試行: {study.best_trial.number}")
    print(f"最良値: {study.best_value:.4f}")
    print()
    print("最良パラメータ:")
    for key, value in study.best_params.items():
        print(f"  {key}: {value:.4f}")
    print()
    
    # 結果をJSONに保存
    best_params_raw = study.best_params.copy()
    
    # Core Score重みの正規化
    w_quality = best_params_raw.get("w_quality", 0.0)
    w_value = best_params_raw.get("w_value", 0.0)
    w_growth = best_params_raw.get("w_growth", 0.0)
    w_record_high = best_params_raw.get("w_record_high", 0.0)
    w_size = best_params_raw.get("w_size", 0.0)
    total = w_quality + w_value + w_growth + w_record_high + w_size
    if total > 0:
        w_quality_norm = w_quality / total
        w_value_norm = w_value / total
        w_growth_norm = w_growth / total
        w_record_high_norm = w_record_high / total
        w_size_norm = w_size / total
    else:
        w_quality_norm = w_quality
        w_value_norm = w_value
        w_growth_norm = w_growth
        w_record_high_norm = w_record_high
        w_size_norm = w_size
    
    normalized_best_params = best_params_raw.copy()
    normalized_best_params["w_quality"] = w_quality_norm
    normalized_best_params["w_value"] = w_value_norm
    normalized_best_params["w_growth"] = w_growth_norm
    normalized_best_params["w_record_high"] = w_record_high_norm
    normalized_best_params["w_size"] = w_size_norm
    
    # 結果ファイル名をentry_modeに応じて決定
    if entry_mode == "mom":
        # 順張りモードの場合は専用ファイル名
        if study_name:
            result_file = f"monthly_params_mom_{study_name}.json"
        else:
            result_file = f"monthly_params_mom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    elif entry_mode == "rev":
        # 逆張りモードの場合は専用ファイル名
        if study_name:
            result_file = f"monthly_params_rev_{study_name}.json"
        else:
            result_file = f"monthly_params_rev_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    else:
        # freeモードの場合は従来のファイル名
        if study_name:
            result_file = f"optimization_result_optimization_timeseries_{study_name}.json"
        else:
            result_file = f"optimization_result_optimization_timeseries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "best_value": study.best_value,
                "best_params": normalized_best_params,  # 正規化後の値を保存
                "best_params_raw": best_params_raw,  # 元の値を保存
                "n_trials": n_trials,
                "calculation_method": "timeseries",
                "entry_mode": entry_mode,
                "description": f"時系列P/L計算を使用した最適化（entry_mode: {entry_mode}）",
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"結果を {result_file} に保存しました")
    
    # サマリーレポート
    print()
    print("=" * 80)
    print("【最適化サマリー】")
    print("=" * 80)
    
    completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if completed_trials:
        # Sharpe_excessの分布を計算
        sharpe_values = [t.value for t in completed_trials if t.value is not None]
        if sharpe_values:
            sharpe_values_sorted = sorted(sharpe_values, reverse=True)
            best_sharpe = sharpe_values_sorted[0]
            p95_idx = max(0, int(len(sharpe_values_sorted) * 0.05))
            p95_sharpe = sharpe_values_sorted[p95_idx] if p95_idx < len(sharpe_values_sorted) else sharpe_values_sorted[-1]
            median_idx = len(sharpe_values_sorted) // 2
            median_sharpe = sharpe_values_sorted[median_idx]
            
            print(f"完了試行数: {len(completed_trials)}")
            print(f"Sharpe_excess分布:")
            print(f"  best: {best_sharpe:.4f}")
            print(f"  p95: {p95_sharpe:.4f} ({p95_sharpe/best_sharpe*100:.1f}% of best)")
            print(f"  median: {median_sharpe:.4f} ({median_sharpe/best_sharpe*100:.1f}% of best)")
            print()
            
            # 上位5 trialのパラメータ分布（簡易版）
            top5_trials = sorted(completed_trials, key=lambda t: t.value if t.value is not None else float('-inf'), reverse=True)[:5]
            print("上位5 trialのパラメータ範囲:")
            if top5_trials:
                param_ranges = {}
                for trial in top5_trials:
                    for key, value in trial.params.items():
                        if key not in param_ranges:
                            param_ranges[key] = []
                        param_ranges[key].append(value)
                
                for key in sorted(param_ranges.keys())[:10]:  # 最初の10パラメータのみ表示
                    values = param_ranges[key]
                    min_val = min(values)
                    max_val = max(values)
                    if max_val - min_val > 0.01:  # 差が大きい場合のみ表示
                        print(f"  {key}: {min_val:.4f} ~ {max_val:.4f} (range: {max_val-min_val:.4f})")
            print()
    
    print("=" * 80)
    
    # Timingサマリーを表示
    if any(timing_summary["total_times"]):
        print()
        print("=" * 80)
        print("【Timingサマリー】")
        print("=" * 80)
        
        def _print_timing_stats(name: str, times: List[float]):
            if not times:
                return
            times_arr = np.array(times)
            print(f"{name}:")
            print(f"  平均: {np.mean(times_arr):.2f}s")
            print(f"  中央値: {np.median(times_arr):.2f}s")
            print(f"  最小: {np.min(times_arr):.2f}s")
            print(f"  最大: {np.max(times_arr):.2f}s")
            print(f"  合計: {np.sum(times_arr):.2f}s")
            print()
        
        _print_timing_stats("data_fetch_time", timing_summary["data_fetch_times"])
        _print_timing_stats("save_time", timing_summary["save_times"])
        _print_timing_stats("timeseries_calc_time", timing_summary["timeseries_calc_times"])
        _print_timing_stats("metrics_calc_time", timing_summary["metrics_calc_times"])
        _print_timing_stats("total_time", timing_summary["total_times"])
        
        # ボトルネック分析
        if timing_summary["total_times"]:
            total_times_arr = np.array(timing_summary["total_times"])
            avg_total = np.mean(total_times_arr)
            
            if avg_total > 0:
                print("ボトルネック分析（平均時間の割合）:")
                if timing_summary["data_fetch_times"]:
                    avg_data = np.mean(timing_summary["data_fetch_times"])
                    print(f"  data_fetch: {avg_data/avg_total*100:.1f}%")
                if timing_summary["save_times"]:
                    avg_save = np.mean(timing_summary["save_times"])
                    print(f"  save: {avg_save/avg_total*100:.1f}%")
                if timing_summary["timeseries_calc_times"]:
                    avg_ts = np.mean(timing_summary["timeseries_calc_times"])
                    print(f"  timeseries_calc: {avg_ts/avg_total*100:.1f}%")
                if timing_summary["metrics_calc_times"]:
                    avg_metrics = np.mean(timing_summary["metrics_calc_times"])
                    print(f"  metrics_calc: {avg_metrics/avg_total*100:.1f}%")
                print()
        
        print("=" * 80)
    
    # 可視化（オプション）
    try:
        fig1 = plot_optimization_history(study)
        fig1.write_image(f"optimization_history_{study_name}.png")
        print(f"最適化履歴を optimization_history_{study_name}.png に保存しました")
        
        fig2 = plot_param_importances(study)
        fig2.write_image(f"param_importances_{study_name}.png")
        print(f"パラメータ重要度を param_importances_{study_name}.png に保存しました")
    except Exception as e:
        print(f"可視化の保存に失敗しました: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="パラメータ最適化（時系列版）")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--n-trials", type=int, default=50, help="試行回数")
    parser.add_argument("--study-name", type=str, help="スタディ名")
    parser.add_argument("--n-jobs", type=int, default=-1, help="trial並列数（-1で自動、parallel-mode='trial'の場合に使用）")
    parser.add_argument("--bt-workers", type=int, default=-1, help="trial内バックテストの並列数（-1で自動、デフォルト: -1）")
    parser.add_argument("--parallel-mode", type=str, default="trial", choices=["trial", "backtest", "hybrid"],
                        help="並列化モード: trial（推奨）、backtest、hybrid")
    parser.add_argument("--cost", type=float, default=0.0, help="取引コスト（bps）")
    parser.add_argument("--storage", type=str, help="Optunaストレージ（例: postgresql://user:pass@host/db、デフォルト: SQLite）")
    parser.add_argument("--no-progress-window", action="store_true", help="進捗ウィンドウを表示しない")
    parser.add_argument("--no-db-write", action="store_true", help="最適化中にDBに書き込まない")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="キャッシュディレクトリ（デフォルト: cache/features）")
    parser.add_argument("--entry-mode", type=str, default="free", choices=["free", "mom", "rev"],
                        help="entry_mode: free（両方向探索）、mom（順張り強制）、rev（逆張り強制）")
    
    args = parser.parse_args()
    
    main(
        start_date=args.start,
        end_date=args.end,
        n_trials=args.n_trials,
        study_name=args.study_name,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
        parallel_mode=args.parallel_mode,
        cost_bps=args.cost,
        storage=args.storage,
        show_progress_window=not args.no_progress_window,
        no_db_write=args.no_db_write,
        cache_dir=args.cache_dir,
        entry_mode=args.entry_mode,
    )


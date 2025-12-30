"""パラメータ最適化システム（Optuna使用、並列計算対応、時系列版）

時系列P/L計算を使用して、標準的なバックテスト指標を最適化します。
月次リバランス戦略として、ti→ti+1の月次リターン系列から指標を計算します。

【既存版との違い】
- 既存版（optimize.py）: 各リバランス日から最終日までの累積リターンを使用
- 時系列版（本ファイル）: 各リバランス日から次のリバランス日までの月次リターンを使用

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
from ..jobs.monthly_run import (
    StrategyParams,
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
)
from ..backtest.timeseries import calculate_timeseries_returns
from ..backtest.metrics import (
    calculate_sharpe_ratio,
    calculate_win_rate_timeseries,
)
from ..jobs.batch_monthly_run import get_monthly_rebalance_dates

# 既存のoptimize.pyから必要な関数をインポート
from .optimize import (
    EntryScoreParams,
    _entry_score_with_params,
    _select_portfolio_with_params,
    _run_single_backtest_portfolio_only,
    ProgressWindow,
)


def run_backtest_for_optimization_timeseries(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    enable_timing: bool = False,
) -> Dict[str, Any]:
    """
    最適化用のバックテスト実行（時系列版、並列計算対応）
    
    設計: 並列ワーカーは「ポートフォリオ選定だけ」を返し、
          保存後に時系列P/Lを計算する
    
    Args:
        rebalance_dates: リバランス日のリスト
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数、1で逐次実行）
        enable_timing: 時間計測を有効にするか
    
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
    
    # ポートフォリオを一括保存
    # 並列実行時の競合を避けるため、各試行で独立したデータベース接続を使用
    # SQLiteのWALモードにより、並列読み取りは可能だが、書き込みは順次実行される
    save_start_time = time.time()
    with connect_db() as conn:
        for rebalance_date, portfolio_df in portfolios.items():
            save_portfolio(conn, portfolio_df)
    save_end_time = time.time()
    timing_info["save_time"] = save_end_time - save_start_time
    
    # 時系列P/Lを計算
    if not rebalance_dates:
        raise RuntimeError("No rebalance dates provided")
    
    start_date = rebalance_dates[0]
    end_date = rebalance_dates[-1]
    
    timeseries_start_time = time.time()
    timeseries_data = calculate_timeseries_returns(
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
    
    return result


def objective_timeseries(
    trial: optuna.Trial,
    rebalance_dates: List[str],
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    enable_timing: bool = False,
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
    
    # EntryScoreParamsのパラメータ（既存版と同じ範囲）
    rsi_base = trial.suggest_float("rsi_base", 35.0, 60.0)
    rsi_max = trial.suggest_float("rsi_max", max(70.0, rsi_base + 5.0), 85.0)
    bb_z_base = trial.suggest_float("bb_z_base", -2.0, 0.0)
    bb_z_max = trial.suggest_float("bb_z_max", max(2.0, bb_z_base + 0.5), 3.5)
    bb_weight = trial.suggest_float("bb_weight", 0.45, 0.75)
    rsi_weight = 1.0 - bb_weight
    
    entry_params = EntryScoreParams(
        rsi_base=rsi_base,
        rsi_max=rsi_max,
        bb_z_base=bb_z_base,
        bb_z_max=bb_z_max,
        bb_weight=bb_weight,
        rsi_weight=rsi_weight,
    )
    
    # バックテスト実行（時系列版）
    perf = run_backtest_for_optimization_timeseries(
        rebalance_dates, strategy_params, entry_params, cost_bps=cost_bps, n_jobs=n_jobs, enable_timing=enable_timing
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
    bt_workers: int = 1,
    parallel_mode: str = "trial",
    cost_bps: float = 0.0,
    show_progress_window: bool = True,
    storage: Optional[str] = None,
):
    """
    最適化を実行（時系列版）
    
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
    
    # 進捗ウィンドウを作成
    progress_window = None
    if show_progress_window and TKINTER_AVAILABLE:
        progress_window = ProgressWindow(n_trials)
        progress_window.run()
        print("進捗ウィンドウを表示しました")
    
    # コールバック関数（既存版と同じ）
    def callback(study: optuna.Study, trial: optuna.Trial):
        """最適化の進捗を更新"""
        if progress_window:
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
    
    # 並列化設定
    cpu_count = mp.cpu_count()
    enable_timing = True  # 時間計測を有効化
    
    if parallel_mode == "trial":
        # trial並列のみ（推奨）
        if n_jobs == -1:
            # SQLiteの場合は控えめに（2-4）
            if storage.startswith("sqlite"):
                optuna_n_jobs = min(4, max(2, cpu_count // 2))
            else:
                optuna_n_jobs = min(8, max(1, cpu_count // 2))
        else:
            optuna_n_jobs = n_jobs
        backtest_n_jobs = bt_workers  # trial内は逐次または指定数
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
            trial, rebalance_dates, cost_bps, backtest_n_jobs, enable_timing=enable_timing
        ),
        n_trials=n_trials,
        show_progress_bar=True,
        n_jobs=optuna_n_jobs,
        callbacks=[callback] if progress_window else None,
    )
    
    # 完了したtrialの時間を収集
    for trial in study.trials:
        if trial.state == optuna.trial.TrialState.COMPLETE and trial.value is not None:
            # trialのシステム属性から時間を取得（可能な場合）
            # 実際の時間はobjective_timeseries内で計測されるため、
            # ここでは簡易的にtrial間の時間差を計算
            pass
    
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
    
    result_file = f"optimization_result_{study_name}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "best_value": study.best_value,
                "best_params": normalized_best_params,  # 正規化後の値を保存
                "best_params_raw": best_params_raw,  # 元の値を保存
                "n_trials": n_trials,
                "calculation_method": "timeseries",
                "description": "時系列P/L計算を使用した最適化",
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
    parser.add_argument("--bt-workers", type=int, default=1, help="trial内バックテストの並列数（デフォルト: 1）")
    parser.add_argument("--parallel-mode", type=str, default="trial", choices=["trial", "backtest", "hybrid"],
                        help="並列化モード: trial（推奨）、backtest、hybrid")
    parser.add_argument("--cost", type=float, default=0.0, help="取引コスト（bps）")
    parser.add_argument("--storage", type=str, help="Optunaストレージ（例: postgresql://user:pass@host/db、デフォルト: SQLite）")
    parser.add_argument("--no-progress-window", action="store_true", help="進捗ウィンドウを表示しない")
    
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
    )


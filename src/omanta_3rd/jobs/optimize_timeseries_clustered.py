"""パラメータ最適化システム（時系列版、Study A/B分割）

ChatGPTの提案に基づいて、パラメータ範囲を調整し、Study A/Bに分割して探索します。
- Study A: BB寄り・低ROE閾値（best系を深掘り）
- Study B: Value寄り・ROE閾値やや高め（Trial #63系を深掘り）

これにより、異なる局所解が混ざってTPEが迷う問題を軽減します。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, replace, fields
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Literal
import numpy as np
import pandas as pd
import optuna
from optuna.visualization import plot_optimization_history, plot_param_importances

# optimize_timeseries.pyから必要な関数をインポート
from .optimize_timeseries import (
    run_backtest_for_optimization_timeseries,
    objective_timeseries,
    _setup_blas_threads,
)
from ..jobs.monthly_run import StrategyParams
from ..jobs.optimize import EntryScoreParams
from ..jobs.batch_monthly_run import get_monthly_rebalance_dates
from ..backtest.feature_cache import FeatureCache


def objective_timeseries_clustered(
    trial: optuna.Trial,
    rebalance_dates: List[str],
    study_type: Literal["A", "B"],
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    enable_timing: bool = False,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
    save_to_db: bool = True,
) -> float:
    """
    Optunaの目的関数（時系列版、Study A/B分割対応）
    
    Args:
        trial: OptunaのTrialオブジェクト
        rebalance_dates: リバランス日のリスト
        study_type: "A"（BB寄り・低ROE閾値）または "B"（Value寄り・ROE閾値やや高め）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        enable_timing: 時間計測を有効にするか
        features_dict: 特徴量辞書（事前計算済み）
        prices_dict: 価格データ辞書（事前計算済み）
        save_to_db: ポートフォリオをDBに保存するか
    
    Returns:
        最適化対象の値（Sharpe_excess）
    """
    # StrategyParamsのパラメータ
    w_quality = trial.suggest_float("w_quality", 0.15, 0.35)
    w_growth = trial.suggest_float("w_growth", 0.05, 0.20)
    w_record_high = trial.suggest_float("w_record_high", 0.035, 0.065)  # 固定級
    w_size = trial.suggest_float("w_size", 0.10, 0.25)
    
    # Study A/Bで異なる範囲
    if study_type == "A":
        # Study A: BB寄り・低ROE閾値
        w_value = trial.suggest_float("w_value", 0.20, 0.35)
        w_forward_per = trial.suggest_float("w_forward_per", 0.40, 0.80)
        roe_min = trial.suggest_float("roe_min", 0.00, 0.08)
        bb_weight = trial.suggest_float("bb_weight", 0.55, 0.90)
    else:  # study_type == "B"
        # Study B: Value寄り・ROE閾値やや高め
        w_value = trial.suggest_float("w_value", 0.33, 0.50)
        w_forward_per = trial.suggest_float("w_forward_per", 0.30, 0.55)
        roe_min = trial.suggest_float("roe_min", 0.08, 0.15)
        bb_weight = trial.suggest_float("bb_weight", 0.40, 0.65)
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
    w_pbr = 1.0 - w_forward_per
    
    # 共通パラメータ（Study A/B共通）
    liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.16, 0.25)
    rsi_base = trial.suggest_float("rsi_base", 40.0, 58.0)
    rsi_max = trial.suggest_float("rsi_max", 76.5, 79.0)
    bb_z_base = trial.suggest_float("bb_z_base", -2.0, -0.8)
    bb_z_max = trial.suggest_float("bb_z_max", 2.0, 3.6)
    rsi_weight = 1.0 - bb_weight
    
    # StrategyParamsを構築
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
    
    # EntryScoreParamsを構築
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
    
    # 目的関数: Sharpe_excess（=IR）
    objective_value = perf["sharpe_ratio"]
    
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
            f"(data={timing['data_fetch_time']:.2f}s)"
        )
    
    print(log_msg)
    
    return objective_value


def main(
    start_date: str,
    end_date: str,
    study_type: Literal["A", "B"],
    n_trials: int = 200,
    study_name: Optional[str] = None,
    n_jobs: int = -1,
    bt_workers: int = -1,
    cost_bps: float = 0.0,
    storage: Optional[str] = None,
    no_db_write: bool = False,
    cache_dir: str = "cache/features",
):
    """
    最適化を実行（時系列版、Study A/B分割）
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        study_type: "A"（BB寄り・低ROE閾値）または "B"（Value寄り・ROE閾値やや高め）
        n_trials: 試行回数
        study_name: スタディ名（Noneの場合は自動生成）
        n_jobs: trial並列数（-1でCPU数）
        bt_workers: trial内バックテストの並列数
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        storage: Optunaストレージ（Noneの場合はSQLite）
        no_db_write: 最適化中にDBに書き込まない
        cache_dir: キャッシュディレクトリ
    """
    # BLASスレッドを1に設定
    _setup_blas_threads()
    
    study_type_desc = "BB寄り・低ROE閾値" if study_type == "A" else "Value寄り・ROE閾値やや高め"
    
    print("=" * 80)
    print(f"パラメータ最適化システム（時系列版、Study {study_type}: {study_type_desc}）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"取引コスト: {cost_bps} bps")
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
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates, 
        n_jobs=bt_workers if bt_workers > 0 else -1
    )
    print(f"[FeatureCache] 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # Optunaスタディを作成
    if study_name is None:
        study_name = f"optimization_timeseries_study{study_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # ストレージの設定
    if storage is None:
        storage = f"sqlite:///optuna_{study_name}.db"
    
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
    )
    
    # 並列化設定
    import multiprocessing as mp
    cpu_count = mp.cpu_count()
    
    if n_jobs == -1:
        if storage.startswith("sqlite"):
            optuna_n_jobs = min(4, max(2, min(4, cpu_count // 8)))
        else:
            optuna_n_jobs = min(8, max(1, cpu_count // 2))
    else:
        optuna_n_jobs = n_jobs
    
    if bt_workers == -1:
        available_cpus = max(1, cpu_count - optuna_n_jobs)
        backtest_n_jobs = max(1, min(len(rebalance_dates), available_cpus))
        if len(rebalance_dates) >= 4 and available_cpus >= 2:
            backtest_n_jobs = max(2, min(len(rebalance_dates), min(4, available_cpus)))
    else:
        backtest_n_jobs = bt_workers
    
    print("最適化を開始します...")
    print(f"CPU数: {cpu_count}")
    print(f"Optuna試行並列数: {optuna_n_jobs}")
    print(f"各試行内のバックテスト並列数: {backtest_n_jobs}")
    print()
    
    # 時間計測を有効化
    enable_timing = True
    
    # 最適化実行
    study.optimize(
        lambda trial: objective_timeseries_clustered(
            trial,
            rebalance_dates,
            study_type,
            cost_bps,
            backtest_n_jobs,
            enable_timing=enable_timing,
            features_dict=features_dict,
            prices_dict=prices_dict,
            save_to_db=not no_db_write,
        ),
        n_trials=n_trials,
        show_progress_bar=True,
        n_jobs=optuna_n_jobs,
    )
    
    # 結果表示
    print()
    print("=" * 80)
    print(f"【最適化結果 - Study {study_type}】")
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
                "study_type": study_type,
                "study_type_desc": study_type_desc,
                "best_value": study.best_value,
                "best_params": normalized_best_params,
                "best_params_raw": best_params_raw,
                "n_trials": n_trials,
                "calculation_method": "timeseries",
                "description": f"時系列P/L計算を使用した最適化（Study {study_type}: {study_type_desc}）",
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"結果を {result_file} に保存しました")
    
    # サマリーレポート
    print()
    print("=" * 80)
    print(f"【最適化サマリー - Study {study_type}】")
    print("=" * 80)
    
    completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if completed_trials:
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
    parser = argparse.ArgumentParser(description="パラメータ最適化（時系列版、Study A/B分割）")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--study-type", type=str, required=True, choices=["A", "B"],
                        help="Studyタイプ: A（BB寄り・低ROE閾値）または B（Value寄り・ROE閾値やや高め）")
    parser.add_argument("--n-trials", type=int, default=200, help="試行回数（デフォルト: 200）")
    parser.add_argument("--study-name", type=str, help="スタディ名")
    parser.add_argument("--n-jobs", type=int, default=-1, help="trial並列数（-1で自動）")
    parser.add_argument("--bt-workers", type=int, default=-1, help="trial内バックテストの並列数（-1で自動）")
    parser.add_argument("--cost", type=float, default=0.0, help="取引コスト（bps）")
    parser.add_argument("--storage", type=str, help="Optunaストレージ（デフォルト: SQLite）")
    parser.add_argument("--no-db-write", action="store_true", help="最適化中にDBに書き込まない")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="キャッシュディレクトリ")
    
    args = parser.parse_args()
    
    main(
        start_date=args.start,
        end_date=args.end,
        study_type=args.study_type,
        n_trials=args.n_trials,
        study_name=args.study_name,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
        cost_bps=args.cost,
        storage=args.storage,
        no_db_write=args.no_db_write,
        cache_dir=args.cache_dir,
    )








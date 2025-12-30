"""
信頼性向上型最適化（時系列版）

WFA/holdout評価を活用して、過学習を避け、より信頼性の高いパラメータを探索します。
複数のfoldで安定したパフォーマンスを示すパラメータを優先します。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import optuna
from dataclasses import replace

from ..infra.db import connect_db
from ..jobs.batch_monthly_run import get_monthly_rebalance_dates
from ..jobs.optimize_timeseries import (
    run_backtest_for_optimization_timeseries,
    objective_timeseries,
)
from ..jobs.monthly_run import StrategyParams
from ..jobs.optimize import EntryScoreParams
from ..backtest.timeseries import calculate_timeseries_returns
from ..backtest.eval_common import calculate_metrics_from_timeseries_data
from ..jobs.walk_forward_timeseries import (
    split_dates_into_folds,
    run_optimization_for_fold,
    run_backtest_with_fixed_params,
)


def objective_robust_timeseries(
    trial: optuna.Trial,
    all_dates: List[str],
    n_folds: int = 3,
    train_min_years: float = 2.0,
    buy_cost_bps: float = 0.0,
    sell_cost_bps: float = 0.0,
    stability_weight: float = 0.3,
) -> float:
    """
    信頼性向上型の目的関数（時系列版）
    
    WFAの複数foldで評価し、安定性を重視します。
    
    Args:
        trial: OptunaのTrialオブジェクト
        all_dates: 全リバランス日のリスト
        n_folds: fold数
        train_min_years: 最小train期間（年）
        buy_cost_bps: 購入コスト（bps）
        sell_cost_bps: 売却コスト（bps）
        stability_weight: 安定性の重み（0.0-1.0、デフォルト: 0.3）
    
    Returns:
        最適化対象の値（Sharpe_excess + 安定性ペナルティ）
    """
    # StrategyParamsのパラメータ
    w_quality = trial.suggest_float("w_quality", 0.15, 0.35)
    w_value = trial.suggest_float("w_value", 0.20, 0.40)
    w_growth = trial.suggest_float("w_growth", 0.05, 0.20)
    w_record_high = trial.suggest_float("w_record_high", 0.03, 0.15)
    w_size = trial.suggest_float("w_size", 0.10, 0.25)
    
    # 正規化
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
    
    # EntryScoreParamsのパラメータ
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
    
    # パラメータを辞書化
    best_params = {
        "w_quality": w_quality,
        "w_value": w_value,
        "w_growth": w_growth,
        "w_record_high": w_record_high,
        "w_size": w_size,
        "w_forward_per": w_forward_per,
        "w_pbr": w_pbr,
        "roe_min": roe_min,
        "liquidity_quantile_cut": liquidity_quantile_cut,
        "rsi_base": rsi_base,
        "rsi_max": rsi_max,
        "bb_z_base": bb_z_base,
        "bb_z_max": bb_z_max,
        "bb_weight": bb_weight,
        "rsi_weight": rsi_weight,
    }
    
    # WFAのfoldに分割
    folds = split_dates_into_folds(all_dates, n_folds, train_min_years)
    
    if not folds:
        return -999.0  # エラー時は低い値を返す
    
    # 各foldでtest期間のパフォーマンスを評価
    test_sharpes = []
    
    for fold_info in folds:
        test_dates = fold_info["test_dates"]
        
        # ポートフォリオを生成して保存
        try:
            run_backtest_for_optimization_timeseries(
                test_dates,
                strategy_params,
                entry_params,
                cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
                n_jobs=1,
            )
            
            # 時系列P/Lを計算
            start_date = test_dates[0]
            end_date = test_dates[-1]
            
            timeseries_data = calculate_timeseries_returns(
                start_date=start_date,
                end_date=end_date,
                rebalance_dates=test_dates,
                cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
                buy_cost_bps=buy_cost_bps,
                sell_cost_bps=sell_cost_bps,
            )
            
            # メトリクスを計算
            metrics = calculate_metrics_from_timeseries_data(timeseries_data)
            sharpe = metrics.get("sharpe_ratio")
            
            if sharpe is not None:
                test_sharpes.append(sharpe)
        except Exception as e:
            print(f"  Fold {fold_info['fold']} でエラー: {e}")
            continue
    
    if not test_sharpes:
        return -999.0  # エラー時は低い値を返す
    
    # 平均Sharpe_excess
    mean_sharpe = np.mean(test_sharpes)
    
    # 安定性指標（標準偏差の逆数、または最小値）
    if len(test_sharpes) > 1:
        std_sharpe = np.std(test_sharpes, ddof=1)
        # 安定性ペナルティ（標準偏差が大きいほどペナルティ）
        stability_penalty = -std_sharpe * stability_weight
    else:
        stability_penalty = 0.0
    
    # 最小Sharpe_excessも考慮（最悪ケースを避ける）
    min_sharpe = np.min(test_sharpes)
    min_penalty = -abs(min_sharpe) * (1.0 - stability_weight) * 0.1 if min_sharpe < 0 else 0.0
    
    # 目的関数: 平均Sharpe_excess + 安定性ペナルティ
    objective_value = mean_sharpe + stability_penalty + min_penalty
    
    print(
        f"[Trial {trial.number}] "
        f"objective={objective_value:.4f}, "
        f"mean_sharpe={mean_sharpe:.4f}, "
        f"std_sharpe={std_sharpe:.4f if len(test_sharpes) > 1 else 0.0:.4f}, "
        f"min_sharpe={min_sharpe:.4f}, "
        f"folds={len(test_sharpes)}"
    )
    
    return float(objective_value)


def run_robust_optimization(
    start_date: str,
    end_date: str,
    n_trials: int = 50,
    n_folds: int = 3,
    train_min_years: float = 2.0,
    buy_cost_bps: float = 0.0,
    sell_cost_bps: float = 0.0,
    stability_weight: float = 0.3,
    seed: Optional[int] = None,
    study_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    信頼性向上型最適化を実行
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        n_trials: 試行回数
        n_folds: WFAのfold数
        train_min_years: 最小train期間（年）
        buy_cost_bps: 購入コスト（bps）
        sell_cost_bps: 売却コスト（bps）
        stability_weight: 安定性の重み（0.0-1.0）
        seed: 乱数シード
        study_name: スタディ名（Noneの場合は自動生成）
    
    Returns:
        最適化結果の辞書
    """
    print("=" * 80)
    print("信頼性向上型最適化（時系列版）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"WFA Fold数: {n_folds}")
    print(f"最小Train期間: {train_min_years}年")
    print(f"取引コスト: buy={buy_cost_bps}bps, sell={sell_cost_bps}bps")
    print(f"安定性の重み: {stability_weight}")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    all_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"全リバランス日数: {len(all_dates)}")
    if not all_dates:
        return {"error": "リバランス日が見つかりませんでした"}
    
    # Optunaスタディを作成
    if study_name is None:
        study_name = f"robust_optimization_timeseries_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=f"sqlite:///optuna_{study_name}.db",
        load_if_exists=True,
    )
    
    if seed is not None:
        study.sampler = optuna.samplers.TPESampler(seed=seed)
    
    # 最適化実行
    print("最適化を開始します...")
    study.optimize(
        lambda trial: objective_robust_timeseries(
            trial,
            all_dates,
            n_folds=n_folds,
            train_min_years=train_min_years,
            buy_cost_bps=buy_cost_bps,
            sell_cost_bps=sell_cost_bps,
            stability_weight=stability_weight,
        ),
        n_trials=n_trials,
        show_progress_bar=True,
        n_jobs=1,  # 逐次実行（各試行内でWFAを実行するため）
    )
    
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
    
    return {
        "best_value": study.best_value,
        "best_params": normalized_best_params,
        "best_params_raw": best_params_raw,
        "n_trials": n_trials,
        "n_folds": n_folds,
        "stability_weight": stability_weight,
        "config": {
            "start_date": start_date,
            "end_date": end_date,
            "buy_cost_bps": buy_cost_bps,
            "sell_cost_bps": sell_cost_bps,
            "train_min_years": train_min_years,
        },
    }


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="信頼性向上型最適化（時系列版）")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--n-trials", type=int, default=50, help="試行回数（デフォルト: 50）")
    parser.add_argument("--folds", type=int, default=3, help="WFAのfold数（デフォルト: 3）")
    parser.add_argument("--train-min-years", type=float, default=2.0, help="最小Train期間（年、デフォルト: 2.0）")
    parser.add_argument("--buy-cost", type=float, default=0.0, help="購入コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--sell-cost", type=float, default=0.0, help="売却コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--stability-weight", type=float, default=0.3, help="安定性の重み（0.0-1.0、デフォルト: 0.3）")
    parser.add_argument("--seed", type=int, help="乱数シード")
    parser.add_argument("--study-name", type=str, help="スタディ名")
    parser.add_argument("--output-dir", type=str, default="artifacts", help="出力ディレクトリ（デフォルト: artifacts）")
    
    args = parser.parse_args()
    
    # 最適化を実行
    result = run_robust_optimization(
        start_date=args.start,
        end_date=args.end,
        n_trials=args.n_trials,
        n_folds=args.folds,
        train_min_years=args.train_min_years,
        buy_cost_bps=args.buy_cost,
        sell_cost_bps=args.sell_cost,
        stability_weight=args.stability_weight,
        seed=args.seed,
        study_name=args.study_name,
    )
    
    if "error" in result:
        print(f"❌ エラー: {result['error']}")
        sys.exit(1)
    
    # 出力ディレクトリを作成
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 結果をJSONに保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = output_dir / f"robust_optimization_result_{timestamp}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"結果を {result_file} に保存しました")


if __name__ == "__main__":
    main()


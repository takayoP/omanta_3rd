"""月次リバランス型で最適化したパラメータを長期保有型で再評価

月次リバランス型の最適化結果（Optunaスタディ）からパラメータを読み込み、
長期保有型のバックテストで評価します。

Usage:
    python evaluate_monthly_params_on_longterm.py --study-name optimization_timeseries_studyB_20251231_174014
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace, fields
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
import optuna

from src.omanta_3rd.jobs.longterm_run import StrategyParams
from src.omanta_3rd.jobs.optimize import EntryScoreParams
from src.omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
from src.omanta_3rd.jobs.optimize_longterm import (
    calculate_longterm_performance,
    split_rebalance_dates,
)
from src.omanta_3rd.backtest.feature_cache import FeatureCache


def load_study_params(study_name: str, storage: Optional[str] = None) -> Dict[str, Any]:
    """
    Optunaスタディから最良パラメータを読み込む
    
    Args:
        study_name: スタディ名
        storage: ストレージパス（Noneの場合は自動検出）
    
    Returns:
        最良パラメータの辞書
    """
    if storage is None:
        storage = f"sqlite:///optuna_{study_name}.db"
    
    study = optuna.load_study(study_name=study_name, storage=storage)
    
    best_params = study.best_params.copy()
    best_value = study.best_value
    
    print(f"スタディ: {study_name}")
    print(f"最良値: {best_value:.6f}")
    print(f"最良試行: {study.best_trial.number}")
    print()
    
    return best_params


def convert_params_to_strategy(
    params: Dict[str, Any],
) -> tuple[StrategyParams, EntryScoreParams]:
    """
    パラメータ辞書をStrategyParamsとEntryScoreParamsに変換
    
    Args:
        params: パラメータ辞書
    
    Returns:
        (strategy_params, entry_params) のタプル
    """
    # 重みを取得
    w_quality = params.get("w_quality", 0.15)
    w_value = params.get("w_value", 0.33)
    w_growth = params.get("w_growth", 0.11)
    w_record_high = params.get("w_record_high", 0.036)
    w_size = params.get("w_size", 0.24)
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    if total > 0:
        w_quality /= total
        w_value /= total
        w_growth /= total
        w_record_high /= total
        w_size /= total
    
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
        w_forward_per=params.get("w_forward_per", 0.50),
        w_pbr=1.0 - params.get("w_forward_per", 0.50),
        roe_min=params.get("roe_min", 0.08),
        liquidity_quantile_cut=params.get("liquidity_quantile_cut", 0.16),
    )
    
    # EntryScoreParamsを構築
    bb_weight = params.get("bb_weight", 0.50)
    entry_params = EntryScoreParams(
        rsi_base=params.get("rsi_base", 50.0),
        rsi_max=params.get("rsi_max", 77.0),
        bb_z_base=params.get("bb_z_base", -1.0),
        bb_z_max=params.get("bb_z_max", 3.0),
        bb_weight=bb_weight,
        rsi_weight=1.0 - bb_weight,
    )
    
    return strategy_params, entry_params


def evaluate_on_longterm(
    study_name: str,
    start_date: str,
    end_date: str,
    storage: Optional[str] = None,
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    cache_dir: str = "cache/features",
    train_ratio: float = 0.8,
    random_seed: int = 42,
    use_test_only: bool = False,
) -> Dict[str, Any]:
    """
    月次リバランス型のパラメータを長期保有型で評価
    
    Args:
        study_name: Optunaスタディ名
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        storage: ストレージパス（Noneの場合は自動検出）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        cache_dir: キャッシュディレクトリ
        train_ratio: 学習データの割合（use_test_only=Falseの場合のみ使用）
        random_seed: ランダムシード
        use_test_only: Trueの場合はテストデータのみで評価（デフォルト: False、全データで評価）
    
    Returns:
        評価結果の辞書
    """
    print("=" * 80)
    print("月次リバランス型パラメータの長期保有型評価")
    print("=" * 80)
    print(f"スタディ: {study_name}")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"取引コスト: {cost_bps} bps")
    print("=" * 80)
    print()
    
    # パラメータを読み込む
    print("パラメータを読み込み中...")
    params = load_study_params(study_name, storage)
    strategy_params, entry_params = convert_params_to_strategy(params)
    
    print("パラメータ:")
    print(f"  w_quality: {strategy_params.w_quality:.6f}")
    print(f"  w_value: {strategy_params.w_value:.6f}")
    print(f"  w_growth: {strategy_params.w_growth:.6f}")
    print(f"  w_record_high: {strategy_params.w_record_high:.6f}")
    print(f"  w_size: {strategy_params.w_size:.6f}")
    print(f"  w_forward_per: {strategy_params.w_forward_per:.6f}")
    print(f"  roe_min: {strategy_params.roe_min:.6f}")
    print(f"  bb_weight: {entry_params.bb_weight:.6f}")
    print()
    
    # リバランス日を取得
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return {}
    
    # 評価用のリバランス日を決定
    if use_test_only:
        # テストデータのみで評価
        _, test_dates = split_rebalance_dates(
            rebalance_dates,
            train_ratio=train_ratio,
            random_seed=random_seed,
        )
        eval_dates = test_dates
        print(f"テストデータのみで評価: {len(eval_dates)}日")
    else:
        # 全データで評価
        eval_dates = rebalance_dates
        print(f"全データで評価: {len(eval_dates)}日")
    
    print()
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築します...")
    print("=" * 80)
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        eval_dates, 
        n_jobs=n_jobs if n_jobs > 0 else -1
    )
    print(f"[FeatureCache] 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # 長期保有型で評価
    print("=" * 80)
    print("長期保有型で評価中...")
    print("=" * 80)
    perf = calculate_longterm_performance(
        eval_dates,
        strategy_params,
        entry_params,
        cost_bps=cost_bps,
        n_jobs=n_jobs,
        features_dict=features_dict,
        prices_dict=prices_dict,
    )
    
    print()
    print("=" * 80)
    print("【評価結果】")
    print("=" * 80)
    print(f"年率超過リターン（平均）: {perf['mean_annual_excess_return_pct']:.4f}%")
    print(f"年率超過リターン（中央値）: {perf['median_annual_excess_return_pct']:.4f}%")
    print(f"年率リターン（平均）: {perf['mean_annual_return_pct']:.4f}%")
    print(f"年率リターン（中央値）: {perf['median_annual_return_pct']:.4f}%")
    print(f"累積リターン: {perf['cumulative_return_pct']:.4f}%")
    print(f"累積超過リターン: {perf['mean_excess_return_pct']:.4f}%")
    print(f"勝率: {perf['win_rate']:.4f}")
    print(f"ポートフォリオ数: {perf['num_portfolios']}")
    print(f"平均保有期間: {perf['mean_holding_years']:.2f}年")
    print(f"全体期間: {perf['total_years']:.2f}年")
    print(f"最初のリバランス日: {perf['first_rebalance']}")
    print(f"最後の評価日: {perf['last_date']}")
    print("=" * 80)
    
    # 結果を辞書にまとめる
    result = {
        "study_name": study_name,
        "start_date": start_date,
        "end_date": end_date,
        "evaluation_mode": "test_only" if use_test_only else "all",
        "performance": perf,
        "parameters": {
            "w_quality": strategy_params.w_quality,
            "w_value": strategy_params.w_value,
            "w_growth": strategy_params.w_growth,
            "w_record_high": strategy_params.w_record_high,
            "w_size": strategy_params.w_size,
            "w_forward_per": strategy_params.w_forward_per,
            "roe_min": strategy_params.roe_min,
            "bb_weight": entry_params.bb_weight,
        },
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="月次リバランス型パラメータの長期保有型評価",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--study-name", type=str, required=True,
                       help="Optunaスタディ名（例: optimization_timeseries_studyB_20251231_174014）")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--storage", type=str, default=None,
                       help="Optunaストレージパス（Noneの場合は自動検出）")
    parser.add_argument("--cost-bps", type=float, default=0.0, help="取引コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--n-jobs", type=int, default=-1, help="並列実行数（-1でCPU数）")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="キャッシュディレクトリ")
    parser.add_argument("--train-ratio", type=float, default=0.8,
                       help="学習データの割合（--test-only使用時、デフォルト: 0.8）")
    parser.add_argument("--random-seed", type=int, default=42, help="ランダムシード（デフォルト: 42）")
    parser.add_argument("--test-only", action="store_true",
                       help="テストデータのみで評価（デフォルト: False、全データで評価）")
    parser.add_argument("--output", type=str, default=None,
                       help="結果をJSONファイルに保存（Noneの場合は保存しない）")
    
    args = parser.parse_args()
    
    result = evaluate_on_longterm(
        study_name=args.study_name,
        start_date=args.start,
        end_date=args.end,
        storage=args.storage,
        cost_bps=args.cost_bps,
        n_jobs=args.n_jobs,
        cache_dir=args.cache_dir,
        train_ratio=args.train_ratio,
        random_seed=args.random_seed,
        use_test_only=args.test_only,
    )
    
    # 結果を保存
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n結果を保存: {args.output}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


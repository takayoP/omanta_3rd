"""
分割seed耐性テスト

最良パラメータを固定し、データ分割のrandom_seedを変えて、
テストデータでのパフォーマンスの安定性を検証します。

Usage:
    python test_split_seed_robustness.py \
        --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json \
        --start 2020-01-01 \
        --end 2022-12-31 \
        --n-seeds 20 \
        --train-ratio 0.8
"""

import argparse
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, replace

from omanta_3rd.jobs.optimize_longterm import (
    split_rebalance_dates,
    calculate_longterm_performance,
    get_monthly_rebalance_dates,
    EntryScoreParams,
)
from omanta_3rd.jobs.monthly_run import StrategyParams
from omanta_3rd.backtest.feature_cache import FeatureCache


def load_best_params(json_file: str) -> Dict[str, Any]:
    """JSONファイルから最良パラメータを読み込む"""
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data["best_trial"]["params"]


def build_params_from_json(params_dict: Dict[str, float]) -> tuple[StrategyParams, EntryScoreParams]:
    """JSONから読み込んだパラメータからStrategyParamsとEntryScoreParamsを構築"""
    # 重みパラメータを正規化
    w_quality = params_dict["w_quality"]
    w_value = params_dict["w_value"]
    w_growth = params_dict["w_growth"]
    w_record_high = params_dict["w_record_high"]
    w_size = params_dict["w_size"]
    
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
        w_forward_per=params_dict["w_forward_per"],
        w_pbr=1.0 - params_dict["w_forward_per"],
        roe_min=params_dict["roe_min"],
        liquidity_quantile_cut=params_dict["liquidity_quantile_cut"],
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=params_dict["rsi_base"],
        rsi_max=params_dict["rsi_max"],
        bb_z_base=params_dict["bb_z_base"],
        bb_z_max=params_dict["bb_z_max"],
        bb_weight=params_dict["bb_weight"],
        rsi_weight=1.0 - params_dict["bb_weight"],
    )
    
    return strategy_params, entry_params


def test_seed_robustness(
    json_file: str,
    start_date: str,
    end_date: str,
    n_seeds: int = 20,
    train_ratio: float = 0.8,
    cost_bps: float = 0.0,
    cache_dir: str = "cache/features",
) -> Dict[str, Any]:
    """
    分割seed耐性テストを実行
    
    Args:
        json_file: 最良パラメータを含むJSONファイル
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        n_seeds: テストするseedの数
        train_ratio: 学習データの割合
        cost_bps: 取引コスト（bps）
        cache_dir: キャッシュディレクトリ
    
    Returns:
        テスト結果の辞書
    """
    print("=" * 80)
    print("分割seed耐性テスト")
    print("=" * 80)
    print(f"JSONファイル: {json_file}")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"テストseed数: {n_seeds}")
    print(f"学習/テスト分割: {train_ratio:.1%} / {1-train_ratio:.1%}")
    print()
    
    # 最良パラメータを読み込む
    print("最良パラメータを読み込みます...")
    best_params = load_best_params(json_file)
    strategy_params, entry_params = build_params_from_json(best_params)
    print("✓ パラメータ読み込み完了")
    print()
    
    # リバランス日を取得
    print("リバランス日を取得します...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"✓ リバランス日数: {len(rebalance_dates)}")
    print()
    
    # 特徴量キャッシュを構築
    print("特徴量キャッシュを構築します...")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates,
        n_jobs=-1
    )
    print(f"✓ 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # 各seedでテスト
    print("=" * 80)
    print("各seedでテストデータのパフォーマンスを計算します...")
    print("=" * 80)
    
    test_results = []  # 各seedでのテストデータの年率超過リターン（平均）
    seed_details = []  # 各seedの詳細情報（test_dates、結果など）
    
    for seed in range(1, n_seeds + 1):
        print(f"\n[Seed {seed}/{n_seeds}]")
        
        # データ分割
        train_dates, test_dates = split_rebalance_dates(
            rebalance_dates,
            train_ratio=train_ratio,
            random_seed=seed,
        )
        
        print(f"  学習データ: {len(train_dates)}日, テストデータ: {len(test_dates)}日")
        
        # テストデータでパフォーマンスを計算
        test_perf = calculate_longterm_performance(
            test_dates,
            strategy_params,
            entry_params,
            cost_bps=cost_bps,
            n_jobs=1,  # 並列化はしない（安定性重視）
            features_dict=features_dict,
            prices_dict=prices_dict,
        )
        
        test_mean_excess_ann = test_perf["mean_annual_excess_return_pct"]
        test_results.append(test_mean_excess_ann)
        
        # seedごとの詳細情報を保存
        seed_detail = {
            "seed": seed,
            "train_dates": train_dates,
            "test_dates": test_dates,
            "test_mean_annual_excess_return_pct": test_mean_excess_ann,
            "test_median_annual_excess_return_pct": test_perf.get("median_annual_excess_return_pct", None),
            "test_mean_annual_return_pct": test_perf.get("mean_annual_return_pct", None),
            "test_win_rate": test_perf.get("win_rate", None),
            "test_num_portfolios": test_perf.get("num_portfolios", None),
        }
        seed_details.append(seed_detail)
        
        print(f"  テストデータ年率超過リターン（平均）: {test_mean_excess_ann:.4f}%")
    
    # 統計を計算
    test_results_array = np.array(test_results)
    
    mean_val = np.mean(test_results_array)
    median_val = np.median(test_results_array)
    std_val = np.std(test_results_array)
    min_val = np.min(test_results_array)
    max_val = np.max(test_results_array)
    
    # 下位10%を計算
    percentile_10 = np.percentile(test_results_array, 10)
    percentile_25 = np.percentile(test_results_array, 25)
    percentile_75 = np.percentile(test_results_array, 75)
    percentile_90 = np.percentile(test_results_array, 90)
    
    # 正の値の割合
    positive_ratio = np.sum(test_results_array > 0) / len(test_results_array)
    
    # 結果を表示
    print()
    print("=" * 80)
    print("【分割seed耐性テスト結果】")
    print("=" * 80)
    print(f"テストseed数: {n_seeds}")
    print(f"最良パラメータ（固定）: {json_file}")
    print()
    print("テストデータ年率超過リターン（平均）の分布:")
    print(f"  平均: {mean_val:.4f}%")
    print(f"  中央値: {median_val:.4f}%")
    print(f"  標準偏差: {std_val:.4f}%")
    print(f"  最小値: {min_val:.4f}%")
    print(f"  最大値: {max_val:.4f}%")
    print()
    print("パーセンタイル:")
    print(f"  下位10%: {percentile_10:.4f}%")
    print(f"  下位25%: {percentile_25:.4f}%")
    print(f"  上位25%: {percentile_75:.4f}%")
    print(f"  上位10%: {percentile_90:.4f}%")
    print()
    print(f"正の値の割合: {positive_ratio:.1%} ({np.sum(test_results_array > 0)}/{n_seeds})")
    print()
    
    # 評価
    print("【評価】")
    if median_val > 0 and percentile_10 > -1.0:  # 中央値がプラス、下位10%が-1%以上
        print("✅ 合格: 中央値がプラス、下位10%も極端にマイナスになりにくい")
        print("   → 採用候補として信頼度が高い")
    elif median_val > 0:
        print("⚠️  要検討: 中央値はプラスだが、下位10%が-1%未満")
        print("   → seedによっては大きくマイナスになる可能性がある")
    else:
        print("❌ 不合格: 中央値がマイナス")
        print("   → seedによって結果が大きく変動する可能性が高い")
    print()
    
    # ワーストseedを特定
    worst_seed_idx = np.argmin(test_results_array)
    worst_seed_detail = seed_details[worst_seed_idx]
    
    # ベストseedを特定
    best_seed_idx = np.argmax(test_results_array)
    best_seed_detail = seed_details[best_seed_idx]
    
    print("【ワーストseedの詳細】")
    print(f"  Seed: {worst_seed_detail['seed']}")
    print(f"  テストデータ年率超過リターン（平均）: {worst_seed_detail['test_mean_annual_excess_return_pct']:.4f}%")
    print(f"  テストデータ日数: {len(worst_seed_detail['test_dates'])}日")
    print(f"  テストデータ: {worst_seed_detail['test_dates']}")
    
    # テストデータの年別分布を確認
    from datetime import datetime as dt
    test_years = {}
    for date_str in worst_seed_detail['test_dates']:
        year = dt.strptime(date_str, "%Y-%m-%d").year
        test_years[year] = test_years.get(year, 0) + 1
    
    print(f"  テストデータの年別分布:")
    for year in sorted(test_years.keys()):
        print(f"    {year}年: {test_years[year]}日")
    print()
    
    # 結果を辞書にまとめる
    result = {
        "json_file": json_file,
        "start_date": start_date,
        "end_date": end_date,
        "n_seeds": n_seeds,
        "train_ratio": train_ratio,
        "test_results": test_results,
        "statistics": {
            "mean": float(mean_val),
            "median": float(median_val),
            "std": float(std_val),
            "min": float(min_val),
            "max": float(max_val),
            "percentile_10": float(percentile_10),
            "percentile_25": float(percentile_25),
            "percentile_75": float(percentile_75),
            "percentile_90": float(percentile_90),
            "positive_ratio": float(positive_ratio),
        },
        "seed_details": seed_details,
        "worst_seed": worst_seed_detail,
        "best_seed": best_seed_detail,
    }
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="分割seed耐性テスト"
    )
    parser.add_argument(
        "--json-file",
        type=str,
        required=True,
        help="最良パラメータを含むJSONファイル",
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="終了日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--n-seeds",
        type=int,
        default=20,
        help="テストするseedの数（デフォルト: 20）",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="学習データの割合（デフォルト: 0.8）",
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=0.0,
        help="取引コスト（bps、デフォルト: 0.0）",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="cache/features",
        help="キャッシュディレクトリ（デフォルト: cache/features）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="結果をJSONファイルに保存（Noneの場合は保存しない）",
    )
    
    args = parser.parse_args()
    
    result = test_seed_robustness(
        json_file=args.json_file,
        start_date=args.start,
        end_date=args.end,
        n_seeds=args.n_seeds,
        train_ratio=args.train_ratio,
        cost_bps=args.cost_bps,
        cache_dir=args.cache_dir,
    )
    
    # 結果をJSONファイルに保存
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"結果を保存しました: {args.output}")


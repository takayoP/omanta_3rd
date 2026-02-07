"""
アブレーション分析（Core/Entryの犯人特定）

Coreスコアのみ、Entryスコアのみ、両方を使用した場合のパフォーマンスを比較します。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.jobs.optimize_longterm import calculate_longterm_performance
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates


def load_params_from_json(json_path: Path) -> dict:
    """最適化結果JSONからパラメータを読み込む"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    normalized_params = data.get("normalized_params", {})
    
    return {
        "normalized_params": normalized_params,
    }


def create_strategy_params(normalized_params: dict, use_entry_score: bool = True) -> StrategyParams:
    """normalized_paramsからStrategyParamsを作成"""
    return StrategyParams(
        w_quality=normalized_params.get("w_quality", 0.0),
        w_value=normalized_params.get("w_value", 0.0),
        w_growth=normalized_params.get("w_growth", 0.0),
        w_record_high=normalized_params.get("w_record_high", 0.0),
        w_size=normalized_params.get("w_size", 0.0),
        w_forward_per=normalized_params.get("w_forward_per", 0.0),
        roe_min=normalized_params.get("roe_min", 0.0),
        liquidity_quantile_cut=normalized_params.get("liquidity_quantile_cut", 0.0),
        use_entry_score=use_entry_score,  # アブレーション用
    )


def create_entry_params(normalized_params: dict) -> EntryScoreParams:
    """normalized_paramsからEntryScoreParamsを作成"""
    return EntryScoreParams(
        rsi_base=normalized_params.get("rsi_base", 50.0),
        rsi_max=normalized_params.get("rsi_max", 75.0),
        bb_z_base=normalized_params.get("bb_z_base", -1.0),
        bb_z_max=normalized_params.get("bb_z_max", 2.0),
        bb_weight=normalized_params.get("bb_weight", 0.5),
        rsi_weight=normalized_params.get("rsi_weight", 0.5),
        rsi_min_width=normalized_params.get("rsi_min_width", 10.0),
        bb_z_min_width=normalized_params.get("bb_z_min_width", 0.5),
    )


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="アブレーション分析（Core/Entryの犯人特定）")
    parser.add_argument("--params-json", type=str, required=True,
                       help="最適化結果JSONファイルのパス")
    parser.add_argument("--test-periods", type=str, default="2022,2021",
                       help="評価する期間（カンマ区切り、デフォルト: 2022,2021）")
    parser.add_argument("--cost-bps", type=float, default=25.0,
                       help="取引コスト（bps、デフォルト: 25.0）")
    parser.add_argument("--horizon-months", type=int, default=24,
                       help="投資ホライズン（月数、デフォルト: 24）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("アブレーション分析（Core/Entryの犯人特定）")
    print("=" * 80)
    print()
    print("Coreスコアのみ、Entryスコアのみ、両方を使用した場合の")
    print("パフォーマンスを比較します。")
    print()
    
    # パラメータを読み込む
    json_path = Path(args.params_json)
    if not json_path.exists():
        print(f"❌ エラー: {json_path} が見つかりません")
        return 1
    
    print(f"📄 パラメータを読み込み中: {json_path}")
    data = load_params_from_json(json_path)
    normalized_params = data["normalized_params"]
    
    # 期間の定義
    test_periods_config = {
        "2022": {
            "test_start_date": "2022-01-31",
            "test_end_date": "2022-12-30",
            "as_of_date": "2024-12-31",
        },
        "2021": {
            "test_start_date": "2021-01-31",
            "test_end_date": "2021-12-30",
            "as_of_date": "2023-12-31",
        },
    }
    
    test_periods = [p.strip() for p in args.test_periods.split(",")]
    
    # 各期間のtest_datesを取得
    test_dates_dict = {}
    max_as_of_date = None
    
    for period in test_periods:
        if period not in test_periods_config:
            print(f"❌ エラー: 期間 '{period}' は定義されていません")
            print(f"   利用可能な期間: {list(test_periods_config.keys())}")
            return 1
        
        config = test_periods_config[period]
        test_dates = get_monthly_rebalance_dates(config["test_start_date"], config["test_end_date"])
        test_dates_dict[period] = {
            "test_dates": test_dates,
            "as_of_date": config["as_of_date"],
        }
        
        if max_as_of_date is None or config["as_of_date"] > max_as_of_date:
            max_as_of_date = config["as_of_date"]
    
    print(f"📅 評価期間: {', '.join(test_periods)}")
    print(f"💰 コスト: {args.cost_bps} bps")
    print()
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    
    all_rebalance_dates = []
    for period_data in test_dates_dict.values():
        all_rebalance_dates.extend(period_data["test_dates"])
    
    start_date_for_features = min([d["test_dates"][0] for d in test_dates_dict.values()])
    all_rebalance_dates.extend(get_monthly_rebalance_dates(start_date_for_features, max_as_of_date))
    all_rebalance_dates = sorted(list(set(all_rebalance_dates)))
    
    features_dict, prices_dict = feature_cache.warm(
        all_rebalance_dates,
        n_jobs=4,
        force_rebuild=False,
    )
    print(f"   特徴量: {len(features_dict)}日分")
    print(f"   価格データ: {len(prices_dict)}日分")
    print()
    
    # アブレーション: 3つのバリエーション
    variants = [
        ("both", True, "Core + Entry（ベースライン）"),
        ("core_only", False, "Coreスコアのみ"),
        ("entry_only", True, "Entryスコアのみ（注意: Coreスコアでプール選定）"),
    ]
    
    # 各期間で評価
    print("=" * 80)
    print("各バリエーションで評価中...")
    print("=" * 80)
    print()
    
    all_results = {}  # {period: {variant: results}}
    
    for period in test_periods:
        period_data = test_dates_dict[period]
        test_dates = period_data["test_dates"]
        as_of_date = period_data["as_of_date"]
        
        print(f"【期間: {period}】")
        print("-" * 80)
        
        period_results = {}
        
        for variant_key, use_entry_score, variant_name in variants:
            print(f"  バリエーション: {variant_name}")
            
            # パラメータを作成
            strategy_params = create_strategy_params(normalized_params, use_entry_score=use_entry_score)
            entry_params = create_entry_params(normalized_params)
            
            perf = calculate_longterm_performance(
                rebalance_dates=test_dates,
                strategy_params=strategy_params,
                entry_params=entry_params,
                cost_bps=args.cost_bps,
                n_jobs=4,
                features_dict=features_dict,
                prices_dict=prices_dict,
                horizon_months=args.horizon_months,
                require_full_horizon=True,
                as_of_date=as_of_date,
            )
            
            mean_excess = perf["mean_annual_excess_return_pct"]
            median_excess = perf.get("median_annual_excess_return_pct", 0.0)
            win_rate = perf["win_rate"]
            
            period_results[variant_key] = {
                "mean_excess": mean_excess,
                "median_excess": median_excess,
                "win_rate": win_rate,
            }
            
            print(f"    平均超過リターン: {mean_excess:.4f}%")
            print(f"    中央値超過リターン: {median_excess:.4f}%")
            print(f"    勝率: {win_rate:.4f}")
            print()
        
        all_results[period] = period_results
    
    # アブレーション結果の比較
    print("=" * 80)
    print("【アブレーション結果の比較】")
    print("=" * 80)
    print()
    
    for period in test_periods:
        if period not in all_results:
            continue
        
        period_results = all_results[period]
        baseline = period_results.get("both", {})
        core_only = period_results.get("core_only", {})
        entry_only = period_results.get("entry_only", {})
        
        print(f"【期間: {period}】")
        print("-" * 80)
        print(f"{'バリエーション':<30} {'平均超過':<15} {'中央値超過':<15} {'勝率':<15}")
        print("-" * 80)
        
        if baseline:
            print(f"{'Core + Entry（ベースライン）':<30} {baseline['mean_excess']:<15.4f} {baseline['median_excess']:<15.4f} {baseline['win_rate']:<15.4f}")
        
        if core_only:
            diff_mean = core_only['mean_excess'] - baseline['mean_excess'] if baseline else 0.0
            diff_median = core_only['median_excess'] - baseline['median_excess'] if baseline else 0.0
            diff_win = core_only['win_rate'] - baseline['win_rate'] if baseline else 0.0
            print(f"{'Coreスコアのみ':<30} {core_only['mean_excess']:<15.4f} {core_only['median_excess']:<15.4f} {core_only['win_rate']:<15.4f}")
            print(f"{'  → 差分（vs ベースライン）':<30} {diff_mean:<15.4f} {diff_median:<15.4f} {diff_win:<15.4f}")
        
        if entry_only:
            diff_mean = entry_only['mean_excess'] - baseline['mean_excess'] if baseline else 0.0
            diff_median = entry_only['median_excess'] - baseline['median_excess'] if baseline else 0.0
            diff_win = entry_only['win_rate'] - baseline['win_rate'] if baseline else 0.0
            print(f"{'Entryスコアのみ':<30} {entry_only['mean_excess']:<15.4f} {entry_only['median_excess']:<15.4f} {entry_only['win_rate']:<15.4f}")
            print(f"{'  → 差分（vs ベースライン）':<30} {diff_mean:<15.4f} {diff_median:<15.4f} {diff_win:<15.4f}")
        
        print()
    
    # 結論
    print("=" * 80)
    print("【結論】")
    print("=" * 80)
    print()
    
    if "2022" in all_results and "2021" in all_results:
        results_2022 = all_results["2022"]
        results_2021 = all_results["2021"]
        
        baseline_2022 = results_2022.get("both", {})
        baseline_2021 = results_2021.get("both", {})
        core_only_2022 = results_2022.get("core_only", {})
        core_only_2021 = results_2021.get("core_only", {})
        entry_only_2022 = results_2022.get("entry_only", {})
        entry_only_2021 = results_2021.get("entry_only", {})
        
        if baseline_2022 and baseline_2021:
            # Coreスコアのみの影響
            core_impact_2022 = core_only_2022.get('mean_excess', 0.0) - baseline_2022.get('mean_excess', 0.0) if core_only_2022 else 0.0
            core_impact_2021 = core_only_2021.get('mean_excess', 0.0) - baseline_2021.get('mean_excess', 0.0) if core_only_2021 else 0.0
            
            # Entryスコアのみの影響
            entry_impact_2022 = entry_only_2022.get('mean_excess', 0.0) - baseline_2022.get('mean_excess', 0.0) if entry_only_2022 else 0.0
            entry_impact_2021 = entry_only_2021.get('mean_excess', 0.0) - baseline_2021.get('mean_excess', 0.0) if entry_only_2021 else 0.0
            
            print("Coreスコアのみの影響:")
            print(f"  2022: {core_impact_2022:.4f}%ポイント")
            print(f"  2021: {core_impact_2021:.4f}%ポイント")
            print()
            
            print("Entryスコアのみの影響:")
            print(f"  2022: {entry_impact_2022:.4f}%ポイント")
            print(f"  2021: {entry_impact_2021:.4f}%ポイント")
            print()
            
            # 犯人特定
            if abs(entry_impact_2021) > abs(core_impact_2021):
                print("⚠️  Entryスコアが2021期間の悪化の主因である可能性が高い")
            elif abs(core_impact_2021) > abs(entry_impact_2021):
                print("⚠️  Coreスコアが2021期間の悪化の主因である可能性が高い")
            else:
                print("⚠️  Core/Entryの両方が影響している可能性がある")
    
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

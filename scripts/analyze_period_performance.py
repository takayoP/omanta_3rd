"""
期間パフォーマンスの詳細分析

2021と2022の期間で、ポートフォリオ特性を比較し、Core/Entryの犯人特定を行います。
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


def create_strategy_params(normalized_params: dict) -> StrategyParams:
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
    
    parser = argparse.ArgumentParser(description="期間パフォーマンスの詳細分析")
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
    print("期間パフォーマンスの詳細分析")
    print("=" * 80)
    print()
    print("2021と2022の期間で、ポートフォリオ特性を比較し、")
    print("Core/Entryの犯人特定を行います。")
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
        "2020": {
            "test_start_date": "2020-01-31",
            "test_end_date": "2020-12-30",
            "as_of_date": "2022-12-30",
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
    
    # パラメータを作成
    strategy_params = create_strategy_params(normalized_params)
    entry_params = create_entry_params(normalized_params)
    
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
    
    # 各期間で評価
    print("=" * 80)
    print("各期間で評価中...")
    print("=" * 80)
    print()
    
    period_results = {}
    
    for period in test_periods:
        period_data = test_dates_dict[period]
        test_dates = period_data["test_dates"]
        as_of_date = period_data["as_of_date"]
        
        print(f"【期間: {period}】")
        print("-" * 80)
        
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
        num_portfolios = perf["num_portfolios"]
        annual_excess_returns = perf.get("annual_excess_returns_list", [])
        excess_by_rebalance = perf.get("annual_excess_by_rebalance", [])
        
        period_results[period] = {
            "mean_excess": mean_excess,
            "median_excess": median_excess,
            "win_rate": win_rate,
            "num_portfolios": num_portfolios,
            "annual_excess_returns": annual_excess_returns,
            "excess_by_rebalance": excess_by_rebalance,
        }
        
        print(f"  年率超過リターン（平均）: {mean_excess:.4f}%")
        print(f"  年率超過リターン（中央値）: {median_excess:.4f}%")
        print(f"  勝率: {win_rate:.4f}")
        print(f"  ポートフォリオ数: {num_portfolios}")
        
        if annual_excess_returns:
            print(f"  個別リターン: {[f'{r:.2f}%' for r in annual_excess_returns]}")
            print(f"  最小リターン: {min(annual_excess_returns):.4f}%")
            print(f"  最大リターン: {max(annual_excess_returns):.4f}%")
        
        # リバランス日別の月次超過リターン一覧（寄与分解用）
        if excess_by_rebalance:
            print("  【月次（リバランス日別）超過リターン一覧】")
            print(f"  {'リバランス日':<12} {'年率超過(%)':<12}")
            for rd, ret in excess_by_rebalance:
                print(f"  {rd:<12} {ret:>10.2f}%")
        
        print()
    
    # 期間比較
    print("=" * 80)
    print("【期間比較】")
    print("=" * 80)
    print()
    
    if len(period_results) >= 2:
        period_2022 = period_results.get("2022", {})
        period_2021 = period_results.get("2021", {})
        
        if period_2022 and period_2021:
            print(f"{'指標':<30} {'2022':<15} {'2021':<15} {'差分':<15}")
            print("-" * 80)
            
            mean_diff = period_2022["mean_excess"] - period_2021["mean_excess"]
            median_diff = period_2022["median_excess"] - period_2021["median_excess"]
            win_rate_diff = period_2022["win_rate"] - period_2021["win_rate"]
            
            print(f"{'平均超過リターン':<30} {period_2022['mean_excess']:<15.4f} {period_2021['mean_excess']:<15.4f} {mean_diff:<15.4f}")
            print(f"{'中央値超過リターン':<30} {period_2022['median_excess']:<15.4f} {period_2021['median_excess']:<15.4f} {median_diff:<15.4f}")
            print(f"{'勝率':<30} {period_2022['win_rate']:<15.4f} {period_2021['win_rate']:<15.4f} {win_rate_diff:<15.4f}")
            print()
            
            # 個別リターンの分析
            returns_2022 = period_2022.get("annual_excess_returns", [])
            returns_2021 = period_2021.get("annual_excess_returns", [])
            
            if returns_2022 and returns_2021:
                print("【個別リターンの分析】")
                print()
                print(f"2022: 最小={min(returns_2022):.2f}%, 最大={max(returns_2022):.2f}%, 平均={np.mean(returns_2022):.2f}%")
                print(f"2021: 最小={min(returns_2021):.2f}%, 最大={max(returns_2021):.2f}%, 平均={np.mean(returns_2021):.2f}%")
                print()
                
                # 負のリターンの数
                negative_2022 = sum(1 for r in returns_2022 if r < 0)
                negative_2021 = sum(1 for r in returns_2021 if r < 0)
                
                print(f"負のリターンの数:")
                print(f"  2022: {negative_2022}/{len(returns_2022)} ({negative_2022/len(returns_2022)*100:.1f}%)")
                print(f"  2021: {negative_2021}/{len(returns_2021)} ({negative_2021/len(returns_2021)*100:.1f}%)")
                print()
                
                if negative_2021 > negative_2022:
                    print("⚠️  2021期間で負のリターンが多くなっています")
                    print("   これは「1〜2本の大事故」ではなく、「恒常的に弱い」可能性が高いです")
    
    print()
    print("=" * 80)
    print("【次のステップ】")
    print("=" * 80)
    print()
    print("この分析結果に基づいて、以下を実施してください:")
    print("1. ポートフォリオ特性の比較（選定銘柄数、業種比率、時価総額など）")
    print("2. アブレーション（Core/Entryの犯人特定）")
    print("3. 2020期間での検証（2021だけ特異点なのか判定）")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

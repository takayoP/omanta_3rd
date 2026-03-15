"""
コスト適用の検証

コストが本当に効いているか確認するため、turnover、cost_deduction、gross_return/net_returnの差分を確認します。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
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
    test_dates = data.get("test_dates", [])
    
    return {
        "normalized_params": normalized_params,
        "test_dates": test_dates,
        "as_of_date": data.get("end_date"),
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
    
    parser = argparse.ArgumentParser(description="コスト適用の検証")
    parser.add_argument("--params-json", type=str, required=True,
                       help="最適化結果JSONファイルのパス")
    parser.add_argument("--cost-bps-list", type=str, default="0,10,25,50",
                       help="評価するコストのリスト（カンマ区切り、デフォルト: 0,10,25,50）")
    parser.add_argument("--as-of-date", type=str, default=None,
                       help="評価の打ち切り日（YYYY-MM-DD、Noneの場合はJSONから取得）")
    parser.add_argument("--horizon-months", type=int, default=24,
                       help="投資ホライズン（月数、デフォルト: 24）")
    parser.add_argument("--test-period", type=str, default="2022",
                       help="検証する期間（2022または2021、デフォルト: 2022）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("コスト適用の検証")
    print("=" * 80)
    print()
    print("コストが本当に効いているか確認するため、")
    print("turnover、cost_deduction、gross_return/net_returnの差分を確認します。")
    print()
    
    # パラメータを読み込む
    json_path = Path(args.params_json)
    if not json_path.exists():
        print(f"❌ エラー: {json_path} が見つかりません")
        return 1
    
    print(f"📄 パラメータを読み込み中: {json_path}")
    data = load_params_from_json(json_path)
    normalized_params = data["normalized_params"]
    
    # 期間の設定
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
    
    if args.test_period not in test_periods_config:
        print(f"❌ エラー: 期間 '{args.test_period}' は定義されていません")
        print(f"   利用可能な期間: {list(test_periods_config.keys())}")
        return 1
    
    config = test_periods_config[args.test_period]
    test_dates = get_monthly_rebalance_dates(config["test_start_date"], config["test_end_date"])
    as_of_date = args.as_of_date or config["as_of_date"]
    
    print(f"   Test期間: {args.test_period} ({len(test_dates)}日分)")
    print(f"   as_of_date: {as_of_date}")
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
    
    start_date_for_features = test_dates[0]
    all_rebalance_dates = get_monthly_rebalance_dates(start_date_for_features, as_of_date)
    
    features_dict, prices_dict = feature_cache.warm(
        all_rebalance_dates,
        n_jobs=4,
        force_rebuild=False,
    )
    print(f"   特徴量: {len(features_dict)}日分")
    print(f"   価格データ: {len(prices_dict)}日分")
    print()
    
    # コストのリストを解析
    cost_bps_list = [float(x.strip()) for x in args.cost_bps_list.split(",")]
    
    # 各コストで評価
    print("=" * 80)
    print("各コストで評価中...")
    print("=" * 80)
    print()
    
    results = []
    
    for cost_bps in cost_bps_list:
        print(f"【cost_bps = {cost_bps} bps】")
        print("-" * 80)
        
        perf = calculate_longterm_performance(
            rebalance_dates=test_dates,
            strategy_params=strategy_params,
            entry_params=entry_params,
            cost_bps=cost_bps,
            n_jobs=4,
            features_dict=features_dict,
            prices_dict=prices_dict,
            horizon_months=args.horizon_months,
            require_full_horizon=True,
            as_of_date=as_of_date,
            return_per_portfolio_details=True,
        )
        
        mean_excess = perf["mean_annual_excess_return_pct"]
        median_excess = perf.get("median_annual_excess_return_pct", 0.0)
        win_rate = perf["win_rate"]
        num_portfolios = perf["num_portfolios"]
        per_portfolio = perf.get("per_portfolio_details", [])
        
        print(f"  年率超過リターン（平均）: {mean_excess:.4f}%")
        print(f"  年率超過リターン（中央値）: {median_excess:.4f}%")
        print(f"  勝率: {win_rate:.4f}")
        print(f"  ポートフォリオ数: {num_portfolios}")
        
        # 1ポートフォリオ単位のgross/net/cost
        if per_portfolio:
            print("  【1ポートフォリオ単位: gross vs net】")
            print(f"  {'リバランス日':<12} {'累積gross%':>10} {'累積net%':>10} {'cost%':>8} {'年率gross%':>10} {'年率net%':>10}")
            for p in per_portfolio[:5]:  # 最初の5件
                print(f"  {p['rebalance_date']:<12} {p['gross_return_pct']:>10.2f} {p['net_return_pct']:>10.2f} "
                      f"{p['total_cost_pct']:>8.2f} {p.get('annualized_gross_pct') or 0:>10.2f} "
                      f"{p.get('annualized_net_pct') or 0:>10.2f}")
            if len(per_portfolio) > 5:
                print(f"  ... 他 {len(per_portfolio) - 5} 件")
            # サマリ
            gross_net_diffs = [p["gross_return_pct"] - p["net_return_pct"] for p in per_portfolio]
            avg_diff = np.mean(gross_net_diffs) if gross_net_diffs else 0.0
            print(f"  平均(gross-net)差分: {avg_diff:.4f}%")
        print()
        
        results.append({
            "cost_bps": cost_bps,
            "mean_annual_excess_return_pct": mean_excess,
            "median_annual_excess_return_pct": median_excess,
            "win_rate": win_rate,
            "num_portfolios": num_portfolios,
            "per_portfolio_details": per_portfolio,
        })
    
    # コスト影響の分析
    print("=" * 80)
    print("【コスト影響の分析】")
    print("=" * 80)
    print()
    
    print(f"{'cost_bps':<10} {'平均超過%':<12} {'中央値超過%':<12} {'勝率':<10}")
    print("-" * 50)
    for r in results:
        print(f"{r['cost_bps']:<10.0f} {r['mean_annual_excess_return_pct']:<12.4f} "
              f"{r['median_annual_excess_return_pct']:<12.4f} {r['win_rate']:<10.4f}")
    
    # 0bps vs 25bps vs 50bps の差分
    result_0 = next((r for r in results if r["cost_bps"] == 0), None)
    result_25 = next((r for r in results if r["cost_bps"] == 25), None)
    result_50 = next((r for r in results if r["cost_bps"] == 50), None)
    
    if result_0 and result_25:
        mean_diff_25 = result_0["mean_annual_excess_return_pct"] - result_25["mean_annual_excess_return_pct"]
        median_diff_25 = result_0["median_annual_excess_return_pct"] - result_25["median_annual_excess_return_pct"]
        print()
        print("0bps vs 25bps:")
        print(f"  平均超過の差分: {mean_diff_25:.4f}%ポイント")
        print(f"  中央値超過の差分: {median_diff_25:.4f}%ポイント")
        
        # 1ポートフォリオ単位のgross-net確認
        pp_25 = result_25.get("per_portfolio_details", [])
        if pp_25:
            avg_cost_pct = np.mean([p["total_cost_pct"] for p in pp_25])
            gross_net_diffs = [p["gross_return_pct"] - p["net_return_pct"] for p in pp_25]
            avg_gross_net_diff = np.mean(gross_net_diffs)
            print(f"  25bps時の平均cost控除（累積）: {avg_cost_pct:.4f}%")
            print(f"  25bps時の平均(gross-net): {avg_gross_net_diff:.4f}%")
        
        print()
        if abs(mean_diff_25) < 0.01 and abs(median_diff_25) < 0.01:
            print("❌ 判定: コストが効いていない可能性が高い")
            print("   0bpsと25bpsの結果がほぼ同じです。")
            print("   確認: turnover、cost適用箇所、gross/net計算")
        else:
            print("✅ 判定: コストは正常に適用されている")
    
    if result_0 and result_50:
        mean_diff_50 = result_0["mean_annual_excess_return_pct"] - result_50["mean_annual_excess_return_pct"]
        print()
        print("0bps vs 50bps: 平均超過の差分: {:.4f}%ポイント".format(mean_diff_50))
    
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

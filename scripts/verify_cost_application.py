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
        )
        
        mean_excess = perf["mean_annual_excess_return_pct"]
        median_excess = perf.get("median_annual_excess_return_pct", 0.0)
        win_rate = perf["win_rate"]
        num_portfolios = perf["num_portfolios"]
        
        # コスト情報を取得（デバッグ用）
        cost_info_list = []
        if cost_bps > 0:
            # 長期保有型の場合、コスト = 購入コスト + 売却コスト
            # 購入コスト = cost_bps / 100.0 (%)
            # 売却コスト = (1.0 + avg_gross_return/100) * cost_bps / 100.0 (%)
            # 平均グロスリターンを推定（年率超過リターン + TOPIXリターン）
            annual_excess_returns = perf.get("annual_excess_returns_list", [])
            if annual_excess_returns:
                # TOPIXリターンを取得（平均的な値を想定）
                # 実際のTOPIXリターンは各ポートフォリオで異なるが、平均値を推定
                mean_annual_return = perf.get("mean_annual_return_pct", 0.0)
                mean_excess_return = perf.get("mean_annual_excess_return_pct", 0.0)
                # グロスリターン = 超過リターン + TOPIXリターン
                # TOPIXリターン = 年率リターン - 超過リターン（近似）
                estimated_topix_return = mean_annual_return - mean_excess_return if mean_annual_return else 0.0
                avg_gross_return = mean_excess_return + estimated_topix_return
            else:
                avg_gross_return = 0.0
            
            # コスト計算（正確な計算式）
            # 購入コスト率（パーセント）: cost_bps / 100.0
            buy_cost_pct = cost_bps / 100.0
            # 売却コスト率（パーセント）: (1.0 + avg_gross_return/100) * cost_bps / 100.0
            sell_cost_pct = (1.0 + avg_gross_return / 100.0) * cost_bps / 100.0
            total_cost_pct = buy_cost_pct + sell_cost_pct
            cost_info_list.append({
                "buy_cost_pct": buy_cost_pct,
                "sell_cost_pct": sell_cost_pct,
                "total_cost_pct": total_cost_pct,
            })
        
        print(f"  年率超過リターン（平均）: {mean_excess:.4f}%")
        print(f"  年率超過リターン（中央値）: {median_excess:.4f}%")
        print(f"  勝率: {win_rate:.4f}")
        print(f"  ポートフォリオ数: {num_portfolios}")
        if cost_info_list:
            cost_info = cost_info_list[0]
            print(f"  コスト情報（推定）:")
            print(f"    購入コスト: {cost_info['buy_cost_pct']:.4f}%")
            print(f"    売却コスト: {cost_info['sell_cost_pct']:.4f}%")
            print(f"    合計コスト: {cost_info['total_cost_pct']:.4f}%")
        print()
        
        results.append({
            "cost_bps": cost_bps,
            "mean_annual_excess_return_pct": mean_excess,
            "median_annual_excess_return_pct": median_excess,
            "win_rate": win_rate,
            "num_portfolios": num_portfolios,
            "cost_info": cost_info_list[0] if cost_info_list else None,
        })
    
    # コスト影響の分析
    print("=" * 80)
    print("【コスト影響の分析】")
    print("=" * 80)
    print()
    
    if len(results) >= 2:
        result_0bps = results[0]  # 最初が0bpsと仮定
        result_25bps = None
        for r in results:
            if r["cost_bps"] == 25.0:
                result_25bps = r
                break
        
        if result_25bps:
            mean_diff = result_0bps["mean_annual_excess_return_pct"] - result_25bps["mean_annual_excess_return_pct"]
            median_diff = result_0bps["median_annual_excess_return_pct"] - result_25bps["median_annual_excess_return_pct"]
            
            print(f"0bps vs 25bps:")
            print(f"  平均超過リターンの差分: {mean_diff:.4f}%ポイント")
            print(f"  中央値超過リターンの差分: {median_diff:.4f}%ポイント")
            print()
            
            if abs(mean_diff) < 0.01 and abs(median_diff) < 0.01:
                print("⚠️  警告: コストが効いていない可能性があります")
                print("   0bpsと25bpsの結果がほぼ同じです。")
                print("   以下を確認してください:")
                print("   - turnover（売買代金/ポートフォリオ）が0に近くないか")
                print("   - cost_deduction（コスト控除額）が計算されているか")
                print("   - gross_returnとnet_returnの差分が存在するか")
            else:
                print("✅ コストは正常に適用されています")
                print(f"   コスト影響: {mean_diff:.4f}%ポイント")
    
    print()
    print("=" * 80)
    print("【注意】")
    print("=" * 80)
    print()
    print("このスクリプトは結果の差分のみを確認します。")
    print("詳細なturnoverやcost_deductionの確認には、")
    print("calculate_longterm_performance関数内のログ出力を確認してください。")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

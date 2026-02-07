"""
候補パラメータの相互採点

複数の最適化結果JSONから候補を集め、同じ評価基準で相互に採点します。
これにより、各候補の性格（上振れ/堅い）を把握できます。
"""

import json
import sys
from pathlib import Path
from datetime import datetime

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
        "study_name": data.get("study_name", "unknown"),
        "best_value": data.get("best_trial", {}).get("value", 0.0),
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


def evaluate_params(
    json_path: Path,
    test_dates: list,
    as_of_date: str,
    cost_bps: float = 0.0,
    horizon_months: int = 24,
    features_dict: dict = None,
    prices_dict: dict = None,
) -> dict:
    """パラメータを評価"""
    data = load_params_from_json(json_path)
    normalized_params = data["normalized_params"]
    
    strategy_params = create_strategy_params(normalized_params)
    entry_params = create_entry_params(normalized_params)
    
    perf = calculate_longterm_performance(
        rebalance_dates=test_dates,
        strategy_params=strategy_params,
        entry_params=entry_params,
        cost_bps=cost_bps,
        n_jobs=4,
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=horizon_months,
        require_full_horizon=True,
        as_of_date=as_of_date,
    )
    
    return {
        "study_name": data["study_name"],
        "best_value": data["best_value"],
        "mean_annual_excess_return_pct": perf["mean_annual_excess_return_pct"],
        "median_annual_excess_return_pct": perf.get("median_annual_excess_return_pct", 0.0),
        "win_rate": perf["win_rate"],
        "num_portfolios": perf["num_portfolios"],
    }


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="候補パラメータの相互採点")
    parser.add_argument("--json-files", type=str, required=True,
                       help="評価するJSONファイルのパス（カンマ区切り）")
    parser.add_argument("--test-dates", type=str, default=None,
                       help="評価するtest_dates（カンマ区切り、Noneの場合は最初のJSONから取得）")
    parser.add_argument("--as-of-date", type=str, default=None,
                       help="評価の打ち切り日（YYYY-MM-DD、Noneの場合は最初のJSONから取得）")
    parser.add_argument("--cost-bps-list", type=str, default="0,25",
                       help="評価するコストのリスト（カンマ区切り、デフォルト: 0,25）")
    parser.add_argument("--horizon-months", type=int, default=24,
                       help="投資ホライズン（月数、デフォルト: 24）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("候補パラメータの相互採点")
    print("=" * 80)
    print()
    
    # JSONファイルのリストを解析
    json_files = [Path(f.strip()) for f in args.json_files.split(",")]
    
    # 各JSONファイルの存在確認
    for json_file in json_files:
        if not json_file.exists():
            print(f"❌ エラー: {json_file} が見つかりません")
            return 1
    
    print(f"📄 評価するJSONファイル: {len(json_files)}個")
    for i, json_file in enumerate(json_files, 1):
        print(f"   {i}. {json_file.name}")
    print()
    
    # 最初のJSONからtest_datesとas_of_dateを取得
    first_data = load_params_from_json(json_files[0])
    test_dates = args.test_dates.split(",") if args.test_dates else first_data["test_dates"]
    as_of_date = args.as_of_date or first_data["as_of_date"]
    
    if not as_of_date:
        print("❌ エラー: as_of_dateが指定されていません")
        return 1
    
    print(f"   Test期間: {len(test_dates)}日")
    print(f"   as_of_date: {as_of_date}")
    print()
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    
    start_date_for_features = test_dates[0] if test_dates else "2018-01-31"
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
    
    # 各候補を各コストで評価
    print("=" * 80)
    print("各候補を評価中...")
    print("=" * 80)
    print()
    
    results = {}
    
    for json_file in json_files:
        candidate_name = json_file.stem
        results[candidate_name] = {}
        
        print(f"【{candidate_name}】")
        print("-" * 80)
        
        for cost_bps in cost_bps_list:
            print(f"  cost_bps = {cost_bps} bps:")
            
            eval_result = evaluate_params(
                json_file,
                test_dates,
                as_of_date,
                cost_bps=cost_bps,
                horizon_months=args.horizon_months,
                features_dict=features_dict,
                prices_dict=prices_dict,
            )
            
            results[candidate_name][cost_bps] = eval_result
            
            print(f"    Test平均超過リターン: {eval_result['mean_annual_excess_return_pct']:.4f}%")
            print(f"    Test中央値超過リターン: {eval_result['median_annual_excess_return_pct']:.4f}%")
            print(f"    勝率: {eval_result['win_rate']:.4f}")
            print()
    
    # 結果サマリー
    print("=" * 80)
    print("【結果サマリー】")
    print("=" * 80)
    print()
    
    # 表形式で出力
    print(f"{'候補':<50} {'cost_bps':<10} {'平均超過':<12} {'中央値超過':<12} {'勝率':<8}")
    print("-" * 100)
    
    for candidate_name, cost_results in results.items():
        for cost_bps, result in cost_results.items():
            print(f"{candidate_name[:48]:<50} {cost_bps:<10.0f} {result['mean_annual_excess_return_pct']:<12.4f} {result['median_annual_excess_return_pct']:<12.4f} {result['win_rate']:<8.4f}")
    
    print()
    
    # 各候補の性格を分析
    print("=" * 80)
    print("【候補の性格分析】")
    print("=" * 80)
    print()
    
    for candidate_name, cost_results in results.items():
        result_0bps = cost_results.get(0.0, {})
        result_25bps = cost_results.get(25.0, {})
        
        if result_0bps and result_25bps:
            mean_0bps = result_0bps["mean_annual_excess_return_pct"]
            mean_25bps = result_25bps["mean_annual_excess_return_pct"]
            cost_impact = mean_0bps - mean_25bps
            
            print(f"【{candidate_name}】")
            print(f"  0bps: {mean_0bps:.4f}%")
            print(f"  25bps: {mean_25bps:.4f}%")
            print(f"  コスト影響: {cost_impact:.4f}%ポイント")
            
            if mean_0bps >= 5.0 and mean_25bps >= 4.0:
                print(f"  性格: ✅ 上振れ + コスト耐性あり")
            elif mean_0bps >= 4.0 and mean_25bps >= 3.0:
                print(f"  性格: ✅ 堅い + コスト耐性あり")
            elif mean_0bps >= 5.0:
                print(f"  性格: ⚠️ 上振れだがコストに弱い")
            else:
                print(f"  性格: ⚠️ 堅いがコストに弱い")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

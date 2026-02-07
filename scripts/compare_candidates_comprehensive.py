"""
候補パラメータの包括的比較

複数の最適化結果JSONから候補を集め、複数の期間とコストで相互に採点します。
これにより、各候補の性格（上振れ/堅い、コスト耐性、期間ロバスト性）を包括的に把握できます。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

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
    normalized_params: dict,
    test_dates: list,
    as_of_date: str,
    cost_bps: float = 0.0,
    horizon_months: int = 24,
    features_dict: dict = None,
    prices_dict: dict = None,
) -> dict:
    """パラメータを評価"""
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
        "mean_annual_excess_return_pct": perf["mean_annual_excess_return_pct"],
        "median_annual_excess_return_pct": perf.get("median_annual_excess_return_pct", 0.0),
        "win_rate": perf["win_rate"],
        "num_portfolios": perf["num_portfolios"],
    }


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="候補パラメータの包括的比較")
    parser.add_argument("--json-files", type=str, required=True,
                       help="評価するJSONファイルのパス（カンマ区切り）")
    parser.add_argument("--cost-bps-list", type=str, default="0,10,25,50",
                       help="評価するコストのリスト（カンマ区切り、デフォルト: 0,10,25,50）")
    parser.add_argument("--test-periods", type=str, default="2022,2021",
                       help="評価する期間（カンマ区切り、デフォルト: 2022,2021）")
    parser.add_argument("--horizon-months", type=int, default=24,
                       help="投資ホライズン（月数、デフォルト: 24）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("候補パラメータの包括的比較")
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
    for period, data in test_dates_dict.items():
        print(f"   {period}: {len(data['test_dates'])}日分（as_of: {data['as_of_date']}）")
    print()
    
    # コストのリストを解析
    cost_bps_list = [float(x.strip()) for x in args.cost_bps_list.split(",")]
    print(f"💰 評価コスト: {', '.join(map(str, cost_bps_list))} bps")
    print()
    
    # 特徴量キャッシュを構築（全期間に対応）
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    
    # 全期間のrebalance_datesを集める
    all_rebalance_dates = []
    for period_data in test_dates_dict.values():
        all_rebalance_dates.extend(period_data["test_dates"])
    
    # as_of_dateまで必要
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
    
    # 各候補を各期間×各コストで評価
    print("=" * 80)
    print("各候補を評価中...")
    print("=" * 80)
    print()
    
    results = {}
    
    for json_file in json_files:
        candidate_name = json_file.stem
        data = load_params_from_json(json_file)
        normalized_params = data["normalized_params"]
        
        results[candidate_name] = {
            "study_name": data["study_name"],
            "best_value": data["best_value"],
            "evaluations": {},
        }
        
        print(f"【{candidate_name}】")
        print("-" * 80)
        
        for period in test_periods:
            period_data = test_dates_dict[period]
            test_dates = period_data["test_dates"]
            as_of_date = period_data["as_of_date"]
            
            print(f"  期間: {period} ({len(test_dates)}日分)")
            
            for cost_bps in cost_bps_list:
                print(f"    cost_bps = {cost_bps} bps:", end=" ")
                
                eval_result = evaluate_params(
                    normalized_params,
                    test_dates,
                    as_of_date,
                    cost_bps=cost_bps,
                    horizon_months=args.horizon_months,
                    features_dict=features_dict,
                    prices_dict=prices_dict,
                )
                
                key = f"{period}_c{cost_bps:.0f}"
                results[candidate_name]["evaluations"][key] = eval_result
                
                print(f"mean={eval_result['mean_annual_excess_return_pct']:.4f}%, "
                      f"median={eval_result['median_annual_excess_return_pct']:.4f}%, "
                      f"win_rate={eval_result['win_rate']:.4f}")
            
            print()
    
    # 結果サマリー（表形式）
    print("=" * 80)
    print("【結果サマリー】")
    print("=" * 80)
    print()
    
    # 表1: 各候補×期間×コストの詳細
    print("【詳細表】")
    print()
    
    for period in test_periods:
        print(f"期間: {period}")
        print(f"{'候補':<50} {'cost_bps':<10} {'平均超過':<12} {'中央値超過':<12} {'勝率':<8}")
        print("-" * 100)
        
        for candidate_name in results.keys():
            for cost_bps in cost_bps_list:
                key = f"{period}_c{cost_bps:.0f}"
                result = results[candidate_name]["evaluations"].get(key, {})
                mean_excess = result.get("mean_annual_excess_return_pct", 0.0)
                median_excess = result.get("median_annual_excess_return_pct", 0.0)
                win_rate = result.get("win_rate", 0.0)
                
                print(f"{candidate_name[:48]:<50} {cost_bps:<10.0f} {mean_excess:<12.4f} {median_excess:<12.4f} {win_rate:<8.4f}")
        
        print()
    
    # 表2: 採用判定用（cost=25bps, median超過）
    print("=" * 80)
    print("【採用判定用（cost=25bps, median超過）】")
    print("=" * 80)
    print()
    
    print(f"{'候補':<50} {'2022 c25 median':<18} {'2021 c25 median':<18} {'worst-of-two':<18} {'判定'}")
    print("-" * 110)
    
    candidate_scores = {}
    
    for candidate_name in results.keys():
        key_2022 = "2022_c25"
        key_2021 = "2021_c25"
        
        result_2022 = results[candidate_name]["evaluations"].get(key_2022, {})
        result_2021 = results[candidate_name]["evaluations"].get(key_2021, {})
        
        median_2022 = result_2022.get("median_annual_excess_return_pct", 0.0)
        median_2021 = result_2021.get("median_annual_excess_return_pct", 0.0)
        worst = min(median_2022, median_2021)
        
        candidate_scores[candidate_name] = {
            "median_2022": median_2022,
            "median_2021": median_2021,
            "worst": worst,
        }
        
        # 判定: worstが3%以上なら合格
        status = "✅ 合格" if worst >= 3.0 else "❌ 不合格"
        
        print(f"{candidate_name[:48]:<50} {median_2022:<18.4f} {median_2021:<18.4f} {worst:<18.4f} {status}")
    
    print()
    
    # 推奨候補
    print("=" * 80)
    print("【推奨候補】")
    print("=" * 80)
    print()
    
    if candidate_scores:
        # worstが最も高い候補を推奨
        best_candidate = max(candidate_scores.items(), key=lambda x: x[1]["worst"])
        candidate_name, scores = best_candidate
        
        print(f"✅ 推奨候補: {candidate_name}")
        print(f"   2022 c25 median: {scores['median_2022']:.4f}%")
        print(f"   2021 c25 median: {scores['median_2021']:.4f}%")
        print(f"   worst-of-two: {scores['worst']:.4f}%")
        print()
        print(f"   理由: worst-of-twoが最も高い（ワーストケース耐性が最も強い）")
        print()
    
    # 各候補の性格分析
    print("=" * 80)
    print("【各候補の性格分析】")
    print("=" * 80)
    print()
    
    for candidate_name, candidate_data in results.items():
        print(f"【{candidate_name}】")
        
        # コスト感度
        result_0bps = candidate_data["evaluations"].get("2022_c0", {})
        result_25bps = candidate_data["evaluations"].get("2022_c25", {})
        
        if result_0bps and result_25bps:
            mean_0bps = result_0bps.get("mean_annual_excess_return_pct", 0.0)
            mean_25bps = result_25bps.get("mean_annual_excess_return_pct", 0.0)
            cost_impact = mean_0bps - mean_25bps
            
            print(f"   コスト感度（2022）:")
            print(f"     0bps: {mean_0bps:.4f}%")
            print(f"     25bps: {mean_25bps:.4f}%")
            print(f"     コスト影響: {cost_impact:.4f}%ポイント")
            
            if mean_25bps >= 4.0:
                print(f"     性格: ✅ コスト耐性あり")
            elif mean_25bps >= 3.0:
                print(f"     性格: ⚠️ コスト耐性やや弱い")
            else:
                print(f"     性格: ❌ コストに弱い")
        
        # 期間ロバスト性
        result_2022 = candidate_data["evaluations"].get("2022_c25", {})
        result_2021 = candidate_data["evaluations"].get("2021_c25", {})
        
        if result_2022 and result_2021:
            median_2022 = result_2022.get("median_annual_excess_return_pct", 0.0)
            median_2021 = result_2021.get("median_annual_excess_return_pct", 0.0)
            period_diff = abs(median_2022 - median_2021)
            
            print(f"   期間ロバスト性（c25 median）:")
            print(f"     2022: {median_2022:.4f}%")
            print(f"     2021: {median_2021:.4f}%")
            print(f"     差分: {period_diff:.4f}%ポイント")
            
            if period_diff <= 1.0:
                print(f"     性格: ✅ 期間ロバスト性が高い")
            elif period_diff <= 2.0:
                print(f"     性格: ⚠️ 期間ロバスト性やや低い")
            else:
                print(f"     性格: ❌ 期間ロバスト性が低い")
        
        print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

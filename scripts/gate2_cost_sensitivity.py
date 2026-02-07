"""
Gate 2: コスト感度チェック

指定されたパラメータセットを、異なる取引コスト（cost_bps）で評価します。
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
        "as_of_date": data.get("end_date"),  # 通常はend_dateと同じ
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
    
    parser = argparse.ArgumentParser(description="Gate 2: コスト感度チェック")
    parser.add_argument("--params-json", type=str, required=True,
                       help="最適化結果JSONファイルのパス")
    parser.add_argument("--cost-bps-list", type=str, default="0,10,25,50",
                       help="評価するコストのリスト（カンマ区切り、デフォルト: 0,10,25,50）")
    parser.add_argument("--as-of-date", type=str, default=None,
                       help="評価の打ち切り日（YYYY-MM-DD、Noneの場合はJSONから取得）")
    parser.add_argument("--horizon-months", type=int, default=24,
                       help="投資ホライズン（月数、デフォルト: 24）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Gate 2: コスト感度チェック")
    print("=" * 80)
    print()
    
    # パラメータを読み込む
    json_path = Path(args.params_json)
    if not json_path.exists():
        print(f"❌ エラー: {json_path} が見つかりません")
        return 1
    
    print(f"📄 パラメータを読み込み中: {json_path}")
    data = load_params_from_json(json_path)
    normalized_params = data["normalized_params"]
    test_dates = data["test_dates"]
    as_of_date = args.as_of_date or data.get("as_of_date")
    
    if not as_of_date:
        print("❌ エラー: as_of_dateが指定されていません")
        return 1
    
    print(f"   Test期間: {len(test_dates)}日")
    print(f"   as_of_date: {as_of_date}")
    print()
    
    # パラメータを作成
    strategy_params = create_strategy_params(normalized_params)
    entry_params = create_entry_params(normalized_params)
    
    # コストのリストを解析
    cost_bps_list = [float(x.strip()) for x in args.cost_bps_list.split(",")]
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    
    # test_datesに必要な日付を追加（特徴量構築用）
    # test_datesの最初の日付から24ヶ月前まで必要
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
        
        print(f"  年率超過リターン（平均）: {mean_excess:.4f}%")
        print(f"  年率超過リターン（中央値）: {median_excess:.4f}%")
        print(f"  勝率: {win_rate:.4f}")
        print(f"  ポートフォリオ数: {num_portfolios}")
        print()
        
        results.append({
            "cost_bps": cost_bps,
            "mean_annual_excess_return_pct": mean_excess,
            "median_annual_excess_return_pct": median_excess,
            "win_rate": win_rate,
            "num_portfolios": num_portfolios,
        })
    
    # 結果サマリー
    print("=" * 80)
    print("【結果サマリー】")
    print("=" * 80)
    print(f"{'cost_bps':<10} {'平均超過':<12} {'中央値超過':<12} {'勝率':<8} {'判定'}")
    print("-" * 80)
    
    all_pass = True
    for r in results:
        cost_bps = r["cost_bps"]
        mean_excess = r["mean_annual_excess_return_pct"]
        median_excess = r["median_annual_excess_return_pct"]
        win_rate = r["win_rate"]
        
        # 判定: 平均超過がプラスを維持しているか
        status = "✅ PASS" if mean_excess > 0 else "❌ FAIL"
        if mean_excess <= 0:
            all_pass = False
        
        print(f"{cost_bps:<10.0f} {mean_excess:<12.4f} {median_excess:<12.4f} {win_rate:<8.4f} {status}")
    
    print()
    
    if all_pass:
        print("✅ Gate 2: すべてのコストでプラスを維持しています")
    else:
        print("❌ Gate 2: 一部のコストでマイナスになっています")
        print("   本番反映前に、コストを考慮した再最適化を検討してください")
    
    print()
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

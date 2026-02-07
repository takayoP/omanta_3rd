"""
Gate 3: 別期間での検証

指定されたパラメータセットを、異なる期間（2021、2020など）で評価します。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

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


def get_test_dates_for_period(test_start_date: str, test_end_date: str) -> list:
    """指定期間のtest_datesを取得"""
    return get_monthly_rebalance_dates(test_start_date, test_end_date)


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gate 3: 別期間での検証")
    parser.add_argument("--params-json", type=str, required=True,
                       help="最適化結果JSONファイルのパス")
    parser.add_argument("--test-start-date", type=str, required=True,
                       help="Test期間の開始日（YYYY-MM-DD）")
    parser.add_argument("--test-end-date", type=str, required=True,
                       help="Test期間の終了日（YYYY-MM-DD）")
    parser.add_argument("--as-of-date", type=str, required=True,
                       help="評価の打ち切り日（YYYY-MM-DD、test_end_date + 24M）")
    parser.add_argument("--horizon-months", type=int, default=24,
                       help="投資ホライズン（月数、デフォルト: 24）")
    parser.add_argument("--cost-bps", type=float, default=0.0,
                       help="取引コスト（bps、デフォルト: 0.0）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Gate 3: 別期間での検証")
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
    
    print(f"   Test期間: {args.test_start_date} ～ {args.test_end_date}")
    print(f"   as_of_date: {args.as_of_date}")
    print(f"   horizon_months: {args.horizon_months}")
    print()
    
    # Test期間のrebalance_datesを取得
    test_dates = get_test_dates_for_period(args.test_start_date, args.test_end_date)
    print(f"   Test期間のrebalance_dates: {len(test_dates)}日")
    print(f"   最初: {test_dates[0] if test_dates else 'N/A'}")
    print(f"   最後: {test_dates[-1] if test_dates else 'N/A'}")
    print()
    
    if len(test_dates) == 0:
        print("❌ エラー: Test期間のrebalance_datesが空です")
        return 1
    
    # パラメータを作成
    strategy_params = create_strategy_params(normalized_params)
    entry_params = create_entry_params(normalized_params)
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    
    # test_datesに必要な日付を追加（特徴量構築用）
    # test_datesの最初の日付から24ヶ月前まで必要
    start_date_for_features = test_dates[0]
    all_rebalance_dates = get_monthly_rebalance_dates(start_date_for_features, args.as_of_date)
    
    features_dict, prices_dict = feature_cache.warm(
        all_rebalance_dates,
        n_jobs=4,
        force_rebuild=False,
    )
    print(f"   特徴量: {len(features_dict)}日分")
    print(f"   価格データ: {len(prices_dict)}日分")
    print()
    
    # 評価
    print("=" * 80)
    print("評価中...")
    print("=" * 80)
    print()
    
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
        as_of_date=args.as_of_date,
    )
    
    mean_excess = perf["mean_annual_excess_return_pct"]
    median_excess = perf.get("median_annual_excess_return_pct", 0.0)
    win_rate = perf["win_rate"]
    num_portfolios = perf["num_portfolios"]
    
    print()
    print("=" * 80)
    print("【評価結果】")
    print("=" * 80)
    print(f"  年率超過リターン（平均）: {mean_excess:.4f}%")
    print(f"  年率超過リターン（中央値）: {median_excess:.4f}%")
    print(f"  勝率: {win_rate:.4f}")
    print(f"  ポートフォリオ数: {num_portfolios}")
    print()
    
    # 判定
    if mean_excess > 0:
        print("✅ Gate 3: この期間でもプラスを維持しています")
        return 0
    else:
        print("❌ Gate 3: この期間でマイナスになっています")
        print("   2022だけが良い（たまたま）の可能性があります")
        return 1


if __name__ == "__main__":
    sys.exit(main())

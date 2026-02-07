"""
1/21のbest_paramsを現在のコード/データで再評価するスクリプト

目的:
- 1/21のbest_paramsが現在でも良いか確認（ケースA/Bの判定）
- 固定ホライズン評価の確認（チェックA）
- 未来リークの確認（チェックB）
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.jobs.optimize_longterm import (
    calculate_longterm_performance,
    split_rebalance_dates,
)
from omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.backtest.feature_cache import FeatureCache


def load_best_params(json_path: Path) -> dict:
    """最適化結果JSONからbest_paramsを読み込む"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    best_params = data["best_trial"]["params"]
    normalized_params = data.get("normalized_params", {})
    
    # 1/21のJSONにはrsi_direction/bb_directionが含まれていない可能性がある
    # パラメータから方向を推論
    rsi_base = best_params.get("rsi_base")
    rsi_max = best_params.get("rsi_max")
    bb_z_base = best_params.get("bb_z_base")
    bb_z_max = best_params.get("bb_z_max")
    
    # 方向の推論
    if rsi_base is not None and rsi_max is not None:
        rsi_direction = "reversal" if rsi_base > rsi_max else "momentum"
    else:
        rsi_direction = None
    
    if bb_z_base is not None and bb_z_max is not None:
        # BB逆張り: base < max かつ base < 0 かつ max < 0
        # BB順張り: base < max かつ base >= 0 かつ max > 0
        if bb_z_base < bb_z_max:
            if bb_z_base < 0 and bb_z_max < 0:
                bb_direction = "reversal"
            else:
                bb_direction = "momentum"
        else:
            bb_direction = "reversal"
    else:
        bb_direction = None
    
    return {
        "best_params": best_params,
        "normalized_params": normalized_params,
        "rsi_direction": rsi_direction,
        "bb_direction": bb_direction,
        "train_dates": data.get("train_dates", []),
        "test_dates": data.get("test_dates", []),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "train_performance": data.get("train_performance", {}),
        "test_performance": data.get("test_performance", {}),
    }


def create_strategy_params(best_params: dict) -> StrategyParams:
    """best_paramsからStrategyParamsを作成"""
    return StrategyParams(
        w_quality=best_params.get("w_quality", 0.0),
        w_value=best_params.get("w_value", 0.0),
        w_growth=best_params.get("w_growth", 0.0),
        w_record_high=best_params.get("w_record_high", 0.0),
        w_size=best_params.get("w_size", 0.0),
        w_forward_per=best_params.get("w_forward_per", 0.0),
        roe_min=best_params.get("roe_min", 0.0),
        liquidity_quantile_cut=best_params.get("liquidity_quantile_cut", 0.0),
    )


def create_entry_params(best_params: dict, rsi_direction: str, bb_direction: str) -> EntryScoreParams:
    """best_paramsからEntryScoreParamsを作成"""
    rsi_base = best_params.get("rsi_base")
    rsi_max = best_params.get("rsi_max")
    bb_z_base = best_params.get("bb_z_base")
    bb_z_max = best_params.get("bb_z_max")
    bb_weight = best_params.get("bb_weight", 0.5)
    
    # rsi_min_widthとbb_z_min_widthはデフォルト値を使用
    rsi_min_width = 10.0
    bb_z_min_width = 0.5
    
    return EntryScoreParams(
        rsi_base=rsi_base,
        rsi_max=rsi_max,
        bb_z_base=bb_z_base,
        bb_z_max=bb_z_max,
        bb_weight=bb_weight,
        rsi_weight=1.0 - bb_weight,
        rsi_min_width=rsi_min_width,
        bb_z_min_width=bb_z_min_width,
    )


def main():
    """メイン処理"""
    print("=" * 80)
    print("1/21のbest_paramsを現在のコード/データで再評価")
    print("=" * 80)
    print()
    
    # 1/21の最適化結果を読み込む
    json_path = Path("optimization_result_optimization_longterm_studyA_20260121_204615.json")
    if not json_path.exists():
        print(f"❌ エラー: {json_path} が見つかりません")
        return 1
    
    print(f"📄 最適化結果を読み込み中: {json_path}")
    data = load_best_params(json_path)
    best_params = data["best_params"]
    rsi_direction = data["rsi_direction"]
    bb_direction = data["bb_direction"]
    
    print(f"   元のtrain performance: {data['train_performance'].get('mean_annual_excess_return_pct', 'N/A'):.4f}%")
    print(f"   元のtest performance: {data['test_performance'].get('mean_annual_excess_return_pct', 'N/A'):.4f}%")
    print(f"   推論されたRSI方向: {rsi_direction}")
    print(f"   推論されたBB方向: {bb_direction}")
    print()
    
    # パラメータを作成
    strategy_params = create_strategy_params(best_params)
    entry_params = create_entry_params(best_params, rsi_direction, bb_direction)
    
    # リバランス日を取得
    start_date = data["start_date"]
    end_date = data["end_date"]
    train_end_date = "2023-12-31"  # 1/21と同じ設定
    as_of_date = "2024-12-31"  # 1/21と同じ設定
    horizon_months = 24
    
    print(f"📅 設定:")
    print(f"   start_date: {start_date}")
    print(f"   end_date: {end_date}")
    print(f"   train_end_date: {train_end_date}")
    print(f"   as_of_date: {as_of_date}")
    print(f"   horizon_months: {horizon_months}")
    print()
    
    # リバランス日を取得
    print("📅 リバランス日を取得中...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"   総リバランス日数: {len(rebalance_dates)}")
    print()
    
    # train/testに分割
    # 1/21のJSONから実際のtrain_dates/test_datesを読み込む（再現性のため）
    print("📊 train/testに分割中...")
    if data.get("train_dates") and data.get("test_dates"):
        # 1/21のJSONから実際のtrain_dates/test_datesを使用
        print("   1/21のJSONから実際のtrain_dates/test_datesを読み込みます")
        train_dates_from_json = data["train_dates"]
        test_dates_from_json = data["test_dates"]
        
        # rebalance_datesに含まれているものだけをフィルタ
        train_dates = [d for d in train_dates_from_json if d in rebalance_dates]
        test_dates = [d for d in test_dates_from_json if d in rebalance_dates]
        
        print(f"   JSONから読み込んだtrain_dates: {len(train_dates_from_json)}日 → フィルタ後: {len(train_dates)}日")
        print(f"   JSONから読み込んだtest_dates: {len(test_dates_from_json)}日 → フィルタ後: {len(test_dates)}日")
    else:
        # フォールバック: split_rebalance_datesを使用
        print("   split_rebalance_datesを使用して計算します")
        train_dates, test_dates = split_rebalance_dates(
            rebalance_dates,
            train_ratio=0.8,
            random_seed=42,
            time_series_split=True,
            train_end_date=train_end_date,
            horizon_months=horizon_months,
            require_full_horizon=True,
            as_of_date=as_of_date,
        )
        print(f"   train_dates: {len(train_dates)}日")
        print(f"   test_dates: {len(test_dates)}日")
    
    if len(test_dates) == 0:
        print("   ⚠️  警告: test_datesが空です。1/21のJSONからtest_datesを読み込めなかった可能性があります。")
        print("   1/21のJSONのtest_datesを確認してください。")
    
    print()
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates,
        n_jobs=4,
        force_rebuild=False,  # 既存キャッシュを使用
    )
    print(f"   特徴量: {len(features_dict)}日分")
    print(f"   価格データ: {len(prices_dict)}日分")
    print()
    
    # Train期間で評価
    print("=" * 80)
    print("【Train期間で評価】")
    print("=" * 80)
    train_perf = calculate_longterm_performance(
        rebalance_dates=train_dates,
        strategy_params=strategy_params,
        entry_params=entry_params,
        cost_bps=0.0,
        n_jobs=4,
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=horizon_months,
        require_full_horizon=True,
        as_of_date=train_end_date,  # train期間の評価ではtrain_end_dateを使用
    )
    
    print()
    print("Train期間評価結果:")
    print(f"  年率超過リターン（平均）: {train_perf['mean_annual_excess_return_pct']:.4f}%")
    print(f"  年率超過リターン（中央値）: {train_perf.get('median_annual_excess_return_pct', 0.0):.4f}%")
    print(f"  勝率: {train_perf['win_rate']:.4f}")
    print(f"  ポートフォリオ数: {train_perf['num_portfolios']}")
    print(f"  評価成功数: {train_perf['num_performances']}")
    print()
    
    # Test期間で評価
    print("=" * 80)
    print("【Test期間で評価】")
    print("=" * 80)
    test_perf = calculate_longterm_performance(
        rebalance_dates=test_dates,
        strategy_params=strategy_params,
        entry_params=entry_params,
        cost_bps=0.0,
        n_jobs=4,
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=horizon_months,
        require_full_horizon=True,
        as_of_date=as_of_date,  # test期間の評価ではas_of_dateを使用
    )
    
    print()
    print("Test期間評価結果:")
    print(f"  年率超過リターン（平均）: {test_perf['mean_annual_excess_return_pct']:.4f}%")
    print(f"  年率超過リターン（中央値）: {test_perf.get('median_annual_excess_return_pct', 0.0):.4f}%")
    print(f"  勝率: {test_perf['win_rate']:.4f}")
    print(f"  ポートフォリオ数: {test_perf['num_portfolios']}")
    print(f"  評価成功数: {test_perf['num_performances']}")
    print()
    
    # 比較結果
    print("=" * 80)
    print("【比較結果】")
    print("=" * 80)
    original_train = data['train_performance'].get('mean_annual_excess_return_pct', 0.0)
    original_test = data['test_performance'].get('mean_annual_excess_return_pct', 0.0)
    new_train = train_perf['mean_annual_excess_return_pct']
    new_test = test_perf['mean_annual_excess_return_pct']
    
    print(f"Train期間:")
    print(f"  元の結果 (1/21): {original_train:.4f}%")
    print(f"  再評価結果 (現在): {new_train:.4f}%")
    print(f"  差分: {new_train - original_train:+.4f}%ポイント")
    print()
    
    print(f"Test期間:")
    print(f"  元の結果 (1/21): {original_test:.4f}%")
    print(f"  再評価結果 (現在): {new_test:.4f}%")
    print(f"  差分: {new_test - original_test:+.4f}%ポイント")
    print()
    
    # ケースA/Bの判定
    print("=" * 80)
    print("【ケースA/Bの判定】")
    print("=" * 80)
    if new_test > 0:
        print("✅ ケースA: 1/21 bestが現在でも良い")
        print("   → 戦略の「良い領域」は存在するが、1/29の最適化がそこに到達できていない")
        print("   → 原因は「探索空間の変更/サンプラーの挙動/並列/乱数/制約」の可能性が高い")
    else:
        print("❌ ケースB: 1/21 bestが現在では悪い")
        print("   → 原因は「データ更新」「評価窓の実装差」「スコア/選定ロジックが変わった」の可能性が高い")
        print("   → 最適化以前の問題が濃厚")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

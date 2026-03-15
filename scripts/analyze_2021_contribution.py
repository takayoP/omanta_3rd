"""
2021の負けを寄与分解

「事故（数銘柄） vs レジーム不適合（広く弱い）」を確定するため、
銘柄別・業種別の寄与を分析します。
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
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
    return {"normalized_params": data.get("normalized_params", {})}


def create_strategy_params(normalized_params: dict) -> StrategyParams:
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
    import argparse
    parser = argparse.ArgumentParser(description="2021の負けを寄与分解")
    parser.add_argument("--params-json", type=str, required=True, help="最適化結果JSON")
    parser.add_argument("--cost-bps", type=float, default=25.0)
    parser.add_argument("--horizon-months", type=int, default=24)
    args = parser.parse_args()

    json_path = Path(args.params_json)
    if not json_path.exists():
        print(f"❌ エラー: {json_path} が見つかりません")
        return 1

    data = load_params_from_json(json_path)
    normalized_params = data["normalized_params"]
    strategy_params = create_strategy_params(normalized_params)
    entry_params = create_entry_params(normalized_params)

    # 2021期間
    test_start = "2021-01-31"
    test_end = "2021-12-30"
    as_of_date = "2023-12-31"
    test_dates = get_monthly_rebalance_dates(test_start, test_end)

    print("=" * 80)
    print("2021の負けを寄与分解")
    print("=" * 80)
    print(f"  params: {json_path.name}")
    print(f"  test: {test_start} ～ {test_end}, as_of={as_of_date}")
    print()

    # 特徴量キャッシュ
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    all_dates = get_monthly_rebalance_dates(test_start, as_of_date)
    features_dict, prices_dict = feature_cache.warm(all_dates, n_jobs=4, force_rebuild=False)

    # 評価（raw_performances取得）
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
        return_raw_performances=True,
    )

    raw_perfs = perf.get("raw_performances", [])
    excess_by_rebalance = perf.get("annual_excess_by_rebalance", [])

    if not raw_perfs:
        print("❌ raw_performancesが空です")
        return 1

    # リバランス日→年率超過のマップ
    excess_map = {rd: ex for rd, ex in excess_by_rebalance}

    # 負け月を特定（年率超過が負の月）
    loss_months = [rd for rd, ex in excess_by_rebalance if ex < 0]

    print("【1. リバランス日別 年率超過リターン】")
    print("-" * 50)
    print(f"{'リバランス日':<14} {'年率超過%':>10} {'判定'}")
    for rd, ex in excess_by_rebalance:
        mark = "負" if ex < 0 else "正"
        print(f"{rd:<14} {ex:>10.2f}% {mark}")
    print()

    # 寄与分解
    all_contributions = []  # (rebalance_date, code, sector, contribution_pct, weight, stock_ret, bench_ret)
    sector_totals_all = defaultdict(lambda: 0.0)

    for p in raw_perfs:
        rd = p.get("rebalance_date")
        if not rd:
            continue
        stocks = p.get("stocks", [])
        topix_comp = p.get("topix_comparison", {})
        bench_ret = topix_comp.get("topix_return_pct")
        if bench_ret is None:
            bench_ret = 0.0

        # 特徴量から業種取得
        feat = features_dict.get(rd)
        sector_map = {}
        if feat is not None and not feat.empty and "sector33" in feat.columns:
            for idx, row in feat.iterrows():
                code = row.get("code", idx) if "code" in feat.columns else idx
                val = row.get("sector33", "UNKNOWN")
                sector_map[str(code)] = str(val) if pd.notna(val) and val else "UNKNOWN"

        contributions = []
        for s in stocks:
            code = s.get("code")
            weight = s.get("weight", 0.0)
            stock_ret = s.get("return_pct")
            tc = s.get("topix_comparison", {})
            if isinstance(tc, dict):
                exc = tc.get("excess_return_pct")
            else:
                exc = None
            if exc is None and stock_ret is not None and bench_ret is not None:
                exc = stock_ret - bench_ret
            if exc is None or pd.isna(exc):
                exc = 0.0
            contrib = weight * exc  # 寄与（ウェイト×超過リターン）
            sector = sector_map.get(str(code), "UNKNOWN")
            contributions.append({
                "code": code,
                "weight": weight,
                "stock_ret": stock_ret,
                "bench_ret": bench_ret,
                "excess": exc,
                "contribution": contrib,
                "sector": sector,
            })
            sector_totals_all[sector] += contrib

        # 寄与でソート
        contributions.sort(key=lambda x: x["contribution"])
        all_contributions.append((rd, contributions))

    print("【2. 負け月の銘柄別寄与（Bottom5 / Top5）】")
    print("-" * 80)
    for rd, contribs in all_contributions:
        ex = excess_map.get(rd, 0.0)
        if ex >= 0:
            continue
        print(f"\n■ {rd} (年率超過: {ex:.2f}%)")
        print("  Bottom5（負の寄与）:")
        for c in contribs[:5]:
            print(f"    {c['code']} {c['sector'][:10]:<12} contrib={c['contribution']:>7.2f}% w={c['weight']:.3f} ret={c['stock_ret'] or 0:.1f}%")
        print("  Top5（正の寄与）:")
        for c in contribs[-5:][::-1]:
            print(f"    {c['code']} {c['sector'][:10]:<12} contrib={c['contribution']:>7.2f}% w={c['weight']:.3f} ret={c['stock_ret'] or 0:.1f}%")

    print()
    print("【3. 業種別合計寄与（2021全体）】")
    print("-" * 50)
    sorted_sectors = sorted(sector_totals_all.items(), key=lambda x: x[1])
    print(f"{'業種':<30} {'合計寄与%':>12}")
    for sector, total in sorted_sectors[:15]:
        print(f"{sector[:28]:<30} {total:>12.2f}%")

    # 事故型 vs 恒常型の判定
    print()
    print("【4. 判定（事故型 vs 恒常型）】")
    print("-" * 50)
    if loss_months:
        # 負け月のBottom3銘柄の合計寄与が全体の何%か
        bottom3_contrib_share = []
        for rd, contribs in all_contributions:
            if excess_map.get(rd, 0) >= 0:
                continue
            total_neg = sum(c["contribution"] for c in contribs if c["contribution"] < 0)
            bottom3 = sum(c["contribution"] for c in contribs[:3])
            if total_neg != 0:
                share = bottom3 / total_neg * 100
                bottom3_contrib_share.append(share)
        if bottom3_contrib_share:
            avg_share = np.mean(bottom3_contrib_share)
            if avg_share > 80:
                print("→ 事故型の可能性: 下位3銘柄で負の寄与の80%以上を占める")
            else:
                print("→ 恒常型の可能性: 負の寄与が広く分散（下位3銘柄の割合 < 80%）")
            print(f"  負け月の下位3銘柄寄与割合（平均）: {avg_share:.1f}%")
    print(f"  負け月数: {len(loss_months)}/11 ({len(loss_months)/11*100:.0f}%)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

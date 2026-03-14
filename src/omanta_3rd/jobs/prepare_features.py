"""
特徴量と ref score を計算して DB に保存する。
V1: v1_ref 固定で core_score_ref / entry_score_ref を書き、既存の core_score/entry_score も更新する。
"""

from __future__ import annotations

import argparse
from typing import Optional

from ..infra.db import connect_db
from ..config.score_profile import get_v1_ref_score_profile
from ..infra.repositories.features_repo import upsert_features
from .longterm_run import build_features, StrategyParams
from .optimize import EntryScoreParams


def _score_profile_to_params(profile):
    """ScoreProfile を longterm_run 用 StrategyParams と EntryScoreParams に変換。"""
    c = profile.core_weights
    e = profile.entry_params
    strategy_params = StrategyParams(
        target_min=12,
        target_max=12,
        pool_size=profile.pool_size,
        roe_min=profile.roe_min,
        liquidity_quantile_cut=profile.liquidity_quantile_cut,
        sector_cap=4,
        w_quality=c["w_quality"],
        w_value=c["w_value"],
        w_growth=c["w_growth"],
        w_record_high=c["w_record_high"],
        w_size=c["w_size"],
        w_forward_per=c["w_forward_per"],
        w_pbr=c["w_pbr"],
        use_entry_score=True,
        rsi_base=e["rsi_base"],
        rsi_max=e["rsi_max"],
        bb_z_base=e["bb_z_base"],
        bb_z_max=e["bb_z_max"],
        bb_weight=e["bb_weight"],
        rsi_weight=e["rsi_weight"],
    )
    entry_params = EntryScoreParams(
        rsi_base=e["rsi_base"],
        rsi_max=e["rsi_max"],
        bb_z_base=e["bb_z_base"],
        bb_z_max=e["bb_z_max"],
        bb_weight=e["bb_weight"],
        rsi_weight=e["rsi_weight"],
    )
    return strategy_params, entry_params


def run_prepare_features(asof: str, score_profile_name: Optional[str] = None) -> int:
    """
    指定日 asof の特徴量を v1_ref で計算し、features_monthly に保存する。
    score_profile, core_score_ref, entry_score_ref を付与する。

    Returns:
        保存した銘柄数
    """
    profile = get_v1_ref_score_profile()
    strategy_params, entry_params = _score_profile_to_params(profile)

    with connect_db() as conn:
        feat = build_features(conn, asof, strategy_params=strategy_params, entry_params=entry_params)
        if feat.empty:
            return 0
        profile_name = score_profile_name or profile.version
        feat["score_profile"] = profile_name
        feat["core_score_ref"] = feat["core_score"]
        feat["entry_score_ref"] = feat["entry_score"]
        upsert_features(conn, feat)
        conn.commit()
        return len(feat)


def main():
    parser = argparse.ArgumentParser(description="Prepare features and ref scores for a given date.")
    parser.add_argument("--asof", type=str, required=True, help="As-of date YYYY-MM-DD")
    parser.add_argument("--start", type=str, help="Start date for batch (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date for batch (YYYY-MM-DD)")
    parser.add_argument("--score-profile", type=str, default="v1_ref", help="Score profile name to write")
    args = parser.parse_args()

    if args.start and args.end:
        from .batch_longterm_run import get_monthly_rebalance_dates
        dates = get_monthly_rebalance_dates(args.start, args.end)
        total = 0
        for d in dates:
            n = run_prepare_features(d, args.score_profile)
            total += n
            print(f"[prepare_features] {d}: {n} rows")
        print(f"[prepare_features] total: {total} rows")
    else:
        n = run_prepare_features(args.asof, args.score_profile)
        print(f"[prepare_features] {args.asof}: {n} rows")


if __name__ == "__main__":
    main()

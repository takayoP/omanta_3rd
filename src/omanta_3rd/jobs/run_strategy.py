"""
共通ランキングを policy で選定する。--mode longterm | monthly。
選定まで。パフォーマンス計算は evaluate_strategy 側で行う。
"""

from __future__ import annotations

import argparse
import uuid
from typing import Optional

from ..infra.db import connect_db
from ..config.score_profile import get_v1_ref_score_profile, get_default_policy_params, PolicyParams, dict_to_policy_params
from ..strategy.snapshot import build_snapshot
from ..strategy.scoring_engine import score_candidates
from ..strategy.policy import select_portfolio
from ..infra.repositories.run_repo import save_run, save_portfolio_snapshots
from .batch_longterm_run import get_monthly_rebalance_dates


def run_strategy_single(
    conn,
    asof: str,
    mode: str,
    policy_params: Optional[PolicyParams] = None,
    run_id: Optional[str] = None,
    save_to_new_tables: bool = True,
) -> str:
    """
    1 リバランス日について選定する。run_id を返す。
    """
    if policy_params is None:
        policy_params = get_default_policy_params()
    if run_id is None:
        run_id = str(uuid.uuid4())

    snapshot = build_snapshot(conn, asof, get_v1_ref_score_profile().version)
    if snapshot.empty:
        return run_id

    scored = score_candidates(snapshot, get_v1_ref_score_profile(), policy_params)
    prev = None  # 単日実行では前回ポートフォリオなし
    portfolio_df = select_portfolio(scored, policy_params, asof, prev_portfolio=prev)

    if portfolio_df.empty:
        return run_id

    if save_to_new_tables:
        save_run(
            conn, run_id=run_id, mode=mode, run_type="backtest",
            score_profile=get_v1_ref_score_profile().version,
            params_json=None, asof=asof,
        )
        save_portfolio_snapshots(conn, run_id, asof, portfolio_df, bucket="selected")
        conn.commit()

    return run_id


def run_strategy_range(
    conn,
    start_date: str,
    end_date: str,
    mode: str,
    policy_params: Optional[PolicyParams] = None,
    run_id: Optional[str] = None,
    save_to_new_tables: bool = True,
) -> str:
    """期間内の各リバランス日について選定する。"""
    if policy_params is None:
        policy_params = get_default_policy_params()
    if run_id is None:
        run_id = str(uuid.uuid4())

    dates = get_monthly_rebalance_dates(start_date, end_date)
    prev_portfolio = None

    if save_to_new_tables and dates:
        save_run(
            conn, run_id=run_id, mode=mode, run_type="backtest",
            score_profile=get_v1_ref_score_profile().version,
            params_json=None, start_date=start_date, end_date=end_date,
        )
        conn.commit()

    for asof in dates:
        snapshot = build_snapshot(conn, asof, get_v1_ref_score_profile().version)
        if snapshot.empty:
            continue
        scored = score_candidates(snapshot, get_v1_ref_score_profile(), policy_params)
        portfolio_df = select_portfolio(scored, policy_params, asof, prev_portfolio=prev_portfolio)
        if portfolio_df.empty:
            continue
        if save_to_new_tables:
            save_portfolio_snapshots(conn, run_id, asof, portfolio_df, bucket="selected")
        prev_portfolio = portfolio_df

    return run_id


def main():
    parser = argparse.ArgumentParser(description="Run strategy: select portfolio by mode (longterm | monthly).")
    parser.add_argument("--mode", type=str, choices=["longterm", "monthly"], default="monthly")
    parser.add_argument("--asof", type=str, help="Single rebalance date YYYY-MM-DD")
    parser.add_argument("--start", type=str, help="Start date for range")
    parser.add_argument("--end", type=str, help="End date for range")
    parser.add_argument("--no-save-new", action="store_true", help="Do not write to strategy_runs/portfolio_snapshots")
    args = parser.parse_args()

    with connect_db() as conn:
        if args.asof:
            run_id = run_strategy_single(
                conn, args.asof, args.mode,
                save_to_new_tables=not args.no_save_new,
            )
        elif args.start and args.end:
            run_id = run_strategy_range(
                conn, args.start, args.end, args.mode,
                save_to_new_tables=not args.no_save_new,
            )
        else:
            print("Either --asof or both --start and --end are required.")
            return
        print(f"[run_strategy] run_id={run_id}")


if __name__ == "__main__":
    main()

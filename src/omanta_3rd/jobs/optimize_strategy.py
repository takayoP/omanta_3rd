"""
月次モードのみ最適化。PolicyParams を Optuna で探索し、目的関数は sharpe_excess - lambda_turnover * avg_turnover。
snapshot は事前キャッシュして trial 内では pure 関数のみ呼ぶ。
"""

from __future__ import annotations

import argparse
from typing import Dict, List, Optional
import pandas as pd
import optuna

from ..infra.db import connect_db
from ..config.score_profile import (
    get_v1_ref_score_profile,
    PolicyParams,
    policy_params_to_dict,
    dict_to_policy_params,
)
from ..strategy.snapshot import build_snapshot
from ..strategy.scoring_engine import score_candidates
from ..strategy.policy import select_portfolio
from ..backtest.evaluator import evaluate_portfolio
from .batch_longterm_run import get_monthly_rebalance_dates


def _build_snapshot_cache(conn, rebalance_dates: List[str], score_profile_name: str) -> Dict[str, pd.DataFrame]:
    """リバランス日ごとのスナップショットを事前に読んで返す。"""
    cache = {}
    for d in rebalance_dates:
        cache[d] = build_snapshot(conn, d, score_profile_name)
    return cache


def _objective_monthly(
    trial: optuna.Trial,
    snapshot_cache: Dict[str, pd.DataFrame],
    rebalance_dates: List[str],
    start_date: str,
    end_date: str,
    cost_bps: float = 0.0,
) -> float:
    """
    Optuna 目的関数。PolicyParams をサンプルし、キャッシュされた snapshot で選定→評価。
    """
    entry_share = trial.suggest_float("entry_share", 0.0, 0.35)
    top_n = trial.suggest_categorical("top_n", [8, 10, 12, 14, 16])
    sector_cap = trial.suggest_int("sector_cap", 2, 4)
    liquidity_floor_q = trial.suggest_float("liquidity_floor_q", 0.30, 0.60)
    rebalance_buffer = trial.suggest_int("rebalance_buffer", 0, 3)
    lambda_turnover = trial.suggest_float("lambda_turnover", 0.0, 0.20)

    policy_params = PolicyParams(
        entry_share=entry_share,
        top_n=top_n,
        sector_cap=sector_cap,
        liquidity_floor_q=liquidity_floor_q,
        rebalance_buffer=rebalance_buffer,
        lambda_turnover=lambda_turnover,
    )

    profile = get_v1_ref_score_profile()
    portfolios: Dict[str, pd.DataFrame] = {}
    prev = None

    for asof in rebalance_dates:
        snapshot = snapshot_cache.get(asof)
        if snapshot is None or snapshot.empty:
            continue
        scored = score_candidates(snapshot, profile, policy_params)
        pf = select_portfolio(scored, policy_params, asof, prev_portfolio=prev)
        if pf.empty:
            continue
        portfolios[asof] = pf[["code", "weight"]].copy() if "code" in pf.columns and "weight" in pf.columns else pf
        prev = pf

    if len(portfolios) < 2:
        return float("-inf")

    result = evaluate_portfolio(
        portfolios=portfolios,
        start_date=start_date,
        end_date=end_date,
        cost_bps=cost_bps,
        lambda_turnover=lambda_turnover,
    )

    objective = result.get("objective")
    if objective is None:
        return float("-inf")
    return float(objective)


def main():
    parser = argparse.ArgumentParser(description="Optimize strategy (monthly mode only).")
    parser.add_argument("--start", type=str, required=True, help="Train start YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True, help="Train end YYYY-MM-DD")
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument("--study-name", type=str, default="optimize_strategy_v1")
    parser.add_argument("--cost-bps", type=float, default=0.0)
    parser.add_argument("--n-jobs", type=int, default=1)
    args = parser.parse_args()

    with connect_db() as conn:
        rebalance_dates = get_monthly_rebalance_dates(args.start, args.end)
        if len(rebalance_dates) < 2:
            print("[optimize_strategy] Too few rebalance dates.")
            return
        profile = get_v1_ref_score_profile()
        snapshot_cache = _build_snapshot_cache(conn, rebalance_dates, profile.version)

    def objective(trial):
        return _objective_monthly(
            trial,
            snapshot_cache,
            rebalance_dates,
            args.start,
            args.end,
            cost_bps=args.cost_bps,
        )

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=args.n_trials, n_jobs=args.n_jobs)

    print(f"[optimize_strategy] best_value={study.best_value}")
    print(f"[optimize_strategy] best_params={study.best_params}")


if __name__ == "__main__":
    main()

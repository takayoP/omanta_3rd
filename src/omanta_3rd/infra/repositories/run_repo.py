"""strategy_runs / portfolio_snapshots への書き込み（run_strategy, optimize_strategy 用）"""

from __future__ import annotations

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd

from ..db import upsert


def save_run(
    conn: sqlite3.Connection,
    run_id: str,
    mode: str,
    run_type: str,
    score_profile: Optional[str] = None,
    params_json: Optional[str] = None,
    asof: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    objective_name: Optional[str] = None,
    objective_value: Optional[float] = None,
    parent_run_id: Optional[str] = None,
) -> str:
    """strategy_runs に 1 行挿入。run_id を返す。"""
    if not run_id:
        run_id = str(uuid.uuid4())
    row = {
        "run_id": run_id,
        "mode": mode,
        "run_type": run_type,
        "score_profile": score_profile,
        "params_json": params_json,
        "asof": asof,
        "start_date": start_date,
        "end_date": end_date,
        "objective_name": objective_name,
        "objective_value": objective_value,
        "parent_run_id": parent_run_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    upsert(conn, "strategy_runs", [row], conflict_columns=["run_id"])
    return run_id


def save_portfolio_snapshots(
    conn: sqlite3.Connection,
    run_id: str,
    rebalance_date: str,
    portfolio_df: pd.DataFrame,
    bucket: str = "selected",
) -> None:
    """
    指定リバランス日のポートフォリオを portfolio_snapshots に保存する。
    portfolio_df は rebalance_date, code, weight, rank, total_score, action 等を含む想定。
    """
    if portfolio_df.empty:
        return
    # 既存の当 run_id / rebalance_date を削除してから挿入
    conn.execute(
        "DELETE FROM portfolio_snapshots WHERE run_id = ? AND rebalance_date = ?",
        (run_id, rebalance_date),
    )
    conn.commit()

    rows = []
    for _, r in portfolio_df.iterrows():
        rows.append({
            "run_id": run_id,
            "rebalance_date": rebalance_date,
            "code": str(r.get("code", "")),
            "rank": int(r.get("rank", 0)),
            "weight": float(r.get("weight", 0.0)),
            "total_score": float(r.get("total_score", 0.0)) if pd.notna(r.get("total_score")) else None,
            "core_score_ref": float(r["core_score_ref"]) if "core_score_ref" in r.index and pd.notna(r.get("core_score_ref")) else (float(r["core_score"]) if "core_score" in r.index and pd.notna(r.get("core_score")) else None),
            "entry_score_ref": float(r["entry_score_ref"]) if "entry_score_ref" in r.index and pd.notna(r.get("entry_score_ref")) else (float(r["entry_score"]) if "entry_score" in r.index and pd.notna(r.get("entry_score")) else None),
            "bucket": bucket,
            "action": str(r.get("action", "new")),
            "detail_json": json.dumps({}) if "detail_json" not in r else (r["detail_json"] if isinstance(r.get("detail_json"), str) else json.dumps(r.get("detail_json", {}))),
        })
    if rows:
        upsert(conn, "portfolio_snapshots", rows, conflict_columns=["run_id", "rebalance_date", "code"])

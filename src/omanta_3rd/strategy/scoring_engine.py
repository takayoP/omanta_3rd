"""
単一の真実: スコア合成の純粋関数。
snapshot に core_score_ref / entry_score_ref がある前提で、
PolicyParams に従い total_score を付与する。DB を書かず Optuna/CLI を知らない。
"""

from __future__ import annotations

from typing import Optional
import pandas as pd
import numpy as np

from ..config.score_profile import ScoreProfile
from ..config.score_profile import PolicyParams


def _pct_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """クロスセクションのパーセンタイル (0〜1)。"""
    return series.rank(pct=True, ascending=ascending)


def score_candidates(
    snapshot: pd.DataFrame,
    score_profile: ScoreProfile,
    policy_params: PolicyParams,
) -> pd.DataFrame:
    """
    スナップショットに total_score を付与する。純粋関数（DB を書かない）。

    total_score = (1 - entry_share) * core_ref_pct + entry_share * entry_ref_pct
    core_ref_pct / entry_ref_pct はクロスセクションのパーセンタイル (0〜1)。

    Args:
        snapshot: build_snapshot の戻り値。core_score_ref, entry_score_ref 列を持つ想定。
        score_profile: 固定プロファイル（V1 では参照のみ。フィルタ等は policy 側で行う）
        policy_params: entry_share, top_n 等

    Returns:
        snapshot に total_score, core_ref_pct, entry_ref_pct を追加した DataFrame。
    """
    if snapshot.empty:
        return snapshot

    df = snapshot.copy()

    core_col = "core_score_ref" if "core_score_ref" in df.columns else "core_score"
    entry_col = "entry_score_ref" if "entry_score_ref" in df.columns else "entry_score"

    if core_col not in df.columns or entry_col not in df.columns:
        df["total_score"] = np.nan
        return df

    # クロスセクションでパーセンタイル (0〜1)。高いほど良いので ascending=False で rank
    df["core_ref_pct"] = _pct_rank(df[core_col], ascending=False)
    df["entry_ref_pct"] = _pct_rank(df[entry_col].fillna(0), ascending=False)

    entry_share = policy_params.entry_share
    df["total_score"] = (
        (1.0 - entry_share) * df["core_ref_pct"] + entry_share * df["entry_ref_pct"]
    )

    return df

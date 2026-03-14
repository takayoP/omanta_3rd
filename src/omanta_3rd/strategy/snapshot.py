"""
スナップショット取得: 指定日の features_monthly を読むだけ（DB を書かない）。
"""

from __future__ import annotations

from typing import Optional
import sqlite3
import pandas as pd

from ..config.score_profile import ScoreProfile


def build_snapshot(
    conn: sqlite3.Connection,
    asof: str,
    score_profile_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    指定日 asof の features_monthly を読んで DataFrame を返す。
    DB は読むだけ。書き込まない。

    Args:
        conn: データベース接続
        asof: 基準日 (YYYY-MM-DD)
        score_profile_name: 使用する score_profile 列の値 (None の場合は core_score_ref/entry_score_ref があればそれを使用、なければ core_score/entry_score をフォールバック)

    Returns:
        as_of_date, code, sector33, liquidity_60d, (core_score_ref or core_score), (entry_score_ref or entry_score), ...
        を含む DataFrame。core_score_ref / entry_score_ref を total_score 計算に使う列名は _ref を優先し、なければ core_score/entry_score。
    """
    # カラム存在確認のため一度全件取得せず、必要な列を列挙
    # 移行期は core_score_ref/entry_score_ref が無い場合があるので、SELECT * で取ってから列を正規化する
    df = pd.read_sql_query(
        """
        SELECT *
        FROM features_monthly
        WHERE as_of_date = ?
        """,
        conn,
        params=(asof,),
    )

    if df.empty:
        return df

    # 列の正規化: total_score 計算に使う core/entry の列名を統一
    if "core_score_ref" in df.columns and "entry_score_ref" in df.columns:
        if score_profile_name and "score_profile" in df.columns:
            mask = df["score_profile"] == score_profile_name
            if not mask.all():
                # 一致しない行は core_score/entry_score にフォールバック
                df = df.copy()
                df.loc[~mask, "core_score_ref"] = df.loc[~mask, "core_score"]
                df.loc[~mask, "entry_score_ref"] = df.loc[~mask, "entry_score"]
    else:
        # 移行前: ref 列が無いので core_score / entry_score を ref として扱う
        df = df.copy()
        df["core_score_ref"] = df["core_score"] if "core_score" in df.columns else 0.0
        df["entry_score_ref"] = df["entry_score"] if "entry_score" in df.columns else 0.0

    return df

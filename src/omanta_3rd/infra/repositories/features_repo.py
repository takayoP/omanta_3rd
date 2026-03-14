"""features_monthly への書き込み（prepare_features 用）"""

from __future__ import annotations

import sqlite3
import pandas as pd

from ..db import upsert


def upsert_features(conn: sqlite3.Connection, feat: pd.DataFrame) -> None:
    """
    月次特徴量を features_monthly に UPSERT する。
    feat に score_profile, core_score_ref, entry_score_ref があればそれも保存する。
    """
    if feat.empty:
        return
    rows = feat.to_dict("records")
    # カラムは DataFrame の列に合わせる。conflict は (as_of_date, code)
    conflict_columns = ["as_of_date", "code"]
    upsert(conn, "features_monthly", rows, conflict_columns=conflict_columns)

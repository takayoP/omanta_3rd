"""汎用ユーティリティ関数"""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd


def _safe_div(a, b):
    try:
        if a is None or b is None:
            return np.nan
        if pd.isna(a) or pd.isna(b):
            return np.nan
        if b == 0:
            return np.nan
        return a / b
    except Exception:
        return np.nan


def _clip01(x):
    if pd.isna(x):
        return np.nan
    return float(max(0.0, min(1.0, x)))


def _pct_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    return series.rank(pct=True, ascending=ascending)


def _log_safe(x: float) -> float:
    if x is None or pd.isna(x) or x <= 0:
        return np.nan
    return math.log(x)


def _calc_slope(values: List[float]) -> float:
    v = [x for x in values if x is not None and not pd.isna(x)]
    n = len(v)
    if n < 3:
        return np.nan
    x = np.arange(n, dtype=float)
    y = np.array(v, dtype=float)
    a, _b = np.polyfit(x, y, 1)
    return float(a)

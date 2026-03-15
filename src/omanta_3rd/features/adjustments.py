"""株式分割・株数調整ロジック"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _get_shares_at_date(conn, code: str, target_date: str) -> tuple:
    """
    指定日の実際の発行済み株式数（自己株式除く）と純資産を取得

    財務データから、target_date以前に開示された最新の期末データを使用します。

    Args:
        conn: データベース接続
        code: 銘柄コード
        target_date: 対象日（YYYY-MM-DD）

    Returns:
        (shares_net, equity) のタプル
        shares_net: 発行済み株式数（自己株式除く）
        equity: 純資産
        データがない場合は (np.nan, np.nan)
    """
    df = pd.read_sql_query(
        """
        SELECT shares_outstanding, treasury_shares, equity
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND shares_outstanding IS NOT NULL
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, target_date),
    )

    if df.empty:
        return np.nan, np.nan

    shares_outstanding = df.iloc[0]["shares_outstanding"]
    treasury_shares = df.iloc[0].get("treasury_shares") or 0.0
    equity = df.iloc[0].get("equity")

    if pd.isna(shares_outstanding) or shares_outstanding <= 0:
        return np.nan, np.nan

    shares_net = shares_outstanding - treasury_shares
    if shares_net <= 0:
        return np.nan, np.nan

    return shares_net, equity


def _get_shares_adjustment_factor(conn, code: str, period_end: str, latest_shares: float, latest_equity: float) -> float:
    """
    発行済み株式数の変化から調整係数を計算
    新規株式発行と株式分割を区別するため、純資産（equity）の変化も考慮

    Args:
        conn: データベース接続
        code: 銘柄コード
        period_end: 財務データの期末日（YYYY-MM-DD）
        latest_shares: 最新期の期末発行済株式数（自己株式除く）
        latest_equity: 最新期の純資産（equity）

    Returns:
        調整係数（当該期の発行済株式数 / 最新期の発行済株式数）
        ただし、新規株式発行の場合は1.0を返す（調整しない）
    """
    if pd.isna(latest_shares) or latest_shares <= 0 or pd.isna(latest_equity) or latest_equity <= 0:
        return 1.0

    period_data = pd.read_sql_query(
        """
        SELECT shares_outstanding, treasury_shares, equity, bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND current_period_end = ?
          AND shares_outstanding IS NOT NULL
        ORDER BY disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, period_end),
    )

    if period_data.empty:
        return 1.0

    period_shares = period_data.iloc[0]["shares_outstanding"]
    treasury_shares = period_data.iloc[0].get("treasury_shares") or 0.0
    period_equity = period_data.iloc[0].get("equity")
    period_bvps = period_data.iloc[0].get("bvps")

    if pd.isna(period_shares) or period_shares <= 0 or pd.isna(period_equity) or period_equity <= 0:
        return 1.0

    period_shares_net = period_shares - treasury_shares

    if period_shares_net <= 0:
        return 1.0

    if pd.notna(period_bvps) and period_bvps > 0:
        period_shares_from_bvps = period_equity / period_bvps
        if not (0.8 <= period_shares_net / period_shares_from_bvps <= 1.2):
            period_shares_net = period_shares_from_bvps

    shares_ratio = latest_shares / period_shares_net
    equity_ratio = latest_equity / period_equity

    is_stock_split = (
        shares_ratio > 1.0 and
        0.85 <= equity_ratio <= 1.15
    )

    if not is_stock_split:
        return 1.0

    adjustment_factor = period_shares_net / latest_shares

    return adjustment_factor

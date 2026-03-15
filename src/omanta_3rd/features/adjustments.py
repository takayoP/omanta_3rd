"""株式分割・株数調整ロジック"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _deprecated_calculate_cumulative_adjustment_factor(conn, code: str, target_date: str) -> float:
    """
    【非推奨・封印関数】累積調整係数（CAF: Cumulative Adjustment Factor）を計算

    【警告】この関数は使用禁止です。呼び出すと例外を投げます。

    現在の実装では、時価総額計算に未調整終値（close）を使用し、
    株数はFY期末→評価日の分割倍率（_split_multiplier_between）で補正しているため、
    このCAF（評価日より後の累積積）は不要です。

    この関数は古いロジックの残骸であり、使用すると二重補正（株数も増やしたのに価格も調整）が
    発生する可能性があります。

    J-QuantsのAdjustmentFactorを使って、その日より後の調整係数の累積積を計算します。
    例：1:2分割（AdjustmentFactor=0.5）が2024-01-01に発生した場合、
    2023-12-31のCAFは0.5（将来の調整係数の累積積）

    Args:
        conn: データベース接続
        code: 銘柄コード
        target_date: 対象日（YYYY-MM-DD）

    Returns:
        累積調整係数（その日より後のAdjustmentFactorの累積積）
        データがない場合は1.0を返す

    Raises:
        DeprecationWarning: この関数は使用禁止です
    """
    import warnings
    warnings.warn(
        "_calculate_cumulative_adjustment_factor is deprecated and should not be used. "
        "Use _split_multiplier_between instead. This function causes double adjustment.",
        DeprecationWarning,
        stacklevel=2
    )
    df = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, target_date),
    )

    if df.empty:
        return 1.0

    caf = 1.0
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        if pd.notna(adj_factor) and adj_factor > 0:
            caf *= adj_factor

    return caf


def _split_multiplier_between(conn, code: str, start_date: str, end_date: str) -> float:
    """
    FY期末から評価日までの分割・併合による株数倍率を計算

    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。

    例: 1:3分割（adjustment_factor = 0.333333）の場合、
    株数倍率 = 1 / 0.333333 ≈ 3.0

    注意: 丸めは行いません（端数が出る比率や制度変更・権利関係などで
          綺麗な逆整数にならないケースに対応するため）。

    Args:
        conn: データベース接続
        code: 銘柄コード
        start_date: 開始日（YYYY-MM-DD、FY期末）
        end_date: 終了日（YYYY-MM-DD、評価日）

    Returns:
        株数倍率（分割・併合がない場合は1.0）
    """
    df = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > ?
          AND date <= ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, start_date, end_date),
    )

    if df.empty:
        return 1.0

    mult = 1.0
    adjustment_dates = []
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        if pd.notna(adj_factor) and adj_factor > 0:
            mult *= (1.0 / float(adj_factor))
            if "date" in row:
                adjustment_dates.append(row["date"])

    if mult > 100 or mult < 0.01:
        import warnings
        warnings.warn(
            f"Unusual split multiplier detected for code {code}: {mult:.6f} "
            f"(start_date={start_date}, end_date={end_date}). "
            f"This may indicate data quality issues.",
            UserWarning,
            stacklevel=2
        )

    return mult


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


def _get_latest_basis_shares(conn, code: str, target_date: str, latest_date: str) -> float:
    """
    最新株数ベースの発行済み株式数を計算

    AdjustmentFactor（株式分割/併合）と新規株式発行の両方を考慮して、
    指定日の発行済み株式数を最新株数ベースに調整します。

    Args:
        conn: データベース接続
        code: 銘柄コード
        target_date: 対象日（YYYY-MM-DD）
        latest_date: 最新期の日付（YYYY-MM-DD）

    Returns:
        最新株数ベースの発行済み株式数
    """
    shares_actual, _ = _get_shares_at_date(conn, code, target_date)

    if pd.isna(shares_actual) or shares_actual <= 0:
        return np.nan

    caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, target_date)

    if pd.isna(caf) or caf <= 0:
        return np.nan

    shares_adjusted = shares_actual / caf

    latest_shares_actual, _ = _get_shares_at_date(conn, code, latest_date)

    if pd.notna(latest_shares_actual) and latest_shares_actual > 0:
        latest_caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, latest_date)

        if pd.notna(latest_caf) and latest_caf > 0:
            latest_shares_adjusted = latest_shares_actual / latest_caf

            if latest_shares_adjusted > 0:
                new_issue_ratio = latest_shares_adjusted / shares_adjusted
                shares_latest_basis = shares_adjusted * new_issue_ratio
            else:
                shares_latest_basis = shares_adjusted
        else:
            shares_latest_basis = shares_adjusted
    else:
        shares_latest_basis = shares_adjusted

    return shares_latest_basis


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

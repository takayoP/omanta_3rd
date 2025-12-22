"""
monthly_run.py

Monthly run:
- Build features snapshot (features_monthly) for a given as-of date
- Select 20-30 stocks and save to portfolio_monthly

Usage:
  python -m omanta_3rd.jobs.monthly_run --asof 2025-12-12
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd

from ..config.settings import EXECUTION_DATE
from ..infra.db import connect_db, upsert


# -----------------------------
# Configuration
# -----------------------------

@dataclass(frozen=True)
class StrategyParams:
    target_min: int = 20
    target_max: int = 30
    pool_size: int = 80

    # Hard filters
    roe_min: float = 0.10
    liquidity_quantile_cut: float = 0.20  # drop bottom 20% by liquidity_60d

    # Sector cap (33-sector)
    sector_cap: int = 4

    # Scoring weights
    w_quality: float = 0.35
    w_value: float = 0.25
    w_growth: float = 0.15
    w_record_high: float = 0.15
    w_size: float = 0.10

    # Value mix
    w_forward_per: float = 0.5
    w_pbr: float = 0.5

    # Entry score (BB/RSI)
    use_entry_score: bool = True


PARAMS = StrategyParams()


# -----------------------------
# Utilities
# -----------------------------

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


def _rsi_from_series(close: pd.Series, n: int) -> float:
    if close is None or close.size < n + 1:
        return np.nan
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.rolling(n).mean().iloc[-1]
    avg_loss = loss.rolling(n).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return np.nan
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)


def _bb_zscore(close: pd.Series, n: int) -> float:
    if close is None or close.size < n:
        return np.nan
    window = close.iloc[-n:]
    mu = window.mean()
    sd = window.std(ddof=0)
    if pd.isna(mu) or pd.isna(sd) or sd == 0:
        return np.nan
    z = (window.iloc[-1] - mu) / sd
    return float(z)


def _entry_score(close: pd.Series) -> float:
    scores = []
    for n in (20, 60, 90):
        z = _bb_zscore(close, n)
        rsi = _rsi_from_series(close, n)

        bb_score = np.nan
        rsi_score = np.nan

        if not pd.isna(z):
            # さらに緩やかな閾値: z=-0.5 => 0, z=-3 => 1 (以前は z=-2 => 0, z=-4 => 1)
            bb_score = _clip01((-0.5 - z) / 2.5)
        if not pd.isna(rsi):
            # さらに緩やかな閾値: rsi=40 => 0, rsi=0 => 1 (以前は rsi=30 => 0, rsi=0 => 1)
            rsi_score = _clip01((40.0 - rsi) / 40.0)

        if not pd.isna(bb_score) and not pd.isna(rsi_score):
            scores.append(0.5 * bb_score + 0.5 * rsi_score)
        elif not pd.isna(bb_score):
            scores.append(bb_score)
        elif not pd.isna(rsi_score):
            scores.append(rsi_score)

    if not scores:
        return np.nan
    return float(np.nanmax(scores))


# -----------------------------
# Data load helpers
# -----------------------------

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
    # その日より後のAdjustmentFactorを取得
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
    
    # 累積積を計算
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
    # start_dateより後、end_date以下のAdjustmentFactorを取得
    # 注意: date > start_date は維持（FY期末当日の調整は通常不要、権利落ちは期末後に来る想定）
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
    
    # 株数倍率を計算: split_mult = ∏(1 / adjustment_factor)
    # 注意: 丸めは行わない（端数が出る比率や制度変更・権利関係などで
    #       綺麗な逆整数にならないケースに対応するため）
    mult = 1.0
    adjustment_dates = []
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        # 念のためゼロ・異常値ガード
        if pd.notna(adj_factor) and adj_factor > 0:
            mult *= (1.0 / float(adj_factor))
            # 取り漏れ検知のため、調整日を記録
            if "date" in row:
                adjustment_dates.append(row["date"])
    
    # 異常値検出: 分割倍率が極端におかしい場合は警告
    if mult > 100 or mult < 0.01:
        import warnings
        warnings.warn(
            f"Unusual split multiplier detected for code {code}: {mult:.6f} "
            f"(start_date={start_date}, end_date={end_date}). "
            f"This may indicate data quality issues.",
            UserWarning,
            stacklevel=2
        )
    
    # 取り漏れ検知: 権利落ち日が休場の場合、J-Quants側の日付設定次第で取り漏れの可能性
    # ただし、price_dateはsnap_price_dateで営業日に寄せているため、通常は問題ない
    # 念のため、調整日が境界付近（start_dateの直後やend_dateの直前）にある場合はログ出力
    if adjustment_dates:
        import warnings
        for adj_date in adjustment_dates:
            # start_dateの直後（3日以内）やend_dateの直前（3日以内）の調整は境界付近
            # これは正常なケースが多いが、念のため記録
            pass  # 現状は警告なし（必要に応じて有効化）
    
    return mult


def _get_shares_at_date(conn, code: str, target_date: str) -> tuple[float, float]:
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
    
    計算式：
    1. 指定日の実際の発行済み株式数を取得: S_actual(d)
    2. 累積調整係数（CAF）を計算: CAF(d) = その日より後のAdjustmentFactorの累積積
    3. 株式分割/併合の影響を除去: S_adjusted(d) = S_actual(d) / CAF(d)
    4. 新規株式発行の影響を考慮:
       - 最新期の実際の株数: S_actual(latest)
       - 最新期のCAF: CAF(latest)
       - 最新期の調整後株数: S_adjusted(latest) = S_actual(latest) / CAF(latest)
       - 新規発行による増加率: ratio = S_adjusted(latest) / S_adjusted(d)
       - 最新株数ベース: S_latest_basis(d) = S_adjusted(d) * ratio
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        target_date: 対象日（YYYY-MM-DD）
        latest_date: 最新期の日付（YYYY-MM-DD）
    
    Returns:
        最新株数ベースの発行済み株式数
    """
    # 指定日の実際の発行済み株式数を取得
    shares_actual, _ = _get_shares_at_date(conn, code, target_date)
    
    if pd.isna(shares_actual) or shares_actual <= 0:
        return np.nan
    
    # 累積調整係数（CAF）を計算（非推奨関数）
    caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, target_date)
    
    if pd.isna(caf) or caf <= 0:
        return np.nan
    
    # 株式分割/併合の影響を除去
    shares_adjusted = shares_actual / caf
    
    # 新規株式発行を考慮
    # 最新期の実際の株数を取得
    latest_shares_actual, _ = _get_shares_at_date(conn, code, latest_date)
    
    if pd.notna(latest_shares_actual) and latest_shares_actual > 0:
        # 最新期のCAFを計算（非推奨関数）
        latest_caf = _deprecated_calculate_cumulative_adjustment_factor(conn, code, latest_date)
        
        if pd.notna(latest_caf) and latest_caf > 0:
            # 最新期の調整後株数
            latest_shares_adjusted = latest_shares_actual / latest_caf
            
            if latest_shares_adjusted > 0:
                # 新規発行による増加率を計算
                # 最新期の調整後株数と対象日の調整後株数の比率
                new_issue_ratio = latest_shares_adjusted / shares_adjusted
                # 最新株数ベースに調整
                shares_latest_basis = shares_adjusted * new_issue_ratio
            else:
                shares_latest_basis = shares_adjusted
        else:
            shares_latest_basis = shares_adjusted
    else:
        # 最新期のデータがない場合は、CAF調整のみ
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
    
    # 当該期の期末発行済株式数（自己株式除く）と純資産を取得
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
    
    # 自己株式を控除
    period_shares_net = period_shares - treasury_shares
    
    if period_shares_net <= 0:
        return 1.0
    
    # BPSから逆算した発行済み株式数（データベースの不整合を補正）
    # データベースに分割後の発行済み株式数が保存されている場合、
    # BPSが分割前の値であれば、BPSから分割前の発行済み株式数を推定
    if pd.notna(period_bvps) and period_bvps > 0:
        period_shares_from_bvps = period_equity / period_bvps
        # BPSから逆算した発行済み株式数と実際の発行済み株式数が大きく異なる場合、
        # データベースの不整合の可能性があるため、BPSから逆算した値を使用
        # 許容誤差: 20%（発行済み株式数がBPSから逆算した値の80%以上120%以下なら、実際の値を使用）
        if not (0.8 <= period_shares_net / period_shares_from_bvps <= 1.2):
            # データベースの不整合を検出: BPSから逆算した値を使用
            period_shares_net = period_shares_from_bvps
    
    # 株式分割と新規株式発行を区別
    # 株式分割の場合: 純資産は変わらない（またはほぼ変わらない）が、発行済み株式数は増える
    #    例: 1株→3株の分割の場合、発行済み株式数は3倍になるが、純資産は変わらない
    # 新規株式発行の場合: 純資産も発行済み株式数も増える（資金調達による）
    #    例: 100株→150株の新規発行の場合、発行済み株式数は1.5倍、純資産も1.5倍程度増える
    
    # 当該期のBPS（純資産 / 発行済み株式数）
    period_bps_implied = period_equity / period_shares_net
    
    # 最新期のBPS（純資産 / 発行済み株式数）
    latest_bps_implied = latest_equity / latest_shares
    
    # 発行済み株式数の変化率
    shares_ratio = latest_shares / period_shares_net
    
    # 純資産の変化率
    equity_ratio = latest_equity / period_equity
    
    # 株式分割と判定する条件:
    # 発行済み株式数が大きく増加しているのに（例: 2倍、3倍）、純資産に大きな変化がない場合
    # 
    # 理論的には、純資産が変わらない場合:
    # - BPS = 純資産 / 発行済み株式数
    # - 発行済み株式数が3倍になると、BPSは1/3になる
    # - bps_ratio = 最新期BPS / 当該期BPS = (1/3) / 1 = 0.333
    # - つまり、bps_ratio = 1.0 / shares_ratio
    #
    # しかし、実際には純資産が少し変わる可能性があるため、
    # shares_ratioとequity_ratioの条件で十分に判定できる
    #
    # 1. 発行済み株式数が増加している（shares_ratio > 1.0）
    # 2. 純資産の増加率がほぼ1.0（誤差15%以内、つまり0.85以上1.15以下）
    #    株式分割の場合、純資産は変わらないため、equity_ratio ≈ 1.0
    #    新規株式発行の場合、純資産も増えるため、equity_ratio > 1.15 になる
    is_stock_split = (
        shares_ratio > 1.0 and
        0.85 <= equity_ratio <= 1.15
    )
    
    if not is_stock_split:
        # 新規株式発行の場合は調整しない
        return 1.0
    
    # 株式分割の場合のみ調整
    # 調整係数 = 当該期の発行済株式数 / 最新期の発行済株式数
    # 例: 分割前100株、分割後300株の場合、調整係数 = 100/300 = 0.333
    #     分割前のEPS 1.0円 → 調整後EPS 1.0 × 0.333 = 0.333円（分割後の基準に合わせる）
    adjustment_factor = period_shares_net / latest_shares
    
    return adjustment_factor

def _snap_price_date(conn, asof: str) -> str:
    row = conn.execute(
        "SELECT MAX(date) AS d FROM prices_daily WHERE date <= ?",
        (asof,),
    ).fetchone()
    d = row["d"] if row else None
    if not d:
        raise RuntimeError(f"No prices_daily.date <= {asof}. Load prices first.")
    return d


def _snap_listed_date(conn, asof: str) -> str:
    row = conn.execute(
        "SELECT MAX(date) AS d FROM listed_info WHERE date <= ?",
        (asof,),
    ).fetchone()
    d = row["d"] if row else None
    if not d:
        row2 = conn.execute("SELECT MAX(date) AS d FROM listed_info").fetchone()
        d = row2["d"] if row2 else None
    if not d:
        raise RuntimeError("listed_info is empty. Run listed ETL.")
    return d


def _load_universe(conn, listed_date: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT code, company_name, market_name, sector17, sector33
        FROM listed_info
        WHERE date = ?
        """,
        conn,
        params=(listed_date,),
    )
    # Prime only (表記ゆれ耐性)
    df = df[df["market_name"].astype(str).str.contains("プライム|Prime", na=False)].copy()
    return df


def _load_prices_window(conn, price_date: str, lookback_days: int = 200) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT date, code, close, adj_close, turnover_value
        FROM prices_daily
        WHERE date <= ?
        """,
        conn,
        params=(price_date,),
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    df = df.groupby("code", group_keys=False).tail(lookback_days)
    return df


def _save_fy_to_statements(conn, fy_df: pd.DataFrame):
    """
    FYデータをfins_statementsテーブルに保存
    
    Args:
        conn: データベース接続
        fy_df: FYデータのDataFrame
    """
    if fy_df.empty:
        return
    
    # 保存用のデータを作成
    save_data = []
    for _, row in fy_df.iterrows():
        # datetimeオブジェクトを文字列に変換
        disclosed_date = row["disclosed_date"]
        if pd.notna(disclosed_date):
            if hasattr(disclosed_date, 'strftime'):
                disclosed_date = disclosed_date.strftime("%Y-%m-%d")
            else:
                disclosed_date = str(disclosed_date)
        else:
            disclosed_date = None
        
        current_period_end = row["current_period_end"]
        if pd.notna(current_period_end):
            if hasattr(current_period_end, 'strftime'):
                current_period_end = current_period_end.strftime("%Y-%m-%d")
            else:
                current_period_end = str(current_period_end)
        else:
            current_period_end = None
        
        # fins_statementsテーブルの全カラムを含む辞書を作成
        save_row = {
            "disclosed_date": disclosed_date,
            "disclosed_time": row.get("disclosed_time"),
            "code": str(row["code"]),
            "type_of_current_period": row.get("type_of_current_period", "FY"),
            "current_period_end": current_period_end,
            "operating_profit": row.get("operating_profit") if pd.notna(row.get("operating_profit")) else None,
            "profit": row.get("profit") if pd.notna(row.get("profit")) else None,
            "equity": row.get("equity") if pd.notna(row.get("equity")) else None,
            "eps": row.get("eps") if pd.notna(row.get("eps")) else None,
            "bvps": row.get("bvps") if pd.notna(row.get("bvps")) else None,
            "forecast_operating_profit": row.get("forecast_operating_profit") if pd.notna(row.get("forecast_operating_profit")) else None,
            "forecast_profit": row.get("forecast_profit") if pd.notna(row.get("forecast_profit")) else None,
            "forecast_eps": row.get("forecast_eps") if pd.notna(row.get("forecast_eps")) else None,
            "next_year_forecast_operating_profit": row.get("next_year_forecast_operating_profit") if pd.notna(row.get("next_year_forecast_operating_profit")) else None,
            "next_year_forecast_profit": row.get("next_year_forecast_profit") if pd.notna(row.get("next_year_forecast_profit")) else None,
            "next_year_forecast_eps": row.get("next_year_forecast_eps") if pd.notna(row.get("next_year_forecast_eps")) else None,
            "shares_outstanding": row.get("shares_outstanding") if pd.notna(row.get("shares_outstanding")) else None,
            "treasury_shares": row.get("treasury_shares") if pd.notna(row.get("treasury_shares")) else None,
        }
        save_data.append(save_row)
    
    # データベースに保存（UPSERT）
    upsert(
        conn,
        "fins_statements",
        save_data,
        conflict_columns=["disclosed_date", "code", "type_of_current_period", "current_period_end"],
    )


def _load_latest_fy(conn, asof: str) -> pd.DataFrame:
    """
    最新のFY実績データを取得（銘柄ごとに最新1件をSQLで確定）
    計算日（asof）以前のFYデータを使用し、開示日が最新のものを選ぶ（当期末ではなく開示日を基準にする）
    
    同じcurrent_period_endのFYデータ間で相互補完を行う：
    - 実績値が欠損している場合、他のFYレコードから実績値を補完（実績値同士で補完）
    - 予想値が欠損している場合、他のFYレコードから予想値を補完（予想値同士で補完）
    - 予想値については、FYレコードから見つからない場合は後で四半期データから補完される（_load_latest_forecastで処理）
    - equity, bvps, shares_outstanding, treasury_sharesは同じ種類のデータ間で補完
    
    注意: SQL側でROW_NUMBER()を使用して銘柄ごとに最新のcurrent_period_endを選び、
          その後Python側で同じcurrent_period_endのデータを集約して相互補完を行います。
    
    変更点: フィルタリング条件を緩和し、主要項目が全て欠損していてもレコードを取得するように変更
            （欠損率を下げるため）
    """
    # まず、銘柄ごとに最新のcurrent_period_endを選ぶ（SQL側で確定）
    # 重要: current_period_end <= asof の条件を追加（計算日より後の期末日のデータは実績値が入っていないため除外）
    # フィルタリング条件を緩和：主要項目が全て欠損していても取得（後でPython側で補完）
    df_latest_period = pd.read_sql_query(
        """
        WITH ranked AS (
          SELECT
            code, current_period_end,
            ROW_NUMBER() OVER (
              PARTITION BY code
              ORDER BY current_period_end DESC, disclosed_date DESC
            ) AS rn
          FROM fins_statements
          WHERE disclosed_date <= ?
            AND current_period_end <= ?
            AND type_of_current_period = 'FY'
        )
        SELECT code, current_period_end
        FROM ranked
        WHERE rn = 1
        """,
        conn,
        params=(asof, asof),
    )
    
    if df_latest_period.empty:
        return pd.DataFrame()
    
    # 最新のcurrent_period_endを持つレコードを全て取得（相互補完のため）
    # 同じcurrent_period_endの複数レコードがある場合に備える
    # (code, current_period_end)のペアでJOINすることで、別銘柄の期末日が混ざることを防止
    # 重要: current_period_end <= asof の条件を追加（計算日より後の期末日のデータは実績値が入っていないため除外）
    # フィルタリング条件を緩和：主要項目が全て欠損していても取得（後でPython側で補完）
    df = pd.read_sql_query(
        """
        WITH latest AS (
          SELECT
            code, current_period_end
          FROM (
            SELECT
              code, current_period_end,
              ROW_NUMBER() OVER (
                PARTITION BY code
                ORDER BY current_period_end DESC, disclosed_date DESC
              ) AS rn
            FROM fins_statements
            WHERE disclosed_date <= ?
              AND current_period_end <= ?
              AND type_of_current_period = 'FY'
          )
          WHERE rn = 1
        )
        SELECT
          fs.disclosed_date, fs.disclosed_time, fs.code, fs.type_of_current_period, fs.current_period_end,
          fs.operating_profit, fs.profit, fs.equity, fs.eps, fs.bvps,
          fs.forecast_operating_profit, fs.forecast_profit, fs.forecast_eps,
          fs.next_year_forecast_operating_profit, fs.next_year_forecast_profit, fs.next_year_forecast_eps,
          fs.shares_outstanding, fs.treasury_shares
        FROM fins_statements fs
        JOIN latest l
          ON fs.code = l.code
         AND fs.current_period_end = l.current_period_end
        WHERE fs.disclosed_date <= ?
          AND fs.current_period_end <= ?
          AND fs.type_of_current_period = 'FY'
        """,
        conn,
        params=(asof, asof, asof, asof),
    )
    if df.empty:
        return pd.DataFrame()
    
    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
    
    # 主要項目（operating_profit, profit, equity）が全て欠損のレコードも含める
    # （後で相互補完を行うため、主要項目が全て欠損していても取得）
    # ただし、shares_outstandingやtreasury_sharesなどの基本情報が全くないレコードは除外
    # 注意: この段階では除外しない（後で相互補完を行うため）
    
    # 同じcurrent_period_endのFYデータ間で相互補完
    # 各code、current_period_endごとに、全てのレコードを集約して補完
    # 実績値は実績値同士で補完、予想値は予想値同士で補完（相互補完しない）
    result_rows = []
    for (code, period_end), group in df.groupby(["code", "current_period_end"]):
        # 開示日が最新のレコードをベースにする
        group_sorted = group.sort_values("disclosed_date", ascending=False)
        base_row = group_sorted.iloc[0].copy()
        
        # 同じcurrent_period_endの全レコードから、欠損している項目を補完
        # 補完元のレコードは、該当項目が有効な値を持つレコードのみを使用
        
        # operating_profitが欠損している場合、他のFYレコードのoperating_profitから補完（実績値同士で補完）
        if pd.isna(base_row["operating_profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["operating_profit"]):
                    base_row["operating_profit"] = row["operating_profit"]
                    break
        
        # forecast_operating_profitが欠損している場合、他のFYレコードのforecast_operating_profitから補完（予想値同士で補完）
        # 注意: 予想値は後で四半期データからも補完される可能性がある（_load_latest_forecastで処理）
        if pd.isna(base_row["forecast_operating_profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["forecast_operating_profit"]):
                    base_row["forecast_operating_profit"] = row["forecast_operating_profit"]
                    break
        
        # profitが欠損している場合、他のFYレコードのprofitから補完（実績値同士で補完）
        if pd.isna(base_row["profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["profit"]):
                    base_row["profit"] = row["profit"]
                    break
        
        # forecast_profitが欠損している場合、他のFYレコードのforecast_profitから補完（予想値同士で補完）
        # 注意: 予想値は後で四半期データからも補完される可能性がある（_load_latest_forecastで処理）
        if pd.isna(base_row["forecast_profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["forecast_profit"]):
                    base_row["forecast_profit"] = row["forecast_profit"]
                    break
        
        # epsが欠損している場合、他のFYレコードのepsから補完（実績値同士で補完）
        if pd.isna(base_row["eps"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["eps"]):
                    base_row["eps"] = row["eps"]
                    break
        
        # forecast_epsが欠損している場合、他のFYレコードのforecast_epsから補完（予想値同士で補完）
        # 注意: 予想値は後で四半期データからも補完される可能性がある（_load_latest_forecastで処理）
        if pd.isna(base_row["forecast_eps"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["forecast_eps"]):
                    base_row["forecast_eps"] = row["forecast_eps"]
                    break
        
        # equityが欠損している場合、他のレコードのequityから補完
        if pd.isna(base_row["equity"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["equity"]):
                    base_row["equity"] = row["equity"]
                    break
        
        # bvpsが欠損している場合、他のレコードのbvpsから補完
        if pd.isna(base_row["bvps"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["bvps"]):
                    base_row["bvps"] = row["bvps"]
                    break
        
        # shares_outstandingが欠損している場合、他のレコードのshares_outstandingから補完
        if pd.isna(base_row["shares_outstanding"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["shares_outstanding"]):
                    base_row["shares_outstanding"] = row["shares_outstanding"]
                    break
        
        # treasury_sharesが欠損している場合、他のレコードのtreasury_sharesから補完
        if pd.isna(base_row["treasury_shares"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["treasury_shares"]):
                    base_row["treasury_shares"] = row["treasury_shares"]
                    break
        
        result_rows.append(base_row)
    
    if not result_rows:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(result_rows)
    
    # 実績値がある最新の期（current_period_end）を選ぶ
    # 実績値（operating_profit, profit, equity）があるレコードを優先し、
    # その中で最新のcurrent_period_endを持つレコードを選ぶ
    # 実績値がない場合は、予想値がある最新のcurrent_period_endを持つレコードを選ぶ
    def _has_actuals(row):
        return (
            pd.notna(row.get("operating_profit")) or
            pd.notna(row.get("profit")) or
            pd.notna(row.get("equity"))
        )
    
    # 実績値の有無をフラグとして追加
    result_df["has_actuals"] = result_df.apply(_has_actuals, axis=1)
    
    # 実績値があるレコードを優先し、その中で最新のcurrent_period_endを選ぶ
    result_df = result_df.sort_values(["code", "has_actuals", "current_period_end"], ascending=[True, False, False])
    latest = result_df.groupby("code", as_index=False).head(1).copy()
    
    # has_actualsカラムを削除（不要なため）
    latest = latest.drop(columns=["has_actuals"])
    
    return latest


def _load_fy_history(conn, asof: str, years: int = 10) -> pd.DataFrame:
    """
    過去のFY実績データを取得（最大years年分）
    各current_period_endごとに開示日が最新のものを選ぶ
    主要項目（operating_profit, profit, equity）が全て欠損のレコードは除外
    
    重要: current_period_end <= asof の条件を追加（計算日より後の期末日のデータは実績値が入っていないため除外）
    
    注意: 欠損値は四半期データで補完しない（会計基準変更などで古い開示日のデータが
          NULLに書き換えられている可能性があるため）
    """
    df = pd.read_sql_query(
        """
        SELECT code, disclosed_date, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND current_period_end <= ?
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL)
        """,
        conn,
        params=(asof, asof),
    )
    if df.empty:
        return df
    
    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
    # 各current_period_endごとに開示日が最新のものを選ぶ
    df = df.sort_values(["code", "current_period_end", "disclosed_date"])
    df = df.groupby(["code", "current_period_end"], as_index=False).tail(1)
    # その中で、current_period_endが新しい順に並べて、最大years年分を取得
    df = df.sort_values(["code", "current_period_end"], ascending=[True, False])
    df = df.groupby("code", group_keys=False).head(years)
    
    # 発行済み株式数の変化から株式分割/併合を検出し、履歴データのEPS/BPSも最新基準に調整
    if not df.empty:
        # 各銘柄の最新期の発行済み株式数（自己株式除く）と純資産を取得
        latest_shares_map = {}
        latest_equity_map = {}
        for code in df["code"].unique():
            code_data = df[df["code"] == code].sort_values("current_period_end", ascending=False)
            if not code_data.empty:
                latest_row = code_data.iloc[0]
                shares_outstanding = latest_row.get("shares_outstanding")
                treasury_shares = latest_row.get("treasury_shares") or 0.0
                equity = latest_row.get("equity")
                if pd.notna(shares_outstanding):
                    latest_shares_map[code] = shares_outstanding - treasury_shares
                if pd.notna(equity):
                    latest_equity_map[code] = equity
        
        # 各期のEPS/BPSを調整
        def _adjust_hist_bps_eps(row):
            code = row.get("code")
            period_end = row.get("current_period_end")
            latest_shares = latest_shares_map.get(code)
            latest_equity = latest_equity_map.get(code)
            
            if pd.isna(period_end) or not code or latest_shares is None or latest_shares <= 0 or latest_equity is None or latest_equity <= 0:
                return row.get("bvps"), row.get("eps")
            
            if hasattr(period_end, 'strftime'):
                period_end_str = period_end.strftime("%Y-%m-%d")
            else:
                period_end_str = str(period_end)
            
            adjustment_factor = _get_shares_adjustment_factor(conn, code, period_end_str, latest_shares, latest_equity)
            
            bvps = row.get("bvps")
            eps = row.get("eps")
            
            # 調整係数を掛ける（最新期の発行済み株式数が多い場合、過去のEPS/BPSを減らす）
            # 例: 分割前100株、分割後300株の場合、調整係数 = 100/300 = 0.333
            #     分割前のEPS 1.0円 → 調整後EPS 1.0 × 0.333 = 0.333円（分割後の基準に合わせる）
            adjusted_bvps = bvps * adjustment_factor if pd.notna(bvps) and adjustment_factor != 1.0 else bvps
            adjusted_eps = eps * adjustment_factor if pd.notna(eps) and adjustment_factor != 1.0 else eps
            
            return adjusted_bvps, adjusted_eps
        
        adjusted_hist_values = df.apply(_adjust_hist_bps_eps, axis=1)
        df["bvps"] = adjusted_hist_values.apply(lambda x: x[0])
        df["eps"] = adjusted_hist_values.apply(lambda x: x[1])
    
    # 注意: 履歴データの補完処理は実行しない
    # （会計基準変更などで古い開示日のデータがNULLに書き換えられている可能性があるため、
    #   forecastデータで補完するよりも、欠損のない直近のFYレコードを使用する方が適切）
    
    return df


def _load_latest_forecast(conn, asof: str) -> pd.DataFrame:
    """
    最新の予想データを取得（銘柄ごとに最新1件をSQLで確定）
    
    予測値についてはFY行にデータがなければ四半期データも3Q→2Q→1Qの順で採用する。
    
    優先順位:
    1. FYデータ（開示日が最新のもの、予想値があるもの）
    2. 四半期データ（3Q → 2Q → 1Qの順、開示日が最新のもの）
    
    注意: _load_latest_fyで既に同じcurrent_period_endのFYデータ間で相互補完を行っているため、
          この関数は主に四半期データから予想を取得する場合に使用される
    """
    # まずFYデータを取得（開示日が最新のもの）
    # 重要: current_period_end <= asof の条件を追加（計算日より後の期末日のデータは実績値が入っていないため除外）
    df_fy = pd.read_sql_query(
        """
        WITH ranked AS (
          SELECT
            code, disclosed_date, type_of_current_period,
            forecast_operating_profit, forecast_profit, forecast_eps,
            next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
            ROW_NUMBER() OVER (
              PARTITION BY code
              ORDER BY disclosed_date DESC
            ) AS rn
          FROM fins_statements
          WHERE disclosed_date <= ?
            AND current_period_end <= ?
            AND type_of_current_period = 'FY'
            AND (forecast_operating_profit IS NOT NULL 
                 OR forecast_profit IS NOT NULL 
                 OR forecast_eps IS NOT NULL)
        )
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM ranked
        WHERE rn = 1
        """,
        conn,
        params=(asof, asof),
    )
    
    # FYデータに予想値がある銘柄のリスト
    codes_with_fy_forecast = set(df_fy["code"].tolist()) if not df_fy.empty else set()
    
    # FYデータに予想値がない銘柄について、四半期データを取得（3Q→2Q→1Qの順）
    df_quarter = pd.read_sql_query(
        """
        WITH ranked AS (
          SELECT
            code, disclosed_date, type_of_current_period,
            forecast_operating_profit, forecast_profit, forecast_eps,
            next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
            ROW_NUMBER() OVER (
              PARTITION BY code
              ORDER BY disclosed_date DESC,
                       CASE 
                         WHEN type_of_current_period = '3Q' THEN 1
                         WHEN type_of_current_period = '2Q' THEN 2
                         WHEN type_of_current_period = '1Q' THEN 3
                         ELSE 4
                       END
            ) AS rn
          FROM fins_statements
          WHERE disclosed_date <= ?
            AND type_of_current_period IN ('3Q', '2Q', '1Q')
            AND (forecast_operating_profit IS NOT NULL 
                 OR forecast_profit IS NOT NULL 
                 OR forecast_eps IS NOT NULL)
        )
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM ranked
        WHERE rn = 1
        """,
        conn,
        params=(asof,),
    )
    
    # FYデータに予想値がない銘柄のみ四半期データを採用
    if not df_quarter.empty:
        df_quarter = df_quarter[~df_quarter["code"].isin(codes_with_fy_forecast)]
    
    # FYデータと四半期データを結合
    if df_fy.empty and df_quarter.empty:
        return pd.DataFrame()
    elif df_fy.empty:
        df = df_quarter
    elif df_quarter.empty:
        df = df_fy
    else:
        df = pd.concat([df_fy, df_quarter], ignore_index=True)
    
    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    return df


# -----------------------------
# Feature building
# -----------------------------

def build_features(conn, asof: str) -> pd.DataFrame:
    price_date = _snap_price_date(conn, asof)
    listed_date = _snap_listed_date(conn, price_date)

    print(f"[monthly] asof requested={asof} | price_date={price_date} | listed_date={listed_date}")

    universe = _load_universe(conn, listed_date)
    print(f"[count] universe (Prime): {len(universe)}")

    prices_win = _load_prices_window(conn, price_date, lookback_days=200)
    print(f"[count] prices rows (window): {len(prices_win)}")

    # 未調整終値（close）を使用（標準的なロジック）
    px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "close"]].copy()
    px_today = px_today.rename(columns={"close": "price"})
    print(f"[count] prices today codes: {len(px_today)}")

    # Liquidity (60d avg turnover_value) - fixed (no Series groupby(as_index=False))
    tmp = prices_win[["code", "date", "turnover_value"]].copy()
    tmp = tmp.sort_values(["code", "date"])
    tmp = tmp.groupby("code", group_keys=False).tail(60)
    liq = tmp.groupby("code", as_index=False)["turnover_value"].mean()
    liq = liq.rename(columns={"turnover_value": "liquidity_60d"})

    fy_latest = _load_latest_fy(conn, price_date)
    print(f"[count] latest FY rows: {len(fy_latest)}")
    
    # 株式分割情報テーブルが存在するか確認（存在しない場合は作成）
    try:
        conn.execute("SELECT 1 FROM stock_splits LIMIT 1")
    except:
        # テーブルが存在しない場合は作成
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_splits (
                code TEXT NOT NULL,
                split_date TEXT NOT NULL,
                split_ratio REAL NOT NULL,
                description TEXT,
                PRIMARY KEY (code, split_date)
            )
        """)
        conn.commit()

    fc_latest = _load_latest_forecast(conn, price_date)
    print(f"[count] latest forecast rows: {len(fc_latest)}")

    fy_hist = _load_fy_history(conn, price_date, years=10)
    print(f"[count] FY history rows (<=10 per code): {len(fy_hist)}")

    df = universe.merge(px_today, on="code", how="inner")
    df = df.merge(liq, on="code", how="left")
    
    # fy_latestとfc_latestのカラム名の競合を解決
    # fc_latestのカラム名に_fcサフィックスを付ける（マージ前にリネーム）
    fc_latest_renamed = fc_latest.copy()
    forecast_cols = [
        "forecast_operating_profit", "forecast_profit", "forecast_eps",
        "next_year_forecast_operating_profit", "next_year_forecast_profit", "next_year_forecast_eps"
    ]
    rename_dict = {}
    for col in forecast_cols:
        if col in fc_latest_renamed.columns:
            rename_dict[col] = f"{col}_fc"
    if rename_dict:
        fc_latest_renamed = fc_latest_renamed.rename(columns=rename_dict)
    
    df = df.merge(fy_latest, on="code", how="left", suffixes=("", "_fy"))
    
    # 予想値が欠損している場合のみ、四半期データから補完
    # fy_latestの予想値が欠損している場合のみ、fc_latest_renamedの予想値を使用
    df = df.merge(fc_latest_renamed, on="code", how="left", suffixes=("", "_fc"))
    
    # 予想値の補完: fy_latestに予想値がない場合のみ、fc_latest_renamedの予想値を使用
    forecast_cols_to_fill = [
        "forecast_operating_profit", "forecast_profit", "forecast_eps",
        "next_year_forecast_operating_profit", "next_year_forecast_profit", "next_year_forecast_eps"
    ]
    for col in forecast_cols_to_fill:
        col_fc = f"{col}_fc"
        if col_fc in df.columns:
            # fy_latestの予想値が欠損している場合のみ、fc_latest_renamedの予想値で補完
            mask = df[col].isna() & df[col_fc].notna()
            df.loc[mask, col] = df.loc[mask, col_fc]
    
    # _fcサフィックス付きのカラムを削除（補完済みのため不要）
    # ただし、後続のコードで使用される可能性があるため、一時的に残す
    # 実際には、元のカラム（forecast_*）を使用するように後続のコードを修正済み

    print(f"[count] merged base rows: {len(df)}")
    
    # マージ後の埋まり率を表示（デバッグ用）
    print("\n[coverage] マージ後のデータ埋まり率:")
    key_columns = [
        "forecast_eps",
        "forecast_operating_profit",
        "forecast_profit",
        "operating_profit",
        "profit",
        "equity",
        "bvps",
    ]
    for col in key_columns:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            coverage = (non_null_count / len(df)) * 100.0 if len(df) > 0 else 0.0
            print(f"  {col}: {non_null_count}/{len(df)} ({coverage:.1f}%)")

    # Actual ROE (latest FY)
    df["roe"] = df.apply(lambda r: _safe_div(r.get("profit"), r.get("equity")), axis=1)

    # 標準的なロジック: EPS/BPS/予想EPSを自前で計算
    # 1. FY期末のネット株数を計算
    # 注意: treasury_sharesがnp.nanの場合は0扱い（明示的に処理）
    def _calculate_net_shares_fy(row):
        """FY期末のネット株数を計算"""
        so = row.get("shares_outstanding")
        ts = row.get("treasury_shares")
        
        if pd.isna(so) or so <= 0:
            return np.nan
        
        # treasury_sharesがnp.nanの場合は0扱い（明示的に処理）
        if pd.isna(ts):
            ts = 0.0
        elif ts < 0:
            ts = 0.0
        
        net_shares = so - ts
        return net_shares if net_shares > 0 else np.nan
    
    df["net_shares_fy"] = df.apply(_calculate_net_shares_fy, axis=1)

    # 2. FY期末から評価日までの分割倍率を計算（性能最適化: 一括取得）
    # 銘柄ごとに1回だけSQLを実行するように最適化
    # 先に「銘柄→fy_end」を1回で作る（O(N^2)を回避）
    fy_end_by_code = (
        df[["code", "current_period_end"]]
        .dropna(subset=["code"])
        .drop_duplicates(subset=["code"])
        .set_index("code")["current_period_end"]
        .to_dict()
    )
    
    # 日付型に統一して比較（型安全）
    price_dt = pd.to_datetime(price_date).date()
    
    split_mult_dict = {}
    for code, fy_end in fy_end_by_code.items():
        if pd.isna(fy_end):
            split_mult_dict[code] = 1.0
            continue
        
        # datetime型に変換して日付部分のみ取得
        fy_end_dt = pd.to_datetime(fy_end, errors="coerce")
        if pd.isna(fy_end_dt):
            split_mult_dict[code] = 1.0
            continue
        
        fy_end_date = fy_end_dt.date()
        
        # fy_end >= price_date の防御（異常な将来日付の場合は倍率=1.0）
        if fy_end_date >= price_dt:
            split_mult_dict[code] = 1.0
            continue
        
        # 文字列に変換して_split_multiplier_betweenに渡す
        fy_end_str = fy_end_date.strftime("%Y-%m-%d")
        split_mult_dict[code] = _split_multiplier_between(conn, code, fy_end_str, price_date)
    
    # dictからmapで流し込む
    df["split_mult_fy_to_price"] = df["code"].map(split_mult_dict).fillna(1.0)

    # 3. 評価日時点のネット株数（補正後）を計算（ベクトル化）
    # 注意: 株数は「発行済み株式数 - 自己株式数」（ネット株数）を使用
    # これは市場で取引可能な株数を表し、標準的なPER/PBR計算に適している
    df["net_shares_at_price"] = (
        df["net_shares_fy"] * df["split_mult_fy_to_price"]
    ).where(
        (df["net_shares_fy"].notna()) & 
        (df["split_mult_fy_to_price"].notna()) & 
        (df["net_shares_fy"] > 0),
        np.nan
    )

    # 4. 標準EPS/BPS/予想EPSを計算（ベクトル化）
    # 標準EPS（実績）
    # 注意: profit <= 0 の場合はNaN（負のPERは意味がないため、スクリーニング用途として妥当）
    df["eps_std"] = np.where(
        (df["profit"].notna()) & 
        (df["net_shares_at_price"].notna()) & 
        (df["profit"] > 0) & 
        (df["net_shares_at_price"] > 0),
        df["profit"] / df["net_shares_at_price"],
        np.nan
    )

    # 標準BPS（実績）
    df["bps_std"] = np.where(
        (df["equity"].notna()) & 
        (df["net_shares_at_price"].notna()) & 
        (df["equity"] > 0) & 
        (df["net_shares_at_price"] > 0),
        df["equity"] / df["net_shares_at_price"],
        np.nan
    )

    # 標準予想EPS（予想）
    # 列名の存在チェック（merge後の列名を確認）
    forecast_profit_col = None
    forecast_eps_col = None
    
    # forecast_profit を使用（_fcサフィックス付きのカラムは補完済み）
    if "forecast_profit" in df.columns:
        forecast_profit_col = "forecast_profit"
    else:
        forecast_profit_col = None
        print("[warning] forecast_profit not found")
    
    # forecast_eps を使用（_fcサフィックス付きのカラムは補完済み）
    if "forecast_eps" in df.columns:
        forecast_eps_col = "forecast_eps"
    else:
        forecast_eps_col = None
        print("[warning] forecast_eps not found")
    
    # 第一優先: forecast_profitから計算（ベクトル化）
    if forecast_profit_col:
        df["forecast_eps_std"] = np.where(
            (df[forecast_profit_col].notna()) & 
            (df["net_shares_at_price"].notna()) & 
            (df[forecast_profit_col] > 0) & 
            (df["net_shares_at_price"] > 0),
            df[forecast_profit_col] / df["net_shares_at_price"],
            np.nan
        )
        # フォールバック使用率を可視化
        profit_based_count = df["forecast_eps_std"].notna().sum()
        total_count = len(df)
        print(f"[forecast_eps] forecast_profitベース: {profit_based_count}/{total_count} ({profit_based_count/total_count*100:.1f}%)")
    else:
        df["forecast_eps_std"] = np.nan
    
    # フォールバック: forecast_eps（J-Quants）を使う
    # forecast_profitが欠損している場合のみ
    # 注意: forecast_epsの株数基準が不明確な場合があるため、ログで可視化
    if forecast_eps_col:
        fallback_mask = df["forecast_eps_std"].isna() & df[forecast_eps_col].notna() & (df[forecast_eps_col] > 0)
        df.loc[fallback_mask, "forecast_eps_std"] = df.loc[fallback_mask, forecast_eps_col]
        
        # フォールバック使用率を可視化
        fallback_count = fallback_mask.sum()
        if fallback_count > 0:
            print(f"[forecast_eps] forecast_epsフォールバック: {fallback_count}/{total_count} ({fallback_count/total_count*100:.1f}%)")
            # フォールバック銘柄に印を付ける（デバッグ用）
            df["forecast_eps_source"] = np.where(
                fallback_mask,
                "eps_fallback",
                np.where(df["forecast_eps_std"].notna(), "profit_based", "missing")
            )

    # 5. PER/PBR/Forward PERを標準的な方法で計算（ベクトル化）
    # 実績PER（Trailing PER）
    df["per"] = np.where(
        (df["eps_std"].notna()) & (df["eps_std"] > 0) & (df["price"].notna()),
        df["price"] / df["eps_std"],
        np.nan
    )

    # 実績PBR
    df["pbr"] = np.where(
        (df["bps_std"].notna()) & (df["bps_std"] > 0) & (df["price"].notna()),
        df["price"] / df["bps_std"],
        np.nan
    )

    # 予想PER（Forward PER）
    df["forward_per"] = np.where(
        (df["forecast_eps_std"].notna()) & (df["forecast_eps_std"] > 0) & (df["price"].notna()),
        df["price"] / df["forecast_eps_std"],
        np.nan
    )

    # 時価総額も計算（他の用途で使用される可能性があるため）
    df["market_cap_latest_basis"] = df.apply(
        lambda r: r.get("price") * r.get("net_shares_at_price")
        if pd.notna(r.get("price")) and pd.notna(r.get("net_shares_at_price")) and r.get("net_shares_at_price") > 0
        else np.nan,
        axis=1
    )
    
    # 一時カラムを削除
    if "latest_shares" in df.columns:
        df = df.drop(columns=["latest_shares"])
    if "latest_equity" in df.columns:
        df = df.drop(columns=["latest_equity"])

    # Growth from forecasts vs latest FY
    df["op_growth"] = df.apply(lambda r: _safe_div(r.get("forecast_operating_profit"), r.get("operating_profit")) - 1.0, axis=1)
    df["profit_growth"] = df.apply(lambda r: _safe_div(r.get("forecast_profit"), r.get("profit")) - 1.0, axis=1)

    # Record high (forecast OP vs past max FY OP)
    if not fy_hist.empty:
        op_max = fy_hist.groupby("code", as_index=False)["operating_profit"].max().rename(columns={"operating_profit": "op_max_past"})
        df = df.merge(op_max, on="code", how="left")
    else:
        df["op_max_past"] = np.nan

    df["record_high_forecast_flag"] = (
        (df["forecast_operating_profit"].notna()) &
        (df["op_max_past"].notna()) &
        (df["forecast_operating_profit"] >= df["op_max_past"])
    ).astype(int)

    # Operating profit trend (5y slope)  ← A案
    if not fy_hist.empty:
        fh = fy_hist.copy()
        fh["current_period_end"] = pd.to_datetime(fh["current_period_end"], errors="coerce")
        fh = fh.sort_values(["code", "current_period_end"])

        slopes = []
        for code, g in fh.groupby("code"):
            vals = g["operating_profit"].tail(5).tolist()
            slopes.append((code, _calc_slope(vals)))

        op_trend_df = pd.DataFrame(slopes, columns=["code", "op_trend"])
        df = df.merge(op_trend_df, on="code", how="left")
    else:
        df["op_trend"] = np.nan

    # ROE trend (current ROE - average of past 4 periods ROE)
    if not fy_hist.empty and not fy_latest.empty:
        fh = fy_hist.copy()
        fh["current_period_end"] = pd.to_datetime(fh["current_period_end"], errors="coerce")
        fh = fh.sort_values(["code", "current_period_end"])
        
        # Get latest period_end for each code
        latest_periods = fy_latest[["code", "current_period_end"]].copy()
        latest_periods["current_period_end"] = pd.to_datetime(latest_periods["current_period_end"], errors="coerce")
        
        # Calculate ROE for each period
        fh["roe_hist"] = fh.apply(lambda r: _safe_div(r.get("profit"), r.get("equity")), axis=1)
        
        roe_trends = []
        for code, g in fh.groupby("code"):
            # Get current ROE from latest FY (from df, which has the latest period)
            current_roe_row = df[df["code"] == code]
            if len(current_roe_row) == 0:
                roe_trends.append((code, np.nan))
                continue
            
            current_roe = current_roe_row["roe"].iloc[0]
            if pd.isna(current_roe):
                roe_trends.append((code, np.nan))
                continue
            
            # Get latest period_end for this code
            latest_period_row = latest_periods[latest_periods["code"] == code]
            if len(latest_period_row) == 0:
                roe_trends.append((code, np.nan))
                continue
            
            latest_period_end = latest_period_row["current_period_end"].iloc[0]
            
            # Get past 4 periods ROE (excluding the latest period)
            past_periods = g[g["current_period_end"] < latest_period_end]
            if len(past_periods) == 0:
                roe_trends.append((code, np.nan))
                continue
            
            past_roes = past_periods["roe_hist"].tail(4).tolist()
            past_roes = [r for r in past_roes if r is not None and not pd.isna(r)]
            
            if len(past_roes) < 4:
                roe_trends.append((code, np.nan))
                continue
            
            avg_past_roe = sum(past_roes) / len(past_roes)
            roe_trend = current_roe - avg_past_roe
            roe_trends.append((code, roe_trend))
        
        roe_trend_df = pd.DataFrame(roe_trends, columns=["code", "roe_trend"])
        df = df.merge(roe_trend_df, on="code", how="left")
    else:
        df["roe_trend"] = np.nan

    # Market cap (最新株数ベースを使用)
    # 既に計算済みのmarket_cap_latest_basisを使用
    df["market_cap"] = df["market_cap_latest_basis"]
    
    # 計算後の埋まり率を表示（デバッグ用）
    print("\n[coverage] 計算後の特徴量埋まり率:")
    feature_columns = [
        "forward_per",
        "op_growth",
        "profit_growth",
        "roe",
        "pbr",
        "market_cap",
    ]
    for col in feature_columns:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            coverage = (non_null_count / len(df)) * 100.0 if len(df) > 0 else 0.0
            print(f"  {col}: {non_null_count}/{len(df)} ({coverage:.1f}%)")
    
    # fc_latestのcode型/桁の確認（デバッグ用）
    if not fc_latest.empty and "code" in fc_latest.columns:
        fc_codes = set(fc_latest["code"].astype(str).str.strip())
        df_codes = set(df["code"].astype(str).str.strip())
        matched = len(fc_codes & df_codes)
        print(f"\n[debug] fc_latest code matching: {matched}/{len(df_codes)} ({matched/len(df_codes)*100:.1f}% if df_codes > 0)")
        if matched < len(df_codes) * 0.8:  # 80%未満の場合は警告
            print(f"  [warning] fc_latestのcodeマッチ率が低いです。code型/桁の不一致の可能性があります。")
            sample_fc = list(fc_codes)[:5] if fc_codes else []
            sample_df = list(df_codes)[:5] if df_codes else []
            print(f"  sample fc_latest codes: {sample_fc}")
            print(f"  sample df codes: {sample_df}")
    
    # 予想があるのに実績がないケースを確認（デバッグ用）
    has_forecast_op = df["forecast_operating_profit"].notna()
    has_actual_op = df["operating_profit"].notna()
    forecast_only = df[has_forecast_op & ~has_actual_op]
    if len(forecast_only) > 0:
        print(f"\n[debug] 予想営業利益があるのに実績営業利益がない銘柄: {len(forecast_only)}件")
        print(f"  sample codes: {forecast_only['code'].head(10).tolist()}")
    
    has_forecast_profit = df["forecast_profit"].notna()
    has_actual_profit = df["profit"].notna()
    forecast_profit_only = df[has_forecast_profit & ~has_actual_profit]
    if len(forecast_profit_only) > 0:
        print(f"[debug] 予想利益があるのに実績利益がない銘柄: {len(forecast_profit_only)}件")
        print(f"  sample codes: {forecast_profit_only['code'].head(10).tolist()}")

    # Entry score
    if PARAMS.use_entry_score:
        close_map = {c: g["adj_close"].reset_index(drop=True) for c, g in prices_win.groupby("code")}
        df["entry_score"] = df["code"].apply(lambda c: _entry_score(close_map.get(c)) if c in close_map else np.nan)
    else:
        df["entry_score"] = np.nan

    # Industry-relative valuation scores
    df["forward_per_pct"] = df.groupby("sector33")["forward_per"].transform(lambda s: _pct_rank(s, ascending=True))
    df["pbr_pct"] = df.groupby("sector33")["pbr"].transform(lambda s: _pct_rank(s, ascending=True))
    df["value_score"] = PARAMS.w_forward_per * (1.0 - df["forward_per_pct"]) + PARAMS.w_pbr * (1.0 - df["pbr_pct"])

    # Size score
    df["log_mcap"] = df["market_cap"].apply(_log_safe)
    df["size_score"] = _pct_rank(df["log_mcap"], ascending=True)

    # Quality score: ROE only（ROE改善は不要という方針）
    df["roe_score"] = _pct_rank(df["roe"], ascending=True)
    df["quality_score"] = df["roe_score"]

    df["op_growth_score"] = _pct_rank(df["op_growth"], ascending=True).fillna(0.5)
    df["profit_growth_score"] = _pct_rank(df["profit_growth"], ascending=True).fillna(0.5)
    df["op_trend_score"] = _pct_rank(df["op_trend"], ascending=True).fillna(0.5)

    df["growth_score"] = (
        0.4 * df["op_growth_score"] +
        0.4 * df["profit_growth_score"] +
        0.2 * df["op_trend_score"]
    )

    # Record-high score
    df["record_high_score"] = df["record_high_forecast_flag"].astype(float)

    # ---- Make scores robust against NaN (critical) ----
    # Neutral defaults (0.5) for percentile-like scores
    df["value_score"] = df["value_score"].fillna(0.5)
    df["growth_score"] = df["growth_score"].fillna(0.5)
    df["size_score"] = df["size_score"].fillna(0.5)

    # quality: if roe missing -> 0 (will be filtered out later by ROE>=0.1 anyway)
    df["quality_score"] = df["quality_score"].fillna(0.0)

    # record-high: if missing -> 0
    df["record_high_score"] = df["record_high_score"].fillna(0.0)

    # Core score
    df["core_score"] = (
        PARAMS.w_quality * df["quality_score"] +
        PARAMS.w_value * df["value_score"] +
        PARAMS.w_growth * df["growth_score"] +
        PARAMS.w_record_high * df["record_high_score"] +
        PARAMS.w_size * df["size_score"]
    )

    df["core_score"] = df["core_score"].fillna(0.0)
    
    # 欠損値による影響の分析
    print("\n[missing_impact] 欠損値による不完全なスコアの割合:")
    
    # 各サブスコアの元となる特徴量が欠損していたかどうかを記録
    # （fillna前の状態を確認するため、計算前に記録が必要だが、ここでは計算結果から逆算）
    
    # value_scoreが不完全（forward_perまたはpbrが欠損）の場合
    missing_forward_per = df["forward_per"].isna()
    missing_pbr = df["pbr"].isna()
    incomplete_value = missing_forward_per | missing_pbr
    value_incomplete_pct = (incomplete_value.sum() / len(df)) * 100.0 if len(df) > 0 else 0.0
    print(f"  value_score不完全（forward_perまたはpbr欠損）: {incomplete_value.sum()}/{len(df)} ({value_incomplete_pct:.1f}%)")
    
    # growth_scoreが不完全（op_growthまたはprofit_growthが欠損）の場合
    missing_op_growth = df["op_growth"].isna()
    missing_profit_growth = df["profit_growth"].isna()
    incomplete_growth = missing_op_growth | missing_profit_growth
    growth_incomplete_pct = (incomplete_growth.sum() / len(df)) * 100.0 if len(df) > 0 else 0.0
    print(f"  growth_score不完全（op_growthまたはprofit_growth欠損）: {incomplete_growth.sum()}/{len(df)} ({growth_incomplete_pct:.1f}%)")
    
    # quality_scoreが不完全（roeが欠損）の場合
    missing_roe = df["roe"].isna()
    quality_incomplete_pct = (missing_roe.sum() / len(df)) * 100.0 if len(df) > 0 else 0.0
    print(f"  quality_score不完全（roe欠損）: {missing_roe.sum()}/{len(df)} ({quality_incomplete_pct:.1f}%)")
    
    # size_scoreが不完全（market_capが欠損）の場合
    missing_market_cap = df["market_cap"].isna()
    size_incomplete_pct = (missing_market_cap.sum() / len(df)) * 100.0 if len(df) > 0 else 0.0
    print(f"  size_score不完全（market_cap欠損）: {missing_market_cap.sum()}/{len(df)} ({size_incomplete_pct:.1f}%)")
    
    # record_high_scoreが不完全（record_high_forecast_flagが欠損）の場合
    missing_record_high = df["record_high_forecast_flag"].isna()
    record_high_incomplete_pct = (missing_record_high.sum() / len(df)) * 100.0 if len(df) > 0 else 0.0
    print(f"  record_high_score不完全（record_high_forecast_flag欠損）: {missing_record_high.sum()}/{len(df)} ({record_high_incomplete_pct:.1f}%)")
    
    # core_scoreが不完全（いずれかのサブスコアが不完全）の場合
    incomplete_core = incomplete_value | incomplete_growth | missing_roe | missing_market_cap | missing_record_high
    core_incomplete_pct = (incomplete_core.sum() / len(df)) * 100.0 if len(df) > 0 else 0.0
    print(f"  core_score不完全（いずれかのサブスコアが不完全）: {incomplete_core.sum()}/{len(df)} ({core_incomplete_pct:.1f}%)")
    
    # 各サブスコアの不完全さを加重平均して、core_scoreへの影響度を定量化
    print("\n[missing_impact] 各サブスコアの不完全さがcore_scoreに与える影響度（加重平均）:")
    
    # 各サブスコアの不完全な割合
    incomplete_rates = {
        "quality_score": quality_incomplete_pct / 100.0,
        "value_score": value_incomplete_pct / 100.0,
        "growth_score": growth_incomplete_pct / 100.0,
        "record_high_score": record_high_incomplete_pct / 100.0,
        "size_score": size_incomplete_pct / 100.0,
    }
    
    # 各サブスコアの重み
    weights = {
        "quality_score": PARAMS.w_quality,
        "value_score": PARAMS.w_value,
        "growth_score": PARAMS.w_growth,
        "record_high_score": PARAMS.w_record_high,
        "size_score": PARAMS.w_size,
    }
    
    # 不完全なスコアがデフォルト値（0.5または0.0）を使っている場合の影響度を計算
    # 完全なスコアの平均値とデフォルト値の差を推定
    # 実際のスコア分布から平均値を計算（不完全でない銘柄のみ）
    
    # quality_score: 不完全な場合は0.0（デフォルト）、完全な場合は実際のスコア
    if not df[~missing_roe].empty and "quality_score" in df.columns:
        complete_quality_mean = df[~missing_roe]["quality_score"].mean()
        quality_impact = incomplete_rates["quality_score"] * weights["quality_score"] * abs(complete_quality_mean - 0.0)
        print(f"  quality_score影響度: {quality_impact:.4f} (不完全率: {incomplete_rates['quality_score']*100:.1f}%, 重み: {weights['quality_score']:.2f}, 完全時平均: {complete_quality_mean:.3f})")
    else:
        quality_impact = 0.0
    
    # value_score: 不完全な場合は0.5（デフォルト）、完全な場合は実際のスコア
    if not df[~incomplete_value].empty and "value_score" in df.columns:
        complete_value_mean = df[~incomplete_value]["value_score"].mean()
        value_impact = incomplete_rates["value_score"] * weights["value_score"] * abs(complete_value_mean - 0.5)
        print(f"  value_score影響度: {value_impact:.4f} (不完全率: {incomplete_rates['value_score']*100:.1f}%, 重み: {weights['value_score']:.2f}, 完全時平均: {complete_value_mean:.3f})")
    else:
        value_impact = 0.0
    
    # growth_score: 不完全な場合は0.5（デフォルト）、完全な場合は実際のスコア
    if not df[~incomplete_growth].empty and "growth_score" in df.columns:
        complete_growth_mean = df[~incomplete_growth]["growth_score"].mean()
        growth_impact = incomplete_rates["growth_score"] * weights["growth_score"] * abs(complete_growth_mean - 0.5)
        print(f"  growth_score影響度: {growth_impact:.4f} (不完全率: {incomplete_rates['growth_score']*100:.1f}%, 重み: {weights['growth_score']:.2f}, 完全時平均: {complete_growth_mean:.3f})")
    else:
        growth_impact = 0.0
    
    # record_high_score: 不完全な場合は0.0（デフォルト）、完全な場合は実際のスコア
    if not df[~missing_record_high].empty and "record_high_score" in df.columns:
        complete_record_high_mean = df[~missing_record_high]["record_high_score"].mean()
        record_high_impact = incomplete_rates["record_high_score"] * weights["record_high_score"] * abs(complete_record_high_mean - 0.0)
        print(f"  record_high_score影響度: {record_high_impact:.4f} (不完全率: {incomplete_rates['record_high_score']*100:.1f}%, 重み: {weights['record_high_score']:.2f}, 完全時平均: {complete_record_high_mean:.3f})")
    else:
        record_high_impact = 0.0
    
    # size_score: 不完全な場合は0.5（デフォルト）、完全な場合は実際のスコア
    if not df[~missing_market_cap].empty and "size_score" in df.columns:
        complete_size_mean = df[~missing_market_cap]["size_score"].mean()
        size_impact = incomplete_rates["size_score"] * weights["size_score"] * abs(complete_size_mean - 0.5)
        print(f"  size_score影響度: {size_impact:.4f} (不完全率: {incomplete_rates['size_score']*100:.1f}%, 重み: {weights['size_score']:.2f}, 完全時平均: {complete_size_mean:.3f})")
    else:
        size_impact = 0.0
    
    # 全体の影響度（加重平均）
    total_impact = quality_impact + value_impact + growth_impact + record_high_impact + size_impact
    print(f"\n  [総合] core_scoreへの総合影響度: {total_impact:.4f}")
    print(f"    (core_scoreの理論的最大値は1.0、平均値は約0.5と想定)")
    
    # 各サブスコアの影響度の割合
    if total_impact > 0:
        print(f"\n  [影響度の内訳]")
        print(f"    quality_score: {quality_impact/total_impact*100:.1f}%")
        print(f"    value_score: {value_impact/total_impact*100:.1f}%")
        print(f"    growth_score: {growth_impact/total_impact*100:.1f}%")
        print(f"    record_high_score: {record_high_impact/total_impact*100:.1f}%")
        print(f"    size_score: {size_impact/total_impact*100:.1f}%")
    
    # フィルタ後の不完全なスコアの割合
    if "liquidity_60d" in df.columns and "roe" in df.columns:
        # 流動性フィルタとROEフィルタを適用
        after_liquidity = df[df["liquidity_60d"] >= df["liquidity_60d"].quantile(PARAMS.liquidity_quantile_cut)]
        after_roe = after_liquidity[after_liquidity["roe"] >= PARAMS.roe_min] if len(after_liquidity) > 0 else pd.DataFrame()
        
        if len(after_roe) > 0:
            incomplete_after_filters = (
                after_roe["forward_per"].isna() | after_roe["pbr"].isna() |
                after_roe["op_growth"].isna() | after_roe["profit_growth"].isna() |
                after_roe["market_cap"].isna() | after_roe["record_high_forecast_flag"].isna()
            )
            incomplete_after_pct = (incomplete_after_filters.sum() / len(after_roe)) * 100.0 if len(after_roe) > 0 else 0.0
            print(f"\n  [フィルタ後] 不完全なcore_scoreの割合: {incomplete_after_filters.sum()}/{len(after_roe)} ({incomplete_after_pct:.1f}%)")
            
            # プールサイズの銘柄についても確認
            pool = after_roe.sort_values("core_score", ascending=False).head(PARAMS.pool_size) if len(after_roe) > 0 else pd.DataFrame()
            if len(pool) > 0:
                incomplete_pool = (
                    pool["forward_per"].isna() | pool["pbr"].isna() |
                    pool["op_growth"].isna() | pool["profit_growth"].isna() |
                    pool["market_cap"].isna() | pool["record_high_forecast_flag"].isna()
                )
                incomplete_pool_pct = (incomplete_pool.sum() / len(pool)) * 100.0 if len(pool) > 0 else 0.0
                print(f"  [プール] 不完全なcore_scoreの割合: {incomplete_pool.sum()}/{len(pool)} ({incomplete_pool_pct:.1f}%)")

    out_cols = [
        "code", "sector33",
        "liquidity_60d", "market_cap",
        "roe", "roe_trend",
        "pbr", "per", "forward_per",
        "op_growth", "profit_growth",
        "record_high_forecast_flag",
        "op_trend",
        "core_score", "entry_score",
    ]
    feat = df[out_cols].copy()
    feat.insert(0, "as_of_date", price_date)

    return feat


# -----------------------------
# Selection
# -----------------------------

def select_portfolio(feat: pd.DataFrame) -> pd.DataFrame:
    if feat.empty:
        return feat

    print(f"[count] features rows before filters: {len(feat)}")

    f = feat.copy()

    # liquidity filter
    q = f["liquidity_60d"].quantile(PARAMS.liquidity_quantile_cut)
    f = f[(f["liquidity_60d"].notna()) & (f["liquidity_60d"] >= q)]
    print(f"[count] after liquidity filter: {len(f)} (cut={PARAMS.liquidity_quantile_cut}, q={q})")

    # ROE threshold
    f = f[(f["roe"].notna()) & (f["roe"] >= PARAMS.roe_min)]
    print(f"[count] after ROE>= {PARAMS.roe_min}: {len(f)}")


    if f.empty:
        print("[warn] 0 rows after filters. Consider relaxing filters or check data availability.")
        return pd.DataFrame()

    # Pool by core score
    pool = f.sort_values("core_score", ascending=False).head(PARAMS.pool_size).copy()
    print(f"[count] pool size: {len(pool)}")

    # Sort by entry_score first (optional)
    if PARAMS.use_entry_score:
        pool = pool.sort_values(["entry_score", "core_score"], ascending=[False, False])

    # Apply sector cap
    selected_rows = []
    sector_counts: Dict[str, int] = {}

    for _, r in pool.iterrows():
        sec = r.get("sector33") or "UNKNOWN"
        if sector_counts.get(sec, 0) >= PARAMS.sector_cap:
            continue
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        selected_rows.append(r)
        if len(selected_rows) >= PARAMS.target_max:
            break

    if len(selected_rows) < PARAMS.target_min:
        print(f"[warn] too few after sector cap ({len(selected_rows)}). Relaxing sector cap.")
        selected_rows = pool.head(PARAMS.target_max).to_dict("records")

    sel = pd.DataFrame(selected_rows)
    if sel.empty:
        return sel

    n = len(sel)
    sel["weight"] = 1.0 / n

    def fmt(x, fstr):
        return "nan" if x is None or pd.isna(x) else format(float(x), fstr)

    sel["reason"] = sel.apply(
        lambda r: (
            f"roe={fmt(r.get('roe'),'0.3f')},"
            f"forward_per={fmt(r.get('forward_per'),'0.2f')},"
            f"pbr={fmt(r.get('pbr'),'0.2f')},"
            f"op_growth={fmt(r.get('op_growth'),'0.2f')},"
            f"op_trend={fmt(r.get('op_trend'),'0.2f')},"
            f"record_high_fc={int(r.get('record_high_forecast_flag') if not pd.isna(r.get('record_high_forecast_flag')) else 0)}"
        ),
        axis=1,
    )

    out = sel[["code", "weight", "core_score", "entry_score", "reason"]].copy()
    out.insert(0, "rebalance_date", feat["as_of_date"].iloc[0])

    return out


# -----------------------------
# Persistence
# -----------------------------

def save_features(conn, feat: pd.DataFrame):
    if feat.empty:
        return
    rows = feat.to_dict("records")
    upsert(conn, "features_monthly", rows, conflict_columns=["as_of_date", "code"])


def save_portfolio(conn, pf: pd.DataFrame):
    if pf.empty:
        return
    rebalance_date = pf["rebalance_date"].iloc[0]
    conn.execute("DELETE FROM portfolio_monthly WHERE rebalance_date = ?", (rebalance_date,))
    conn.commit()

    rows = pf.to_dict("records")
    upsert(conn, "portfolio_monthly", rows, conflict_columns=["rebalance_date", "code"])


# -----------------------------
# Main
# -----------------------------

def main(asof: Optional[str] = None):
    run_date = asof or EXECUTION_DATE or datetime.now().strftime("%Y-%m-%d")
    print(f"[monthly] start | asof={run_date}")

    with connect_db() as conn:
        feat = build_features(conn, run_date)
        print(f"[monthly] features built: {len(feat)} codes")

        save_features(conn, feat)

        pf = select_portfolio(feat)
        print(f"[monthly] selected: {len(pf)} codes")

        save_portfolio(conn, pf)



    print("[monthly] done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monthly run (feature build & selection)")
    parser.add_argument("--asof", type=str, help="As-of date (YYYY-MM-DD)")
    args = parser.parse_args()
    main(asof=args.asof)

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
        SELECT date, code, adj_close, turnover_value
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
    最新のFY実績データを取得
    開示日が最新のものを選ぶ（当期末ではなく開示日を基準にする）
    主要項目（operating_profit, profit, equity）が全て欠損のレコードは除外
    
    同じcurrent_period_endのFYデータ間で相互補完を行う：
    - operating_profitが欠損しているが、forecast_operating_profitがあるレコードから補完
    - forecast_operating_profitが欠損しているが、operating_profitがあるレコードから補完
    - profit, forecast_profit, forecast_epsについても同様
    """
    df = pd.read_sql_query(
        """
        SELECT disclosed_date, disclosed_time, code, type_of_current_period, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
               OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
        """,
        conn,
        params=(asof,),
    )
    if df.empty:
        return pd.DataFrame()
    
    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
    
    # 欠損があるレコードは除外（会計基準変更などで古い開示日のデータがNULLに書き換えられている可能性があるため）
    # ただし、forecast_*がある場合は含める（相互補完のため）
    df = df[
        (df["operating_profit"].notna()) |
        (df["profit"].notna()) |
        (df["equity"].notna()) |
        (df["forecast_operating_profit"].notna()) |
        (df["forecast_profit"].notna()) |
        (df["forecast_eps"].notna())
    ].copy()
    if df.empty:
        return pd.DataFrame()
    
    # 同じcurrent_period_endのFYデータ間で相互補完
    # 各code、current_period_endごとに、全てのレコードを集約して補完
    result_rows = []
    for (code, period_end), group in df.groupby(["code", "current_period_end"]):
        # 開示日が最新のレコードをベースにする
        group_sorted = group.sort_values("disclosed_date", ascending=False)
        base_row = group_sorted.iloc[0].copy()
        
        # 同じcurrent_period_endの全レコードから、欠損している項目を補完
        # operating_profitが欠損している場合、forecast_operating_profitから補完（最新の開示日のものを優先）
        if pd.isna(base_row["operating_profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["forecast_operating_profit"]):
                    base_row["operating_profit"] = row["forecast_operating_profit"]
                    break
        
        # forecast_operating_profitが欠損している場合、operating_profitから補完（最新の開示日のものを優先）
        if pd.isna(base_row["forecast_operating_profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["operating_profit"]):
                    base_row["forecast_operating_profit"] = row["operating_profit"]
                    break
        
        # profitとforecast_profitの相互補完
        if pd.isna(base_row["profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["forecast_profit"]):
                    base_row["profit"] = row["forecast_profit"]
                    break
        
        if pd.isna(base_row["forecast_profit"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["profit"]):
                    base_row["forecast_profit"] = row["profit"]
                    break
        
        # forecast_epsが欠損している場合、epsから補完（最新の開示日のものを優先）
        if pd.isna(base_row["forecast_eps"]):
            for _, row in group_sorted.iterrows():
                if pd.notna(row["eps"]):
                    base_row["forecast_eps"] = row["eps"]
                    break
        
        result_rows.append(base_row)
    
    if not result_rows:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(result_rows)
    
    # 開示日が最新のものを選ぶ（当期末ではなく開示日を基準にする）
    result_df = result_df.sort_values(["code", "disclosed_date"])
    latest = result_df.groupby("code", as_index=False).tail(1).copy()
    
    return latest


def _load_fy_history(conn, asof: str, years: int = 10) -> pd.DataFrame:
    """
    過去のFY実績データを取得（最大years年分）
    各current_period_endごとに開示日が最新のものを選ぶ
    主要項目（operating_profit, profit, equity）が全て欠損のレコードは除外
    
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
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL)
        """,
        conn,
        params=(asof,),
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
    
    # 注意: 履歴データの補完処理は実行しない
    # （会計基準変更などで古い開示日のデータがNULLに書き換えられている可能性があるため、
    #   forecastデータで補完するよりも、欠損のない直近のFYレコードを使用する方が適切）
    
    return df


def _load_latest_forecast(conn, asof: str) -> pd.DataFrame:
    """
    最新の予想データを取得
    FYを優先し、同じ開示日の場合FYを優先
    注意: _load_latest_fyで既に同じcurrent_period_endのFYデータ間で相互補完を行っているため、
          この関数は主に四半期データから予想を取得する場合に使用される
    """
    df = pd.read_sql_query(
        """
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM fins_statements
        WHERE disclosed_date <= ?
        """,
        conn,
        params=(asof,),
    )
    if df.empty:
        return df
    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    # FYを優先するため、period_priorityを設定（FY=0、その他=1）
    df["period_priority"] = df["type_of_current_period"].apply(
        lambda x: 0 if x == "FY" else 1
    )
    # 開示日が最新のものを選び、同じ開示日の場合FYを優先
    df = df.sort_values(["code", "disclosed_date", "period_priority"])
    latest = df.groupby("code", as_index=False).tail(1).copy()
    # period_priorityカラムを削除（不要なため）
    latest = latest.drop(columns=["period_priority"])
    return latest


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

    px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "adj_close"]].copy()
    px_today = px_today.rename(columns={"adj_close": "price"})
    print(f"[count] prices today codes: {len(px_today)}")

    # Liquidity (60d avg turnover_value) - fixed (no Series groupby(as_index=False))
    tmp = prices_win[["code", "date", "turnover_value"]].copy()
    tmp = tmp.sort_values(["code", "date"])
    tmp = tmp.groupby("code", group_keys=False).tail(60)
    liq = tmp.groupby("code", as_index=False)["turnover_value"].mean()
    liq = liq.rename(columns={"turnover_value": "liquidity_60d"})

    fy_latest = _load_latest_fy(conn, price_date)
    print(f"[count] latest FY rows: {len(fy_latest)}")

    fc_latest = _load_latest_forecast(conn, price_date)
    print(f"[count] latest forecast rows: {len(fc_latest)}")

    fy_hist = _load_fy_history(conn, price_date, years=10)
    print(f"[count] FY history rows (<=10 per code): {len(fy_hist)}")

    df = universe.merge(px_today, on="code", how="inner")
    df = df.merge(liq, on="code", how="left")
    df = df.merge(fy_latest, on="code", how="left", suffixes=("", "_fy"))
    df = df.merge(fc_latest, on="code", how="left", suffixes=("", "_fc"))

    print(f"[count] merged base rows: {len(df)}")
    
    # マージ後の埋まり率を表示（デバッグ用）
    print("\n[coverage] マージ後のデータ埋まり率:")
    key_columns = [
        "forecast_eps_fc",
        "forecast_operating_profit_fc",
        "forecast_profit_fc",
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

    # PBR from latest FY
    df["pbr"] = df.apply(lambda r: _safe_div(r.get("price"), r.get("bvps")), axis=1)

    # Forward PER from forecast_eps
    df["forward_per"] = df.apply(lambda r: _safe_div(r.get("price"), r.get("forecast_eps_fc")), axis=1)

    # Growth from forecasts vs latest FY
    df["op_growth"] = df.apply(lambda r: _safe_div(r.get("forecast_operating_profit_fc"), r.get("operating_profit")) - 1.0, axis=1)
    df["profit_growth"] = df.apply(lambda r: _safe_div(r.get("forecast_profit_fc"), r.get("profit")) - 1.0, axis=1)

    # Record high (forecast OP vs past max FY OP)
    if not fy_hist.empty:
        op_max = fy_hist.groupby("code", as_index=False)["operating_profit"].max().rename(columns={"operating_profit": "op_max_past"})
        df = df.merge(op_max, on="code", how="left")
    else:
        df["op_max_past"] = np.nan

    df["record_high_forecast_flag"] = (
        (df["forecast_operating_profit_fc"].notna()) &
        (df["op_max_past"].notna()) &
        (df["forecast_operating_profit_fc"] >= df["op_max_past"])
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

    # Market cap
    def _market_cap(row):
        price = row.get("price")
        if price is None or pd.isna(price):
            return np.nan
        so = row.get("shares_outstanding")
        ts = row.get("treasury_shares")
        if so is not None and not pd.isna(so):
            shares = so - (ts if ts is not None and not pd.isna(ts) else 0.0)
            if shares and shares > 0:
                return price * shares
        eq = row.get("equity")
        bvps = row.get("bvps")
        shares2 = _safe_div(eq, bvps)
        if shares2 is None or pd.isna(shares2) or shares2 <= 0:
            return np.nan
        return price * shares2

    df["market_cap"] = df.apply(_market_cap, axis=1)
    
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
    has_forecast_op = df["forecast_operating_profit_fc"].notna()
    has_actual_op = df["operating_profit"].notna()
    forecast_only = df[has_forecast_op & ~has_actual_op]
    if len(forecast_only) > 0:
        print(f"\n[debug] 予想営業利益があるのに実績営業利益がない銘柄: {len(forecast_only)}件")
        print(f"  sample codes: {forecast_only['code'].head(10).tolist()}")
    
    has_forecast_profit = df["forecast_profit_fc"].notna()
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
        "roe",
        "pbr", "forward_per",
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

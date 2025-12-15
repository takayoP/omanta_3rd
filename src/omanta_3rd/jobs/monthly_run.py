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
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd

from ..config.settings import EXECUTION_DATE
from ..infra.db import connect_db, upsert


# -----------------------------
# Configuration (tune later)
# -----------------------------

@dataclass(frozen=True)
class StrategyParams:
    target_min: int = 20
    target_max: int = 30
    pool_size: int = 80

    # Hard filters
    roe_min: float = 0.10
    require_roe_trend_positive: bool = True
    liquidity_quantile_cut: float = 0.20  # drop bottom 20% by liquidity_60d

    # Sector cap (33-sector)
    sector_cap: int = 4

    # Scoring weights (sum ~ 1.0)
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

def _to_dt(s: Optional[str]) -> Optional[pd.Timestamp]:
    if not s:
        return None
    return pd.to_datetime(s, errors="coerce")


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
    # rank(pct=True) returns [0..1], but NaN -> NaN
    return series.rank(pct=True, ascending=ascending)


def _log_safe(x: float) -> float:
    if x is None or pd.isna(x) or x <= 0:
        return np.nan
    return math.log(x)


def _calc_slope(values: List[float]) -> float:
    """
    Slope of values over time index 0..n-1 using simple linear regression.
    Returns NaN if not enough points.
    """
    v = [x for x in values if x is not None and not pd.isna(x)]
    n = len(v)
    if n < 3:
        return np.nan
    x = np.arange(n, dtype=float)
    y = np.array(v, dtype=float)
    # slope of y ~ a*x + b
    a, _b = np.polyfit(x, y, 1)
    return float(a)


def _rsi_from_series(close: pd.Series, n: int) -> float:
    """
    Simple RSI (Wilder-style approximated via rolling mean of gains/losses).
    """
    if close is None or close.size < n + 1:
        return np.nan
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.rolling(n).mean().iloc[-1]
    avg_loss = loss.rolling(n).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss) or avg_loss == 0:
        return np.nan if avg_loss != 0 else 100.0
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
    """
    Entry score from BB(-2sigma) and RSI(<=30) with N in {20,60,90}.
    Returns [0..1] (higher is "better entry").
    """
    scores = []
    for n in (20, 60, 90):
        z = _bb_zscore(close, n)
        rsi = _rsi_from_series(close, n)
        bb_score = np.nan
        rsi_score = np.nan

        # BB: below -2σ => higher score
        if not pd.isna(z):
            bb_score = _clip01((-2.0 - z) / 2.0)  # z=-2 => 0, z=-4 => 1

        # RSI: <=30 => higher score
        if not pd.isna(rsi):
            rsi_score = _clip01((30.0 - rsi) / 30.0)  # rsi=30 => 0, rsi=0 => 1

        if not pd.isna(bb_score) and not pd.isna(rsi_score):
            scores.append(0.5 * bb_score + 0.5 * rsi_score)
        elif not pd.isna(bb_score):
            scores.append(bb_score)
        elif not pd.isna(rsi_score):
            scores.append(rsi_score)

    if not scores:
        return np.nan
    # Use max to prioritize "best entry" signal among windows
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
        # fallback to latest
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
    # Prime only
    df = df[df["market_name"] == "プライム"].copy()
    return df


def _load_prices_window(conn, price_date: str, lookback_days: int = 200) -> pd.DataFrame:
    """
    Load a rolling window of prices up to price_date for all codes.
    Note: For large history, optimize with DuckDB/Parquet later.
    """
    # We don't have a trading calendar table; use date range by simple heuristic:
    # fetch rows where date <= price_date and keep last N rows per code in pandas.
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
    # Keep last lookback_days per code
    df = df.groupby("code", group_keys=False).tail(lookback_days)
    return df


def _load_latest_fy(conn, asof: str) -> pd.DataFrame:
    """
    Latest FY (actual) per code with disclosed_date <= asof.
    """
    df = pd.read_sql_query(
        """
        SELECT *
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND type_of_current_period = 'FY'
        """,
        conn,
        params=(asof,),
    )
    if df.empty:
        return df

    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
    df = df.sort_values(["code", "disclosed_date", "current_period_end"])
    latest = df.groupby("code", as_index=False).tail(1).copy()
    return latest


def _load_fy_history(conn, asof: str, years: int = 10) -> pd.DataFrame:
    """
    FY history per code with disclosed_date <= asof.
    Limit by most recent N fiscal periods per code (approx years).
    """
    df = pd.read_sql_query(
        """
        SELECT code, disclosed_date, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND type_of_current_period = 'FY'
        """,
        conn,
        params=(asof,),
    )
    if df.empty:
        return df
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
    df = df.sort_values(["code", "current_period_end"])
    df = df.groupby("code", group_keys=False).tail(years)
    return df


def _load_latest_forecast(conn, asof: str) -> pd.DataFrame:
    """
    Latest statement (any period) per code with disclosed_date <= asof.
    Used for forecast_* fields (forward PER, forecast OP, etc).
    """
    df = pd.read_sql_query(
        """
        SELECT code, disclosed_date,
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
    df = df.sort_values(["code", "disclosed_date"])
    latest = df.groupby("code", as_index=False).tail(1).copy()
    return latest


# -----------------------------
# Feature building
# -----------------------------

def build_features(conn, asof: str) -> pd.DataFrame:
    """
    Build features for asof (snapped to available price date).
    Returns a DataFrame with one row per code.
    """
    # snap dates
    price_date = _snap_price_date(conn, asof)
    listed_date = _snap_listed_date(conn, price_date)

    print(f"[monthly] asof requested={asof} | price_date={price_date} | listed_date={listed_date}")

    universe = _load_universe(conn, listed_date)
    print(f"[count] universe (Prime): {len(universe)}")

    prices_win = _load_prices_window(conn, price_date, lookback_days=200)
    print(f"[count] prices rows (window): {len(prices_win)}")

    # Today's price (adj_close) at price_date
    px_today = prices_win[prices_win["date"] == pd.to_datetime(price_date)][["code", "adj_close"]].copy()
    px_today = px_today.rename(columns={"adj_close": "price"})
    print(f"[count] prices today codes: {len(px_today)}")

    # Liquidity (60d avg turnover_value)
    tmp = prices_win[["code", "date", "turnover_value"]].copy()
    tmp = tmp.sort_values(["code", "date"])
    tmp = tmp.groupby("code", group_keys=False).tail(60)
    liq = tmp.groupby("code", as_index=False)["turnover_value"].mean()
    liq = liq.rename(columns={"turnover_value": "liquidity_60d"})


    # merge core frame
    df = universe.merge(px_today, on="code", how="inner")
    df = df.merge(liq, on="code", how="left")
    fy_latest = _load_latest_fy(conn, price_date)
    print(f"[count] latest FY rows: {len(fy_latest)}")
    df = df.merge(fy_latest, on="code", how="left", suffixes=("", "_fy"))
    fc_latest = _load_latest_forecast(conn, price_date)
    print(f"[count] latest forecast rows: {len(fc_latest)}")
    df = df.merge(fc_latest, on="code", how="left", suffixes=("", "_fc"))

    print(f"[count] merged base rows: {len(df)}")

    # --- Actual ROE (latest FY) ---
    df["roe"] = df.apply(lambda r: _safe_div(r.get("profit"), r.get("equity")), axis=1)
    # --- Valuation (PBR from latest FY) ---
    df["pbr"] = df.apply(lambda r: _safe_div(r.get("price"), r.get("bvps")), axis=1)
    # --- Forward PER (forecast eps from latest statement) ---
    df["forward_per"] = df.apply(lambda r: _safe_div(r.get("price"), r.get("forecast_eps")), axis=1)

    # --- Growth (forecast / last FY) ---
    df["op_growth"] = df.apply(lambda r: _safe_div(r.get("forecast_operating_profit"), r.get("operating_profit")) - 1.0, axis=1)
    df["profit_growth"] = df.apply(lambda r: _safe_div(r.get("forecast_profit"), r.get("profit")) - 1.0, axis=1)

    # --- Record high (forecast OP vs past max FY OP) ---
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

    # --- ROE trend (5y slope) ---
    if not fy_hist.empty:
        # compute roe per FY row
        fh = fy_hist.copy()
        fh["roe"] = fh.apply(lambda r: _safe_div(r.get("profit"), r.get("equity")), axis=1)
        fh = fh.sort_values(["code", "current_period_end"])
        slopes = []
        for code, g in fh.groupby("code"):
            vals = g["roe"].tail(5).tolist()
            slopes.append((code, _calc_slope(vals)))
        slope_df = pd.DataFrame(slopes, columns=["code", "roe_trend"])
        df = df.merge(slope_df, on="code", how="left")
    else:
        df["roe_trend"] = np.nan

    # --- Market cap (prefer shares_outstanding - treasury_shares, fallback equity/bvps) ---
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
        # fallback: shares ~= equity / bvps
        eq = row.get("equity")
        bvps = row.get("bvps")
        shares2 = _safe_div(eq, bvps)
        if shares2 is None or pd.isna(shares2) or shares2 <= 0:
            return np.nan
        return price * shares2

    df["market_cap"] = df.apply(_market_cap, axis=1)

    # --- Entry score (BB/RSI) ---
    if PARAMS.use_entry_score:
        # build close series per code
        close_map = {c: g["adj_close"].reset_index(drop=True) for c, g in prices_win.groupby("code")}
        df["entry_score"] = df["code"].apply(lambda c: _entry_score(close_map.get(c)) if c in close_map else np.nan)
    else:
        df["entry_score"] = np.nan

    # --- Industry-relative valuation scores ---
    # Lower forward_per and lower pbr are better (rank ascending then invert)
    df["forward_per_pct"] = df.groupby("sector33")["forward_per"].transform(lambda s: _pct_rank(s, ascending=True))
    df["pbr_pct"] = df.groupby("sector33")["pbr"].transform(lambda s: _pct_rank(s, ascending=True))

    df["value_score"] = (
        PARAMS.w_forward_per * (1.0 - df["forward_per_pct"]) +
        PARAMS.w_pbr * (1.0 - df["pbr_pct"])
    )

    # Size score (bigger is better)
    df["log_mcap"] = df["market_cap"].apply(_log_safe)
    df["size_score"] = _pct_rank(df["log_mcap"], ascending=True)  # bigger log -> higher pct

    # Quality score
    df["roe_score"] = _pct_rank(df["roe"], ascending=True)
    df["roe_trend_score"] = _pct_rank(df["roe_trend"], ascending=True)

    df["quality_score"] = 0.75 * df["roe_score"] + 0.25 * df["roe_trend_score"]

    # Growth score (forecast growth; NaN -> median-ish behavior by pct rank)
    df["op_growth_score"] = _pct_rank(df["op_growth"], ascending=True)
    df["profit_growth_score"] = _pct_rank(df["profit_growth"], ascending=True)
    df["growth_score"] = 0.5 * df["op_growth_score"] + 0.5 * df["profit_growth_score"]

    # Record-high score: 1/0 -> rank
    df["record_high_score"] = df["record_high_forecast_flag"].astype(float)

    # Core score
    df["core_score"] = (
        PARAMS.w_quality * df["quality_score"] +
        PARAMS.w_value * df["value_score"] +
        PARAMS.w_growth * df["growth_score"] +
        PARAMS.w_record_high * df["record_high_score"] +
        PARAMS.w_size * df["size_score"]
    )

    # Keep only required columns for saving
    out_cols = [
        "code", "sector33",
        "liquidity_60d", "market_cap",
        "roe", "roe_trend",
        "pbr", "forward_per",
        "op_growth", "profit_growth",
        "record_high_forecast_flag",
        "core_score", "entry_score",
    ]
    feat = df[out_cols].copy()
    feat.insert(0, "as_of_date", price_date)

    return feat


# -----------------------------
# Selection
# -----------------------------

def select_portfolio(feat: pd.DataFrame) -> pd.DataFrame:
    """
    Select 20-30 stocks from features snapshot.
    Returns DataFrame: rebalance_date, code, weight, core_score, entry_score, reason
    """
    if feat.empty:
        return feat

    # Counts before filters
    print(f"[count] features rows before filters: {len(feat)}")

    # Hard filters
    f = feat.copy()

    # liquidity filter (drop bottom quantile)
    q = f["liquidity_60d"].quantile(PARAMS.liquidity_quantile_cut)
    f = f[(f["liquidity_60d"].notna()) & (f["liquidity_60d"] >= q)]
    print(f"[count] after liquidity filter: {len(f)} (cut={PARAMS.liquidity_quantile_cut}, q={q})")

    # ROE threshold
    f = f[(f["roe"].notna()) & (f["roe"] >= PARAMS.roe_min)]
    print(f"[count] after ROE>= {PARAMS.roe_min}: {len(f)}")

    # ROE trend positive
    if PARAMS.require_roe_trend_positive:
        f = f[(f["roe_trend"].notna()) & (f["roe_trend"] > 0)]
        print(f"[count] after ROE trend > 0: {len(f)}")

    # record high forecast flag (soft -> NOT hard filter by default)
    # If you want it hard, uncomment:
    # f = f[f["record_high_forecast_flag"] == 1]
    # print(f"[count] after record high forecast filter: {len(f)}")

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

    # If too few due to sector cap, relax cap
    if len(selected_rows) < PARAMS.target_min:
        print(f"[warn] too few after sector cap ({len(selected_rows)}). Relaxing sector cap.")
        selected_rows = pool.head(PARAMS.target_max).to_dict("records")

    sel = pd.DataFrame(selected_rows)
    if sel.empty:
        return sel

    # Determine weights (equal weight)
    n = len(sel)
    sel["weight"] = 1.0 / n

    # Add reason (JSON-ish string; keep simple)
    def _reason(row) -> str:
        return (
            f"roe={row.get('roe'):.3f if not pd.isna(row.get('roe')) else 'nan'}, "
            f"roe_trend={row.get('roe_trend'):.4f if not pd.isna(row.get('roe_trend')) else 'nan'}, "
            f"forward_per={row.get('forward_per'):.2f if not pd.isna(row.get('forward_per')) else 'nan'}, "
            f"pbr={row.get('pbr'):.2f if not pd.isna(row.get('pbr')) else 'nan'}, "
            f"op_growth={row.get('op_growth'):.2f if not pd.isna(row.get('op_growth')) else 'nan'}, "
            f"record_high_fc={int(row.get('record_high_forecast_flag') if not pd.isna(row.get('record_high_forecast_flag')) else 0)}"
        )

    # pandas formatting in f-string is tricky; use safe conversions
    def _reason2(row) -> str:
        def fmt(x, f):
            return "nan" if x is None or pd.isna(x) else format(float(x), f)
        return (
            f"roe={fmt(row.get('roe'),'0.3f')},"
            f"roe_trend={fmt(row.get('roe_trend'),'0.4f')},"
            f"forward_per={fmt(row.get('forward_per'),'0.2f')},"
            f"pbr={fmt(row.get('pbr'),'0.2f')},"
            f"op_growth={fmt(row.get('op_growth'),'0.2f')},"
            f"record_high_fc={int(row.get('record_high_forecast_flag') if not pd.isna(row.get('record_high_forecast_flag')) else 0)}"
        )

    sel["reason"] = sel.apply(_reason2, axis=1)

    # Build portfolio table schema
    out = sel[["code", "weight", "core_score", "entry_score", "reason"]].copy()
    out.insert(0, "rebalance_date", feat["as_of_date"].iloc[0])

    return out


# -----------------------------
# Persistence
# -----------------------------

def save_features(conn, feat: pd.DataFrame):
    if feat.empty:
        return
    # Map to list[dict] for upsert
    rows = feat.to_dict("records")
    upsert(
        conn,
        "features_monthly",
        rows,
        conflict_columns=["as_of_date", "code"],
    )


def save_portfolio(conn, pf: pd.DataFrame):
    if pf.empty:
        return
    rows = pf.to_dict("records")
    upsert(
        conn,
        "portfolio_monthly",
        rows,
        conflict_columns=["rebalance_date", "code"],
    )


# -----------------------------
# Main
# -----------------------------

def main(asof: Optional[str] = None):
    # asof is the user-specified date; use it first
    run_date = asof or EXECUTION_DATE or datetime.now().strftime("%Y-%m-%d")

    print(f"[monthly] start | asof={run_date}")

    with connect_db() as conn:
        feat = build_features(conn, run_date)
        print(f"[monthly] features built: {len(feat)} codes")

        # Save features snapshot
        save_features(conn, feat)

        # Selection
        pf = select_portfolio(feat)
        print(f"[monthly] selected: {len(pf)} codes")

        # Save portfolio
        save_portfolio(conn, pf)

    print("[monthly] done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monthly run (feature build & selection)")
    parser.add_argument("--asof", type=str, help="As-of date (YYYY-MM-DD)")
    args = parser.parse_args()
    main(asof=args.asof)

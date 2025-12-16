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
            bb_score = _clip01((-2.0 - z) / 2.0)  # z=-2 => 0, z=-4 => 1
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


def _load_latest_fy(conn, asof: str) -> pd.DataFrame:
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
        (df["forecast_operating_profit"].notna()) &
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

"""
longterm_run.py（長期保有型用）

長期保有型の月次実行スクリプト:
- Build features snapshot (features_monthly) for a given as-of date
- Select 20-30 stocks and save to portfolio_monthly（長期保有型用テーブル）

【注意】このスクリプトは長期保有型専用です。
月次リバランス型の運用には使用しません。

Usage:
  python -m omanta_3rd.jobs.longterm_run --asof 2025-12-12
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

import numpy as np
import pandas as pd

from ..config.settings import EXECUTION_DATE
from ..infra.db import connect_db, upsert
from ..features.utils import _safe_div, _clip01, _pct_rank, _log_safe, _calc_slope
from ..features.technicals import bb_zscore as _bb_zscore, rsi_from_series as _rsi_from_series
from ..backtest.performance import _split_multiplier_between
from ..features.loader import (
    _snap_price_date, _snap_listed_date, _load_universe, _load_prices_window,
    _save_fy_to_statements, _load_latest_fy, _load_fy_history, _load_latest_forecast,
)

# -----------------------------
# Configuration
# -----------------------------

@dataclass(frozen=True)
class StrategyParams:
    target_min: int = 12  # 最適化結果: 12銘柄ポートフォリオ
    target_max: int = 12  # 最適化結果: 12銘柄ポートフォリオ
    pool_size: int = 80

    # Hard filters（最適化結果を適用: 2025-12-29 21:23）
    roe_min: float = 0.0621  # 最適化結果: 0.0621（6.21%）
    liquidity_quantile_cut: float = 0.1509  # 最適化結果: 0.1509（15.09%）

    # Sector cap (33-sector)
    sector_cap: int = 4

    # Scoring weights（最適化結果を適用: 2025-12-29 21:23）
    w_quality: float = 0.1519  # 最適化結果: 0.1519（15.19%）
    w_value: float = 0.3908   # 最適化結果: 0.3908（39.08%）← 最も重要
    w_growth: float = 0.1120  # 最適化結果: 0.1120（11.20%）
    w_record_high: float = 0.0364  # 最適化結果: 0.0364（3.64%）
    w_size: float = 0.2448    # 最適化結果: 0.2448（24.48%）

    # Value mix（最適化結果を適用: 2025-12-29 21:23）
    w_forward_per: float = 0.4977  # 最適化結果: 0.4977（49.77%）
    w_pbr: float = 0.5023  # 最適化結果: 0.5023（50.23% = 1.0 - 0.4977）

    # Entry score (BB/RSI)
    use_entry_score: bool = True
    
    # Entry score parameters（最適化結果を適用: 2025-12-29 21:23）
    rsi_base: float = 51.18  # 最適化結果: 51.1777
    rsi_max: float = 73.58   # 最適化結果: 73.5846
    bb_z_base: float = -0.57  # 最適化結果: -0.5709
    bb_z_max: float = 2.16    # 最適化結果: 2.1630
    bb_weight: float = 0.5527   # 最適化結果: 0.5527（55.27%）
    rsi_weight: float = 0.4473  # 最適化結果: 0.4473（44.73% = 1.0 - 0.5527）


PARAMS = StrategyParams()


def _entry_score(close: pd.Series) -> float:
    """
    Entry score計算（最適化結果のパラメータを使用）
    
    最適化結果（2025-12-29 21:23）:
    - rsi_base: 51.18, rsi_max: 73.58
    - bb_z_base: -0.57, bb_z_max: 2.16
    - bb_weight: 0.5527, rsi_weight: 0.4473
    """
    # 以前の実装: 3つの期間（20日、60日、200日）でBBとRSIの値を計算し、最大値を採用
    bb_z_values = []
    rsi_values = []
    
    for n in (20, 60, 200):
        z = _bb_zscore(close, n)
        rsi = _rsi_from_series(close, n)
        
        if not pd.isna(z):
            bb_z_values.append(z)
        if not pd.isna(rsi):
            rsi_values.append(rsi)
    
    # BBとRSIの値の最大値を採用（以前の実装）
    if not bb_z_values and not rsi_values:
        return np.nan
    
    # BB値の最大値を採用（順張りの場合は最大値、逆張りの場合は最小値）
    # ただし、スコア計算時に順張り/逆張りを考慮するため、ここでは単純に最大値を取る
    bb_z = np.nanmax(bb_z_values) if bb_z_values else np.nan
    rsi = np.nanmax(rsi_values) if rsi_values else np.nan
    
    # スコア計算
    bb_score = np.nan
    rsi_score = np.nan

    if not pd.isna(bb_z):
        # 最適化結果のパラメータを使用
        # z=bb_z_baseのとき0、z=bb_z_maxのとき1になる線形変換
        bb_z_base = PARAMS.bb_z_base
        bb_z_max = PARAMS.bb_z_max
        if bb_z_max != bb_z_base:
            bb_score = (bb_z - bb_z_base) / (bb_z_max - bb_z_base)
        else:
            bb_score = 0.0
        # クリップ処理（0〜1に制限）
        bb_score = np.clip(bb_score, 0.0, 1.0)
                
    if not pd.isna(rsi):
        # 最適化結果のパラメータを使用
        # RSI=rsi_baseのとき0、RSI=rsi_maxのとき1になる線形変換
        rsi_base = PARAMS.rsi_base
        rsi_max = PARAMS.rsi_max
        if rsi_max != rsi_base:
            rsi_score = (rsi - rsi_base) / (rsi_max - rsi_base)
        else:
            rsi_score = 0.0
        # クリップ処理（0〜1に制限）
        rsi_score = np.clip(rsi_score, 0.0, 1.0)

    # 最適化結果の重みを使用
    bb_weight = PARAMS.bb_weight
    rsi_weight = PARAMS.rsi_weight
    total_weight = bb_weight + rsi_weight
    
    if total_weight > 0:
        if not pd.isna(bb_score) and not pd.isna(rsi_score):
            return float((bb_weight * bb_score + rsi_weight * rsi_score) / total_weight)
        elif not pd.isna(bb_score):
            return float(bb_score)
        elif not pd.isna(rsi_score):
            return float(rsi_score)
    
    return np.nan


# _entry_score_with_params, _calculate_entry_score_with_params は features/technicals.py に移動
# （ファイル先頭のre-exportからインポート済み）


# _deprecated_calculate_cumulative_adjustment_factor, _split_multiplier_between,
# _get_shares_at_date, _get_latest_basis_shares, _get_shares_adjustment_factor は
# features/adjustments.py に移動（ファイル先頭のre-exportからインポート済み）
#
# _snap_price_date, _snap_listed_date, _load_universe, _load_prices_window,
# _save_fy_to_statements, _load_latest_fy, _load_fy_history, _load_latest_forecast は
# features/loader.py に移動（ファイル先頭のre-exportからインポート済み）

# Feature building
# -----------------------------

def build_features(
    conn,
    asof: str,
    strategy_params: Optional[StrategyParams] = None,
    entry_params: Optional[Any] = None,  # EntryScoreParams（循環参照回避のためAny）
) -> pd.DataFrame:
    price_date = _snap_price_date(conn, asof)
    listed_date = _snap_listed_date(conn, price_date)

    print(f"[longterm] asof requested={asof} | price_date={price_date} | listed_date={listed_date}")

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

    fy_hist = _load_fy_history(conn, price_date, years=3)
    print(f"[count] FY history rows (<=3 per code): {len(fy_hist)}")

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
    # 過去の取得できる（None以外の）利益を全て参照して、リバランス日（ポートフォリオ作成日）における最新の利益が最高益になっているかどうかをチェック
    # リバランス日以前に開示されたデータのみを参照（データリーク防止）
    # fy_histはyears=3に制限されているため、最高益フラグの計算では全期間のデータを直接取得する
    op_max_df = pd.read_sql_query(
        """
        SELECT code, MAX(operating_profit) as op_max_past
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND current_period_end <= ?
          AND type_of_current_period = 'FY'
          AND operating_profit IS NOT NULL
        GROUP BY code
        """,
        conn,
        params=(price_date, price_date),  # price_dateはリバランス日（ポートフォリオ作成日）
    )
    if not op_max_df.empty:
        df = df.merge(op_max_df, on="code", how="left")
    else:
        df["op_max_past"] = np.nan

    df["record_high_forecast_flag"] = (
        (df["forecast_operating_profit"].notna()) &
        (df["op_max_past"].notna()) &
        (df["forecast_operating_profit"] >= df["op_max_past"])
    ).astype(int)

    # Operating profit trend (3y slope)  ← 5年→3年に変更
    if not fy_hist.empty:
        fh = fy_hist.copy()
        fh["current_period_end"] = pd.to_datetime(fh["current_period_end"], errors="coerce")
        fh = fh.sort_values(["code", "current_period_end"])

        slopes = []
        for code, g in fh.groupby("code"):
            vals = g["operating_profit"].tail(3).tolist()
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
    # パラメータが渡された場合はそれを使用、そうでない場合は既存のPARAMSを使用
    use_entry_score = (strategy_params.use_entry_score if strategy_params else PARAMS.use_entry_score)
    
    if use_entry_score:
        if entry_params:
            # パラメータ化版のentry_score計算を使用
            df = _calculate_entry_score_with_params(df, prices_win, entry_params)
        else:
            # 既存の_entry_score関数を使用（PARAMSを使用）
            close_map = {c: g["adj_close"].reset_index(drop=True) for c, g in prices_win.groupby("code")}
            df["entry_score"] = df["code"].apply(lambda c: _entry_score(close_map.get(c)) if c in close_map else np.nan)
    else:
        df["entry_score"] = np.nan

    # Industry-relative valuation scores
    df["forward_per_pct"] = df.groupby("sector33")["forward_per"].transform(lambda s: _pct_rank(s, ascending=True))
    df["pbr_pct"] = df.groupby("sector33")["pbr"].transform(lambda s: _pct_rank(s, ascending=True))
    # パラメータが渡された場合はそれを使用、そうでない場合は既存のPARAMSを使用
    w_forward_per = (strategy_params.w_forward_per if strategy_params else PARAMS.w_forward_per)
    w_pbr = (strategy_params.w_pbr if strategy_params else PARAMS.w_pbr)
    df["value_score"] = w_forward_per * (1.0 - df["forward_per_pct"]) + w_pbr * (1.0 - df["pbr_pct"])

    # Size score
    # 大きいほど高スコア（時価総額が大きい銘柄を好む）
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
    # パラメータが渡された場合はそれを使用、そうでない場合は既存のPARAMSを使用
    w_quality = (strategy_params.w_quality if strategy_params else PARAMS.w_quality)
    w_value = (strategy_params.w_value if strategy_params else PARAMS.w_value)
    w_growth = (strategy_params.w_growth if strategy_params else PARAMS.w_growth)
    w_record_high = (strategy_params.w_record_high if strategy_params else PARAMS.w_record_high)
    w_size = (strategy_params.w_size if strategy_params else PARAMS.w_size)
    
    df["core_score"] = (
        w_quality * df["quality_score"] +
        w_value * df["value_score"] +
        w_growth * df["growth_score"] +
        w_record_high * df["record_high_score"] +
        w_size * df["size_score"]
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
    # パラメータが渡された場合はそれを使用、そうでない場合は既存のPARAMSを使用
    params_for_weights = strategy_params if strategy_params else PARAMS
    weights = {
        "quality_score": params_for_weights.w_quality,
        "value_score": params_for_weights.w_value,
        "growth_score": params_for_weights.w_growth,
        "record_high_score": params_for_weights.w_record_high,
        "size_score": params_for_weights.w_size,
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
        # パラメータが渡された場合はそれを使用、そうでない場合は既存のPARAMSを使用
        params_for_filter = strategy_params if strategy_params else PARAMS
        # 流動性フィルタとROEフィルタを適用
        after_liquidity = df[df["liquidity_60d"] >= df["liquidity_60d"].quantile(params_for_filter.liquidity_quantile_cut)]
        after_roe = after_liquidity[after_liquidity["roe"] >= params_for_filter.roe_min] if len(after_liquidity) > 0 else pd.DataFrame()
        
        if len(after_roe) > 0:
            incomplete_after_filters = (
                after_roe["forward_per"].isna() | after_roe["pbr"].isna() |
                after_roe["op_growth"].isna() | after_roe["profit_growth"].isna() |
                after_roe["market_cap"].isna() | after_roe["record_high_forecast_flag"].isna()
            )
            incomplete_after_pct = (incomplete_after_filters.sum() / len(after_roe)) * 100.0 if len(after_roe) > 0 else 0.0
            print(f"\n  [フィルタ後] 不完全なcore_scoreの割合: {incomplete_after_filters.sum()}/{len(after_roe)} ({incomplete_after_pct:.1f}%)")
            
            # プールサイズの銘柄についても確認
            pool = after_roe.sort_values("core_score", ascending=False).head(params_for_filter.pool_size) if len(after_roe) > 0 else pd.DataFrame()
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

def select_portfolio(
    feat: pd.DataFrame,
    strategy_params: Optional[StrategyParams] = None,
) -> pd.DataFrame:
    if feat.empty:
        return feat

    print(f"[count] features rows before filters: {len(feat)}")

    f = feat.copy()

    # パラメータが渡された場合はそれを使用、そうでない場合は既存のPARAMSを使用
    params = strategy_params if strategy_params else PARAMS
    
    # liquidity filter
    q = f["liquidity_60d"].quantile(params.liquidity_quantile_cut)
    f = f[(f["liquidity_60d"].notna()) & (f["liquidity_60d"] >= q)]
    print(f"[count] after liquidity filter: {len(f)} (cut={params.liquidity_quantile_cut}, q={q})")

    # ROE threshold
    f = f[(f["roe"].notna()) & (f["roe"] >= params.roe_min)]
    print(f"[count] after ROE>= {params.roe_min}: {len(f)}")


    if f.empty:
        print("[warn] 0 rows after filters. Consider relaxing filters or check data availability.")
        return pd.DataFrame()

    # Pool by core score
    pool = f.sort_values("core_score", ascending=False).head(params.pool_size).copy()
    print(f"[count] pool size: {len(pool)}")

    # Sort by entry_score first (optional)
    if params.use_entry_score:
        pool = pool.sort_values(["entry_score", "core_score"], ascending=[False, False])

    # Apply sector cap
    selected_rows = []
    sector_counts: Dict[str, int] = {}

    for _, r in pool.iterrows():
        sec = r.get("sector33") or "UNKNOWN"
        if sector_counts.get(sec, 0) >= params.sector_cap:
            continue
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        selected_rows.append(r)
        if len(selected_rows) >= params.target_max:
            break

    if len(selected_rows) < params.target_min:
        print(f"[warn] too few after sector cap ({len(selected_rows)}). Relaxing sector cap.")
        selected_rows = pool.head(params.target_max).to_dict("records")

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
    """
    長期保有型用のポートフォリオ保存（portfolio_monthlyテーブルに保存）
    """
    if pf.empty:
        return
    rebalance_date = pf["rebalance_date"].iloc[0]
    conn.execute("DELETE FROM portfolio_monthly WHERE rebalance_date = ?", (rebalance_date,))
    conn.commit()

    rows = pf.to_dict("records")
    upsert(conn, "portfolio_monthly", rows, conflict_columns=["rebalance_date", "code"])


def save_portfolio_for_rebalance(conn, pf: pd.DataFrame):
    """
    月次リバランス型用のポートフォリオ保存（monthly_rebalance_portfolioテーブルに保存）
    """
    if pf.empty:
        return
    rebalance_date = pf["rebalance_date"].iloc[0]
    conn.execute("DELETE FROM monthly_rebalance_portfolio WHERE rebalance_date = ?", (rebalance_date,))
    conn.commit()

    rows = pf.to_dict("records")
    upsert(conn, "monthly_rebalance_portfolio", rows, conflict_columns=["rebalance_date", "code"])
    conn.commit()  # upsert後にコミットを追加


# -----------------------------
# Main
# -----------------------------

def main(asof: Optional[str] = None):
    run_date = asof or EXECUTION_DATE or datetime.now().strftime("%Y-%m-%d")
    print(f"[longterm] start | asof={run_date}")

    with connect_db() as conn:
        feat = build_features(conn, run_date)
        print(f"[longterm] features built: {len(feat)} codes")

        save_features(conn, feat)

        pf = select_portfolio(feat)
        print(f"[longterm] selected: {len(pf)} codes")

        save_portfolio(conn, pf)



    print("[longterm] done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Long-term run (feature build & selection)【長期保有型用】")
    parser.add_argument("--asof", type=str, help="As-of date (YYYY-MM-DD)")
    args = parser.parse_args()
    main(asof=args.asof)

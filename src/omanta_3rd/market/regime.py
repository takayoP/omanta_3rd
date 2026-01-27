"""
市場レジーム判定モジュール

TOPIXの移動平均（MA）を使用して市場レジームを判定します。
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import sqlite3

from ..infra.db import connect_db
from ..ingest.indices import TOPIX_CODE


def get_topix_close_series(conn: sqlite3.Connection, end_date: str, lookback_days: int = 250) -> pd.Series:
    """
    TOPIXの終値時系列を取得
    
    Args:
        conn: データベース接続
        end_date: 終了日（YYYY-MM-DD、この日を含む）
        lookback_days: 取得する過去日数（デフォルト: 250日）
    
    Returns:
        TOPIX終値のSeries（DatetimeIndex、昇順）
    """
    df = pd.read_sql_query(
        """
        SELECT date, close
        FROM index_daily
        WHERE index_code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
        """,
        conn,
        params=(TOPIX_CODE, end_date, lookback_days),
    )
    
    if df.empty:
        return pd.Series(dtype=float)
    
    # 日付をDatetimeIndexに変換し、昇順にソート
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    df = df.set_index('date')
    
    return df['close']


def get_market_regime(
    conn: sqlite3.Connection,
    rebalance_date: str,
    lookback_days: int = 250,
) -> Dict[str, Any]:
    """
    市場レジームを判定
    
    判定ロジック:
    - up: MA20 > MA60 > MA200 and slope200_20 > 0
    - down: MA20 < MA60 < MA200 and slope200_20 < 0
    - range: else
    
    Args:
        conn: データベース接続
        rebalance_date: リバランス日（YYYY-MM-DD、この日を含む）
        lookback_days: 過去データの取得日数（デフォルト: 250日）
    
    Returns:
        レジーム情報の辞書:
        {
            "regime": "up" | "down" | "range",
            "ma20": float,
            "ma60": float,
            "ma200": float,
            "slope200_20": float,
        }
    """
    # TOPIX終値時系列を取得
    topix_close = get_topix_close_series(conn, rebalance_date, lookback_days)
    
    if len(topix_close) < 200:
        # MA200が計算できない場合はrange扱い
        return {
            "regime": "range",
            "ma20": None,
            "ma60": None,
            "ma200": None,
            "slope200_20": None,
        }
    
    # 移動平均を計算
    ma20 = topix_close.rolling(20).mean().iloc[-1]
    ma60 = topix_close.rolling(60).mean().iloc[-1]
    ma200 = topix_close.rolling(200).mean().iloc[-1]
    
    # MA200の傾きを計算（20日前との差）
    if len(topix_close) >= 220:
        ma200_today = topix_close.rolling(200).mean().iloc[-1]
        ma200_20days_ago = topix_close.rolling(200).mean().iloc[-21]
        slope200_20 = ma200_today - ma200_20days_ago
    else:
        # 20日前のデータがない場合は0とする
        slope200_20 = 0.0
    
    # NaNチェック
    if pd.isna(ma20) or pd.isna(ma60) or pd.isna(ma200):
        return {
            "regime": "range",
            "ma20": float(ma20) if not pd.isna(ma20) else None,
            "ma60": float(ma60) if not pd.isna(ma60) else None,
            "ma200": float(ma200) if not pd.isna(ma200) else None,
            "slope200_20": float(slope200_20) if not pd.isna(slope200_20) else None,
        }
    
    # レジーム判定
    if ma20 > ma60 > ma200 and slope200_20 > 0:
        regime = "up"
    elif ma20 < ma60 < ma200 and slope200_20 < 0:
        regime = "down"
    else:
        regime = "range"
    
    return {
        "regime": regime,
        "ma20": float(ma20),
        "ma60": float(ma60),
        "ma200": float(ma200),
        "slope200_20": float(slope200_20),
    }














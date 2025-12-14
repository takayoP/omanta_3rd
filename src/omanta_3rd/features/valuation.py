"""PER/PBR/ForwardPER、同業比較"""

from typing import Optional, Dict, Any
import sqlite3

from ..infra.db import connect_db


def calculate_per(
    price: float,
    eps: Optional[float],
) -> Optional[float]:
    """
    PERを計算
    
    Args:
        price: 株価
        eps: EPS
        
    Returns:
        PER（None if 計算不可）
    """
    if eps is None or eps == 0:
        return None
    return price / eps


def calculate_pbr(
    price: float,
    bvps: Optional[float],
) -> Optional[float]:
    """
    PBRを計算
    
    Args:
        price: 株価
        bvps: BVPS
        
    Returns:
        PBR（None if 計算不可）
    """
    if bvps is None or bvps == 0:
        return None
    return price / bvps


def calculate_forward_per(
    price: float,
    forecast_eps: Optional[float],
) -> Optional[float]:
    """
    フォワードPERを計算
    
    Args:
        price: 株価
        forecast_eps: 予想EPS
        
    Returns:
        フォワードPER（None if 計算不可）
    """
    if forecast_eps is None or forecast_eps == 0:
        return None
    return price / forecast_eps


def get_sector_median_per(
    conn: sqlite3.Connection,
    sector33: str,
    as_of_date: str,
) -> Optional[float]:
    """
    業種別中央値PERを取得
    
    Args:
        conn: データベース接続
        sector33: 33業種コード
        as_of_date: 基準日（YYYY-MM-DD）
        
    Returns:
        業種中央値PER（None if 計算不可）
    """
    sql = """
        SELECT per
        FROM features_monthly
        WHERE sector33 = ? AND as_of_date = ? AND per IS NOT NULL
        ORDER BY per
    """
    rows = conn.execute(sql, (sector33, as_of_date)).fetchall()
    
    if not rows:
        return None
    
    pers = [row["per"] for row in rows]
    n = len(pers)
    
    if n % 2 == 0:
        return (pers[n // 2 - 1] + pers[n // 2]) / 2
    else:
        return pers[n // 2]



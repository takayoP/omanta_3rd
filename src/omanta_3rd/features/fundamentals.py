"""ROE、最高益（実績/予想）、成長率"""

from typing import Optional, List, Dict, Any, Tuple
import sqlite3

from ..infra.db import connect_db


def calculate_roe(profit: Optional[float], equity: Optional[float]) -> Optional[float]:
    """
    ROEを計算
    
    Args:
        profit: 当期純利益
        equity: 純資産
        
    Returns:
        ROE（None if 計算不可）
    """
    if profit is None or equity is None or equity == 0:
        return None
    return profit / equity


def calculate_roe_trend(
    conn: sqlite3.Connection,
    code: str,
    current_period_end: str,
    periods: int = 3,
) -> Optional[float]:
    """
    ROEのトレンドを計算（過去N期の平均ROEとの比較）
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        current_period_end: 現在の期末日（YYYY-MM-DD）
        periods: 比較期間数
        
    Returns:
        ROEトレンド（現在ROE - 過去平均ROE、None if 計算不可）
    """
    # 最新のROEを取得
    sql = """
        SELECT profit, equity
        FROM fins_statements
        WHERE code = ? AND type_of_current_period = 'FY'
        ORDER BY current_period_end DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code,)).fetchone()
    if not row or row["profit"] is None or row["equity"] is None:
        return None
    
    current_roe = calculate_roe(row["profit"], row["equity"])
    if current_roe is None:
        return None
    
    # 過去N期のROEを取得
    sql = """
        SELECT profit, equity
        FROM fins_statements
        WHERE code = ? AND type_of_current_period = 'FY'
          AND current_period_end < ?
        ORDER BY current_period_end DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (code, current_period_end, periods)).fetchall()
    
    if not rows:
        return None
    
    past_roes = [calculate_roe(row["profit"], row["equity"]) for row in rows]
    past_roes = [r for r in past_roes if r is not None]
    
    if not past_roes:
        return None
    
    avg_past_roe = sum(past_roes) / len(past_roes)
    return current_roe - avg_past_roe


def check_record_high(
    conn: sqlite3.Connection,
    code: str,
    current_period_end: str,
    rebalance_date: Optional[str] = None,
) -> Tuple[bool, bool]:
    """
    最高益フラグをチェック（実績/予想）
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        current_period_end: 現在の期末日（YYYY-MM-DD）
        rebalance_date: リバランス日（ポートフォリオ作成日、YYYY-MM-DD、データリーク防止のため必須）
                        リバランス日以前に開示されたデータのみを参照
        
    Returns:
        (実績最高益フラグ, 予想最高益フラグ)
    """
    if rebalance_date is None:
        raise ValueError("rebalance_dateは必須です。データリークを防ぐため、リバランス日（ポートフォリオ作成日）を明示的に指定してください。")
    
    # 最新の実績利益を取得（リバランス日以前に開示されたデータのみ）
    sql = """
        SELECT profit
        FROM fins_statements
        WHERE code = ? 
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND current_period_end <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, rebalance_date, rebalance_date)).fetchone()
    current_profit = row["profit"] if row else None
    
    # 過去最高の実績利益を取得（過去の取得できる（None以外の）利益を全て参照）
    # リバランス日以前に開示されたデータのみを参照
    sql = """
        SELECT MAX(profit) as max_profit
        FROM fins_statements
        WHERE code = ? 
          AND type_of_current_period = 'FY'
          AND current_period_end < ?
          AND disclosed_date <= ?
          AND profit IS NOT NULL
    """
    row = conn.execute(sql, (code, current_period_end, rebalance_date)).fetchone()
    max_past_profit = row["max_profit"] if row else None
    
    record_high_flag = (
        current_profit is not None
        and max_past_profit is not None
        and current_profit > max_past_profit
    )
    
    # 予想最高益フラグ（リバランス日以前に開示されたデータのみ）
    sql = """
        SELECT forecast_profit
        FROM fins_statements
        WHERE code = ? 
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND current_period_end <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, rebalance_date, rebalance_date)).fetchone()
    current_forecast = row["forecast_profit"] if row else None
    
    record_high_forecast_flag = (
        current_forecast is not None
        and max_past_profit is not None
        and current_forecast > max_past_profit
    )
    
    return (record_high_flag, record_high_forecast_flag)


def calculate_growth_rate(
    current: Optional[float],
    previous: Optional[float],
) -> Optional[float]:
    """
    成長率を計算
    
    Args:
        current: 現在値
        previous: 前期値
        
    Returns:
        成長率（None if 計算不可）
    """
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


"""Prime、流動性、サイズ加点など"""

from typing import Optional
import sqlite3

from ..infra.db import connect_db


def is_prime_market(
    conn: sqlite3.Connection,
    code: str,
    date: str,
) -> bool:
    """
    プライム市場（旧：東証一部）かどうかを判定
    
    市場区分の変遷:
    - 2022年4月以前: 「東証一部」「東証二部」「マザーズ」など
    - 2022年4月以降: 「プライム」「スタンダード」「グロース」など
    
    プライム市場 = 「プライム」「Prime」「東証一部」
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        date: 基準日（YYYY-MM-DD）
        
    Returns:
        プライム市場（旧：東証一部）の場合True
    """
    sql = """
        SELECT market_name
        FROM listed_info
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, date)).fetchone()
    
    if not row or not row["market_name"]:
        return False
    
    market_name = str(row["market_name"]).strip()
    
    # プライム市場の判定（旧区分も含む）
    return (
        market_name == "プライム" or
        market_name.lower() == "prime" or
        market_name == "東証一部"
    )


def calculate_liquidity_60d(
    conn: sqlite3.Connection,
    code: str,
    end_date: str,
) -> Optional[float]:
    """
    60営業日の平均売買代金を計算
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        end_date: 終了日（YYYY-MM-DD）
        
    Returns:
        平均売買代金（None if 計算不可）
    """
    sql = """
        SELECT AVG(turnover_value) as avg_turnover
        FROM (
            SELECT turnover_value
            FROM prices_daily
            WHERE code = ? AND date <= ? AND turnover_value IS NOT NULL
            ORDER BY date DESC
            LIMIT 60
        )
    """
    row = conn.execute(sql, (code, end_date)).fetchone()
    
    if not row or row["avg_turnover"] is None:
        return None
    
    return row["avg_turnover"]


def estimate_market_cap(
    conn: sqlite3.Connection,
    code: str,
    date: str,
) -> Optional[float]:
    """
    時価総額を推定（株価 × 発行済株式数）
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        date: 基準日（YYYY-MM-DD）
        
    Returns:
        時価総額（None if 計算不可）
    """
    # 最新の株価を取得
    sql = """
        SELECT adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, date)).fetchone()
    
    if not row or row["adj_close"] is None:
        return None
    
    price = row["adj_close"]
    
    # 最新の発行済株式数を取得
    sql = """
        SELECT shares_outstanding
        FROM fins_statements
        WHERE code = ? AND shares_outstanding IS NOT NULL
        ORDER BY current_period_end DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code,)).fetchone()
    
    if not row or row["shares_outstanding"] is None:
        return None
    
    shares = row["shares_outstanding"]
    
    return price * shares



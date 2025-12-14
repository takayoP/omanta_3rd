"""BB/RSI（テクニカル指標）"""

from typing import Optional, List
import sqlite3

from ..infra.db import connect_db


def calculate_bollinger_bands(
    conn: sqlite3.Connection,
    code: str,
    end_date: str,
    period: int = 20,
    num_std: float = 2.0,
) -> Optional[Dict[str, float]]:
    """
    ボリンジャーバンドを計算
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        end_date: 終了日（YYYY-MM-DD）
        period: 期間（デフォルト20日）
        num_std: 標準偏差の倍数（デフォルト2.0）
        
    Returns:
        {"upper": 上限, "middle": 中央（SMA）, "lower": 下限} または None
    """
    sql = """
        SELECT adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (code, end_date, period)).fetchall()
    
    if len(rows) < period:
        return None
    
    prices = [row["adj_close"] for row in reversed(rows) if row["adj_close"] is not None]
    
    if len(prices) < period:
        return None
    
    # 単純移動平均
    sma = sum(prices) / len(prices)
    
    # 標準偏差
    variance = sum((p - sma) ** 2 for p in prices) / len(prices)
    std = variance ** 0.5
    
    return {
        "upper": sma + num_std * std,
        "middle": sma,
        "lower": sma - num_std * std,
    }


def calculate_rsi(
    conn: sqlite3.Connection,
    code: str,
    end_date: str,
    period: int = 14,
) -> Optional[float]:
    """
    RSIを計算
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        end_date: 終了日（YYYY-MM-DD）
        period: 期間（デフォルト14日）
        
    Returns:
        RSI（0-100、None if 計算不可）
    """
    sql = """
        SELECT adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (code, end_date, period + 1)).fetchall()
    
    if len(rows) < period + 1:
        return None
    
    prices = [row["adj_close"] for row in reversed(rows) if row["adj_close"] is not None]
    
    if len(prices) < period + 1:
        return None
    
    # 価格変動を計算
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
    
    if not gains or not losses:
        return None
    
    avg_gain = sum(gains) / len(gains)
    avg_loss = sum(losses) / len(losses)
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi



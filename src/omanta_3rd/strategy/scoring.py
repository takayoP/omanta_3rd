"""core_score / entry_score"""

from typing import Optional, Dict, Any
import sqlite3

from ..config.strategy import StrategyConfig, default_strategy
from ..features.fundamentals import calculate_roe, calculate_roe_trend, calculate_growth_rate
from ..features.valuation import calculate_per, calculate_pbr


def calculate_core_score(
    conn: sqlite3.Connection,
    code: str,
    as_of_date: str,
    config: StrategyConfig = default_strategy,
) -> Optional[float]:
    """
    core_scoreを計算（中長期投資の基本スコア）
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        as_of_date: 基準日（YYYY-MM-DD）
        config: 戦略設定
        
    Returns:
        core_score（None if 計算不可）
    """
    # ROE
    sql = """
        SELECT profit, equity
        FROM fins_statements
        WHERE code = ? AND type_of_current_period = 'FY'
        ORDER BY current_period_end DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code,)).fetchone()
    if not row:
        return None
    
    roe = calculate_roe(row["profit"], row["equity"])
    if roe is None:
        return None
    
    # ROEトレンド
    sql = """
        SELECT current_period_end
        FROM fins_statements
        WHERE code = ? AND type_of_current_period = 'FY'
        ORDER BY current_period_end DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code,)).fetchone()
    current_period_end = row["current_period_end"] if row else None
    
    roe_trend = calculate_roe_trend(conn, code, current_period_end) if current_period_end else None
    
    # 利益成長率
    sql = """
        SELECT profit, forecast_profit
        FROM fins_statements
        WHERE code = ? AND type_of_current_period = 'FY'
        ORDER BY current_period_end DESC
        LIMIT 2
    """
    rows = conn.execute(sql, (code,)).fetchall()
    
    profit_growth = None
    if len(rows) >= 2:
        current_profit = rows[0]["profit"]
        previous_profit = rows[1]["profit"]
        profit_growth = calculate_growth_rate(current_profit, previous_profit)
    elif len(rows) == 1 and rows[0]["forecast_profit"]:
        # 予想成長率を使用
        current_profit = rows[0]["profit"]
        forecast_profit = rows[0]["forecast_profit"]
        profit_growth = calculate_growth_rate(forecast_profit, current_profit) if current_profit else None
    
    # スコア計算（正規化が必要な場合は調整）
    score = 0.0
    
    # ROEスコア（0-1に正規化、10%以上で0.5、20%以上で1.0と仮定）
    roe_score = min(roe / 0.20, 1.0) if roe >= 0 else 0.0
    score += roe_score * config.roe_weight
    
    # ROEトレンドスコア
    if roe_trend is not None:
        roe_trend_score = min(max(roe_trend / 0.05, 0.0), 1.0)  # 5%改善で1.0
        score += roe_trend_score * config.roe_trend_weight
    
    # 利益成長率スコア
    if profit_growth is not None:
        profit_growth_score = min(max(profit_growth / 0.20, 0.0), 1.0)  # 20%成長で1.0
        score += profit_growth_score * config.profit_growth_weight
    
    return score


def calculate_entry_score(
    conn: sqlite3.Connection,
    code: str,
    as_of_date: str,
    config: StrategyConfig = default_strategy,
) -> Optional[float]:
    """
    entry_scoreを計算（エントリータイミングのスコア）
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        as_of_date: リバランス日（ポートフォリオ作成日、YYYY-MM-DD）
                    リバランス日以前に開示されたデータのみを参照
        config: 戦略設定
        
    Returns:
        entry_score（None if 計算不可）
    """
    # 最新の株価を取得
    sql = """
        SELECT adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, as_of_date)).fetchone()
    if not row or row["adj_close"] is None:
        return None
    
    price = row["adj_close"]
    
    # PER/PBR（リバランス日（ポートフォリオ作成日）以前に開示されたデータのみ）
    sql = """
        SELECT eps, bvps, forecast_eps
        FROM fins_statements
        WHERE code = ? 
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND current_period_end <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, as_of_date, as_of_date)).fetchone()
    if not row:
        return None
    
    per = calculate_per(price, row["eps"])
    pbr = calculate_pbr(price, row["bvps"])
    forward_per = calculate_per(price, row["forecast_eps"]) if row["forecast_eps"] else None
    
    # バリュエーションスコア（PER/PBRが低いほど高スコア）
    valuation_score = 0.0
    if per is not None and per > 0:
        # PERが10以下で1.0、30以上で0.0
        per_score = max(0.0, 1.0 - (per - 10) / 20)
        valuation_score += per_score * 0.5
    
    if pbr is not None and pbr > 0:
        # PBRが1以下で1.0、3以上で0.0
        pbr_score = max(0.0, 1.0 - (pbr - 1) / 2)
        valuation_score += pbr_score * 0.5
    
    # 最高益フラグ
    # リバランス日（ポートフォリオ作成日）以前に開示されたデータのみを参照
    sql = """
        SELECT current_period_end
        FROM fins_statements
        WHERE code = ? 
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND current_period_end <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
    """
    row = conn.execute(sql, (code, as_of_date, as_of_date)).fetchone()
    current_period_end = row["current_period_end"] if row else None
    
    from ..features.fundamentals import check_record_high
    record_high_flag, record_high_forecast_flag = (
        check_record_high(conn, code, current_period_end, as_of_date) if current_period_end
        else (False, False)
    )
    
    record_score = 0.0
    if record_high_flag:
        record_score += 0.5
    if record_high_forecast_flag:
        record_score += 0.5
    
    # スコア合成
    score = (
        valuation_score * config.valuation_weight +
        record_score * config.record_high_weight
    )
    
    return score



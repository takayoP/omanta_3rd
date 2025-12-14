"""20-30銘柄選定（業種上限・入替上限）"""

from typing import List, Dict, Any, Optional
import sqlite3
import json

from ..infra.db import connect_db
from ..config.strategy import StrategyConfig, default_strategy
from .scoring import calculate_core_score, calculate_entry_score


def select_portfolio(
    conn: sqlite3.Connection,
    as_of_date: str,
    config: StrategyConfig = default_strategy,
) -> List[Dict[str, Any]]:
    """
    ポートフォリオを選定
    
    Args:
        conn: データベース接続
        as_of_date: 基準日（YYYY-MM-DD）
        config: 戦略設定
        
    Returns:
        選定銘柄のリスト（code, weight, core_score, entry_score, reason）
    """
    # フィルタリング条件を適用
    sql = """
        SELECT DISTINCT fm.code, fm.sector33, fm.core_score, fm.entry_score,
               li.market_name, fm.liquidity_60d, fm.market_cap, fm.per, fm.pbr
        FROM features_monthly fm
        LEFT JOIN listed_info li ON fm.code = li.code AND li.date = (
            SELECT MAX(date) FROM listed_info WHERE code = fm.code AND date <= ?
        )
        WHERE fm.as_of_date = ?
          AND fm.liquidity_60d >= ?
          AND fm.market_cap >= ?
    """
    params = [as_of_date, as_of_date, config.min_liquidity_60d, config.min_market_cap]
    
    if config.max_per:
        sql += " AND (fm.per IS NULL OR fm.per <= ?)"
        params.append(config.max_per)
    
    if config.max_pbr:
        sql += " AND (fm.pbr IS NULL OR fm.pbr <= ?)"
        params.append(config.max_pbr)
    
    if config.target_markets:
        placeholders = ",".join(["?"] * len(config.target_markets))
        sql += f" AND li.market_name IN ({placeholders})"
        params.extend(config.target_markets)
    
    sql += " ORDER BY fm.core_score DESC, fm.entry_score DESC"
    
    candidates = conn.execute(sql, params).fetchall()
    
    # 業種別に上限を適用
    selected = []
    sector_count = {}
    
    for row in candidates:
        code = row["code"]
        sector = row["sector33"] or "OTHER"
        
        # 業種上限チェック
        if sector_count.get(sector, 0) >= config.max_stocks_per_sector:
            continue
        
        # スコアがNoneの場合はスキップ
        if row["core_score"] is None:
            continue
        
        selected.append({
            "code": code,
            "sector33": sector,
            "core_score": row["core_score"],
            "entry_score": row["entry_score"],
            "reason": json.dumps({
                "market_name": row["market_name"],
                "liquidity_60d": row["liquidity_60d"],
                "market_cap": row["market_cap"],
            }, ensure_ascii=False),
        })
        
        sector_count[sector] = sector_count.get(sector, 0) + 1
        
        # 目標銘柄数に達したら終了
        if len(selected) >= config.target_stock_count:
            break
    
    # 等加重で重み付け
    if selected:
        weight = 1.0 / len(selected)
        for item in selected:
            item["weight"] = weight
    
    return selected


def apply_replacement_limit(
    conn: sqlite3.Connection,
    new_portfolio: List[Dict[str, Any]],
    previous_date: str,
    config: StrategyConfig = default_strategy,
) -> List[Dict[str, Any]]:
    """
    入替上限を適用
    
    Args:
        conn: データベース接続
        new_portfolio: 新ポートフォリオ
        previous_date: 前回リバランス日（YYYY-MM-DD）
        config: 戦略設定
        
    Returns:
        入替上限適用後のポートフォリオ
    """
    # 前回ポートフォリオを取得
    sql = """
        SELECT code
        FROM portfolio_monthly
        WHERE rebalance_date = ?
    """
    previous_codes = {row["code"] for row in conn.execute(sql, (previous_date,)).fetchall()}
    
    new_codes = {item["code"] for item in new_portfolio}
    
    # 新規追加銘柄数
    new_additions = len(new_codes - previous_codes)
    max_additions = int(len(new_portfolio) * config.max_replacement_ratio)
    
    if new_additions <= max_additions:
        return new_portfolio
    
    # 入替上限を超える場合は、前回ポートフォリオを優先
    result = []
    kept_count = 0
    
    # 前回ポートフォリオから保持
    for item in new_portfolio:
        if item["code"] in previous_codes:
            result.append(item)
            kept_count += 1
    
    # 新規追加分を制限
    remaining_slots = len(new_portfolio) - kept_count
    max_new = min(max_additions, remaining_slots)
    
    new_items = [item for item in new_portfolio if item["code"] not in previous_codes]
    new_items.sort(key=lambda x: (x["core_score"] or 0, x["entry_score"] or 0), reverse=True)
    
    result.extend(new_items[:max_new])
    
    # 重みを再計算
    if result:
        weight = 1.0 / len(result)
        for item in result:
            item["weight"] = weight
    
    return result



"""ポートフォリオのパフォーマンス計算"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import pandas as pd

from ..infra.db import connect_db, upsert


def calculate_portfolio_performance(
    rebalance_date: str,
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    指定されたrebalance_dateのポートフォリオのパフォーマンスを計算
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        
    Returns:
        パフォーマンス情報の辞書
    """
    with connect_db() as conn:
        # ポートフォリオを取得
        portfolio = pd.read_sql_query(
            """
            SELECT code, weight, core_score, entry_score
            FROM portfolio_monthly
            WHERE rebalance_date = ?
            """,
            conn,
            params=(rebalance_date,),
        )
        
        if portfolio.empty:
            return {
                "rebalance_date": rebalance_date,
                "as_of_date": as_of_date,
                "error": "ポートフォリオが見つかりません",
            }
        
        # 評価日を決定
        if as_of_date is None:
            latest_date = pd.read_sql_query(
                "SELECT MAX(date) as max_date FROM prices_daily",
                conn
            )["max_date"].iloc[0]
            as_of_date = latest_date
        
        # 各銘柄のリバランス日時点の価格を取得
        rebalance_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT adj_close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, rebalance_date),
            )
            if not price_row.empty and price_row["adj_close"].iloc[0] is not None:
                rebalance_prices.append({
                    "code": code,
                    "rebalance_price": price_row["adj_close"].iloc[0],
                })
        
        rebalance_prices_df = pd.DataFrame(rebalance_prices)
        portfolio = portfolio.merge(rebalance_prices_df, on="code", how="left")
        
        # 各銘柄の現在価格を取得
        current_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT adj_close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, as_of_date),
            )
            if not price_row.empty and price_row["adj_close"].iloc[0] is not None:
                current_prices.append({
                    "code": code,
                    "current_price": price_row["adj_close"].iloc[0],
                })
        
        current_prices_df = pd.DataFrame(current_prices)
        portfolio = portfolio.merge(current_prices_df, on="code", how="left")
        
        # 損益率を計算
        portfolio["return_pct"] = (
            (portfolio["current_price"] - portfolio["rebalance_price"]) 
            / portfolio["rebalance_price"] 
            * 100.0
        )
        
        # ポートフォリオ全体の損益を計算（weightを考慮）
        portfolio["weighted_return"] = portfolio["weight"] * portfolio["return_pct"]
        total_return = portfolio["weighted_return"].sum()
        
        # 統計情報
        valid_returns = portfolio[portfolio["return_pct"].notna()]["return_pct"]
        
        result = {
            "rebalance_date": rebalance_date,
            "as_of_date": as_of_date,
            "total_return_pct": float(total_return) if not pd.isna(total_return) else None,
            "num_stocks": len(portfolio),
            "num_stocks_with_price": len(portfolio[portfolio["current_price"].notna()]),
            "avg_return_pct": float(valid_returns.mean()) if len(valid_returns) > 0 else None,
            "min_return_pct": float(valid_returns.min()) if len(valid_returns) > 0 else None,
            "max_return_pct": float(valid_returns.max()) if len(valid_returns) > 0 else None,
            "stocks": portfolio[
                ["code", "weight", "rebalance_price", "current_price", "return_pct"]
            ].to_dict("records"),
        }
        
        return result


def calculate_all_portfolios_performance(
    as_of_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    すべてのポートフォリオのパフォーマンスを計算
    
    Args:
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        
    Returns:
        各ポートフォリオのパフォーマンス情報のリスト
    """
    with connect_db() as conn:
        # すべてのrebalance_dateを取得
        rebalance_dates = pd.read_sql_query(
            """
            SELECT DISTINCT rebalance_date
            FROM portfolio_monthly
            ORDER BY rebalance_date
            """,
            conn,
        )["rebalance_date"].tolist()
        
        results = []
        for rebalance_date in rebalance_dates:
            perf = calculate_portfolio_performance(rebalance_date, as_of_date)
            results.append(perf)
        
        return results


def save_performance_to_db(
    performance: Dict[str, Any],
) -> None:
    """
    パフォーマンス結果をデータベースに保存
    
    Args:
        performance: calculate_portfolio_performance()の戻り値
    """
    if "error" in performance:
        return
    
    with connect_db() as conn:
        # ポートフォリオ全体のパフォーマンスを保存
        perf_row = {
            "rebalance_date": performance["rebalance_date"],
            "as_of_date": performance["as_of_date"],
            "total_return_pct": performance.get("total_return_pct"),
            "num_stocks": performance.get("num_stocks"),
            "num_stocks_with_price": performance.get("num_stocks_with_price"),
            "avg_return_pct": performance.get("avg_return_pct"),
            "min_return_pct": performance.get("min_return_pct"),
            "max_return_pct": performance.get("max_return_pct"),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        upsert(conn, "backtest_performance", [perf_row], conflict_columns=["rebalance_date", "as_of_date"])
        
        # 銘柄別のパフォーマンスを保存
        stock_rows = []
        for stock in performance.get("stocks", []):
            stock_rows.append({
                "rebalance_date": performance["rebalance_date"],
                "as_of_date": performance["as_of_date"],
                "code": stock["code"],
                "weight": stock["weight"],
                "rebalance_price": stock.get("rebalance_price"),
                "current_price": stock.get("current_price"),
                "return_pct": stock.get("return_pct"),
            })
        
        if stock_rows:
            upsert(
                conn,
                "backtest_stock_performance",
                stock_rows,
                conflict_columns=["rebalance_date", "as_of_date", "code"],
            )


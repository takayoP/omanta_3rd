"""ポートフォリオのパフォーマンス計算"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import pandas as pd

from ..infra.db import connect_db, upsert


def _get_next_trading_day(conn, date: str) -> Optional[str]:
    """
    指定日付の翌営業日を取得（価格データが存在する最初の日付）
    
    Args:
        conn: データベース接続
        date: 基準日（YYYY-MM-DD）
    
    Returns:
        翌営業日（YYYY-MM-DD）、存在しない場合はNone
    """
    next_date_df = pd.read_sql_query(
        """
        SELECT MIN(date) AS next_date
        FROM prices_daily
        WHERE date > ?
        """,
        conn,
        params=(date,),
    )
    
    if next_date_df.empty or pd.isna(next_date_df["next_date"].iloc[0]):
        return None
    
    return str(next_date_df["next_date"].iloc[0])


def _split_multiplier_between(conn, code: str, start_date: str, end_date: str) -> float:
    """
    指定期間内の分割・併合による株数倍率を計算
    
    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。
    
    例: 1:3分割（adjustment_factor = 0.333333）の場合、
    株数倍率 = 1 / 0.333333 ≈ 3.0
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        start_date: 開始日（YYYY-MM-DD、通常は購入日の翌営業日）
        end_date: 終了日（YYYY-MM-DD、評価日）
    
    Returns:
        株数倍率（分割・併合がない場合は1.0）
    """
    # start_dateより後、end_date以下のAdjustmentFactorを取得
    df = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > ?
          AND date <= ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, start_date, end_date),
    )
    
    if df.empty:
        return 1.0
    
    # 株数倍率を計算: split_mult = ∏(1 / adjustment_factor)
    mult = 1.0
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        # 念のためゼロ・異常値ガード
        if pd.notna(adj_factor) and adj_factor > 0:
            mult *= (1.0 / float(adj_factor))
    
    return mult


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
            latest_date_df = pd.read_sql_query(
                "SELECT MAX(date) as max_date FROM prices_daily",
                conn
            )
            if latest_date_df.empty or pd.isna(latest_date_df["max_date"].iloc[0]):
                return {
                    "rebalance_date": rebalance_date,
                    "as_of_date": None,
                    "error": "価格データが見つかりません",
                }
            as_of_date = latest_date_df["max_date"].iloc[0]
        
        # リバランス日の翌営業日を取得
        next_trading_day = _get_next_trading_day(conn, rebalance_date)
        if next_trading_day is None:
            return {
                "rebalance_date": rebalance_date,
                "as_of_date": as_of_date,
                "error": f"リバランス日の翌営業日が見つかりません: {rebalance_date}",
            }
        
        # 各銘柄のリバランス日の翌営業日の始値を取得（購入価格）
        rebalance_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT open
                FROM prices_daily
                WHERE code = ? AND date = ?
                """,
                conn,
                params=(code, next_trading_day),
            )
            if not price_row.empty and price_row["open"].iloc[0] is not None:
                rebalance_prices.append({
                    "code": code,
                    "rebalance_price": price_row["open"].iloc[0],
                })
        
        rebalance_prices_df = pd.DataFrame(rebalance_prices)
        portfolio = portfolio.merge(rebalance_prices_df, on="code", how="left")
        
        # 各銘柄の現在価格を取得（終値を使用）
        current_prices = []
        split_multipliers = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, as_of_date),
            )
            if not price_row.empty and price_row["close"].iloc[0] is not None:
                current_prices.append({
                    "code": code,
                    "current_price": price_row["close"].iloc[0],
                })
                # リバランス日の翌営業日以後の分割倍率を計算
                # 注: 翌営業日以降の分割を考慮するため、next_trading_dayを使用
                split_mult = _split_multiplier_between(conn, code, next_trading_day, as_of_date)
                split_multipliers.append({
                    "code": code,
                    "split_multiplier": split_mult,
                })
        
        current_prices_df = pd.DataFrame(current_prices)
        portfolio = portfolio.merge(current_prices_df, on="code", how="left")
        
        split_multipliers_df = pd.DataFrame(split_multipliers)
        portfolio = portfolio.merge(split_multipliers_df, on="code", how="left")
        # 分割倍率が取得できなかった場合は1.0とする
        portfolio["split_multiplier"] = portfolio["split_multiplier"].fillna(1.0)
        
        # 損益率を計算（分割を考慮）
        # 分割が発生した場合、現在価格に分割倍率を掛けて調整
        portfolio["adjusted_current_price"] = portfolio["current_price"] * portfolio["split_multiplier"]
        portfolio["return_pct"] = (
            (portfolio["adjusted_current_price"] - portfolio["rebalance_price"]) 
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
                ["code", "weight", "rebalance_price", "current_price", "split_multiplier", "adjusted_current_price", "return_pct"]
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
        stocks = performance.get("stocks", [])
        if stocks:
            for stock in stocks:
                # codeが存在することを確認
                if "code" in stock:
                    stock_rows.append({
                        "rebalance_date": performance["rebalance_date"],
                        "as_of_date": performance["as_of_date"],
                        "code": stock["code"],
                        "weight": stock.get("weight"),
                        "rebalance_price": stock.get("rebalance_price"),
                        "current_price": stock.get("current_price"),
                        "split_multiplier": stock.get("split_multiplier"),
                        "adjusted_current_price": stock.get("adjusted_current_price"),
                        "return_pct": stock.get("return_pct"),
                    })
        
        if stock_rows:
            upsert(
                conn,
                "backtest_stock_performance",
                stock_rows,
                conflict_columns=["rebalance_date", "as_of_date", "code"],
            )


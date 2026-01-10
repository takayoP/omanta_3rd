"""
ポートフォリオDataFrameから直接パフォーマンスを計算

DBを使わず、メモリ内のポートフォリオDataFrameから直接パフォーマンスを計算します。
複数戦略の比較時に、DBの上書き問題を回避するために使用します。
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import pandas as pd

from ..infra.db import connect_db
from ..ingest.indices import TOPIX_CODE
from .performance import (
    _get_next_trading_day,
    _get_topix_price,
    _split_multiplier_between,
)


def calculate_portfolio_performance_from_dataframe(
    portfolio: pd.DataFrame,
    rebalance_date: str,
    as_of_date: str,
) -> Dict[str, Any]:
    """
    ポートフォリオDataFrameから直接パフォーマンスを計算
    
    Args:
        portfolio: ポートフォリオDataFrame（code, weightカラムが必要）
        rebalance_date: リバランス日（YYYY-MM-DD）
        as_of_date: 評価日（YYYY-MM-DD、必須）
    
    Returns:
        パフォーマンス情報の辞書
    """
    if portfolio.empty:
        return {
            "rebalance_date": rebalance_date,
            "as_of_date": as_of_date,
            "error": "ポートフォリオが空です",
        }
    
    with connect_db() as conn:
        # リバランス日の翌営業日を取得
        # 重要: as_of_date以前のデータのみを参照（データリーク防止）
        next_trading_day = _get_next_trading_day(conn, rebalance_date, max_date=as_of_date)
        if next_trading_day is None:
            return {
                "rebalance_date": rebalance_date,
                "as_of_date": as_of_date,
                "error": f"リバランス日の翌営業日が見つかりません: {rebalance_date} (as_of_date={as_of_date}以前のデータを参照)",
            }
        
        # 各銘柄のリバランス日の翌営業日の始値を取得（購入価格）
        rebalance_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT open, close
                FROM prices_daily
                WHERE code = ? AND date = ?
                """,
                conn,
                params=(code, next_trading_day),
            )
            if not price_row.empty:
                # 始値がNULLの場合は終値をフォールバックとして使用
                buy_price = price_row["open"].iloc[0]
                if buy_price is None or pd.isna(buy_price):
                    buy_price = price_row["close"].iloc[0]
                
                if buy_price is not None and not pd.isna(buy_price):
                    rebalance_prices.append({
                        "code": code,
                        "rebalance_price": buy_price,
                    })
        
        if rebalance_prices:
            rebalance_prices_df = pd.DataFrame(rebalance_prices)
        else:
            rebalance_prices_df = pd.DataFrame(columns=["code", "rebalance_price"])
        
        portfolio = portfolio.merge(rebalance_prices_df, on="code", how="left")
        
        # 各銘柄の現在価格を取得（終値を使用）
        current_prices = []
        split_multipliers = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT date, close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, as_of_date),
            )
            if not price_row.empty and price_row["close"].iloc[0] is not None:
                effective_asof_date = str(price_row["date"].iloc[0])
                current_prices.append({
                    "code": code,
                    "current_price": price_row["close"].iloc[0],
                })
                # リバランス日の翌営業日以後の分割倍率を計算
                split_mult = _split_multiplier_between(conn, code, next_trading_day, effective_asof_date)
                split_multipliers.append({
                    "code": code,
                    "split_multiplier": split_mult,
                })
        
        current_prices_df = pd.DataFrame(current_prices)
        portfolio = portfolio.merge(current_prices_df, on="code", how="left")
        
        split_multipliers_df = pd.DataFrame(split_multipliers)
        portfolio = portfolio.merge(split_multipliers_df, on="code", how="left")
        portfolio["split_multiplier"] = portfolio["split_multiplier"].fillna(1.0)
        
        # 損益率を計算（分割を考慮）
        portfolio["adjusted_current_price"] = portfolio["current_price"] * portfolio["split_multiplier"]
        portfolio["return_pct"] = (
            (portfolio["adjusted_current_price"] - portfolio["rebalance_price"]) 
            / portfolio["rebalance_price"] 
            * 100.0
        )
        
        # ポートフォリオ全体の損益を計算（weightを考慮）
        portfolio["weighted_return"] = portfolio["weight"] * portfolio["return_pct"]
        
        # 有効銘柄（return_pctがNaNでない）のweight合計を計算
        valid_mask = portfolio["return_pct"].notna()
        valid_weight_sum = portfolio.loc[valid_mask, "weight"].sum()
        total_weight = portfolio["weight"].sum()
        
        # sum(min_count=1)を使用: 全部NaNならNaNを維持
        total_return = portfolio["weighted_return"].sum(min_count=1)
        
        # TOPIX比較
        topix_buy_price = _get_topix_price(conn, next_trading_day, use_open=True)
        topix_sell_price = _get_topix_price(conn, as_of_date, use_open=False)
        
        topix_return_pct = None
        if topix_buy_price is not None and topix_sell_price is not None and topix_buy_price > 0:
            topix_return_pct = ((topix_sell_price - topix_buy_price) / topix_buy_price) * 100.0
        
        excess_return_pct = None
        if total_return is not None and not pd.isna(total_return) and topix_return_pct is not None:
            excess_return_pct = total_return - topix_return_pct
        
        # 統計情報
        valid_returns = portfolio[portfolio["return_pct"].notna()]["return_pct"]
        
        result = {
            "rebalance_date": rebalance_date,
            "as_of_date": as_of_date,
            "total_return_pct": float(total_return) if total_return is not None and not pd.isna(total_return) else None,
            "num_stocks": len(portfolio),
            "num_stocks_with_price": len(portfolio[portfolio["current_price"].notna()]),
            "avg_return_pct": float(valid_returns.mean()) if len(valid_returns) > 0 else None,
            "min_return_pct": float(valid_returns.min()) if len(valid_returns) > 0 else None,
            "max_return_pct": float(valid_returns.max()) if len(valid_returns) > 0 else None,
            "topix_comparison": {
                "topix_return_pct": topix_return_pct,
                "excess_return_pct": excess_return_pct,
            },
        }
        
        return result


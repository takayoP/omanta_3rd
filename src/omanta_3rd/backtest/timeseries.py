"""
時系列P/L計算モジュール

月次リバランス戦略としての正しい時系列リターンを計算します。
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from ..infra.db import connect_db
from .performance import _get_next_trading_day, _split_multiplier_between, _get_topix_price


def _get_previous_trading_day(conn, date: str) -> Optional[str]:
    """
    指定日付の前営業日を取得
    
    Args:
        conn: データベース接続
        date: 基準日（YYYY-MM-DD）
    
    Returns:
        前営業日（YYYY-MM-DD）、存在しない場合はNone
    """
    prev_date_df = pd.read_sql_query(
        """
        SELECT MAX(date) AS prev_date
        FROM prices_daily
        WHERE date < ?
        """,
        conn,
        params=(date,),
    )
    
    if prev_date_df.empty or pd.isna(prev_date_df["prev_date"].iloc[0]):
        return None
    
    return str(prev_date_df["prev_date"].iloc[0])


def _get_price(conn, code: str, date: str, use_open: bool = False) -> Optional[float]:
    """
    指定日の価格を取得
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        date: 日付（YYYY-MM-DD）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        価格、存在しない場合はNone
    """
    price_column = "open" if use_open else "close"
    price_df = pd.read_sql_query(
        f"""
        SELECT {price_column}
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """,
        conn,
        params=(code, date),
    )
    
    if price_df.empty or pd.isna(price_df[price_column].iloc[0]):
        return None
    
    return float(price_df[price_column].iloc[0])


def _get_rebalance_dates(conn, start_date: str, end_date: str) -> List[str]:
    """
    リバランス日のリストを取得
    
    Args:
        conn: データベース接続
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    
    Returns:
        リバランス日のリスト
    """
    df = pd.read_sql_query(
        """
        SELECT DISTINCT rebalance_date
        FROM portfolio_monthly
        WHERE rebalance_date >= ? AND rebalance_date <= ?
        ORDER BY rebalance_date ASC
        """,
        conn,
        params=(start_date, end_date),
    )
    return df["rebalance_date"].tolist()


def _get_portfolio(conn, rebalance_date: str) -> pd.DataFrame:
    """
    指定日のポートフォリオを取得
    
    Args:
        conn: データベース接続
        rebalance_date: リバランス日（YYYY-MM-DD）
    
    Returns:
        ポートフォリオのDataFrame（code, weight列を含む）
    """
    return pd.read_sql_query(
        """
        SELECT code, weight
        FROM portfolio_monthly
        WHERE rebalance_date = ?
        """,
        conn,
        params=(rebalance_date,),
    )


def calculate_timeseries_returns(
    start_date: str,
    end_date: str,
    rebalance_dates: Optional[List[str]] = None,
    cost_bps: float = 0.0,
) -> Dict[str, Any]:
    """
    時系列P/Lを計算
    
    各リバランス日 ti から次のリバランス日 ti+1 までの月次リターンを計算します。
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        rebalance_dates: リバランス日のリスト（Noneの場合は自動取得）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
    
    Returns:
        時系列P/L情報の辞書:
        - monthly_returns: 月次リターンのリスト（小数、0.01 = 1%）
        - monthly_excess_returns: 月次超過リターンのリスト（小数）
        - equity_curve: エクイティカーブ（初期値1.0）
        - dates: リバランス日のリスト
        - portfolio_details: 各リバランス日のポートフォリオ詳細
    """
    with connect_db() as conn:
        # リバランス日のリストを取得
        if rebalance_dates is None:
            rebalance_dates = _get_rebalance_dates(conn, start_date, end_date)
        
        if not rebalance_dates:
            return {
                "monthly_returns": [],
                "monthly_excess_returns": [],
                "equity_curve": [1.0],
                "dates": [],
                "portfolio_details": [],
            }
        
        monthly_returns = []
        monthly_excess_returns = []
        equity_curve = [1.0]  # 初期値1.0
        portfolio_details = []
        
        for i, rebalance_date in enumerate(rebalance_dates):
            # 次のリバランス日を取得（最後の場合はend_date）
            if i + 1 < len(rebalance_dates):
                next_rebalance_date = rebalance_dates[i + 1]
            else:
                next_rebalance_date = end_date
            
            # ポートフォリオを取得
            portfolio = _get_portfolio(conn, rebalance_date)
            if portfolio.empty:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # リバランス日の翌営業日を取得（購入日）
            purchase_date = _get_next_trading_day(conn, rebalance_date)
            if purchase_date is None:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 次のリバランス日の前営業日を取得（売却日）
            # 注意: 次のリバランス日の価格は使わない（リバランス前の価格を使用）
            sell_date = _get_previous_trading_day(conn, next_rebalance_date)
            if sell_date is None:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 各銘柄のリターンを計算
            stock_returns = []
            for _, row in portfolio.iterrows():
                code = row["code"]
                weight = row["weight"]
                
                # 購入価格（リバランス日の翌営業日の始値）
                purchase_price = _get_price(conn, code, purchase_date, use_open=True)
                if purchase_price is None:
                    continue
                
                # 売却価格（次のリバランス日の前営業日の終値）
                sell_price = _get_price(conn, code, sell_date, use_open=False)
                if sell_price is None:
                    continue
                
                # 株式分割を考慮
                split_mult = _split_multiplier_between(conn, code, purchase_date, sell_date)
                
                # リターン計算（分割を考慮）
                # 分割が発生した場合、購入価格を分割後の基準に調整
                adjusted_purchase_price = purchase_price / split_mult
                return_decimal = (sell_price / adjusted_purchase_price - 1.0)
                
                stock_returns.append({
                    "code": code,
                    "weight": weight,
                    "return_decimal": return_decimal,
                })
            
            # ポートフォリオ全体のグロスリターン（重み付き平均）
            if stock_returns:
                # 重みの合計を計算（正規化のため）
                total_weight = sum(r["weight"] for r in stock_returns)
                if total_weight > 0:
                    portfolio_return_gross = sum(
                        (r["weight"] / total_weight) * r["return_decimal"] 
                        for r in stock_returns
                    )
                else:
                    portfolio_return_gross = 0.0
                
                # 取引コストを控除（簡易版：ターンオーバーは後で計算）
                portfolio_return_net = portfolio_return_gross - (cost_bps / 1e4)
                
                # TOPIXリターンを計算
                topix_purchase = _get_topix_price(conn, purchase_date, use_open=False)
                topix_sell = _get_topix_price(conn, sell_date, use_open=False)
                
                if topix_purchase is not None and topix_sell is not None and topix_purchase > 0:
                    topix_return = (topix_sell / topix_purchase - 1.0)
                    excess_return = portfolio_return_net - topix_return
                else:
                    topix_return = 0.0
                    excess_return = portfolio_return_net
                
                monthly_returns.append(portfolio_return_net)
                monthly_excess_returns.append(excess_return)
                equity_curve.append(equity_curve[-1] * (1.0 + portfolio_return_net))
                
                portfolio_details.append({
                    "rebalance_date": rebalance_date,
                    "purchase_date": purchase_date,
                    "sell_date": sell_date,
                    "next_rebalance_date": next_rebalance_date,
                    "num_stocks": len(stock_returns),
                    "portfolio_return_gross": portfolio_return_gross,
                    "portfolio_return_net": portfolio_return_net,
                    "topix_return": topix_return,
                    "excess_return": excess_return,
                })
            else:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
        
        return {
            "monthly_returns": monthly_returns,  # 小数（0.01 = 1%）
            "monthly_excess_returns": monthly_excess_returns,  # 小数
            "equity_curve": equity_curve,  # 初期値1.0からの累積
            "dates": rebalance_dates,
            "portfolio_details": portfolio_details,
        }


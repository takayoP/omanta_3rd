"""
コード7419のデータベース状態を確認
"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

code = "7419"
asof = "2025-12-19"

with connect_db() as conn:
    # 価格データを確認
    print("【価格データ】")
    price_data = pd.read_sql_query(
        """
        SELECT date, code, close, adj_close, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date = ?
        """,
        conn,
        params=(code, asof),
    )
    print(price_data)
    
    # 財務データを確認
    print("\n【財務データ】")
    fy_data = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, profit, equity, 
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 5
        """,
        conn,
        params=(code, asof),
    )
    print(fy_data)
    
    # 予想データを確認
    print("\n【予想データ】")
    fc_data = pd.read_sql_query(
        """
        SELECT disclosed_date, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND type_of_current_period = 'FY'
          AND forecast_profit IS NOT NULL
        ORDER BY disclosed_date DESC
        LIMIT 5
        """,
        conn,
        params=(code, asof),
    )
    print(fc_data)
    
    # 分割情報を確認
    print("\n【分割情報】")
    split_data = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > '2025-03-31'
          AND date <= ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, asof),
    )
    print(split_data)

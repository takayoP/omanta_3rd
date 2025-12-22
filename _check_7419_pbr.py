"""コード7419のPBR計算を確認"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    # 最新のfeatures_monthlyからPBRを確認
    features = pd.read_sql_query(
        """
        SELECT as_of_date, code, per, pbr, forward_per, market_cap, core_score
        FROM features_monthly
        WHERE code = '7419'
        ORDER BY as_of_date DESC
        LIMIT 5
        """,
        conn
    )
    print("features_monthlyのPBR:")
    print(features)
    
    # 最新の財務データを確認
    fins = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, equity, bvps, shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE code = '7419'
          AND type_of_current_period = 'FY'
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 5
        """,
        conn
    )
    print("\n最新の財務データ:")
    print(fins)
    
    # 最新の価格データを確認
    prices = pd.read_sql_query(
        """
        SELECT date, adj_close, adjustment_factor
        FROM prices_daily
        WHERE code = '7419'
          AND date = (SELECT MAX(date) FROM prices_daily WHERE code = '7419')
        """,
        conn
    )
    print("\n最新の価格データ:")
    print(prices)
    
    # adjustment_factorの履歴を確認
    adj_history = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = '7419'
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date DESC
        LIMIT 10
        """,
        conn
    )
    print("\n調整係数の履歴（1.0以外）:")
    print(adj_history)

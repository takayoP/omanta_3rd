"""
コード7419の詳細データを確認
"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

code = "7419"
asof = "2025-12-19"

with connect_db() as conn:
    # 最新のFYデータを確認（ROW_NUMBER()を使った方法）
    print("【最新のFYデータ（ROW_NUMBER()方式）】")
    fy_data = pd.read_sql_query(
        """
        WITH ranked AS (
          SELECT
            code, current_period_end, disclosed_date,
            profit, equity, shares_outstanding, treasury_shares,
            ROW_NUMBER() OVER (
              PARTITION BY code
              ORDER BY current_period_end DESC, disclosed_date DESC
            ) AS rn
          FROM fins_statements
          WHERE disclosed_date <= ?
            AND type_of_current_period = 'FY'
            AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
                 OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
        )
        SELECT code, current_period_end, disclosed_date,
               profit, equity, shares_outstanding, treasury_shares
        FROM ranked
        WHERE rn = 1
          AND code = ?
        """,
        conn,
        params=(asof, code),
    )
    print(fy_data)
    
    # 価格データを確認
    print("\n【価格データ（2025-12-19）】")
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
    
    # 分割情報を確認（2025-03-31から2025-12-19まで）
    print("\n【分割情報（2025-03-31から2025-12-19まで）】")
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
    
    # 予想データを確認
    print("\n【予想データ】")
    fc_data = pd.read_sql_query(
        """
        WITH ranked AS (
          SELECT
            code, disclosed_date, forecast_profit,
            ROW_NUMBER() OVER (
              PARTITION BY code
              ORDER BY disclosed_date DESC
            ) AS rn
          FROM fins_statements
          WHERE disclosed_date <= ?
            AND type_of_current_period = 'FY'
            AND forecast_profit IS NOT NULL
        )
        SELECT code, disclosed_date, forecast_profit
        FROM ranked
        WHERE rn = 1
          AND code = ?
        """,
        conn,
        params=(asof, code),
    )
    print(fc_data)
    
    # features_monthlyから直接取得
    print("\n【features_monthlyから直接取得】")
    feat_data = pd.read_sql_query(
        """
        SELECT as_of_date, code, per, pbr, forward_per, market_cap
        FROM features_monthly
        WHERE code = ?
          AND as_of_date = ?
        """,
        conn,
        params=(code, asof),
    )
    print(feat_data)

"""コード7419のPBR計算の詳細をデバッグ"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    # features_monthlyのデータを確認
    features = pd.read_sql_query(
        """
        SELECT as_of_date, code, per, pbr, forward_per, market_cap, equity, profit
        FROM features_monthly
        WHERE code = ?
          AND as_of_date = ?
        """,
        conn,
        params=(code, price_date)
    )
    print("features_monthlyのデータ:")
    print(features)
    
    # 最新のFYデータを確認（_load_latest_fyと同じロジック）
    fy_latest = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, equity, profit, bvps, eps,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
               OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
          AND code = ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        """,
        conn,
        params=(price_date, code)
    )
    print("\n最新のFYデータ（_load_latest_fyと同じロジック）:")
    print(fy_latest.head(10))
    
    # 価格データを確認
    price_data = pd.read_sql_query(
        """
        SELECT date, adj_close
        FROM prices_daily
        WHERE code = ?
          AND date = ?
        """,
        conn,
        params=(code, price_date)
    )
    print("\n価格データ:")
    print(price_data)
    
    # 手動でPBRを計算
    if not features.empty and not price_data.empty and not fy_latest.empty:
        price = price_data.iloc[0]["adj_close"]
        equity = features.iloc[0]["equity"]
        market_cap = features.iloc[0]["market_cap"]
        pbr = features.iloc[0]["pbr"]
        
        print(f"\n手動計算:")
        print(f"  価格: {price:,.0f}円")
        print(f"  純資産: {equity:,.0f}円")
        print(f"  時価総額: {market_cap:,.0f}円")
        print(f"  PBR（時価総額 / 純資産）: {market_cap / equity:.6f}")
        print(f"  features_monthlyのPBR: {pbr:.6f}")

"""コード7419のPERとforward_perを確認"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    # features_monthlyのデータを確認
    features = pd.read_sql_query(
        """
        SELECT as_of_date, code, per, forward_per, market_cap
        FROM features_monthly
        WHERE code = ?
          AND as_of_date = ?
        """,
        conn,
        params=(code, price_date)
    )
    print("features_monthlyのデータ:")
    print(features)
    
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
    price = price_data.iloc[0]["adj_close"] if not price_data.empty else None
    print(f"\n価格: {price:,.0f}円")
    
    # 最新のFYデータを確認
    fy_latest = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, profit, eps, equity,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND (profit IS NOT NULL OR equity IS NOT NULL)
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 5
        """,
        conn,
        params=(code, price_date)
    )
    print("\n最新のFYデータ:")
    print(fy_latest)
    
    # 最新の予想データを確認
    forecast_latest = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, forecast_eps, forecast_profit
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND forecast_eps IS NOT NULL
        ORDER BY disclosed_date DESC, current_period_end DESC
        LIMIT 5
        """,
        conn,
        params=(code, price_date)
    )
    print("\n最新の予想データ:")
    print(forecast_latest)
    
    # 最新期の発行済み株式数を取得
    latest_shares = pd.read_sql_query(
        """
        SELECT shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND shares_outstanding IS NOT NULL
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date)
    )
    
    if not latest_shares.empty and price and not features.empty:
        shares_outstanding = latest_shares.iloc[0]["shares_outstanding"]
        treasury_shares = latest_shares.iloc[0].get("treasury_shares") or 0.0
        shares_net = shares_outstanding - treasury_shares
        
        market_cap = features.iloc[0]["market_cap"]
        per = features.iloc[0]["per"]
        forward_per = features.iloc[0]["forward_per"]
        
        print(f"\n手動計算:")
        print(f"  最新期の発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
        print(f"  時価総額: {market_cap:,.0f}円")
        print(f"  features_monthlyのPER: {per:.6f}")
        print(f"  features_monthlyのforward_per: {forward_per:.6f}")
        
        # PERを手動計算
        if not fy_latest.empty and pd.notna(fy_latest.iloc[0]["profit"]) and fy_latest.iloc[0]["profit"] > 0:
            profit = fy_latest.iloc[0]["profit"]
            per_calc = market_cap / profit
            print(f"\n  PER計算:")
            print(f"    利益: {profit:,.0f}円")
            print(f"    PER（時価総額 / 利益）: {per_calc:.6f}")
            print(f"    features_monthlyのPER: {per:.6f}")
            print(f"    差: {abs(per_calc - per):.6f}")
            
            # 従来の計算方法（価格 / EPS）と比較
            if pd.notna(fy_latest.iloc[0]["eps"]) and fy_latest.iloc[0]["eps"] > 0:
                eps = fy_latest.iloc[0]["eps"]
                per_old = price / eps
                print(f"    従来のPER（価格 / EPS）: {per_old:.6f}")
        
        # Forward PERを手動計算
        if not forecast_latest.empty and pd.notna(forecast_latest.iloc[0]["forecast_eps"]) and forecast_latest.iloc[0]["forecast_eps"] > 0:
            forecast_eps = forecast_latest.iloc[0]["forecast_eps"]
            forward_per_calc = market_cap / forecast_eps
            print(f"\n  Forward PER計算:")
            print(f"    予想EPS: {forecast_eps:.2f}円")
            print(f"    Forward PER（時価総額 / 予想EPS）: {forward_per_calc:.6f}")
            print(f"    features_monthlyのforward_per: {forward_per:.6f}")
            print(f"    差: {abs(forward_per_calc - forward_per):.6f}")
            
            # 従来の計算方法（価格 / 予想EPS）と比較
            forward_per_old = price / forecast_eps
            print(f"    従来のForward PER（価格 / 予想EPS）: {forward_per_old:.6f}")

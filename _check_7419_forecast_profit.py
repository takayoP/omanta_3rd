"""コード7419の予想利益からForward PERを計算"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    # features_monthlyのデータを確認
    features = pd.read_sql_query(
        """
        SELECT as_of_date, code, forward_per, market_cap
        FROM features_monthly
        WHERE code = ?
          AND as_of_date = ?
        """,
        conn,
        params=(code, price_date)
    )
    print("features_monthlyのデータ:")
    print(features)
    
    # 最新の予想データを確認
    forecast = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND forecast_profit IS NOT NULL
        ORDER BY disclosed_date DESC, current_period_end DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date)
    )
    
    if not forecast.empty and not features.empty:
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        forecast_eps = forecast.iloc[0]["forecast_eps"]
        market_cap = features.iloc[0]["market_cap"]
        forward_per = features.iloc[0]["forward_per"]
        
        print(f"\n予想利益: {forecast_profit:,.0f}円")
        print(f"予想EPS: {forecast_eps:.2f}円")
        print(f"時価総額: {market_cap:,.0f}円")
        
        # Forward PERを予想利益から直接計算
        forward_per_from_profit = market_cap / forecast_profit if forecast_profit > 0 else None
        print(f"\nForward PER（時価総額 / 予想利益）: {forward_per_from_profit:.6f}" if forward_per_from_profit else "計算不可")
        print(f"features_monthlyのforward_per: {forward_per:.6f}")
        
        if forward_per_from_profit:
            print(f"差: {abs(forward_per_from_profit - forward_per):.6f}")
        
        # 予想EPSから計算（比較用）
        forward_per_from_eps = market_cap / forecast_eps if forecast_eps > 0 else None
        print(f"\nForward PER（時価総額 / 予想EPS）: {forward_per_from_eps:.6f}" if forward_per_from_eps else "計算不可")

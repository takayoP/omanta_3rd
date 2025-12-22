"""コード7419の予想EPS調整の正しい方法を確認"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _calculate_cumulative_adjustment_factor
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    # 予想データを取得
    forecast = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, forecast_eps, forecast_profit,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND forecast_eps IS NOT NULL
        ORDER BY disclosed_date DESC, current_period_end DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date)
    )
    
    if not forecast.empty:
        forecast_eps = forecast.iloc[0]["forecast_eps"]
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        forecast_period_end = forecast.iloc[0]["current_period_end"]
        shares_outstanding = forecast.iloc[0].get("shares_outstanding")
        treasury_shares = forecast.iloc[0].get("treasury_shares") or 0.0
        
        print(f"コード: {code}")
        print(f"予想EPS（データベース）: {forecast_eps:.2f}円")
        print(f"予想利益: {forecast_profit:,.0f}円")
        print(f"予想EPSの期末日: {forecast_period_end}")
        
        if pd.notna(shares_outstanding):
            shares_net = shares_outstanding - treasury_shares
            print(f"発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
            
            # 予想EPSを逆算
            implied_eps = forecast_profit / shares_net
            print(f"予想EPS（逆算）: {implied_eps:.2f}円")
            print(f"比率: {implied_eps / forecast_eps:.6f}")
            print(f"→ 予想EPSは分割前の基準で計算されている可能性が高い（比率 ≈ 3.0）")
        
        # 調整係数の履歴を確認
        adj_history = pd.read_sql_query(
            """
            SELECT date, adjustment_factor
            FROM prices_daily
            WHERE code = ?
              AND date > ?
              AND adjustment_factor IS NOT NULL
              AND adjustment_factor != 1.0
            ORDER BY date ASC
            """,
            conn,
            params=(code, forecast_period_end)
        )
        
        print(f"\n{forecast_period_end}より後の調整係数:")
        print(adj_history)
        
        # CAFを計算
        caf = 1.0
        for _, row in adj_history.iterrows():
            caf *= row["adjustment_factor"]
        print(f"累積調整係数（CAF）: {caf:.6f}")
        
        # 価格を取得（調整後終値）
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
        if not price_data.empty:
            price_adj = price_data.iloc[0]["adj_close"]  # 調整後終値
            
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
            
            if not latest_shares.empty:
                latest_shares_outstanding = latest_shares.iloc[0]["shares_outstanding"]
                latest_treasury_shares = latest_shares.iloc[0].get("treasury_shares") or 0.0
                latest_shares_net = latest_shares_outstanding - latest_treasury_shares
                
                # 評価日より後のCAFを計算
                caf_price_date = _calculate_cumulative_adjustment_factor(conn, code, price_date)
                
                # 調整後株価の基準に合わせた株数
                shares_adjunit = latest_shares_net / caf_price_date if pd.notna(caf_price_date) and caf_price_date > 0 else latest_shares_net
                
                # 時価総額（調整後株価ベース）
                market_cap_adj = price_adj * shares_adjunit
                
                print(f"\n価格（調整後終値）: {price_adj:,.0f}円")
                print(f"最新期の発行済み株式数（自己株式除く）: {latest_shares_net:,.0f}株")
                print(f"評価日より後のCAF: {caf_price_date:.6f}")
                print(f"調整後株価の基準に合わせた株数: {shares_adjunit:,.0f}株")
                print(f"時価総額（調整後株価ベース）: {market_cap_adj:,.0f}円")
                
                # 予想EPSを調整後株価の基準に合わせる
                # 予想EPSは分割前の基準で計算されているので、CAFで割って分割後の基準に調整
                adjusted_forecast_eps = forecast_eps / caf if caf != 1.0 else forecast_eps
                print(f"\n予想EPS（調整後、CAFで割る）: {adjusted_forecast_eps:.2f}円")
                
                # Forward PERを計算
                forward_per_calc = market_cap_adj / adjusted_forecast_eps
                print(f"Forward PER（時価総額 / 調整後予想EPS）: {forward_per_calc:.6f}")
                
                # 従来の計算方法
                forward_per_old = price_adj / forecast_eps
                print(f"従来のForward PER（価格 / 予想EPS）: {forward_per_old:.6f}")
                print(f"差: {abs(forward_per_calc - forward_per_old):.6f}")
                
                # features_monthlyの値と比較
                features = pd.read_sql_query(
                    """
                    SELECT forward_per, market_cap
                    FROM features_monthly
                    WHERE code = ?
                      AND as_of_date = ?
                    """,
                    conn,
                    params=(code, price_date)
                )
                if not features.empty:
                    forward_per_db = features.iloc[0]["forward_per"]
                    market_cap_db = features.iloc[0]["market_cap"]
                    print(f"\nfeatures_monthlyのforward_per: {forward_per_db:.6f}")
                    print(f"features_monthlyのmarket_cap: {market_cap_db:,.0f}円")
                    print(f"差: {abs(forward_per_calc - forward_per_db):.6f}")

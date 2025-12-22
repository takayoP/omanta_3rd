"""コード7419の期待値から逆算"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    # 期待値
    expected_forward_per = 8.95
    expected_per = 7.9
    expected_pbr = 1.52
    
    print(f"コード: {code}")
    print(f"評価日: {price_date}\n")
    print(f"期待値:")
    print(f"  Forward PER: {expected_forward_per}")
    print(f"  PER: {expected_per}")
    print(f"  PBR: {expected_pbr}\n")
    
    # 最新のFYデータを取得
    fy_latest = pd.read_sql_query(
        """
        SELECT profit, equity, eps, bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND profit IS NOT NULL
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date)
    )
    
    # 最新の予想データを取得
    forecast = pd.read_sql_query(
        """
        SELECT forecast_profit, forecast_eps
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
    
    if not fy_latest.empty and not forecast.empty:
        profit = fy_latest.iloc[0]["profit"]
        equity = fy_latest.iloc[0]["equity"]
        eps = fy_latest.iloc[0].get("eps")
        bvps = fy_latest.iloc[0].get("bvps")
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        forecast_eps = forecast.iloc[0].get("forecast_eps")
        
        print(f"財務データ:")
        print(f"  利益: {profit:,.0f}円")
        print(f"  純資産: {equity:,.0f}円")
        print(f"  EPS: {eps:.2f}円" if pd.notna(eps) else "  EPS: N/A")
        print(f"  BPS: {bvps:.2f}円" if pd.notna(bvps) else "  BPS: N/A")
        print(f"  予想利益: {forecast_profit:,.0f}円")
        print(f"  予想EPS: {forecast_eps:.2f}円" if pd.notna(forecast_eps) else "  予想EPS: N/A")
        
        # 期待値から逆算した時価総額
        market_cap_from_forward_per = expected_forward_per * forecast_profit
        market_cap_from_per = expected_per * profit
        market_cap_from_pbr = expected_pbr * equity
        
        print(f"\n期待値から逆算した時価総額:")
        print(f"  Forward PER基準: {market_cap_from_forward_per:,.0f}円")
        print(f"  PER基準: {market_cap_from_per:,.0f}円")
        print(f"  PBR基準: {market_cap_from_pbr:,.0f}円")
        
        # 価格データを取得
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
            adj_close = price_data.iloc[0]["adj_close"]
            print(f"\n価格（調整後終値）: {adj_close:,.0f}円")
            
            # 期待値から逆算した発行済み株式数
            shares_from_forward_per = market_cap_from_forward_per / adj_close
            shares_from_per = market_cap_from_per / adj_close
            shares_from_pbr = market_cap_from_pbr / adj_close
            
            print(f"\n期待値から逆算した発行済み株式数:")
            print(f"  Forward PER基準: {shares_from_forward_per:,.0f}株")
            print(f"  PER基準: {shares_from_per:,.0f}株")
            print(f"  PBR基準: {shares_from_pbr:,.0f}株")
            
            # 実際の発行済み株式数を取得
            shares_actual = pd.read_sql_query(
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
            
            if not shares_actual.empty:
                shares_outstanding = shares_actual.iloc[0]["shares_outstanding"]
                treasury_shares = shares_actual.iloc[0].get("treasury_shares") or 0.0
                shares_net = shares_outstanding - treasury_shares
                
                print(f"\n実際の発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
                print(f"\n比率:")
                print(f"  Forward PER基準 / 実際: {shares_from_forward_per / shares_net:.6f}")
                print(f"  PER基準 / 実際: {shares_from_per / shares_net:.6f}")
                print(f"  PBR基準 / 実際: {shares_from_pbr / shares_net:.6f}")
                
                # 従来の計算方法（価格 / EPS）
                if pd.notna(eps) and eps > 0:
                    per_old = adj_close / eps
                    print(f"\n従来のPER（価格 / EPS）: {per_old:.6f}")
                
                if pd.notna(forecast_eps) and forecast_eps > 0:
                    forward_per_old = adj_close / forecast_eps
                    print(f"従来のForward PER（価格 / 予想EPS）: {forward_per_old:.6f}")
                
                if pd.notna(bvps) and bvps > 0:
                    pbr_old = adj_close / bvps
                    print(f"従来のPBR（価格 / BPS）: {pbr_old:.6f}")

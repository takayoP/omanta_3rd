"""コード7419のシンプルな計算方法を検証"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    print(f"コード: {code}")
    print(f"評価日: {price_date}\n")
    
    # 期待値
    expected_forward_per = 8.95
    expected_per = 7.9
    expected_pbr = 1.52
    
    # 1. 価格データを取得（調整後終値）
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
        print(f"1. 調整後終値: {adj_close:,.0f}円")
    
    # 2. 最新のFYデータを取得
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
    
    # 3. 最新の予想データを取得
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
        
        print(f"2. 最新FYデータ:")
        print(f"   利益: {profit:,.0f}円")
        print(f"   純資産: {equity:,.0f}円")
        print(f"   EPS: {eps:.2f}円" if pd.notna(eps) else "   EPS: N/A")
        print(f"   BPS: {bvps:.2f}円" if pd.notna(bvps) else "   BPS: N/A")
        print(f"   予想利益: {forecast_profit:,.0f}円")
        print(f"   予想EPS: {forecast_eps:.2f}円" if pd.notna(forecast_eps) else "   予想EPS: N/A")
        
        # 3. 従来の計算方法（価格 / EPS）
        if pd.notna(eps) and eps > 0:
            per_simple = adj_close / eps
            print(f"\n3. PER（価格 / EPS）: {per_simple:.6f}")
            print(f"   期待値: {expected_per}")
            print(f"   差: {abs(per_simple - expected_per):.6f}")
        
        if pd.notna(bvps) and bvps > 0:
            pbr_simple = adj_close / bvps
            print(f"4. PBR（価格 / BPS）: {pbr_simple:.6f}")
            print(f"   期待値: {expected_pbr}")
            print(f"   差: {abs(pbr_simple - expected_pbr):.6f}")
        
        if pd.notna(forecast_eps) and forecast_eps > 0:
            forward_per_simple = adj_close / forecast_eps
            print(f"5. Forward PER（価格 / 予想EPS）: {forward_per_simple:.6f}")
            print(f"   期待値: {expected_forward_per}")
            print(f"   差: {abs(forward_per_simple - expected_forward_per):.6f}")
        
        # 6. 時価総額ベースで計算する場合
        # 最新期の発行済み株式数を取得
        shares_data = pd.read_sql_query(
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
        
        if not shares_data.empty:
            shares_outstanding = shares_data.iloc[0]["shares_outstanding"]
            treasury_shares = shares_data.iloc[0].get("treasury_shares") or 0.0
            shares_net = shares_outstanding - treasury_shares
            
            market_cap = adj_close * shares_net
            
            print(f"\n6. 時価総額ベースでの計算:")
            print(f"   発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
            print(f"   時価総額: {market_cap:,.0f}円")
            
            per_mcap = market_cap / profit if profit > 0 else None
            pbr_mcap = market_cap / equity if equity > 0 else None
            forward_per_mcap = market_cap / forecast_profit if forecast_profit > 0 else None
            
            print(f"   PER（時価総額 / 利益）: {per_mcap:.6f}" if per_mcap else "   PER: 計算不可")
            print(f"   PBR（時価総額 / 純資産）: {pbr_mcap:.6f}" if pbr_mcap else "   PBR: 計算不可")
            print(f"   Forward PER（時価総額 / 予想利益）: {forward_per_mcap:.6f}" if forward_per_mcap else "   Forward PER: 計算不可")

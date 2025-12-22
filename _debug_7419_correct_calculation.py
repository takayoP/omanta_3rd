"""コード7419の正しい計算方法を確認"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _calculate_cumulative_adjustment_factor, _get_shares_at_date
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    print(f"コード: {code}")
    print(f"評価日: {price_date}\n")
    
    # 1. 価格データを取得（調整後終値）
    price_data = pd.read_sql_query(
        """
        SELECT date, adj_close, adjustment_factor
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
    
    # 2. 最新期の発行済み株式数を取得
    shares_raw, equity = _get_shares_at_date(conn, code, price_date)
    print(f"2. 発行済み株式数（自己株式除く）: {shares_raw:,.0f}株")
    print(f"   純資産: {equity:,.0f}円")
    
    # 3. CAFを計算（評価日より後のAdjustmentFactorの累積積）
    caf = _calculate_cumulative_adjustment_factor(conn, code, price_date)
    print(f"3. 累積調整係数（CAF）: {caf:.6f}")
    
    # 4. 調整後株価の基準に合わせた株数
    shares_adjunit = shares_raw / caf if pd.notna(caf) and caf > 0 else shares_raw
    print(f"4. 調整後株価の基準に合わせた株数: {shares_adjunit:,.0f}株")
    
    # 5. 時価総額を計算
    market_cap = adj_close * shares_adjunit
    print(f"5. 時価総額: {market_cap:,.0f}円")
    
    # 6. 最新のFYデータを取得
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
    
    if not fy_latest.empty:
        profit = fy_latest.iloc[0]["profit"]
        equity_fy = fy_latest.iloc[0]["equity"]
        eps = fy_latest.iloc[0].get("eps")
        bvps = fy_latest.iloc[0].get("bvps")
        
        print(f"\n6. 最新FYデータ:")
        print(f"   利益: {profit:,.0f}円")
        print(f"   純資産: {equity_fy:,.0f}円")
        print(f"   EPS: {eps:.2f}円" if pd.notna(eps) else "   EPS: N/A")
        print(f"   BPS: {bvps:.2f}円" if pd.notna(bvps) else "   BPS: N/A")
        
        # 7. PERを計算
        per = market_cap / profit if profit > 0 else None
        print(f"\n7. PER（時価総額 / 利益）: {per:.6f}" if per else "   PER: 計算不可")
        
        # 8. PBRを計算
        pbr = market_cap / equity_fy if equity_fy > 0 else None
        print(f"8. PBR（時価総額 / 純資産）: {pbr:.6f}" if pbr else "   PBR: 計算不可")
        
        # 9. 従来の計算方法と比較
        if pd.notna(eps) and eps > 0:
            per_old = adj_close / eps
            print(f"\n9. 従来のPER（価格 / EPS）: {per_old:.6f}")
        
        if pd.notna(bvps) and bvps > 0:
            pbr_old = adj_close / bvps
            print(f"10. 従来のPBR（価格 / BPS）: {pbr_old:.6f}")
    
    # 11. 最新の予想データを取得
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
    
    if not forecast.empty:
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        forecast_eps = forecast.iloc[0].get("forecast_eps")
        
        print(f"\n11. 最新予想データ:")
        print(f"    予想利益: {forecast_profit:,.0f}円")
        print(f"    予想EPS: {forecast_eps:.2f}円" if pd.notna(forecast_eps) else "    予想EPS: N/A")
        
        # 12. Forward PERを計算
        forward_per = market_cap / forecast_profit if forecast_profit > 0 else None
        print(f"\n12. Forward PER（時価総額 / 予想利益）: {forward_per:.6f}" if forward_per else "    Forward PER: 計算不可")
        
        # 13. 従来の計算方法と比較
        if pd.notna(forecast_eps) and forecast_eps > 0:
            forward_per_old = adj_close / forecast_eps
            print(f"13. 従来のForward PER（価格 / 予想EPS）: {forward_per_old:.6f}")
    
    # 14. 期待値との比較
    print(f"\n14. 期待値との比較:")
    print(f"    期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
    if forward_per:
        print(f"    計算値: Forward PER={forward_per:.2f}, PER={per:.2f}, PBR={pbr:.2f}")
        print(f"    差: Forward PER={abs(forward_per - 8.95):.2f}, PER={abs(per - 7.9):.2f}, PBR={abs(pbr - 1.52):.2f}")

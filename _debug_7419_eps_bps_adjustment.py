"""コード7419のEPS/BPS調整を検証"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _calculate_cumulative_adjustment_factor
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
    
    # 1. 価格データを取得
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
        SELECT current_period_end, profit, equity, eps, bvps
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
        SELECT current_period_end, forecast_profit, forecast_eps
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
        period_end = fy_latest.iloc[0]["current_period_end"]
        profit = fy_latest.iloc[0]["profit"]
        equity = fy_latest.iloc[0]["equity"]
        eps = fy_latest.iloc[0].get("eps")
        bvps = fy_latest.iloc[0].get("bvps")
        forecast_period_end = forecast.iloc[0]["current_period_end"]
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        forecast_eps = forecast.iloc[0].get("forecast_eps")
        
        print(f"2. 財務データの期末日: {period_end}")
        print(f"   EPS: {eps:.2f}円")
        print(f"   BPS: {bvps:.2f}円")
        print(f"   予想データの期末日: {forecast_period_end}")
        print(f"   予想EPS: {forecast_eps:.2f}円")
        
        # 3. 財務データの期末日より後のCAFを計算
        caf_period = _calculate_cumulative_adjustment_factor(conn, code, period_end)
        caf_forecast = _calculate_cumulative_adjustment_factor(conn, code, forecast_period_end)
        
        print(f"\n3. 累積調整係数（CAF）:")
        print(f"   財務データの期末日（{period_end}）より後: {caf_period:.6f}")
        print(f"   予想データの期末日（{forecast_period_end}）より後: {caf_forecast:.6f}")
        
        # 4. EPS/BPSを分割前の基準に調整
        # 財務データの期末日より後に分割が発生している場合、
        # EPS/BPSは分割後の基準で計算されている可能性がある
        # 分割前の基準に戻すには、CAFで割る必要がある
        eps_before = eps / caf_period if pd.notna(eps) and pd.notna(caf_period) and caf_period > 0 and caf_period != 1.0 else eps
        bvps_before = bvps / caf_period if pd.notna(bvps) and pd.notna(caf_period) and caf_period > 0 and caf_period != 1.0 else bvps
        forecast_eps_before = forecast_eps / caf_forecast if pd.notna(forecast_eps) and pd.notna(caf_forecast) and caf_forecast > 0 and caf_forecast != 1.0 else forecast_eps
        
        print(f"\n4. EPS/BPS（分割前の基準）:")
        print(f"   EPS: {eps_before:.2f}円" if pd.notna(eps_before) else "   EPS: N/A")
        print(f"   BPS: {bvps_before:.2f}円" if pd.notna(bvps_before) else "   BPS: N/A")
        print(f"   予想EPS: {forecast_eps_before:.2f}円" if pd.notna(forecast_eps_before) else "   予想EPS: N/A")
        
        # 5. PER/PBR/Forward PERを計算（分割前の基準）
        per = adj_close / eps_before if pd.notna(eps_before) and eps_before > 0 else None
        pbr = adj_close / bvps_before if pd.notna(bvps_before) and bvps_before > 0 else None
        forward_per = adj_close / forecast_eps_before if pd.notna(forecast_eps_before) and forecast_eps_before > 0 else None
        
        print(f"\n5. PER/PBR/Forward PER（分割前の基準）:")
        print(f"   PER: {per:.6f}" if per else "   PER: 計算不可")
        print(f"   PBR: {pbr:.6f}" if pbr else "   PBR: 計算不可")
        print(f"   Forward PER: {forward_per:.6f}" if forward_per else "   Forward PER: 計算不可")
        
        print(f"\n6. 期待値との比較:")
        print(f"   期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
        if forward_per and per and pbr:
            print(f"   計算値: Forward PER={forward_per:.2f}, PER={per:.2f}, PBR={pbr:.2f}")
            print(f"   差: Forward PER={abs(forward_per - expected_forward_per):.2f}, PER={abs(per - expected_per):.2f}, PBR={abs(pbr - expected_pbr):.2f}")

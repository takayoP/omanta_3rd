"""コード7419の正しい計算方法を検証"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _calculate_cumulative_adjustment_factor, _get_shares_at_date
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
    
    # 3. 財務データの期末日を取得
    fy_data = pd.read_sql_query(
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
    
    forecast_data = pd.read_sql_query(
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
    
    if not fy_data.empty and not forecast_data.empty:
        period_end = fy_data.iloc[0]["current_period_end"]
        profit = fy_data.iloc[0]["profit"]
        equity_fy = fy_data.iloc[0]["equity"]
        eps = fy_data.iloc[0].get("eps")
        bvps = fy_data.iloc[0].get("bvps")
        forecast_profit = forecast_data.iloc[0]["forecast_profit"]
        forecast_eps = forecast_data.iloc[0].get("forecast_eps")
        forecast_period_end = forecast_data.iloc[0]["current_period_end"]
        
        print(f"3. 財務データの期末日: {period_end}")
        print(f"   利益: {profit:,.0f}円")
        print(f"   純資産: {equity_fy:,.0f}円")
        print(f"   予想利益の期末日: {forecast_period_end}")
        print(f"   予想利益: {forecast_profit:,.0f}円")
        
        # 4. 財務データの期末日より後のCAFを計算
        caf_period = _calculate_cumulative_adjustment_factor(conn, code, period_end)
        caf_forecast = _calculate_cumulative_adjustment_factor(conn, code, forecast_period_end)
        
        print(f"\n4. 累積調整係数（CAF）:")
        print(f"   財務データの期末日（{period_end}）より後: {caf_period:.6f}")
        print(f"   予想データの期末日（{forecast_period_end}）より後: {caf_forecast:.6f}")
        
        # 5. 分割前の基準での発行済み株式数を計算
        # 財務データの期末日より後に分割が発生している場合、
        # その時点の発行済み株式数は分割前の基準で計算されている
        shares_before_split_period = shares_raw / caf_period if pd.notna(caf_period) and caf_period > 0 else shares_raw
        shares_before_split_forecast = shares_raw / caf_forecast if pd.notna(caf_forecast) and caf_forecast > 0 else shares_raw
        
        print(f"\n5. 分割前の基準での発行済み株式数:")
        print(f"   財務データの期末日基準: {shares_before_split_period:,.0f}株")
        print(f"   予想データの期末日基準: {shares_before_split_forecast:,.0f}株")
        
        # 6. 分割前の基準での調整前終値を計算
        # 評価日より前のCAFを計算（評価日より前の分割を考慮）
        # 評価日より前のAdjustmentFactorの累積積
        adj_history_before = pd.read_sql_query(
            """
            SELECT date, adjustment_factor
            FROM prices_daily
            WHERE code = ?
              AND date <= ?
              AND adjustment_factor IS NOT NULL
              AND adjustment_factor != 1.0
            ORDER BY date DESC
            """,
            conn,
            params=(code, price_date)
        )
        
        caf_before = 1.0
        for _, row in adj_history_before.iterrows():
            caf_before *= row["adjustment_factor"]
        
        print(f"\n6. 評価日より前のCAF: {caf_before:.6f}")
        
        # 分割前の基準での調整前終値
        close_before = adj_close / caf_before if pd.notna(caf_before) and caf_before > 0 else adj_close
        print(f"   分割前の基準での調整前終値: {close_before:,.0f}円")
        
        # 7. 時価総額を計算（分割前の基準）
        market_cap_before_period = close_before * shares_before_split_period
        market_cap_before_forecast = close_before * shares_before_split_forecast
        
        print(f"\n7. 時価総額（分割前の基準）:")
        print(f"   財務データの期末日基準: {market_cap_before_period:,.0f}円")
        print(f"   予想データの期末日基準: {market_cap_before_forecast:,.0f}円")
        
        # 8. PER/PBR/Forward PERを計算
        per = market_cap_before_period / profit if profit > 0 else None
        pbr = market_cap_before_period / equity_fy if equity_fy > 0 else None
        forward_per = market_cap_before_forecast / forecast_profit if forecast_profit > 0 else None
        
        print(f"\n8. PER/PBR/Forward PER（分割前の基準）:")
        print(f"   PER: {per:.6f}" if per else "   PER: 計算不可")
        print(f"   PBR: {pbr:.6f}" if pbr else "   PBR: 計算不可")
        print(f"   Forward PER: {forward_per:.6f}" if forward_per else "   Forward PER: 計算不可")
        
        print(f"\n9. 期待値との比較:")
        print(f"   期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
        if forward_per and per and pbr:
            print(f"   計算値: Forward PER={forward_per:.2f}, PER={per:.2f}, PBR={pbr:.2f}")
            print(f"   差: Forward PER={abs(forward_per - expected_forward_per):.2f}, PER={abs(per - expected_per):.2f}, PBR={abs(pbr - expected_pbr):.2f}")

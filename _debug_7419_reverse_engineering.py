"""コード7419の期待値から逆算して正しい計算方法を特定"""
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
        profit = fy_latest.iloc[0]["profit"]
        equity = fy_latest.iloc[0]["equity"]
        eps = fy_latest.iloc[0].get("eps")
        bvps = fy_latest.iloc[0].get("bvps")
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        forecast_eps = forecast.iloc[0].get("forecast_eps")
        
        print(f"2. 財務データ:")
        print(f"   利益: {profit:,.0f}円")
        print(f"   純資産: {equity:,.0f}円")
        print(f"   EPS: {eps:.2f}円" if pd.notna(eps) else "   EPS: N/A")
        print(f"   BPS: {bvps:.2f}円" if pd.notna(bvps) else "   BPS: N/A")
        print(f"   予想利益: {forecast_profit:,.0f}円")
        print(f"   予想EPS: {forecast_eps:.2f}円" if pd.notna(forecast_eps) else "   予想EPS: N/A")
        
        # 4. 期待値から逆算したEPS/BPS
        eps_expected = adj_close / expected_per if expected_per > 0 else None
        bps_expected = adj_close / expected_pbr if expected_pbr > 0 else None
        forecast_eps_expected = adj_close / expected_forward_per if expected_forward_per > 0 else None
        
        print(f"\n3. 期待値から逆算したEPS/BPS:")
        print(f"   EPS: {eps_expected:.2f}円" if eps_expected else "   EPS: 計算不可")
        print(f"   BPS: {bps_expected:.2f}円" if bps_expected else "   BPS: 計算不可")
        print(f"   予想EPS: {forecast_eps_expected:.2f}円" if forecast_eps_expected else "   予想EPS: 計算不可")
        
        # 5. 実際のEPS/BPSとの比較
        if pd.notna(eps) and eps_expected:
            ratio_eps = eps / eps_expected
            print(f"\n4. 実際のEPS / 期待値から逆算したEPS: {ratio_eps:.6f}")
        
        if pd.notna(bvps) and bps_expected:
            ratio_bps = bvps / bps_expected
            print(f"   実際のBPS / 期待値から逆算したBPS: {ratio_bps:.6f}")
        
        if pd.notna(forecast_eps) and forecast_eps_expected:
            ratio_forecast_eps = forecast_eps / forecast_eps_expected
            print(f"   実際の予想EPS / 期待値から逆算した予想EPS: {ratio_forecast_eps:.6f}")
        
        # 6. 調整係数の履歴を確認
        adj_history = pd.read_sql_query(
            """
            SELECT date, adjustment_factor
            FROM prices_daily
            WHERE code = ?
              AND adjustment_factor IS NOT NULL
              AND adjustment_factor != 1.0
            ORDER BY date DESC
            """,
            conn,
            params=(code,)
        )
        
        print(f"\n5. 調整係数の履歴:")
        print(adj_history)
        
        # 7. 財務データの期末日を確認
        period_end = fy_latest.iloc[0]["current_period_end"]
        forecast_period_end = forecast.iloc[0]["current_period_end"]
        
        print(f"\n6. 財務データの期末日:")
        print(f"   実績: {period_end}")
        print(f"   予想: {forecast_period_end}")
        
        # 8. 分割が発生した日付を確認
        if not adj_history.empty:
            latest_split_date = adj_history.iloc[0]["date"]
            print(f"   最新の分割日: {latest_split_date}")
            
            if latest_split_date > period_end:
                print(f"   → 実績データの期末日より後に分割が発生")
            if latest_split_date > forecast_period_end:
                print(f"   → 予想データの期末日より後に分割が発生")

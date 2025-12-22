"""コード7419の最新株数ベース計算をデバッグ"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _calculate_cumulative_adjustment_factor, _get_shares_at_date, _get_latest_basis_shares
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    period_end = "2025-03-31"  # 最新の財務データの期末日
    
    print(f"コード: {code}")
    print(f"評価日: {price_date}")
    print(f"財務データ期末日: {period_end}\n")
    
    # 1. 指定日の実際の発行済み株式数を取得
    shares_actual, equity_actual = _get_shares_at_date(conn, code, period_end)
    print(f"1. 指定日({period_end})の実際の発行済み株式数: {shares_actual:,.0f}")
    print(f"   純資産: {equity_actual:,.0f}")
    
    # 2. 累積調整係数（CAF）を計算
    caf = _calculate_cumulative_adjustment_factor(conn, code, period_end)
    print(f"\n2. 累積調整係数（CAF）: {caf:.6f}")
    
    # 3. 最新株数ベースの発行済み株式数を計算
    shares_latest_basis = _get_latest_basis_shares(conn, code, period_end, price_date)
    print(f"\n3. 最新株数ベースの発行済み株式数: {shares_latest_basis:,.0f}")
    
    # 4. 最新期の実際の発行済み株式数を取得
    latest_shares_actual, latest_equity_actual = _get_shares_at_date(conn, code, price_date)
    print(f"\n4. 最新期({price_date})の実際の発行済み株式数: {latest_shares_actual:,.0f}")
    print(f"   純資産: {latest_equity_actual:,.0f}")
    
    # 5. 最新期のCAFを計算
    latest_caf = _calculate_cumulative_adjustment_factor(conn, code, price_date)
    print(f"\n5. 最新期の累積調整係数（CAF）: {latest_caf:.6f}")
    
    # 6. 価格データを取得
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
        price = price_data.iloc[0]["adj_close"]
        print(f"\n6. 最新価格: {price:,.0f}円")
        
        # 7. 時価総額を計算
        market_cap = price * shares_latest_basis
        print(f"\n7. 時価総額（最新株数ベース）: {market_cap:,.0f}円")
        
        # 8. PBRを計算
        if pd.notna(equity_actual) and equity_actual > 0:
            pbr = market_cap / equity_actual
            print(f"\n8. PBR（時価総額 / 純資産）: {pbr:.6f}")
            
            # 従来の計算方法（価格 / BPS）と比較
            fins_data = pd.read_sql_query(
                """
                SELECT bvps
                FROM fins_statements
                WHERE code = ?
                  AND type_of_current_period = 'FY'
                  AND current_period_end = ?
                ORDER BY disclosed_date DESC
                LIMIT 1
                """,
                conn,
                params=(code, period_end)
            )
            if not fins_data.empty and pd.notna(fins_data.iloc[0]["bvps"]):
                bvps = fins_data.iloc[0]["bvps"]
                pbr_old = price / bvps
                print(f"\n9. 従来のPBR（価格 / BPS）: {pbr_old:.6f}")
                print(f"   差: {abs(pbr - pbr_old):.6f}")
    
    # 10. adjustment_factorの履歴を確認
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
    print(f"\n10. 調整係数の履歴（1.0以外）:")
    print(adj_history)

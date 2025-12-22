"""コード7419の期待されるPBRを計算"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    period_end = "2025-03-31"  # 財務データの期末日
    
    # 価格を取得
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
    
    # 財務データを取得
    fins = pd.read_sql_query(
        """
        SELECT equity, shares_outstanding, treasury_shares, bvps
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
    
    if not fins.empty and price:
        equity = fins.iloc[0]["equity"]
        shares_outstanding = fins.iloc[0]["shares_outstanding"]
        treasury_shares = fins.iloc[0].get("treasury_shares") or 0.0
        shares_net = shares_outstanding - treasury_shares
        bvps = fins.iloc[0]["bvps"]
        
        print(f"コード: {code}")
        print(f"評価日: {price_date}")
        print(f"財務データ期末日: {period_end}")
        print(f"価格: {price:,.0f}円")
        print(f"純資産: {equity:,.0f}円")
        print(f"発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
        print(f"BPS: {bvps:.2f}円")
        
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
            params=(code, period_end)
        )
        
        print(f"\n{period_end}より後の調整係数:")
        print(adj_history)
        
        # CAFを計算
        caf = 1.0
        for _, row in adj_history.iterrows():
            caf *= row["adjustment_factor"]
        print(f"\n累積調整係数（CAF）: {caf:.6f}")
        
        # 最新期の株数を取得
        latest_fins = pd.read_sql_query(
            """
            SELECT shares_outstanding, treasury_shares
            FROM fins_statements
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND disclosed_date <= ?
            ORDER BY current_period_end DESC, disclosed_date DESC
            LIMIT 1
            """,
            conn,
            params=(code, price_date)
        )
        
        if not latest_fins.empty:
            latest_shares_outstanding = latest_fins.iloc[0]["shares_outstanding"]
            latest_treasury_shares = latest_fins.iloc[0].get("treasury_shares") or 0.0
            latest_shares_net = latest_shares_outstanding - latest_treasury_shares
            
            print(f"\n最新期の発行済み株式数（自己株式除く）: {latest_shares_net:,.0f}株")
            
            # 時価総額を計算（最新株数ベース）
            market_cap = price * latest_shares_net
            print(f"\n時価総額（最新株数ベース）: {market_cap:,.0f}円")
            
            # PBRを計算
            pbr = market_cap / equity
            print(f"PBR（時価総額 / 純資産）: {pbr:.6f}")
            
            # 従来の計算方法と比較
            pbr_old = price / bvps if pd.notna(bvps) and bvps > 0 else None
            if pbr_old:
                print(f"従来のPBR（価格 / BPS）: {pbr_old:.6f}")
                print(f"差: {abs(pbr - pbr_old):.6f}")

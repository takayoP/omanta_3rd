"""コード7419の計算ロジックを詳細にデバッグ"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    period_end = "2025-03-31"
    
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
        SELECT disclosed_date, current_period_end, equity, profit, bvps, eps,
               shares_outstanding, treasury_shares
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
        
        print(f"コード: {code}")
        print(f"評価日: {price_date}")
        print(f"財務データ期末日: {period_end}")
        print(f"価格: {price:,.0f}円")
        print(f"純資産: {equity:,.0f}円")
        print(f"発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
        
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
        
        # 最新株数ベースの発行済み株式数を計算
        shares_adjusted = shares_net / caf
        print(f"調整後株数（分割/併合の影響を除去）: {shares_adjusted:,.0f}株")
        
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
            
            # 最新期のCAFを計算
            latest_adj_history = pd.read_sql_query(
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
                params=(code, price_date)
            )
            
            latest_caf = 1.0
            for _, row in latest_adj_history.iterrows():
                latest_caf *= row["adjustment_factor"]
            print(f"最新期の累積調整係数（CAF）: {latest_caf:.6f}")
            
            latest_shares_adjusted = latest_shares_net / latest_caf
            print(f"最新期の調整後株数: {latest_shares_adjusted:,.0f}株")
            
            # 新規発行の影響を考慮
            if latest_shares_adjusted > 0:
                new_issue_ratio = latest_shares_adjusted / shares_adjusted
                print(f"\n新規発行による増加率: {new_issue_ratio:.6f}")
                
                shares_latest_basis = shares_adjusted * new_issue_ratio
                print(f"最新株数ベースの発行済み株式数: {shares_latest_basis:,.0f}株")
                
                # 時価総額とPBRを計算
                market_cap = price * shares_latest_basis
                pbr = market_cap / equity
                
                print(f"\n時価総額: {market_cap:,.0f}円")
                print(f"PBR: {pbr:.6f}")
                
                # 従来の計算方法と比較
                pbr_old = price / fins.iloc[0]["bvps"] if pd.notna(fins.iloc[0]["bvps"]) else None
                if pbr_old:
                    print(f"従来のPBR（価格 / BPS）: {pbr_old:.6f}")

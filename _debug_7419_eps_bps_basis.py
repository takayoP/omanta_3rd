"""コード7419のEPS/BPSの基準を確認"""
from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    print(f"コード: {code}")
    print(f"評価日: {price_date}\n")
    
    # 1. 最新のFYデータを取得
    fy_latest = pd.read_sql_query(
        """
        SELECT current_period_end, profit, equity, eps, bvps,
               shares_outstanding, treasury_shares
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
        period_end = fy_latest.iloc[0]["current_period_end"]
        profit = fy_latest.iloc[0]["profit"]
        equity = fy_latest.iloc[0]["equity"]
        eps = fy_latest.iloc[0].get("eps")
        bvps = fy_latest.iloc[0].get("bvps")
        shares_outstanding = fy_latest.iloc[0].get("shares_outstanding")
        treasury_shares = fy_latest.iloc[0].get("treasury_shares") or 0.0
        
        shares_net = shares_outstanding - treasury_shares
        
        print(f"1. 財務データの期末日: {period_end}")
        print(f"   利益: {profit:,.0f}円")
        print(f"   純資産: {equity:,.0f}円")
        print(f"   発行済み株式数（自己株式除く）: {shares_net:,.0f}株")
        print(f"   EPS: {eps:.2f}円" if pd.notna(eps) else "   EPS: N/A")
        print(f"   BPS: {bvps:.2f}円" if pd.notna(bvps) else "   BPS: N/A")
        
        # 2. EPS/BPSを逆算
        if pd.notna(shares_net) and shares_net > 0:
            eps_calc = profit / shares_net
            bps_calc = equity / shares_net
            
            print(f"\n2. EPS/BPS（逆算）:")
            print(f"   EPS = 利益 / 発行済み株式数 = {eps_calc:.2f}円")
            print(f"   BPS = 純資産 / 発行済み株式数 = {bps_calc:.2f}円")
            
            if pd.notna(eps):
                print(f"   実際のEPS: {eps:.2f}円")
                print(f"   差: {abs(eps - eps_calc):.2f}円")
                print(f"   比率: {eps / eps_calc:.6f}" if eps_calc > 0 else "   比率: 計算不可")
            
            if pd.notna(bvps):
                print(f"   実際のBPS: {bvps:.2f}円")
                print(f"   差: {abs(bvps - bps_calc):.2f}円")
                print(f"   比率: {bvps / bps_calc:.6f}" if bps_calc > 0 else "   比率: 計算不可")
        
        # 3. 調整係数の履歴を確認
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
        
        print(f"\n3. {period_end}より後の調整係数:")
        print(adj_history)
        
        if not adj_history.empty:
            # 4. 分割前の発行済み株式数を推定
            caf = 1.0
            for _, row in adj_history.iterrows():
                caf *= row["adjustment_factor"]
            
            shares_before_split = shares_net / caf if caf > 0 else shares_net
            
            print(f"\n4. 分割前の発行済み株式数（推定）: {shares_before_split:,.0f}株")
            print(f"   CAF: {caf:.6f}")
            
            # 5. 分割前の基準でのEPS/BPSを計算
            eps_before = profit / shares_before_split if shares_before_split > 0 else None
            bps_before = equity / shares_before_split if shares_before_split > 0 else None
            
            print(f"\n5. EPS/BPS（分割前の基準、計算）:")
            print(f"   EPS: {eps_before:.2f}円" if eps_before else "   EPS: 計算不可")
            print(f"   BPS: {bps_before:.2f}円" if bps_before else "   BPS: 計算不可")
            
            # 6. 期待値から逆算したEPS/BPS
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
                expected_per = 7.9
                expected_pbr = 1.52
                
                eps_expected = adj_close / expected_per if expected_per > 0 else None
                bps_expected = adj_close / expected_pbr if expected_pbr > 0 else None
                
                print(f"\n6. 期待値から逆算したEPS/BPS:")
                print(f"   EPS: {eps_expected:.2f}円" if eps_expected else "   EPS: 計算不可")
                print(f"   BPS: {bps_expected:.2f}円" if bps_expected else "   BPS: 計算不可")
                
                if eps_before and eps_expected:
                    print(f"   分割前EPS / 期待値EPS: {eps_before / eps_expected:.6f}")
                if bps_before and bps_expected:
                    print(f"   分割前BPS / 期待値BPS: {bps_before / bps_expected:.6f}")

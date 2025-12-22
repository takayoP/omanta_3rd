"""コード7419の最終的な計算を確認"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _get_shares_at_date, _calculate_cumulative_adjustment_factor
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
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
    
    # 最新期の実際の発行済み株式数を取得
    latest_shares_actual, latest_equity = _get_shares_at_date(conn, code, price_date)
    
    # 最新期のCAFを計算
    latest_caf = _calculate_cumulative_adjustment_factor(conn, code, price_date)
    
    # 最新株数ベースの発行済み株式数を計算
    shares_latest_basis = latest_shares_actual / latest_caf if pd.notna(latest_shares_actual) and pd.notna(latest_caf) and latest_caf > 0 else None
    
    # 財務データの純資産を取得（最新のFY）
    fins = pd.read_sql_query(
        """
        SELECT equity
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND equity IS NOT NULL
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date)
    )
    equity = fins.iloc[0]["equity"] if not fins.empty else None
    
    print(f"コード: {code}")
    print(f"評価日: {price_date}")
    print(f"価格: {price:,.0f}円")
    print(f"最新期の実際の発行済み株式数: {latest_shares_actual:,.0f}株")
    print(f"最新期のCAF: {latest_caf:.6f}")
    print(f"最新株数ベースの発行済み株式数: {shares_latest_basis:,.0f}株")
    print(f"純資産: {equity:,.0f}円")
    
    if price and shares_latest_basis and equity:
        market_cap = price * shares_latest_basis
        pbr = market_cap / equity
        
        print(f"\n時価総額: {market_cap:,.0f}円")
        print(f"PBR: {pbr:.6f}")
        
        # features_monthlyのPBRと比較
        features = pd.read_sql_query(
            """
            SELECT pbr, market_cap
            FROM features_monthly
            WHERE code = ?
              AND as_of_date = ?
            """,
            conn,
            params=(code, price_date)
        )
        if not features.empty:
            print(f"\nfeatures_monthlyのPBR: {features.iloc[0]['pbr']:.6f}")
            print(f"features_monthlyの時価総額: {features.iloc[0]['market_cap']:,.0f}円")
            print(f"差: {abs(pbr - features.iloc[0]['pbr']):.6f}")

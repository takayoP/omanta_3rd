"""コード7419の予想EPS調整をデバッグ"""
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _get_shares_at_date, _calculate_cumulative_adjustment_factor, _get_shares_adjustment_factor
import pandas as pd

with connect_db() as conn:
    code = "7419"
    price_date = "2025-12-19"
    
    # 最新の予想データを取得
    forecast_latest = pd.read_sql_query(
        """
        SELECT disclosed_date, current_period_end, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND forecast_eps IS NOT NULL
        ORDER BY disclosed_date DESC, current_period_end DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date)
    )
    
    if not forecast_latest.empty:
        forecast_eps = forecast_latest.iloc[0]["forecast_eps"]
        forecast_period_end = forecast_latest.iloc[0]["current_period_end"]
        
        print(f"コード: {code}")
        print(f"評価日: {price_date}")
        print(f"予想EPS（調整前）: {forecast_eps:.2f}円")
        print(f"予想EPSの期末日: {forecast_period_end}")
        
        # 最新期の発行済み株式数と純資産を取得
        latest_shares_data = pd.read_sql_query(
            """
            SELECT shares_outstanding, treasury_shares, equity
            FROM fins_statements
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND shares_outstanding IS NOT NULL
              AND disclosed_date <= ?
            ORDER BY current_period_end DESC, disclosed_date DESC
            LIMIT 1
            """,
            conn,
            params=(code, price_date)
        )
        
        if not latest_shares_data.empty:
            latest_shares_outstanding = latest_shares_data.iloc[0]["shares_outstanding"]
            latest_treasury_shares = latest_shares_data.iloc[0].get("treasury_shares") or 0.0
            latest_shares = latest_shares_outstanding - latest_treasury_shares
            latest_equity = latest_shares_data.iloc[0].get("equity")
            
            print(f"\n最新期の発行済み株式数（自己株式除く）: {latest_shares:,.0f}株")
            print(f"最新期の純資産: {latest_equity:,.0f}円")
            
            # 予想EPSの期末日を文字列に変換
            if hasattr(forecast_period_end, 'strftime'):
                period_end_str = forecast_period_end.strftime("%Y-%m-%d")
            else:
                period_end_str = str(forecast_period_end)
            
            # 調整係数を計算（旧方式）
            adjustment_factor = _get_shares_adjustment_factor(conn, code, period_end_str, latest_shares, latest_equity)
            print(f"\n調整係数（旧方式）: {adjustment_factor:.6f}")
            
            # 予想EPSを調整（旧方式）
            adjusted_forecast_eps_old = forecast_eps * adjustment_factor if adjustment_factor != 1.0 else forecast_eps
            print(f"予想EPS（調整後、旧方式）: {adjusted_forecast_eps_old:.2f}円")
            
            # 最新株数ベースで調整
            # 予想EPSの期末日より後の調整係数を取得
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
                params=(code, period_end_str)
            )
            
            print(f"\n{period_end_str}より後の調整係数:")
            print(adj_history)
            
            # CAFを計算
            caf = 1.0
            for _, row in adj_history.iterrows():
                caf *= row["adjustment_factor"]
            print(f"累積調整係数（CAF）: {caf:.6f}")
            
            # 予想EPSを最新株数ベースに調整
            # 予想EPSは予想EPSの期末日時点の基準で計算されているので、
            # その日より後の分割を考慮して調整する必要がある
            adjusted_forecast_eps = forecast_eps * caf if caf != 1.0 else forecast_eps
            print(f"\n予想EPS（調整後、CAF方式）: {adjusted_forecast_eps:.2f}円")
            
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
            if not price_data.empty:
                price = price_data.iloc[0]["adj_close"]
                
                # 最新期の発行済み株式数を取得
                latest_shares_actual, _ = _get_shares_at_date(conn, code, price_date)
                latest_caf = _calculate_cumulative_adjustment_factor(conn, code, price_date)
                shares_latest_basis = latest_shares_actual / latest_caf if pd.notna(latest_shares_actual) and pd.notna(latest_caf) and latest_caf > 0 else None
                
                if shares_latest_basis:
                    market_cap = price * shares_latest_basis
                    forward_per_correct = market_cap / adjusted_forecast_eps
                    
                    print(f"\n価格: {price:,.0f}円")
                    print(f"最新株数ベースの発行済み株式数: {shares_latest_basis:,.0f}株")
                    print(f"時価総額: {market_cap:,.0f}円")
                    print(f"Forward PER（正しい計算）: {forward_per_correct:.6f}")
                    
                    # 現在のfeatures_monthlyの値と比較
                    features = pd.read_sql_query(
                        """
                        SELECT forward_per
                        FROM features_monthly
                        WHERE code = ?
                          AND as_of_date = ?
                        """,
                        conn,
                        params=(code, price_date)
                    )
                    if not features.empty:
                        forward_per_current = features.iloc[0]["forward_per"]
                        print(f"features_monthlyのforward_per: {forward_per_current:.6f}")
                        print(f"差: {abs(forward_per_correct - forward_per_current):.6f}")

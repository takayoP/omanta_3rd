"""コード7419の計算ロジックを詳細に検証"""
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
    
    # 3. CAFを計算（評価日より後のAdjustmentFactorの累積積）
    caf = _calculate_cumulative_adjustment_factor(conn, code, price_date)
    print(f"3. 累積調整係数（CAF）: {caf:.6f}")
    
    # 4. 調整後株価の基準に合わせた株数（ChatGPTの方法）
    shares_adjunit = shares_raw / caf if pd.notna(caf) and caf > 0 else shares_raw
    print(f"4. 調整後株価の基準に合わせた株数（ChatGPT方式）: {shares_adjunit:,.0f}株")
    
    # 5. 時価総額を計算（ChatGPTの方法）
    market_cap_adj = adj_close * shares_adjunit
    print(f"5. 時価総額（ChatGPT方式）: {market_cap_adj:,.0f}円")
    
    # 6. 期待値から逆算した時価総額
    fy_latest = pd.read_sql_query(
        """
        SELECT profit, equity
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
    
    forecast = pd.read_sql_query(
        """
        SELECT forecast_profit
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
        equity_fy = fy_latest.iloc[0]["equity"]
        forecast_profit = forecast.iloc[0]["forecast_profit"]
        
        market_cap_expected_forward = expected_forward_per * forecast_profit
        market_cap_expected_per = expected_per * profit
        market_cap_expected_pbr = expected_pbr * equity_fy
        
        print(f"\n6. 期待値から逆算した時価総額:")
        print(f"   Forward PER基準: {market_cap_expected_forward:,.0f}円")
        print(f"   PER基準: {market_cap_expected_per:,.0f}円")
        print(f"   PBR基準: {market_cap_expected_pbr:,.0f}円")
        
        print(f"\n7. 時価総額の比較:")
        print(f"   ChatGPT方式: {market_cap_adj:,.0f}円")
        print(f"   期待値（Forward PER基準）: {market_cap_expected_forward:,.0f}円")
        print(f"   比率: {market_cap_expected_forward / market_cap_adj:.6f}")
        
        # 8. 期待値に合わせるために必要な株数
        shares_needed = market_cap_expected_forward / adj_close
        print(f"\n8. 期待値に合わせるために必要な株数: {shares_needed:,.0f}株")
        print(f"   実際の株数: {shares_raw:,.0f}株")
        print(f"   比率: {shares_needed / shares_raw:.6f}")
        
        # 9. 調整係数の履歴を確認
        adj_history = pd.read_sql_query(
            """
            SELECT date, adjustment_factor
            FROM prices_daily
            WHERE code = ?
              AND adjustment_factor IS NOT NULL
              AND adjustment_factor != 1.0
            ORDER BY date DESC
            LIMIT 10
            """,
            conn,
            params=(code,)
        )
        
        print(f"\n9. 調整係数の履歴:")
        print(adj_history)
        
        # 10. 分割前の発行済み株式数を推定
        if not adj_history.empty:
            # 最新の分割を確認
            latest_split = adj_history.iloc[0]
            split_date = latest_split["date"]
            split_factor = latest_split["adjustment_factor"]
            
            print(f"\n10. 最新の分割:")
            print(f"    日付: {split_date}")
            print(f"    調整係数: {split_factor:.6f}")
            print(f"    分割比率: 1:{1/split_factor:.0f}")
            
            # 分割前の発行済み株式数を推定
            shares_before_split = shares_raw / split_factor
            print(f"    分割前の発行済み株式数（推定）: {shares_before_split:,.0f}株")
            
            # 分割前の発行済み株式数で時価総額を計算
            # 調整前終値を使う必要があるが、現在は保存されていない
            # 調整後終値から調整前終値を逆算
            # AdjustmentClose = Close * CAF（過去の分割を考慮）
            # 評価日時点では、CAF = 1.0なので、AdjustmentClose = Close
            # しかし、分割前の基準で計算する場合は、調整前終値を使う必要がある
            
            # 分割前の基準で計算する場合
            # 時価総額 = 調整前終値 × 分割前の発行済み株式数
            # 調整前終値 = 調整後終値 / CAF（評価日より前の分割を考慮）
            
            # 評価日より前のCAFを計算
            caf_before = _calculate_cumulative_adjustment_factor(conn, code, split_date)
            print(f"    分割日より前のCAF: {caf_before:.6f}")
            
            # 分割前の基準での調整前終値
            close_before_split = adj_close / caf_before if pd.notna(caf_before) and caf_before > 0 else adj_close
            print(f"    分割前の基準での調整前終値（推定）: {close_before_split:,.0f}円")
            
            # 分割前の基準での時価総額
            market_cap_before_split = close_before_split * shares_before_split
            print(f"    分割前の基準での時価総額: {market_cap_before_split:,.0f}円")
            
            # 分割前の基準でのPER/PBR
            per_before = market_cap_before_split / profit if profit > 0 else None
            pbr_before = market_cap_before_split / equity_fy if equity_fy > 0 else None
            forward_per_before = market_cap_before_split / forecast_profit if forecast_profit > 0 else None
            
            print(f"\n11. 分割前の基準での計算:")
            print(f"    PER: {per_before:.6f}" if per_before else "    PER: 計算不可")
            print(f"    PBR: {pbr_before:.6f}" if pbr_before else "    PBR: 計算不可")
            print(f"    Forward PER: {forward_per_before:.6f}" if forward_per_before else "    Forward PER: 計算不可")

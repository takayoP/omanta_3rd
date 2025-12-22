"""
コード7419の計算を手動で確認
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import _split_multiplier_between
import pandas as pd
import numpy as np

code = "7419"
asof = "2025-12-19"

with connect_db() as conn:
    # 最新のFYデータを取得
    fy_data = pd.read_sql_query(
        """
        WITH ranked AS (
          SELECT
            code, current_period_end, disclosed_date,
            profit, equity, shares_outstanding, treasury_shares,
            ROW_NUMBER() OVER (
              PARTITION BY code
              ORDER BY current_period_end DESC, disclosed_date DESC
            ) AS rn
          FROM fins_statements
          WHERE disclosed_date <= ?
            AND type_of_current_period = 'FY'
            AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
                 OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
        )
        SELECT code, current_period_end, disclosed_date,
               profit, equity, shares_outstanding, treasury_shares
        FROM ranked
        WHERE rn = 1
          AND code = ?
        """,
        conn,
        params=(asof, code),
    )
    
    if fy_data.empty:
        print("FYデータが見つかりません")
    else:
        fy_row = fy_data.iloc[0]
        fy_end = fy_row['current_period_end']
        profit = fy_row['profit']
        equity = fy_row['equity']
        shares_outstanding = fy_row['shares_outstanding']
        treasury_shares = fy_row['treasury_shares']
        
        print(f"【FYデータ】")
        print(f"期末日: {fy_end}")
        print(f"利益: {profit:,.0f}円" if pd.notna(profit) else "利益: N/A")
        print(f"純資産: {equity:,.0f}円" if pd.notna(equity) else "純資産: N/A")
        print(f"発行済み株式数: {shares_outstanding:,.0f}株" if pd.notna(shares_outstanding) else "発行済み株式数: N/A")
        print(f"自己株式数: {treasury_shares:,.0f}株" if pd.notna(treasury_shares) else "自己株式数: N/A")
        
        # 価格データ
        price_data = pd.read_sql_query(
            """
            SELECT date, code, close, adj_close
            FROM prices_daily
            WHERE code = ?
              AND date = ?
            """,
            conn,
            params=(code, asof),
        )
        
        if price_data.empty:
            print("\n価格データが見つかりません")
        else:
            price_row = price_data.iloc[0]
            close = price_row['close']
            adj_close = price_row['adj_close']
            price = close if pd.notna(close) else adj_close
            
            print(f"\n【価格データ】")
            print(f"未調整終値 (close): {close}" if pd.notna(close) else "未調整終値 (close): NULL")
            print(f"調整後終値 (adj_close): {adj_close}")
            print(f"使用する価格: {price:.2f}円")
            
            # 分割倍率を計算
            if pd.notna(fy_end):
                if hasattr(fy_end, 'strftime'):
                    fy_end_str = fy_end.strftime("%Y-%m-%d")
                else:
                    fy_end_str = str(fy_end)
                
                print(f"\n【分割倍率の計算】")
                print(f"FY期末: {fy_end_str}")
                print(f"評価日: {asof}")
                
                split_mult = _split_multiplier_between(conn, code, fy_end_str, asof)
                print(f"分割倍率: {split_mult:.6f}")
                
                # 株数を計算
                if pd.notna(shares_outstanding):
                    treasury = treasury_shares if pd.notna(treasury_shares) else 0.0
                    shares_base = shares_outstanding - treasury
                    shares_at_price_date = shares_base * split_mult
                    
                    print(f"\n【株数の計算】")
                    print(f"FY期末株数 (shares_base): {shares_base:,.0f}株")
                    print(f"分割倍率 (split_mult): {split_mult:.6f}")
                    print(f"評価日時点の株数 (shares_at_price_date): {shares_at_price_date:,.0f}株")
                    
                    # 時価総額を計算
                    if pd.notna(price) and price > 0:
                        market_cap = price * shares_at_price_date
                        print(f"\n【時価総額の計算】")
                        print(f"価格: {price:.2f}円")
                        print(f"株数: {shares_at_price_date:,.0f}株")
                        print(f"時価総額: {market_cap:,.0f}円")
                        
                        # PER/PBRを計算
                        if pd.notna(profit) and profit > 0:
                            per = market_cap / profit
                            print(f"\n【PERの計算】")
                            print(f"時価総額: {market_cap:,.0f}円")
                            print(f"利益: {profit:,.0f}円")
                            print(f"PER: {per:.2f}")
                            print(f"期待値: 7.9")
                        
                        if pd.notna(equity) and equity > 0:
                            pbr = market_cap / equity
                            print(f"\n【PBRの計算】")
                            print(f"時価総額: {market_cap:,.0f}円")
                            print(f"純資産: {equity:,.0f}円")
                            print(f"PBR: {pbr:.2f}")
                            print(f"期待値: 1.52")
                        
                        # 予想データを確認
                        fc_data = pd.read_sql_query(
                            """
                            WITH ranked AS (
                              SELECT
                                code, disclosed_date, forecast_profit,
                                ROW_NUMBER() OVER (
                                  PARTITION BY code
                                  ORDER BY disclosed_date DESC
                                ) AS rn
                              FROM fins_statements
                              WHERE disclosed_date <= ?
                                AND type_of_current_period = 'FY'
                                AND forecast_profit IS NOT NULL
                            )
                            SELECT code, disclosed_date, forecast_profit
                            FROM ranked
                            WHERE rn = 1
                              AND code = ?
                            """,
                            conn,
                            params=(asof, code),
                        )
                        
                        if not fc_data.empty:
                            fc_row = fc_data.iloc[0]
                            forecast_profit = fc_row['forecast_profit']
                            if pd.notna(forecast_profit) and forecast_profit > 0:
                                forward_per = market_cap / forecast_profit
                                print(f"\n【Forward PERの計算】")
                                print(f"時価総額: {market_cap:,.0f}円")
                                print(f"予想利益: {forecast_profit:,.0f}円")
                                print(f"Forward PER: {forward_per:.2f}")
                                print(f"期待値: 8.95")
                        else:
                            print(f"\n【Forward PERの計算】")
                            print("予想データが見つかりません")
                            
                        print(f"\n【期待値との比較】")
                        print(f"期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
                        if pd.notna(profit) and profit > 0:
                            print(f"計算値: PER={per:.2f}")
                        if pd.notna(equity) and equity > 0:
                            print(f"計算値: PBR={pbr:.2f}")
                        if not fc_data.empty and pd.notna(fc_row['forecast_profit']) and fc_row['forecast_profit'] > 0:
                            print(f"計算値: Forward PER={forward_per:.2f}")

"""
コード7419の最終確認（修正後のロジック）
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features, _split_multiplier_between
import pandas as pd
import numpy as np

code = "7419"
asof = "2025-12-19"

print(f"コード {code}（ノジマ）の最終確認")
print(f"評価日: {asof}")
print("=" * 80)

with connect_db() as conn:
    # 特徴量を計算
    feat = build_features(conn, asof)
    code_data = feat[feat["code"] == code].copy()
    
    if code_data.empty:
        print("データが見つかりません")
    else:
        row = code_data.iloc[0]
        
        print(f"\n【計算結果】")
        print(f"PER: {row.get('per'):.2f}" if pd.notna(row.get('per')) else "PER: N/A")
        print(f"PBR: {row.get('pbr'):.2f}" if pd.notna(row.get('pbr')) else "PBR: N/A")
        print(f"Forward PER: {row.get('forward_per'):.2f}" if pd.notna(row.get('forward_per')) else "Forward PER: N/A")
        
        print(f"\n【期待値との比較】")
        print(f"期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
        forward_per_str = f"{row.get('forward_per'):.2f}" if pd.notna(row.get('forward_per')) else "N/A"
        per_str = f"{row.get('per'):.2f}" if pd.notna(row.get('per')) else "N/A"
        pbr_str = f"{row.get('pbr'):.2f}" if pd.notna(row.get('pbr')) else "N/A"
        print(f"計算値: Forward PER={forward_per_str}, PER={per_str}, PBR={pbr_str}")
        
        # 詳細データを確認
        print(f"\n【詳細データ】")
        print(f"時価総額: {row.get('market_cap_latest_basis'):,.0f}円" if pd.notna(row.get('market_cap_latest_basis')) else "時価総額: N/A")
        print(f"株数: {row.get('shares_latest_basis'):,.0f}株" if pd.notna(row.get('shares_latest_basis')) else "株数: N/A")
        print(f"価格: {row.get('price'):.2f}円" if pd.notna(row.get('price')) else "価格: N/A")
        print(f"利益: {row.get('profit'):,.0f}円" if pd.notna(row.get('profit')) else "利益: N/A")
        print(f"純資産: {row.get('equity'):,.0f}円" if pd.notna(row.get('equity')) else "純資産: N/A")
        print(f"予想利益: {row.get('forecast_profit_fc'):,.0f}円" if pd.notna(row.get('forecast_profit_fc')) else "予想利益: N/A")
        
        # FYデータを確認
        print(f"\n【FYデータ】")
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
        if not fy_data.empty:
            fy_row = fy_data.iloc[0]
            print(f"期末日: {fy_row.get('current_period_end')}")
            print(f"開示日: {fy_row.get('disclosed_date')}")
            
            # 分割倍率を確認
            fy_end = fy_row.get('current_period_end')
            if pd.notna(fy_end):
                if hasattr(fy_end, 'strftime'):
                    fy_end_str = fy_end.strftime("%Y-%m-%d")
                else:
                    fy_end_str = str(fy_end)
                
                split_mult = _split_multiplier_between(conn, code, fy_end_str, asof)
                print(f"分割倍率: {split_mult:.6f}")
        
        # 予想データを確認
        print(f"\n【予想データ】")
        fc_data = pd.read_sql_query(
            """
            WITH ranked AS (
              SELECT
                code, disclosed_date, type_of_current_period,
                forecast_profit,
                ROW_NUMBER() OVER (
                  PARTITION BY code
                  ORDER BY disclosed_date DESC,
                           CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END
                ) AS rn
              FROM fins_statements
              WHERE disclosed_date <= ?
                AND (forecast_operating_profit IS NOT NULL 
                     OR forecast_profit IS NOT NULL 
                     OR forecast_eps IS NOT NULL)
            )
            SELECT code, disclosed_date, type_of_current_period, forecast_profit
            FROM ranked
            WHERE rn = 1
              AND code = ?
            """,
            conn,
            params=(asof, code),
        )
        if not fc_data.empty:
            fc_row = fc_data.iloc[0]
            print(f"開示日: {fc_row.get('disclosed_date')}")
            print(f"期間: {fc_row.get('type_of_current_period')}")
            print(f"予想利益: {fc_row.get('forecast_profit'):,.0f}円" if pd.notna(fc_row.get('forecast_profit')) else "予想利益: N/A")

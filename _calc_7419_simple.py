"""
コード7419（ノジマ）のPER、PBR、Forward PERを計算（簡易版）
現在のロジックで実際に計算を実行
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features
import pandas as pd
import numpy as np

# 評価日
asof = "2025-12-19"
code = "7419"

print(f"コード {code}（ノジマ）の計算を実行します")
print(f"評価日: {asof}")
print("=" * 80)

try:
    with connect_db() as conn:
        # 特徴量を計算
        print("\n特徴量を計算中...")
        feat = build_features(conn, asof)
        
        # コード7419のデータを取得
        code_data = feat[feat["code"] == code].copy()
        
        if code_data.empty:
            print(f"\nエラー: コード {code} のデータが見つかりません")
        else:
            row = code_data.iloc[0]
            
            print(f"\n【計算結果】")
            print(f"銘柄コード: {row.get('code')}")
            print(f"評価日: {row.get('as_of_date')}")
            
            # 価格データ
            price = row.get('price')
            shares = row.get('shares_latest_basis')
            market_cap = row.get('market_cap_latest_basis')
            
            print(f"\n【価格・株数データ】")
            if pd.notna(price):
                print(f"価格: {price:.2f}円")
            else:
                print(f"価格: N/A")
            
            if pd.notna(shares) and shares > 0:
                print(f"評価日時点の株数: {shares:,.0f}株")
            else:
                print(f"評価日時点の株数: N/A")
            
            if pd.notna(market_cap) and market_cap > 0:
                print(f"時価総額: {market_cap:,.0f}円")
            else:
                print(f"時価総額: N/A")
            
            # 財務データを直接取得
            print(f"\n【財務データ】")
            fy_data = pd.read_sql_query(
                """
                SELECT profit, equity, shares_outstanding, treasury_shares, current_period_end
                FROM fins_statements
                WHERE code = ?
                  AND type_of_current_period = 'FY'
                  AND disclosed_date <= ?
                ORDER BY current_period_end DESC, disclosed_date DESC
                LIMIT 1
                """,
                conn,
                params=(code, asof),
            )
            
            if not fy_data.empty:
                fy_row = fy_data.iloc[0]
                profit = fy_row.get('profit')
                equity = fy_row.get('equity')
                shares_out = fy_row.get('shares_outstanding')
                treasury = fy_row.get('treasury_shares')
                period_end = fy_row.get('current_period_end')
                
                print(f"利益 (profit): {profit:,.0f}円" if pd.notna(profit) else "利益 (profit): N/A")
                print(f"純資産 (equity): {equity:,.0f}円" if pd.notna(equity) else "純資産 (equity): N/A")
                print(f"発行済み株式数: {shares_out:,.0f}株" if pd.notna(shares_out) else "発行済み株式数: N/A")
                print(f"自己株式数: {treasury:,.0f}株" if pd.notna(treasury) else "自己株式数: N/A")
                print(f"期末日: {period_end}")
            
            # 予想データを取得
            print(f"\n【予想データ】")
            fc_data = pd.read_sql_query(
                """
                SELECT forecast_profit, disclosed_date
                FROM fins_statements
                WHERE code = ?
                  AND disclosed_date <= ?
                  AND type_of_current_period = 'FY'
                  AND forecast_profit IS NOT NULL
                ORDER BY disclosed_date DESC
                LIMIT 1
                """,
                conn,
                params=(code, asof),
            )
            
            if not fc_data.empty:
                fc_row = fc_data.iloc[0]
                forecast_profit = fc_row.get('forecast_profit')
                print(f"予想利益 (forecast_profit): {forecast_profit:,.0f}円" if pd.notna(forecast_profit) else "予想利益 (forecast_profit): N/A")
                print(f"予想開示日: {fc_row.get('disclosed_date', 'N/A')}")
            else:
                print("予想データ: 見つかりませんでした")
            
            # 計算結果
            print(f"\n【計算結果】")
            per = row.get('per')
            pbr = row.get('pbr')
            forward_per = row.get('forward_per')
            
            print(f"PER: {per:.2f}" if pd.notna(per) else "PER: N/A")
            print(f"PBR: {pbr:.2f}" if pd.notna(pbr) else "PBR: N/A")
            print(f"Forward PER: {forward_per:.2f}" if pd.notna(forward_per) else "Forward PER: N/A")
            
            print(f"\n【期待値との比較】")
            print(f"期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
            forward_per_str = f"{forward_per:.2f}" if pd.notna(forward_per) else "N/A"
            per_str = f"{per:.2f}" if pd.notna(per) else "N/A"
            pbr_str = f"{pbr:.2f}" if pd.notna(pbr) else "N/A"
            print(f"計算値: Forward PER={forward_per_str}, PER={per_str}, PBR={pbr_str}")
            
            # 分割倍率を確認
            if not fy_data.empty and pd.notna(period_end):
                if hasattr(period_end, 'strftime'):
                    fy_end_str = period_end.strftime("%Y-%m-%d")
                else:
                    fy_end_str = str(period_end)
                
                split_data = pd.read_sql_query(
                    """
                    SELECT date, adjustment_factor
                    FROM prices_daily
                    WHERE code = ?
                      AND date > ?
                      AND date <= ?
                      AND adjustment_factor IS NOT NULL
                      AND adjustment_factor != 1.0
                    ORDER BY date ASC
                    """,
                    conn,
                    params=(code, fy_end_str, asof),
                )
                
                if not split_data.empty:
                    print(f"\n【分割・併合情報】")
                    print(f"FY期末: {fy_end_str}")
                    print(f"評価日: {asof}")
                    print(f"分割・併合イベント:")
                    split_mult = 1.0
                    for _, split_row in split_data.iterrows():
                        adj_factor = split_row.get('adjustment_factor')
                        if pd.notna(adj_factor) and adj_factor > 0:
                            inv_af = 1.0 / float(adj_factor)
                            split_mult *= inv_af
                            print(f"  {split_row.get('date')}: adjustment_factor={adj_factor:.6f} (株数倍率={inv_af:.6f})")
                    print(f"累積分割倍率: {split_mult:.6f}")
                    
                    # 株数計算の確認
                    if pd.notna(shares_out) and pd.notna(treasury):
                        shares_base = shares_out - (treasury if pd.notna(treasury) else 0)
                        shares_calc = shares_base * split_mult
                        print(f"\n【株数計算の確認】")
                        print(f"FY期末株数 (shares_base): {shares_base:,.0f}株")
                        print(f"分割倍率 (split_mult): {split_mult:.6f}")
                        print(f"計算された株数 (shares_calc): {shares_calc:,.0f}株")
                        print(f"実際の株数 (shares_latest_basis): {shares:,.0f}株" if pd.notna(shares) else "実際の株数: N/A")
                else:
                    print(f"\n【分割・併合情報】")
                    print(f"FY期末から評価日までの間に分割・併合はありません")
                    print(f"累積分割倍率: 1.0")

except Exception as e:
    print(f"\nエラーが発生しました: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

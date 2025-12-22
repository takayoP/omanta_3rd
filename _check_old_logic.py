"""
以前のロジックを確認して、正しい部分だけを採用する
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features
import pandas as pd

code = "7419"
asof = "2025-12-19"

print(f"コード {code}（ノジマ）の計算結果を確認")
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
        
        print(f"\n【現在の計算結果】")
        print(f"PER: {row.get('per'):.2f}" if pd.notna(row.get('per')) else "PER: N/A")
        print(f"PBR: {row.get('pbr'):.2f}" if pd.notna(row.get('pbr')) else "PBR: N/A")
        print(f"Forward PER: {row.get('forward_per'):.2f}" if pd.notna(row.get('forward_per')) else "Forward PER: N/A")
        
        print(f"\n【詳細データ】")
        print(f"価格 (adj_close): {row.get('price'):.2f}円" if pd.notna(row.get('price')) else "価格: N/A")
        print(f"EPS: {row.get('eps'):.2f}円" if pd.notna(row.get('eps')) else "EPS: N/A")
        print(f"BPS: {row.get('bvps'):.2f}円" if pd.notna(row.get('bvps')) else "BPS: N/A")
        print(f"予想EPS: {row.get('forecast_eps_fc'):.2f}円" if pd.notna(row.get('forecast_eps_fc')) else "予想EPS: N/A")
        
        print(f"\n【計算式の確認】")
        if pd.notna(row.get('price')) and pd.notna(row.get('eps')) and row.get('eps') > 0:
            per_calc = row.get('price') / row.get('eps')
            print(f"PER = price / eps = {row.get('price'):.2f} / {row.get('eps'):.2f} = {per_calc:.2f}")
        
        if pd.notna(row.get('price')) and pd.notna(row.get('bvps')) and row.get('bvps') > 0:
            pbr_calc = row.get('price') / row.get('bvps')
            print(f"PBR = price / bvps = {row.get('price'):.2f} / {row.get('bvps'):.2f} = {pbr_calc:.2f}")
        
        if pd.notna(row.get('price')) and pd.notna(row.get('forecast_eps_fc')) and row.get('forecast_eps_fc') > 0:
            forward_per_calc = row.get('price') / row.get('forecast_eps_fc')
            print(f"Forward PER = price / forecast_eps = {row.get('price'):.2f} / {row.get('forecast_eps_fc'):.2f} = {forward_per_calc:.2f}")
        
        print(f"\n【期待値との比較】")
        print(f"期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
        forward_per_str = f"{row.get('forward_per'):.2f}" if pd.notna(row.get('forward_per')) else "N/A"
        per_str = f"{row.get('per'):.2f}" if pd.notna(row.get('per')) else "N/A"
        pbr_str = f"{row.get('pbr'):.2f}" if pd.notna(row.get('pbr')) else "N/A"
        print(f"計算値: Forward PER={forward_per_str}, PER={per_str}, PBR={pbr_str}")

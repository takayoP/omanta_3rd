"""
複数の銘柄コードについて計算を実行
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features
import pandas as pd
import numpy as np

codes = ["1605", "6005", "8136", "9202", "8725", "4507", "8111"]
asof = "2025-12-19"

print(f"複数銘柄の計算結果")
print(f"評価日: {asof}")
print("=" * 100)

with connect_db() as conn:
    # 特徴量を計算
    feat = build_features(conn, asof)
    
    results = []
    for code in codes:
        code_data = feat[feat["code"] == code].copy()
        
        if code_data.empty:
            print(f"\nコード {code}: データが見つかりません")
            continue
        
        row = code_data.iloc[0]
        
        # カラム名を確認
        available_cols = row.index.tolist()
        
        result = {
            "code": code,
            "price": row.get("price") if "price" in available_cols else None,
            "eps": row.get("eps") if "eps" in available_cols else None,
            "bvps": row.get("bvps") if "bvps" in available_cols else None,
            "forecast_eps_fc": row.get("forecast_eps_fc") if "forecast_eps_fc" in available_cols else None,
            "profit": row.get("profit") if "profit" in available_cols else None,
            "equity": row.get("equity") if "equity" in available_cols else None,
            "shares_outstanding": row.get("shares_outstanding") if "shares_outstanding" in available_cols else None,
            "treasury_shares": row.get("treasury_shares") if "treasury_shares" in available_cols else None,
            "current_period_end": row.get("current_period_end") if "current_period_end" in available_cols else None,
            "per": row.get("per") if "per" in available_cols else None,
            "pbr": row.get("pbr") if "pbr" in available_cols else None,
            "forward_per": row.get("forward_per") if "forward_per" in available_cols else None,
            "market_cap_latest_basis": row.get("market_cap_latest_basis") if "market_cap_latest_basis" in available_cols else None,
            "shares_latest_basis": row.get("shares_latest_basis") if "shares_latest_basis" in available_cols else None,
        }
        results.append(result)
        
        print(f"\n【コード {code}】")
        print(f"  価格 (adj_close): {result['price']:.2f}円" if pd.notna(result['price']) else "  価格: N/A")
        print(f"  EPS: {result['eps']:.2f}円" if pd.notna(result['eps']) else "  EPS: N/A")
        print(f"  BPS: {result['bvps']:.2f}円" if pd.notna(result['bvps']) else "  BPS: N/A")
        print(f"  予想EPS: {result['forecast_eps_fc']:.2f}円" if pd.notna(result['forecast_eps_fc']) else "  予想EPS: N/A")
        print(f"  利益: {result['profit']:,.0f}円" if pd.notna(result['profit']) else "  利益: N/A")
        print(f"  純資産: {result['equity']:,.0f}円" if pd.notna(result['equity']) else "  純資産: N/A")
        print(f"  発行済み株式数: {result['shares_outstanding']:,.0f}株" if pd.notna(result['shares_outstanding']) else "  発行済み株式数: N/A")
        print(f"  自己株式数: {result['treasury_shares']:,.0f}株" if pd.notna(result['treasury_shares']) else "  自己株式数: N/A")
        print(f"  期末日: {result['current_period_end']}" if pd.notna(result['current_period_end']) else "  期末日: N/A")
        print(f"  調整後株数: {result['shares_latest_basis']:,.0f}株" if pd.notna(result['shares_latest_basis']) else "  調整後株数: N/A")
        print(f"  時価総額: {result['market_cap_latest_basis']:,.0f}円" if pd.notna(result['market_cap_latest_basis']) else "  時価総額: N/A")
        print(f"  PER: {result['per']:.2f}" if pd.notna(result['per']) else "  PER: N/A")
        print(f"  PBR: {result['pbr']:.2f}" if pd.notna(result['pbr']) else "  PBR: N/A")
        print(f"  Forward PER: {result['forward_per']:.2f}" if pd.notna(result['forward_per']) else "  Forward PER: N/A")
        
        # 計算式の確認
        if pd.notna(result['price']) and pd.notna(result['eps']) and result['eps'] > 0:
            per_calc = result['price'] / result['eps']
            print(f"  PER計算: {result['price']:.2f} / {result['eps']:.2f} = {per_calc:.2f}")
        
        if pd.notna(result['price']) and pd.notna(result['bvps']) and result['bvps'] > 0:
            pbr_calc = result['price'] / result['bvps']
            print(f"  PBR計算: {result['price']:.2f} / {result['bvps']:.2f} = {pbr_calc:.2f}")
        
        if pd.notna(result['price']) and pd.notna(result['forecast_eps_fc']) and result['forecast_eps_fc'] > 0:
            forward_per_calc = result['price'] / result['forecast_eps_fc']
            print(f"  Forward PER計算: {result['price']:.2f} / {result['forecast_eps_fc']:.2f} = {forward_per_calc:.2f}")
    
    # 結果をDataFrameにまとめる
    df_results = pd.DataFrame(results)
    print(f"\n\n【全銘柄の結果サマリー】")
    print(df_results[["code", "per", "pbr", "forward_per", "price", "eps", "bvps", "forecast_eps_fc"]].to_string(index=False))

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FYデータの相互補完機能の詳細テスト
同じcurrent_period_endのFYデータで、補完前と補完後を比較
"""

import sys
from pathlib import Path
import pandas as pd
import sqlite3

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"
test_code = "6191"  # 相互補完可能なケース

print("=== FYデータの相互補完機能の詳細テスト ===\n")
print(f"テスト対象: 銘柄コード {test_code}\n")

with connect_db() as conn:
    # 補完前のデータを確認
    print("【補完前】同じcurrent_period_endのFYデータ（最新のcurrent_period_end）:\n")
    fy_data = pd.read_sql_query("""
        SELECT disclosed_date, current_period_end,
               operating_profit, forecast_operating_profit,
               profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
        ORDER BY current_period_end DESC, disclosed_date
        LIMIT 10
    """, conn, params=(test_code, asof))

if not fy_data.empty:
    latest_period = fy_data.iloc[0]["current_period_end"]
    same_period_data = fy_data[fy_data["current_period_end"] == latest_period]
    
    print(f"当期末: {latest_period}\n")
    for _, row in same_period_data.iterrows():
        op_str = f"{row['operating_profit']:,.0f}" if pd.notna(row["operating_profit"]) else "NULL"
        forecast_op_str = f"{row['forecast_operating_profit']:,.0f}" if pd.notna(row["forecast_operating_profit"]) else "NULL"
        profit_str = f"{row['profit']:,.0f}" if pd.notna(row["profit"]) else "NULL"
        forecast_profit_str = f"{row['forecast_profit']:,.0f}" if pd.notna(row["forecast_profit"]) else "NULL"
        forecast_eps_str = f"{row['forecast_eps']:.2f}" if pd.notna(row["forecast_eps"]) else "NULL"
        
        print(f"  開示日: {row['disclosed_date']}")
        print(f"    operating_profit: {op_str}, forecast_operating_profit: {forecast_op_str}")
        print(f"    profit: {profit_str}, forecast_profit: {forecast_profit_str}")
        print(f"    forecast_eps: {forecast_eps_str}")
        print()

    # 補完後のデータを確認
    print("\n【補完後】_load_latest_fyで取得したデータ:\n")
    # _load_latest_fyは内部でconnect_db()を呼び出すため、ここでは直接SQLで確認
    latest = pd.read_sql_query("""
        SELECT disclosed_date, current_period_end,
               operating_profit, forecast_operating_profit,
               profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND current_period_end = ?
        ORDER BY disclosed_date DESC
        LIMIT 1
    """, conn, params=(test_code, asof, latest_period))
    
    # 実際の補完ロジックをテストするため、_load_latest_fyのロジックを再現
    all_fy = pd.read_sql_query("""
        SELECT disclosed_date, current_period_end,
               operating_profit, forecast_operating_profit,
               profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date <= ?
          AND current_period_end = ?
        ORDER BY disclosed_date DESC
    """, conn, params=(test_code, asof, latest_period))
    
    if not all_fy.empty:
        base_row = all_fy.iloc[0].copy()
        
        # 相互補完
        if pd.isna(base_row["operating_profit"]):
            for _, row in all_fy.iterrows():
                if pd.notna(row["forecast_operating_profit"]):
                    base_row["operating_profit"] = row["forecast_operating_profit"]
                    print("  → operating_profitをforecast_operating_profitから補完")
                    break
        
        if pd.isna(base_row["forecast_operating_profit"]):
            for _, row in all_fy.iterrows():
                if pd.notna(row["operating_profit"]):
                    base_row["forecast_operating_profit"] = row["operating_profit"]
                    print("  → forecast_operating_profitをoperating_profitから補完")
                    break
        
        if pd.isna(base_row["profit"]):
            for _, row in all_fy.iterrows():
                if pd.notna(row["forecast_profit"]):
                    base_row["profit"] = row["forecast_profit"]
                    print("  → profitをforecast_profitから補完")
                    break
        
        if pd.isna(base_row["forecast_profit"]):
            for _, row in all_fy.iterrows():
                if pd.notna(row["profit"]):
                    base_row["forecast_profit"] = row["profit"]
                    print("  → forecast_profitをprofitから補完")
                    break
        
        if pd.isna(base_row["forecast_eps"]):
            for _, row in all_fy.iterrows():
                if pd.notna(row.get("eps")):
                    base_row["forecast_eps"] = row["eps"]
                    print("  → forecast_epsをepsから補完")
                    break
        
        latest = pd.DataFrame([base_row])
    test_row = latest[latest["code"] == test_code]

    if not test_row.empty:
        row = test_row.iloc[0]
        print(f"銘柄コード: {row['code']}")
        print(f"  開示日: {row['disclosed_date']}")
        print(f"  当期末: {row['current_period_end']}")
        op_str = f"{row['operating_profit']:,.0f}" if pd.notna(row['operating_profit']) else "NULL"
        forecast_op_str = f"{row['forecast_operating_profit']:,.0f}" if pd.notna(row['forecast_operating_profit']) else "NULL"
        profit_str = f"{row['profit']:,.0f}" if pd.notna(row['profit']) else "NULL"
        forecast_profit_str = f"{row['forecast_profit']:,.0f}" if pd.notna(row['forecast_profit']) else "NULL"
        forecast_eps_str = f"{row['forecast_eps']:.2f}" if pd.notna(row['forecast_eps']) else "NULL"
        
        print(f"  operating_profit: {op_str}")
        print(f"  forecast_operating_profit: {forecast_op_str}")
        print(f"  profit: {profit_str}")
        print(f"  forecast_profit: {forecast_profit_str}")
        print(f"  forecast_eps: {forecast_eps_str}")
        
        # 補完が行われたかどうかを確認
        print("\n【補完の確認】")
        if pd.notna(row['operating_profit']) and pd.notna(row['forecast_operating_profit']):
            if abs(row['operating_profit'] - row['forecast_operating_profit']) < 1:
                print("  ✓ operating_profitとforecast_operating_profitが同じ値 → 相互補完が行われた可能性")
            else:
                print("  → operating_profitとforecast_operating_profitが異なる値")
        elif pd.notna(row['operating_profit']) or pd.notna(row['forecast_operating_profit']):
            print("  → 一方のみが存在（補完されなかった）")
        else:
            print("  → 両方とも欠損")

print("\n" + "="*60)
print("テスト完了")

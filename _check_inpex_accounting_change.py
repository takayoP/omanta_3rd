#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
INPEX（1605）の会計基準変更ケースを確認
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

code = "1605"
asof = "2025-12-19"

print(f"=== INPEX（コード{code}）のFYデータ確認 ===\n")

# FYデータを取得（開示日順）
fy_data = pd.read_sql_query("""
    SELECT disclosed_date, disclosed_time, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period = 'FY'
      AND disclosed_date <= ?
    ORDER BY disclosed_date, current_period_end
""", conn, params=(code, asof))

print(f"FYデータ総数: {len(fy_data)}件\n")

if len(fy_data) > 0:
    print("FYデータ（開示日順）:")
    for idx, row in fy_data.iterrows():
        print(f"  開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}, "
              f"operating_profit: {row['operating_profit']}, profit: {row['profit']}")
    
    print("\n" + "="*60)
    print("current_period_endの種類:\n")
    period_ends = fy_data.groupby("current_period_end").agg({
        "disclosed_date": ["min", "max", "count"]
    }).reset_index()
    period_ends.columns = ["current_period_end", "min_disclosed_date", "max_disclosed_date", "count"]
    
    for _, row in period_ends.iterrows():
        print(f"  当期末: {row['current_period_end']}")
        print(f"    件数: {row['count']}件")
        print(f"    開示日の範囲: {row['min_disclosed_date']} ～ {row['max_disclosed_date']}")
        print()

# 現在のロジックで選ばれるデータを確認
print("="*60)
print("現在のロジック（sort + groupby tail(1)）で選ばれるデータ:\n")

df = fy_data.copy()
df["code"] = code  # codeカラムを追加
df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
df = df.sort_values(["code", "disclosed_date", "current_period_end"])
latest = df.groupby("code", as_index=False).tail(1).copy()

if not latest.empty:
    selected = latest.iloc[0]
    print(f"選ばれるデータ:")
    print(f"  開示日: {selected['disclosed_date']}")
    print(f"  当期末: {selected['current_period_end']}")
    print(f"  operating_profit: {selected['operating_profit']}")
    print(f"  profit: {selected['profit']}")
    
    # 同じcurrent_period_endで最新のdisclosed_dateを持つデータがあるか確認
    same_period = fy_data[fy_data["current_period_end"] == selected["current_period_end"]]
    if len(same_period) > 1:
        print(f"\n同じ当期末（{selected['current_period_end']}）のデータが{len(same_period)}件あります。")
        print("最新の開示日が選ばれています。")

print("\n" + "="*60)
print("【考察】")
print("会計基準変更により、異なるcurrent_period_endのデータが存在する場合、")
print("現在のロジックではdisclosed_dateが最新のものが選ばれます。")
print()
print("選択肢:")
print("1. current_period_endが最新のものを選ぶ（最新の会計期間）")
print("2. disclosed_dateが最新のものを選ぶ（現状、最新の情報）")
print("3. current_period_endごとに最新のdisclosed_dateを選び、その中でcurrent_period_endが最新のものを選ぶ")

conn.close()

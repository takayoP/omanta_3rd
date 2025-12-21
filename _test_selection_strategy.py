#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
異なる選択戦略をテスト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

code = "1605"
asof = "2025-12-19"

print(f"=== INPEX（コード{code}）の選択戦略の比較 ===\n")

# FYデータを取得
fy_data = pd.read_sql_query("""
    SELECT code, disclosed_date, disclosed_time, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period = 'FY'
      AND disclosed_date <= ?
""", conn, params=(code, asof))

fy_data["disclosed_date"] = pd.to_datetime(fy_data["disclosed_date"], errors="coerce")
fy_data["current_period_end"] = pd.to_datetime(fy_data["current_period_end"], errors="coerce")

print("【戦略1】現在のロジック: disclosed_dateが最新のものを選ぶ")
df1 = fy_data.sort_values(["code", "disclosed_date", "current_period_end"])
selected1 = df1.groupby("code", as_index=False).tail(1).iloc[0]
print(f"  選ばれるデータ:")
print(f"    開示日: {selected1['disclosed_date']}")
print(f"    当期末: {selected1['current_period_end']}")
print(f"    operating_profit: {selected1['operating_profit']}")

print("\n【戦略2】current_period_endが最新のものを選ぶ")
df2 = fy_data.sort_values(["code", "current_period_end", "disclosed_date"])
selected2 = df2.groupby("code", as_index=False).tail(1).iloc[0]
print(f"  選ばれるデータ:")
print(f"    開示日: {selected2['disclosed_date']}")
print(f"    当期末: {selected2['current_period_end']}")
print(f"    operating_profit: {selected2['operating_profit']}")

print("\n【戦略3（推奨）】current_period_endごとに最新のdisclosed_dateを選び、その中でcurrent_period_endが最新のものを選ぶ")
# 各current_period_endごとに最新のdisclosed_dateを選ぶ
df3 = fy_data.sort_values(["code", "current_period_end", "disclosed_date"])
latest_by_period = df3.groupby(["code", "current_period_end"], as_index=False).tail(1)
# その中でcurrent_period_endが最新のものを選ぶ
latest_by_period = latest_by_period.sort_values(["code", "current_period_end"])
selected3 = latest_by_period.groupby("code", as_index=False).tail(1).iloc[0]
print(f"  選ばれるデータ:")
print(f"    開示日: {selected3['disclosed_date']}")
print(f"    当期末: {selected3['current_period_end']}")
print(f"    operating_profit: {selected3['operating_profit']}")

print("\n" + "="*60)
print("【推奨】")
print("戦略3が最も適切です。")
print("- 各会計期間（current_period_end）ごとに最新の開示情報を使用")
print("- 最新の会計期間を優先")
print("- 会計基準変更後のデータを優先")

conn.close()

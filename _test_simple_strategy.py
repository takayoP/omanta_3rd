#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
シンプルな戦略のテスト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

code = "1605"
asof = "2025-12-19"

print("=== シンプルな戦略のテスト ===\n")

# FYデータを取得
fy_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period = 'FY'
      AND disclosed_date <= ?
""", conn, params=(code, asof))

fy_data["disclosed_date"] = pd.to_datetime(fy_data["disclosed_date"], errors="coerce")
fy_data["current_period_end"] = pd.to_datetime(fy_data["current_period_end"], errors="coerce")

print("【シンプルな戦略】")
print("ステップ1: 当期末が最新のものを選ぶ（複数ある可能性）")
print("ステップ2: その中で開示日が最新のものを選ぶ\n")

# ステップ1: 当期末が最新のものを選ぶ
df = fy_data.sort_values("current_period_end", ascending=False)
max_period_end = df.iloc[0]["current_period_end"]
latest_period_data = df[df["current_period_end"] == max_period_end]

print(f"当期末が最新（{max_period_end.strftime('%Y-%m-%d')}）のデータ:")
for _, row in latest_period_data.iterrows():
    print(f"  開示日: {row['disclosed_date'].strftime('%Y-%m-%d')}, "
          f"operating_profit: {row['operating_profit']}")

print()
print("ステップ2: その中で開示日が最新のものを選ぶ")
selected = latest_period_data.sort_values("disclosed_date", ascending=False).iloc[0]

print(f"\n結果:")
print(f"  当期末: {selected['current_period_end'].strftime('%Y-%m-%d')}")
print(f"  開示日: {selected['disclosed_date'].strftime('%Y-%m-%d')}")
print(f"  operating_profit: {selected['operating_profit']}")

print("\n" + "="*60)
print("【比較：戦略3（二段階）の場合】")

# 戦略3（二段階）
df3 = fy_data.sort_values(["current_period_end", "disclosed_date"])
latest_by_period = df3.groupby("current_period_end", as_index=False).tail(1)
latest_by_period = latest_by_period.sort_values("current_period_end", ascending=False)
selected3 = latest_by_period.iloc[0]

print(f"  当期末: {selected3['current_period_end'].strftime('%Y-%m-%d')}")
print(f"  開示日: {selected3['disclosed_date'].strftime('%Y-%m-%d')}")
print(f"  operating_profit: {selected3['operating_profit']}")

print("\n→ 同じ結果になり、シンプルな方が理解しやすい！")

conn.close()

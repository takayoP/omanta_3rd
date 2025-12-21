#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
選択戦略の説明（具体例付き）
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

code = "1605"
asof = "2025-12-19"

print("="*70)
print("選択戦略の説明：INPEX（1605）のケース")
print("="*70)
print()

# FYデータを取得
fy_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period = 'FY'
      AND disclosed_date <= ?
    ORDER BY current_period_end, disclosed_date
""", conn, params=(code, asof))

fy_data["disclosed_date"] = pd.to_datetime(fy_data["disclosed_date"], errors="coerce")
fy_data["current_period_end"] = pd.to_datetime(fy_data["current_period_end"], errors="coerce")

print("【INPEXのFYデータ一覧】")
print("（当期末ごとにグループ化して表示）\n")

# 当期末ごとにグループ化して表示
for period_end, group in fy_data.groupby("current_period_end"):
    print(f"当期末: {period_end.strftime('%Y-%m-%d')}")
    for _, row in group.iterrows():
        op = row['operating_profit']
        profit = row['profit']
        op_str = f"{op:,.0f}" if pd.notna(op) else "NaN"
        profit_str = f"{profit:,.0f}" if pd.notna(profit) else "NaN"
        print(f"  └─ 開示日: {row['disclosed_date'].strftime('%Y-%m-%d')}, "
              f"営業利益: {op_str}, 利益: {profit_str}")
    print()

print("="*70)
print("【戦略の説明】")
print("="*70)
print()

print("【戦略1（現在のロジック）】")
print("全てのデータを開示日順に並べて、最新の1件を選ぶ")
print()
df1 = fy_data.sort_values(["code", "disclosed_date", "current_period_end"])
selected1 = df1.groupby("code", as_index=False).tail(1).iloc[0]
print(f"結果: 開示日 {selected1['disclosed_date'].strftime('%Y-%m-%d')} "
      f"（当期末: {selected1['current_period_end'].strftime('%Y-%m-%d')}）")
print()
print("→ 問題点: 古い会計期間のデータが選ばれる可能性がある")
print("   （例: 2019-03-31決算のデータが2025年に修正開示された場合、")
print("        それが選ばれてしまう可能性）")
print()

print("="*70)
print("【戦略3（推奨）】")
print("="*70)
print()
print("ステップ1: 各「当期末」ごとに、最新の「開示日」を選ぶ")
print()

# 各current_period_endごとに最新のdisclosed_dateを選ぶ
latest_by_period = fy_data.sort_values(["current_period_end", "disclosed_date"])\
    .groupby("current_period_end", as_index=False).tail(1)

print("各当期末ごとに最新の開示日を選んだ結果:")
for _, row in latest_by_period.iterrows():
    op = row['operating_profit']
    profit = row['profit']
    op_str = f"{op:,.0f}" if pd.notna(op) else "NaN"
    profit_str = f"{profit:,.0f}" if pd.notna(profit) else "NaN"
    print(f"  当期末: {row['current_period_end'].strftime('%Y-%m-%d')}, "
          f"開示日: {row['disclosed_date'].strftime('%Y-%m-%d')}, "
          f"営業利益: {op_str}")

print()
print("ステップ2: その中で、「当期末」が最新のものを選ぶ")
print()

latest_by_period = latest_by_period.sort_values("current_period_end")
selected3 = latest_by_period.tail(1).iloc[0]

print(f"結果: 当期末 {selected3['current_period_end'].strftime('%Y-%m-%d')}, "
      f"開示日 {selected3['disclosed_date'].strftime('%Y-%m-%d')}")
print()
print("→ メリット:")
print("  - 各会計期間ごとに最新の開示情報を使用（修正開示を反映）")
print("  - 最新の会計期間を優先（会計基準変更後を優先）")
print("  - 同じ当期末で複数の開示日がある場合、最新の開示日を使用")
print()

print("="*70)
print("【具体例：INPEXの場合】")
print("="*70)
print()
print("INPEXは2019年に会計基準を日本基準→IFRSに変更しました。")
print()
print("この場合:")
print("  - 2019-03-31（日本基準）のデータ")
print("  - 2019-12-31（IFRS移行後）のデータ")
print("  の両方が存在します。")
print()
print("戦略3では:")
print("  1. 2019-03-31期間: 最新開示日を選ぶ → 1件のみ")
print("  2. 2019-12-31期間: 最新開示日を選ぶ → 1件のみ")
print("  3. その他の期間: それぞれ最新開示日を選ぶ")
print("  4. それらの中から、当期末が最新（2024-12-31）のものを選ぶ")
print()
print("→ IFRS移行後のデータ（2019-12-31以降）が優先されます。")

conn.close()

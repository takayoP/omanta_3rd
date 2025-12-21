#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
同じcurrent_period_endを持つFYデータが複数ある場合の選択ロジックを確認
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

asof = "2025-12-19"

print("=== 同じcurrent_period_endを持つFYデータの確認 ===\n")

# 同じcurrent_period_endを持つFYデータが複数ある銘柄を探す
duplicate_periods = pd.read_sql_query("""
    SELECT code, current_period_end, COUNT(*) as cnt
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND disclosed_date <= ?
    GROUP BY code, current_period_end
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC, code, current_period_end
    LIMIT 10
""", conn, params=(asof,))

print(f"同じcurrent_period_endを持つFYデータが複数ある銘柄: {len(duplicate_periods)}件\n")

if len(duplicate_periods) > 0:
    print("サンプル（最初の5件）:")
    for idx, row in duplicate_periods.head(5).iterrows():
        code = row["code"]
        period_end = row["current_period_end"]
        
        print(f"\n銘柄コード: {code}, 当期末: {period_end} ({row['cnt']}件)")
        
        # 該当するFYデータを取得
        fy_data = pd.read_sql_query("""
            SELECT code, disclosed_date, disclosed_time, current_period_end,
                   operating_profit, profit, equity, eps, bvps
            FROM fins_statements
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND current_period_end = ?
              AND disclosed_date <= ?
            ORDER BY disclosed_date
        """, conn, params=(code, period_end, asof))
        
        print("  開示日ごとのデータ:")
        for _, fy_row in fy_data.iterrows():
            print(f"    開示日: {fy_row['disclosed_date']}, "
                  f"operating_profit: {fy_row['operating_profit']}, "
                  f"profit: {fy_row['profit']}")
        
        # 現在のロジック（sort + tail(1)）で選ばれるデータをシミュレート
        fy_data_sorted = fy_data.sort_values(["code", "disclosed_date", "current_period_end"])
        selected = fy_data_sorted.groupby("code", as_index=False).tail(1).iloc[0]
        
        print(f"\n  → 現在のロジックで選ばれるデータ:")
        print(f"    開示日: {selected['disclosed_date']}")
        print(f"    operating_profit: {selected['operating_profit']}, profit: {selected['profit']}")
else:
    print("同じcurrent_period_endを持つFYデータが複数ある銘柄は見つかりませんでした。")

print("\n" + "="*60)
print("【現在のロジック】")
print("`df.sort_values(['code', 'disclosed_date', 'current_period_end'])`")
print("`df.groupby('code', as_index=False).tail(1)`")
print()
print("同じcode、同じcurrent_period_endの場合、disclosed_dateが最新のものが選ばれます。")
print("これは修正開示（修正後のデータ）が選ばれる可能性があります。")

conn.close()

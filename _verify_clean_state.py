#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
データのクリーンな状態を確認
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

print("=== データのクリーンな状態の確認 ===\n")

# 補完フラグの確認
imputed_count = pd.read_sql_query("""
    SELECT 
        SUM(imputed_op) as op_count,
        SUM(imputed_profit) as profit_count,
        SUM(imputed_equity) as equity_count,
        SUM(imputed_eps) as eps_count,
        SUM(imputed_bvps) as bvps_count
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
""", conn)

print("補完フラグの統計（FYレコード）:")
print(f"  imputed_op: {imputed_count.iloc[0]['op_count'] or 0}件")
print(f"  imputed_profit: {imputed_count.iloc[0]['profit_count'] or 0}件")
print(f"  imputed_equity: {imputed_count.iloc[0]['equity_count'] or 0}件")
print(f"  imputed_eps: {imputed_count.iloc[0]['eps_count'] or 0}件")
print(f"  imputed_bvps: {imputed_count.iloc[0]['bvps_count'] or 0}件")

total_imputed = (imputed_count.iloc[0]['op_count'] or 0) + \
                (imputed_count.iloc[0]['profit_count'] or 0) + \
                (imputed_count.iloc[0]['equity_count'] or 0) + \
                (imputed_count.iloc[0]['eps_count'] or 0) + \
                (imputed_count.iloc[0]['bvps_count'] or 0)

print(f"\n合計: {total_imputed}件")

if total_imputed == 0:
    print("\n✓ 補完フラグが立っているレコードはありません")
    print("✓ データはクリーンな状態です")
else:
    print(f"\n⚠ 補完フラグが立っているレコードが{total_imputed}件あります")

# fins_fy_rawの確認
print("\n" + "="*60)
print("fins_fy_rawテーブルの状態\n")

raw_count = pd.read_sql_query("""
    SELECT COUNT(*) as cnt, MAX(as_of_date) as latest_date
    FROM fins_fy_raw
""", conn)

print(f"fins_fy_rawのレコード数: {raw_count.iloc[0]['cnt']:,}件")
print(f"最新のas_of_date: {raw_count.iloc[0]['latest_date']}")

print("\n" + "="*60)
print("【結論】")
print("現在の実装では、fins_fy_rawから補完前データを取得するため、")
print("fins_statementsが汚れていても問題ありません。")
print("ただし、データの整合性を保つために、必要に応じて広い範囲のデータを再取得することを推奨します。")

conn.close()

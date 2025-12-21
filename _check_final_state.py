#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最終状態の確認
"""

import sqlite3

conn = sqlite3.connect("data/db/jquants.sqlite")

cursor = conn.execute("SELECT COUNT(*) FROM fins_statements")
total_count = cursor.fetchone()[0]
print(f"総レコード数: {total_count:,}件")

cursor = conn.execute("SELECT MIN(disclosed_date), MAX(disclosed_date) FROM fins_statements")
row = cursor.fetchone()
print(f"データ範囲: {row[0]} ～ {row[1]}")

cursor = conn.execute('SELECT COUNT(*) FROM fins_statements WHERE type_of_current_period = "FY"')
fy_count = cursor.fetchone()[0]
print(f"FYデータ数: {fy_count:,}件")

# 補完フラグカラムが存在しないことを確認
cursor = conn.execute("PRAGMA table_info(fins_statements)")
columns = [row[1] for row in cursor.fetchall()]
imputed_cols = ["imputed_op", "imputed_profit", "imputed_equity", "imputed_eps", "imputed_bvps"]
found_imputed = [col for col in imputed_cols if col in columns]
if found_imputed:
    print(f"⚠ 補完フラグカラムがまだ存在します: {found_imputed}")
else:
    print("✓ 補完フラグカラムは削除されています")

# fins_fy_rawテーブルが存在しないことを確認
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fins_fy_raw'")
if cursor.fetchone():
    print("⚠ fins_fy_rawテーブルがまだ存在します")
else:
    print("✓ fins_fy_rawテーブルは削除されています")

conn.close()

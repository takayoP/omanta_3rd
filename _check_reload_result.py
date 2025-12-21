#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""データ取得結果を確認"""

import sqlite3

conn = sqlite3.connect("data/db/jquants.sqlite")

count = conn.execute("SELECT COUNT(*) FROM fins_statements").fetchone()[0]
min_date = conn.execute("SELECT MIN(disclosed_date) FROM fins_statements").fetchone()[0]
max_date = conn.execute("SELECT MAX(disclosed_date) FROM fins_statements").fetchone()[0]
imputed_count = conn.execute(
    "SELECT COUNT(*) FROM fins_statements WHERE imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 OR imputed_eps = 1 OR imputed_bvps = 1"
).fetchone()[0]

print("=== データ取得結果 ===")
print(f"総レコード数: {count:,}件")
print(f"開示日の範囲: {min_date} ～ {max_date}")
print(f"補完フラグが立っているレコード: {imputed_count}件")
print()

print("補完フラグの内訳:")
print(f"  imputed_op: {conn.execute('SELECT COUNT(*) FROM fins_statements WHERE imputed_op = 1').fetchone()[0]}件")
print(f"  imputed_profit: {conn.execute('SELECT COUNT(*) FROM fins_statements WHERE imputed_profit = 1').fetchone()[0]}件")
print(f"  imputed_equity: {conn.execute('SELECT COUNT(*) FROM fins_statements WHERE imputed_equity = 1').fetchone()[0]}件")
print(f"  imputed_eps: {conn.execute('SELECT COUNT(*) FROM fins_statements WHERE imputed_eps = 1').fetchone()[0]}件")
print(f"  imputed_bvps: {conn.execute('SELECT COUNT(*) FROM fins_statements WHERE imputed_bvps = 1').fetchone()[0]}件")

conn.close()

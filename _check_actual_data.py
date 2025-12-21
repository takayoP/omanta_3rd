#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""実際のデータを確認"""

import sqlite3

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

code = "2130"
row = conn.execute("""
    SELECT code, disclosed_date, equity, imputed_equity, 
           operating_profit, profit, eps, bvps,
           imputed_op, imputed_profit, imputed_eps, imputed_bvps
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period = 'FY'
    ORDER BY disclosed_date DESC
    LIMIT 1
""", (code,)).fetchone()

print(f"銘柄コード: {row['code']}")
print(f"開示日: {row['disclosed_date']}")
print(f"equity: {row['equity']}")
print(f"imputed_equity: {row['imputed_equity']}")
print(f"operating_profit: {row['operating_profit']}")
print(f"profit: {row['profit']}")
print(f"eps: {row['eps']}")
print(f"bvps: {row['bvps']}")
print(f"\n補完フラグ:")
print(f"  imputed_op: {row['imputed_op']}")
print(f"  imputed_profit: {row['imputed_profit']}")
print(f"  imputed_equity: {row['imputed_equity']}")
print(f"  imputed_eps: {row['imputed_eps']}")
print(f"  imputed_bvps: {row['imputed_bvps']}")

conn.close()

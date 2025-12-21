#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fins_fy_rawに欠損がある銘柄を探す"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

asof = "2025-12-19"

# fins_fy_rawで欠損がある銘柄を探す
raw_with_missing = pd.read_sql_query("""
    SELECT code, as_of_date, disclosed_date, 
           operating_profit, profit, equity, eps, bvps
    FROM fins_fy_raw
    WHERE as_of_date = ?
      AND (
        operating_profit IS NULL OR profit IS NULL OR equity IS NULL
        OR eps IS NULL OR bvps IS NULL
      )
    LIMIT 5
""", conn, params=(asof,))

print(f"fins_fy_rawに欠損がある銘柄（as_of_date={asof}）:")
print(f"件数: {len(raw_with_missing)}件\n")

for idx, row in raw_with_missing.iterrows():
    missing = []
    if pd.isna(row["operating_profit"]):
        missing.append("operating_profit")
    if pd.isna(row["profit"]):
        missing.append("profit")
    if pd.isna(row["equity"]):
        missing.append("equity")
    if pd.isna(row["eps"]):
        missing.append("eps")
    if pd.isna(row["bvps"]):
        missing.append("bvps")
    
    print(f"銘柄コード: {row['code']}, 開示日: {row['disclosed_date']}")
    print(f"  欠損項目: {', '.join(missing)}")
    print()

conn.close()

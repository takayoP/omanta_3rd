#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
monthly_run実行後の補完処理状況を確認するスクリプト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

print("=== 補完処理の実行状況（最新FYデータ） ===\n")

# 最新基準日の補完前データを確認
latest_date = conn.execute("SELECT MAX(as_of_date) as d FROM fins_fy_raw").fetchone()["d"]
print(f"最新基準日: {latest_date}\n")

# 補完前データの欠損状況
raw_data = pd.read_sql_query("""
    SELECT *
    FROM fins_fy_raw
    WHERE as_of_date = ?
""", conn, params=(latest_date,))

print(f"補完前データの総数: {len(raw_data):,}件\n")

# 各項目の欠損数を確認
print("補完前データの欠損数:")
print(f"  operating_profit: {raw_data['operating_profit'].isna().sum():,}件")
print(f"  profit: {raw_data['profit'].isna().sum():,}件")
print(f"  equity: {raw_data['equity'].isna().sum():,}件")
print(f"  eps: {raw_data['eps'].isna().sum():,}件")
print(f"  bvps: {raw_data['bvps'].isna().sum():,}件")

has_missing = raw_data[
    (raw_data["operating_profit"].isna()) |
    (raw_data["profit"].isna()) |
    (raw_data["equity"].isna()) |
    (raw_data["eps"].isna()) |
    (raw_data["bvps"].isna())
]
print(f"\n欠損があるレコード数: {len(has_missing):,}件")

# 補完後のデータを確認
print("\n=== 補完後のデータ（fins_statements） ===\n")

imputed_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           imputed_op, imputed_profit, imputed_equity, imputed_eps, imputed_bvps,
           operating_profit, profit, equity, eps, bvps
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
           OR imputed_eps = 1 OR imputed_bvps = 1)
""", conn)

print(f"補完されたレコード数: {len(imputed_data):,}件")

if len(imputed_data) > 0:
    print("\n補完された項目の内訳:")
    print(f"  operating_profit (imputed_op): {imputed_data['imputed_op'].sum()}件")
    print(f"  profit (imputed_profit): {imputed_data['imputed_profit'].sum()}件")
    print(f"  equity (imputed_equity): {imputed_data['imputed_equity'].sum()}件")
    print(f"  eps (imputed_eps): {imputed_data['imputed_eps'].sum()}件")
    print(f"  bvps (imputed_bvps): {imputed_data['imputed_bvps'].sum()}件")
    
    print("\n補完されたレコードのサンプル（最初の10件）:")
    for idx, row in imputed_data.head(10).iterrows():
        imputed_items = []
        if row["imputed_op"] == 1:
            imputed_items.append(f"operating_profit={row['operating_profit']}")
        if row["imputed_profit"] == 1:
            imputed_items.append(f"profit={row['profit']}")
        if row["imputed_equity"] == 1:
            imputed_items.append(f"equity={row['equity']}")
        if row["imputed_eps"] == 1:
            imputed_items.append(f"eps={row['eps']}")
        if row["imputed_bvps"] == 1:
            imputed_items.append(f"bvps={row['bvps']}")
        
        print(f"  銘柄コード: {row['code']}, 開示日: {row['disclosed_date']} | 当期末: {row['current_period_end']}")
        print(f"    補完された項目: {', '.join(imputed_items)}")
else:
    print("補完されたレコードはありませんでした。")

conn.close()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完前データの欠損検出が正しくできているか確認するスクリプト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

latest_date = "2025-12-19"

print("=== 補完前データ（fins_fy_raw）の欠損状況の詳細確認 ===\n")

raw_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_fy_raw
    WHERE as_of_date = ?
""", conn, params=(latest_date,))

print(f"補完前データの総数: {len(raw_data):,}件\n")

# 各項目の欠損数を詳細に確認
print("各項目の欠損数:")
for col in ["operating_profit", "profit", "equity", "eps", "bvps"]:
    missing_count = raw_data[col].isna().sum()
    print(f"  {col}: {missing_count}件 ({missing_count/len(raw_data)*100:.1f}%)")

# 欠損の組み合わせを確認
print("\n欠損の組み合わせ:")
has_missing = raw_data[
    (raw_data["operating_profit"].isna()) |
    (raw_data["profit"].isna()) |
    (raw_data["equity"].isna()) |
    (raw_data["eps"].isna()) |
    (raw_data["bvps"].isna())
]
print(f"いずれかの項目が欠損しているレコード: {len(has_missing):,}件\n")

# 補完後のデータを確認
print("=== 補完後のデータ（fins_statements）の状況 ===\n")

imputed_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit, equity, eps, bvps,
           imputed_op, imputed_profit, imputed_equity, imputed_eps, imputed_bvps
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
""", conn)

print(f"補完後のFYデータ総数: {len(imputed_data):,}件\n")

# 補完後の各項目の欠損数を確認
print("補完後の各項目の欠損数:")
for col in ["operating_profit", "profit", "equity", "eps", "bvps"]:
    missing_count = imputed_data[col].isna().sum()
    print(f"  {col}: {missing_count}件 ({missing_count/len(imputed_data)*100:.1f}%)")

# 補完されたレコード数
imputed_count = imputed_data[
    (imputed_data["imputed_op"] == 1) |
    (imputed_data["imputed_profit"] == 1) |
    (imputed_data["imputed_equity"] == 1) |
    (imputed_data["imputed_eps"] == 1) |
    (imputed_data["imputed_bvps"] == 1)
]
print(f"\n補完されたレコード数: {len(imputed_count):,}件")

# 補完前と補完後で欠損が減ったか確認
print("\n=== 補完による改善状況 ===")
raw_missing = raw_data[
    (raw_data["operating_profit"].isna()) |
    (raw_data["profit"].isna()) |
    (raw_data["equity"].isna()) |
    (raw_data["eps"].isna()) |
    (raw_data["bvps"].isna())
]
imputed_missing = imputed_data[
    (imputed_data["operating_profit"].isna()) |
    (imputed_data["profit"].isna()) |
    (imputed_data["equity"].isna()) |
    (imputed_data["eps"].isna()) |
    (imputed_data["bvps"].isna())
]

print(f"補完前の欠損レコード数: {len(raw_missing):,}件")
print(f"補完後の欠損レコード数: {len(imputed_missing):,}件")
print(f"改善されたレコード数: {len(raw_missing) - len(imputed_missing):,}件")

conn.close()

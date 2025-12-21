#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fins_statementsテーブルの欠損値状況を確認するスクリプト
"""
import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

# 総件数
total = conn.execute("SELECT COUNT(*) as cnt FROM fins_statements").fetchone()["cnt"]
print(f"総件数: {total:,}")

# 主キー部分の欠損確認
print("\n=== 主キー部分の欠損確認 ===")
pk_null = conn.execute("""
    SELECT 
        COUNT(*) as cnt,
        SUM(CASE WHEN disclosed_date IS NULL THEN 1 ELSE 0 END) as null_disclosed_date,
        SUM(CASE WHEN code IS NULL OR code = '' THEN 1 ELSE 0 END) as null_code,
        SUM(CASE WHEN type_of_current_period IS NULL THEN 1 ELSE 0 END) as null_type,
        SUM(CASE WHEN current_period_end IS NULL THEN 1 ELSE 0 END) as null_period_end
    FROM fins_statements
""").fetchone()

print(f"  disclosed_dateがNULL: {pk_null['null_disclosed_date']:,}件")
print(f"  codeがNULL/空: {pk_null['null_code']:,}件")
print(f"  type_of_current_periodがNULL: {pk_null['null_type']:,}件")
print(f"  current_period_endがNULL: {pk_null['null_period_end']:,}件")

# 数値カラムの欠損状況
print("\n=== 実績データの欠損状況 ===")
actual_cols = ["operating_profit", "profit", "equity", "eps", "bvps"]
for col in actual_cols:
    null_cnt = conn.execute(f"SELECT COUNT(*) as cnt FROM fins_statements WHERE {col} IS NULL").fetchone()["cnt"]
    null_pct = (null_cnt / total * 100) if total > 0 else 0
    print(f"  {col}: {null_cnt:,}件 ({null_pct:.1f}%)")

print("\n=== 予想データの欠損状況 ===")
forecast_cols = [
    "forecast_operating_profit", "forecast_profit", "forecast_eps",
    "next_year_forecast_operating_profit", "next_year_forecast_profit", "next_year_forecast_eps"
]
for col in forecast_cols:
    null_cnt = conn.execute(f"SELECT COUNT(*) as cnt FROM fins_statements WHERE {col} IS NULL").fetchone()["cnt"]
    null_pct = (null_cnt / total * 100) if total > 0 else 0
    print(f"  {col}: {null_cnt:,}件 ({null_pct:.1f}%)")

print("\n=== 株数データの欠損状況 ===")
share_cols = ["shares_outstanding", "treasury_shares"]
for col in share_cols:
    null_cnt = conn.execute(f"SELECT COUNT(*) as cnt FROM fins_statements WHERE {col} IS NULL").fetchone()["cnt"]
    null_pct = (null_cnt / total * 100) if total > 0 else 0
    print(f"  {col}: {null_cnt:,}件 ({null_pct:.1f}%)")

# type_of_current_periodがNULLのサンプル
print("\n=== type_of_current_periodがNULLのサンプル ===")
null_type_samples = conn.execute("""
    SELECT disclosed_date, code, type_of_current_period, current_period_end,
           operating_profit, profit, forecast_operating_profit, forecast_profit
    FROM fins_statements
    WHERE type_of_current_period IS NULL
    LIMIT 10
""").fetchall()

if null_type_samples:
    for row in null_type_samples:
        print(f"  {row['disclosed_date']} | {row['code']} | type={row['type_of_current_period']} | end={row['current_period_end']}")
else:
    print("  該当なし")

# current_period_endがNULLのサンプル
print("\n=== current_period_endがNULLのサンプル ===")
null_end_samples = conn.execute("""
    SELECT disclosed_date, code, type_of_current_period, current_period_end
    FROM fins_statements
    WHERE current_period_end IS NULL
    LIMIT 10
""").fetchall()

if null_end_samples:
    for row in null_end_samples:
        print(f"  {row['disclosed_date']} | {row['code']} | type={row['type_of_current_period']} | end={row['current_period_end']}")
else:
    print("  該当なし")

# 主キーが完全にNULLの行（保存できないはず）
print("\n=== 主キーが不完全な行の確認 ===")
incomplete_pk = conn.execute("""
    SELECT COUNT(*) as cnt
    FROM fins_statements
    WHERE disclosed_date IS NULL 
       OR code IS NULL OR code = ''
       OR type_of_current_period IS NULL
       OR current_period_end IS NULL
""").fetchone()["cnt"]
print(f"  主キーが不完全な行: {incomplete_pk:,}件")

conn.close()

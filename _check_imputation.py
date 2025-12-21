#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完処理の実行状況を確認するスクリプト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

# 補完フラグが設定されているFY行の数を確認
print("=== 補完処理の実行状況 ===\n")

# 補完フラグが1のレコード数を確認
imputed_counts = conn.execute("""
    SELECT 
        SUM(CASE WHEN imputed_op = 1 THEN 1 ELSE 0 END) as imputed_op_count,
        SUM(CASE WHEN imputed_profit = 1 THEN 1 ELSE 0 END) as imputed_profit_count,
        SUM(CASE WHEN imputed_equity = 1 THEN 1 ELSE 0 END) as imputed_equity_count,
        SUM(CASE WHEN imputed_eps = 1 THEN 1 ELSE 0 END) as imputed_eps_count,
        SUM(CASE WHEN imputed_bvps = 1 THEN 1 ELSE 0 END) as imputed_bvps_count,
        COUNT(*) as total_fy_rows
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
""").fetchone()

print(f"FY行の総数: {imputed_counts['total_fy_rows']:,}")
print(f"\n補完された項目数:")
print(f"  operating_profit (imputed_op): {imputed_counts['imputed_op_count']:,}件")
print(f"  profit (imputed_profit): {imputed_counts['imputed_profit_count']:,}件")
print(f"  equity (imputed_equity): {imputed_counts['imputed_equity_count']:,}件")
print(f"  eps (imputed_eps): {imputed_counts['imputed_eps_count']:,}件")
print(f"  bvps (imputed_bvps): {imputed_counts['imputed_bvps_count']:,}件")

# 補完されたレコードのサンプルを表示
print("\n=== 補完されたレコードのサンプル ===")
imputed_samples = conn.execute("""
    SELECT code, disclosed_date, current_period_end,
           imputed_op, imputed_profit, imputed_equity, imputed_eps, imputed_bvps,
           operating_profit, profit, equity, eps, bvps
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
           OR imputed_eps = 1 OR imputed_bvps = 1)
    LIMIT 10
""").fetchall()

if imputed_samples:
    for row in imputed_samples:
        print(f"\n銘柄コード: {row['code']}")
        print(f"  開示日: {row['disclosed_date']} | 当期末: {row['current_period_end']}")
        flags = []
        if row['imputed_op']:
            flags.append(f"operating_profit={row['operating_profit']:.0f}")
        if row['imputed_profit']:
            flags.append(f"profit={row['profit']:.0f}")
        if row['imputed_equity']:
            flags.append(f"equity={row['equity']:.0f}")
        if row['imputed_eps']:
            flags.append(f"eps={row['eps']:.2f}")
        if row['imputed_bvps']:
            flags.append(f"bvps={row['bvps']:.2f}")
        print(f"  補完された項目: {', '.join(flags)}")
else:
    print("  補完されたレコードはありません")

# fins_fy_rawテーブルの件数
print("\n=== 補完前データの保存状況 ===")
raw_count = conn.execute("SELECT COUNT(*) as cnt FROM fins_fy_raw").fetchone()["cnt"]
print(f"fins_fy_rawテーブルのレコード数: {raw_count:,}")

if raw_count > 0:
    # 最新のas_of_date
    latest_date = conn.execute("SELECT MAX(as_of_date) as d FROM fins_fy_raw").fetchone()["d"]
    print(f"最新の基準日: {latest_date}")
    
    # 最新の基準日でのレコード数
    latest_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM fins_fy_raw WHERE as_of_date = ?",
        (latest_date,)
    ).fetchone()["cnt"]
    print(f"最新基準日のレコード数: {latest_count:,}")

conn.close()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fins_statementsテーブルの汚染状況を確認
補完フラグが立っているデータを確認し、問題があれば報告
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

print("=== fins_statementsテーブルの補完データ確認 ===\n")

# 補完フラグが立っているレコードを確認
imputed_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end, type_of_current_period,
           operating_profit, profit, equity, eps, bvps,
           imputed_op, imputed_profit, imputed_equity, imputed_eps, imputed_bvps
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
           OR imputed_eps = 1 OR imputed_bvps = 1)
    ORDER BY disclosed_date DESC
    LIMIT 20
""", conn)

print(f"補完フラグが立っているFYレコード数: {len(imputed_data)}件\n")

if len(imputed_data) > 0:
    print("補完された項目の内訳:")
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
        
        print(f"  銘柄コード: {row['code']}, 開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
        print(f"    補完された項目: {', '.join(imputed_items)}")
else:
    print("補完フラグが立っているレコードはありません。")

# 全体的な統計
print("\n" + "="*60)
print("全体的な統計\n")

total_fy = pd.read_sql_query("""
    SELECT COUNT(*) as cnt
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
""", conn).iloc[0]['cnt']

print(f"FYレコード総数: {total_fy:,}件")

# 補完フラグの統計
flag_stats = pd.read_sql_query("""
    SELECT 
        SUM(imputed_op) as op_count,
        SUM(imputed_profit) as profit_count,
        SUM(imputed_equity) as equity_count,
        SUM(imputed_eps) as eps_count,
        SUM(imputed_bvps) as bvps_count
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
""", conn)

print(f"\n補完フラグの統計:")
print(f"  imputed_op: {flag_stats.iloc[0]['op_count']}件")
print(f"  imputed_profit: {flag_stats.iloc[0]['profit_count']}件")
print(f"  imputed_equity: {flag_stats.iloc[0]['equity_count']}件")
print(f"  imputed_eps: {flag_stats.iloc[0]['eps_count']}件")
print(f"  imputed_bvps: {flag_stats.iloc[0]['bvps_count']}件")

print("\n" + "="*60)
print("【判断】")
print("以前の実装では、四半期データの実績データ（累計値）も使用して補完していました。")
print("これらはFYデータ（通期）の補完には不適切です。")
print("予想データのみを使用する現在の実装では、補完件数が減る可能性があります。")
print("データの整合性を保つために、再取得を推奨します。")

conn.close()

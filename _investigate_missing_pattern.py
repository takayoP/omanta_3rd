#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FYレコードの欠損パターンを調査
会計基準変更などで古い決算日のデータがNullに書き換えられているかを確認
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

asof = "2025-12-19"

print("=== FYレコードの欠損パターン調査 ===\n")

# 同じcurrent_period_endで複数のdisclosed_dateがあるケースで、欠損値があるものを調査
print("【ケース1】同じcurrent_period_endで複数のdisclosed_dateがある場合の欠損状況\n")

duplicate_periods = pd.read_sql_query("""
    SELECT code, current_period_end, COUNT(*) as cnt
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND disclosed_date <= ?
    GROUP BY code, current_period_end
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC, code, current_period_end
    LIMIT 5
""", conn, params=(asof,))

for idx, dup_row in duplicate_periods.iterrows():
    code = dup_row["code"]
    period_end = dup_row["current_period_end"]
    
    fy_data = pd.read_sql_query("""
        SELECT disclosed_date, operating_profit, profit, equity, eps, bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND current_period_end = ?
          AND disclosed_date <= ?
        ORDER BY disclosed_date
    """, conn, params=(code, period_end, asof))
    
    print(f"銘柄コード: {code}, 当期末: {period_end} ({dup_row['cnt']}件)")
    for _, row in fy_data.iterrows():
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
        
        missing_str = f" (欠損: {', '.join(missing)})" if missing else ""
        print(f"  開示日: {row['disclosed_date']}{missing_str}")
    print()

print("="*60)
print("【ケース2】欠損があるFYレコードの開示日と当期末の関係\n")

missing_fy = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           CASE 
             WHEN operating_profit IS NULL THEN 1 ELSE 0 END as missing_op,
           CASE 
             WHEN profit IS NULL THEN 1 ELSE 0 END as missing_profit,
           CASE 
             WHEN equity IS NULL THEN 1 ELSE 0 END as missing_equity,
           CASE 
             WHEN eps IS NULL THEN 1 ELSE 0 END as missing_eps,
           CASE 
             WHEN bvps IS NULL THEN 1 ELSE 0 END as missing_bvps
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND disclosed_date <= ?
      AND (
        operating_profit IS NULL OR profit IS NULL OR equity IS NULL
        OR eps IS NULL OR bvps IS NULL
      )
    ORDER BY code, current_period_end, disclosed_date
    LIMIT 20
""", conn, params=(asof,))

if len(missing_fy) > 0:
    print(f"欠損があるFYレコード（最初の20件）:\n")
    for _, row in missing_fy.iterrows():
        missing = []
        if row["missing_op"] == 1:
            missing.append("operating_profit")
        if row["missing_profit"] == 1:
            missing.append("profit")
        if row["missing_equity"] == 1:
            missing.append("equity")
        if row["missing_eps"] == 1:
            missing.append("eps")
        if row["missing_bvps"] == 1:
            missing.append("bvps")
        
        print(f"  銘柄コード: {row['code']}, "
              f"開示日: {row['disclosed_date']}, "
              f"当期末: {row['current_period_end']}, "
              f"欠損: {', '.join(missing)}")
    
    # 同じcodeで、同じcurrent_period_endで欠損があるものとないものを比較
    print("\n" + "="*60)
    print("【ケース3】同じcode、同じcurrent_period_endで欠損があるものとないものの比較\n")
    
    sample_code = missing_fy.iloc[0]["code"]
    sample_period = missing_fy.iloc[0]["current_period_end"]
    
    same_period_all = pd.read_sql_query("""
        SELECT disclosed_date, operating_profit, profit, equity, eps, bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND current_period_end = ?
          AND disclosed_date <= ?
        ORDER BY disclosed_date
    """, conn, params=(sample_code, sample_period, asof))
    
    print(f"サンプル: 銘柄コード {sample_code}, 当期末 {sample_period}")
    for _, row in same_period_all.iterrows():
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
        
        missing_str = f" (欠損: {', '.join(missing)})" if missing else ""
        op_str = f"{row['operating_profit']:,.0f}" if pd.notna(row["operating_profit"]) else "NaN"
        print(f"  開示日: {row['disclosed_date']}, operating_profit: {op_str}{missing_str}")
    
    print("\n→ もし古い開示日のデータがNULLに書き換えられている場合、")
    print("  開示日が古いものほど欠損が多いパターンが見られるはずです。")

print("\n" + "="*60)
print("調査完了")

conn.close()

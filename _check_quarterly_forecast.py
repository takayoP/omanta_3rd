#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
四半期データの予想データの存在を確認するスクリプト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

latest_date = "2025-12-19"

# 四半期データに予想データが含まれているか確認
print("=== 四半期データの予想データの存在確認 ===\n")

# サンプルとして、補完されなかった銘柄の四半期データを確認
sample_codes = ["2282", "2389", "2651"]

for code in sample_codes:
    print(f"銘柄コード: {code}")
    
    # 四半期データを取得（予想データカラムも含む）
    quarterly = pd.read_sql_query("""
        SELECT disclosed_date, type_of_current_period, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               forecast_operating_profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period IN ('3Q', '2Q', '1Q')
          AND disclosed_date <= ?
        ORDER BY disclosed_date DESC, type_of_current_period
        LIMIT 5
    """, conn, params=(code, latest_date))
    
    if quarterly.empty:
        print(f"  四半期データが存在しません\n")
        continue
    
    print(f"  四半期データ件数: {len(quarterly)}件（最新5件を表示）\n")
    
    for idx, row in quarterly.iterrows():
        print(f"  [{idx}] {row['type_of_current_period']}, 開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
        print(f"      実績 operating_profit: {row['operating_profit']} (isna: {pd.isna(row['operating_profit'])})")
        print(f"      予想 forecast_operating_profit: {row['forecast_operating_profit']} (isna: {pd.isna(row['forecast_operating_profit'])})")
        print(f"      実績 profit: {row['profit']} (isna: {pd.isna(row['profit'])})")
        print(f"      予想 forecast_profit: {row['forecast_profit']} (isna: {pd.isna(row['forecast_profit'])})")
        print(f"      実績 eps: {row['eps']} (isna: {pd.isna(row['eps'])})")
        print(f"      予想 forecast_eps: {row['forecast_eps']} (isna: {pd.isna(row['forecast_eps'])})")
        print()
    
    print()

# 全体的な統計も確認
print("\n=== 四半期データ全体の予想データの欠損状況 ===\n")

quarterly_all = pd.read_sql_query("""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(operating_profit) as has_op_actual,
        COUNT(forecast_operating_profit) as has_op_forecast,
        COUNT(profit) as has_profit_actual,
        COUNT(forecast_profit) as has_profit_forecast,
        COUNT(eps) as has_eps_actual,
        COUNT(forecast_eps) as has_eps_forecast
    FROM fins_statements
    WHERE type_of_current_period IN ('3Q', '2Q', '1Q')
      AND disclosed_date <= ?
""", conn, params=(latest_date,))

print(f"四半期データ総数: {quarterly_all.iloc[0]['total_rows']:,}件")
print(f"operating_profit 実績あり: {quarterly_all.iloc[0]['has_op_actual']:,}件")
print(f"operating_profit 予想あり: {quarterly_all.iloc[0]['has_op_forecast']:,}件")
print(f"profit 実績あり: {quarterly_all.iloc[0]['has_profit_actual']:,}件")
print(f"profit 予想あり: {quarterly_all.iloc[0]['has_profit_forecast']:,}件")
print(f"eps 実績あり: {quarterly_all.iloc[0]['has_eps_actual']:,}件")
print(f"eps 予想あり: {quarterly_all.iloc[0]['has_eps_forecast']:,}件")

conn.close()

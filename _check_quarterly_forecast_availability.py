#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FY開示日より前の四半期データの予想データがどのくらい利用可能か確認
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

latest_date = "2025-12-19"

# 補完前データに欠損があるレコードを取得
raw_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_fy_raw
    WHERE as_of_date = ?
      AND (
        operating_profit IS NULL OR profit IS NULL OR equity IS NULL
        OR eps IS NULL OR bvps IS NULL
      )
""", conn, params=(latest_date,))

print(f"補完前データに欠損があるレコード数: {len(raw_data):,}件\n")

# サンプルとして、欠損があるレコードのうち、operating_profitが欠損しているものを確認
sample_missing = raw_data[raw_data["operating_profit"].isna()].head(10)

print("=== サンプル銘柄の四半期予想データの利用可能性確認 ===\n")

for idx, row in sample_missing.iterrows():
    code = row["code"]
    fy_disclosed = row["disclosed_date"]
    
    print(f"銘柄コード: {code}, FY開示日: {fy_disclosed}")
    
    # FY開示日より前の四半期データを取得
    quarterly = pd.read_sql_query("""
        SELECT disclosed_date, type_of_current_period, current_period_end,
               operating_profit, forecast_operating_profit,
               profit, forecast_profit,
               equity, eps, forecast_eps, bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period IN ('3Q', '2Q', '1Q')
          AND disclosed_date < ?
        ORDER BY disclosed_date DESC, type_of_current_period
    """, conn, params=(code, fy_disclosed))
    
    if quarterly.empty:
        print(f"  → 四半期データが存在しません\n")
        continue
    
    print(f"  → 四半期データ: {len(quarterly)}件")
    
    # 最新の5件を確認
    print(f"  最新5件の詳細:")
    for q_idx, q_row in quarterly.head(5).iterrows():
        has_op_actual = pd.notna(q_row.get("operating_profit"))
        has_op_forecast = pd.notna(q_row.get("forecast_operating_profit"))
        has_eps_actual = pd.notna(q_row.get("eps"))
        has_eps_forecast = pd.notna(q_row.get("forecast_eps"))
        
        print(f"    {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}")
        print(f"      operating_profit: 実績={has_op_actual}, 予想={has_op_forecast}")
        print(f"      eps: 実績={has_eps_actual}, 予想={has_eps_forecast}")
    
    # 予想データがある最新の四半期データを探す
    if pd.isna(row["operating_profit"]):
        # operating_profitの予想データまたは実績データがあるか
        q_with_data = quarterly[
            quarterly["operating_profit"].notna() | quarterly["forecast_operating_profit"].notna()
        ]
        if not q_with_data.empty:
            latest_with_data = q_with_data.iloc[0]
            if pd.notna(latest_with_data["operating_profit"]):
                print(f"  → operating_profitの実績データがある最新: {latest_with_data['type_of_current_period']}, 開示日: {latest_with_data['disclosed_date']}, 値: {latest_with_data['operating_profit']}")
            elif pd.notna(latest_with_data["forecast_operating_profit"]):
                print(f"  → operating_profitの予想データがある最新: {latest_with_data['type_of_current_period']}, 開示日: {latest_with_data['disclosed_date']}, 値: {latest_with_data['forecast_operating_profit']}")
        else:
            print(f"  → operating_profitのデータ（実績・予想とも）は見つかりませんでした")
    
    print()

conn.close()

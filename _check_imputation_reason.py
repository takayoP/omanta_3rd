#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完されなかった理由を詳細に調査するスクリプト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

latest_date = "2025-12-19"

# 補完前データに欠損があるが、補完されなかったレコードを取得
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

# 補完されたコードを取得
imputed_codes = set(pd.read_sql_query("""
    SELECT DISTINCT code
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
           OR imputed_eps = 1 OR imputed_bvps = 1)
""", conn)["code"].astype(str))

# 補完されなかったレコード
not_imputed = raw_data[~raw_data["code"].astype(str).isin(imputed_codes)]
print(f"補完されなかったレコード数: {len(not_imputed):,}件\n")

# サンプルについて、四半期データの存在を確認
print("=== 補完されなかった理由の調査（サンプル5件） ===\n")

for idx, row in not_imputed.head(5).iterrows():
    code = row["code"]
    print(f"銘柄コード: {code}")
    print(f"  FY開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
    
    # 欠損項目を確認
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
    print(f"  欠損項目: {', '.join(missing)}")
    
    # 四半期データを確認
    quarterly = pd.read_sql_query("""
        SELECT disclosed_date, type_of_current_period, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               forecast_operating_profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period IN ('3Q', '2Q', '1Q')
          AND disclosed_date <= ?
        ORDER BY disclosed_date DESC, type_of_current_period
    """, conn, params=(code, latest_date))
    
    if quarterly.empty:
        print(f"  → 四半期データが存在しません")
    else:
        print(f"  → 四半期データ: {len(quarterly)}件")
        # 最新の四半期データを確認
        latest_q = quarterly.iloc[0]
        print(f"    最新四半期: {latest_q['type_of_current_period']}, 開示日: {latest_q['disclosed_date']}, 当期末: {latest_q['current_period_end']}")
        
        # 各欠損項目について、四半期データに値があるか確認
        for item in missing:
            if item == "operating_profit":
                has_actual = pd.notna(latest_q.get("operating_profit"))
                has_forecast = pd.notna(latest_q.get("forecast_operating_profit"))
                print(f"    {item}: 実績={has_actual}, 予想={has_forecast}")
            elif item == "profit":
                has_actual = pd.notna(latest_q.get("profit"))
                has_forecast = pd.notna(latest_q.get("forecast_profit"))
                print(f"    {item}: 実績={has_actual}, 予想={has_forecast}")
            elif item == "eps":
                has_actual = pd.notna(latest_q.get("eps"))
                has_forecast = pd.notna(latest_q.get("forecast_eps"))
                print(f"    {item}: 実績={has_actual}, 予想={has_forecast}")
            elif item in ["equity", "bvps"]:
                has_actual = pd.notna(latest_q.get(item))
                print(f"    {item}: 実績={has_actual}")
    
    print()

conn.close()

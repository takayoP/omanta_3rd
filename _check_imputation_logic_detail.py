#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完ロジックの詳細確認
欠損があるが補完されなかったケースを詳しく調査
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

latest_date = "2025-12-19"

print("=== 補完前データの欠損状況 ===\n")

# 補完前データ
raw_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_fy_raw
    WHERE as_of_date = ?
""", conn, params=(latest_date,))

print(f"補完前データの総数: {len(raw_data):,}件")

# 欠損があるレコード
has_missing = raw_data[
    (raw_data["operating_profit"].isna()) |
    (raw_data["profit"].isna()) |
    (raw_data["equity"].isna()) |
    (raw_data["eps"].isna()) |
    (raw_data["bvps"].isna())
].copy()

print(f"欠損があるレコード数: {len(has_missing):,}件\n")

# 補完されたレコード
imputed_codes = set(pd.read_sql_query("""
    SELECT DISTINCT code
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
           OR imputed_eps = 1 OR imputed_bvps = 1)
""", conn)["code"].astype(str))

# 補完されなかったレコード
not_imputed = has_missing[~has_missing["code"].astype(str).isin(imputed_codes)]
print(f"補完されなかったレコード数: {len(not_imputed):,}件\n")

# サンプルを詳しく調査
print("=== 補完されなかった理由の詳細調査（サンプル5件） ===\n")

for idx, row in not_imputed.head(5).iterrows():
    code = row["code"]
    fy_disclosed = pd.to_datetime(row["disclosed_date"])
    fy_period_end = pd.to_datetime(row["current_period_end"])
    
    print(f"銘柄コード: {code}")
    print(f"  FY開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
    
    # 欠損項目
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
    
    # FY開示日より前の四半期データを取得
    quarterly = pd.read_sql_query("""
        SELECT disclosed_date, type_of_current_period, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               forecast_operating_profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period IN ('3Q', '2Q', '1Q')
          AND disclosed_date < ?
        ORDER BY disclosed_date DESC, 
                 CASE type_of_current_period 
                   WHEN '3Q' THEN 1 
                   WHEN '2Q' THEN 2 
                   WHEN '1Q' THEN 3 
                 END
        LIMIT 10
    """, conn, params=(code, row["disclosed_date"]))
    
    if quarterly.empty:
        print(f"  → FY開示日より前の四半期データが存在しません")
    else:
        print(f"  → FY開示日より前の四半期データ: {len(quarterly)}件")
        
        # 各欠損項目について、四半期データに値があるか確認
        for item in missing:
            found = False
            for q_idx, q_row in quarterly.iterrows():
                q_disclosed = pd.to_datetime(q_row["disclosed_date"])
                
                if item == "operating_profit":
                    if pd.notna(q_row["operating_profit"]):
                        print(f"    {item}: 実績あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row['operating_profit']})")
                        found = True
                        break
                    elif pd.notna(q_row["forecast_operating_profit"]):
                        print(f"    {item}: 予想あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row['forecast_operating_profit']})")
                        found = True
                        break
                elif item == "profit":
                    if pd.notna(q_row["profit"]):
                        print(f"    {item}: 実績あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row['profit']})")
                        found = True
                        break
                    elif pd.notna(q_row["forecast_profit"]):
                        print(f"    {item}: 予想あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row['forecast_profit']})")
                        found = True
                        break
                elif item == "eps":
                    if pd.notna(q_row["eps"]):
                        print(f"    {item}: 実績あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row['eps']})")
                        found = True
                        break
                    elif pd.notna(q_row["forecast_eps"]):
                        print(f"    {item}: 予想あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row['forecast_eps']})")
                        found = True
                        break
                elif item in ["equity", "bvps"]:
                    if pd.notna(q_row[item]):
                        print(f"    {item}: 実績あり (四半期: {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, 値: {q_row[item]})")
                        found = True
                        break
            
            if not found:
                print(f"    {item}: 四半期データに実績も予想もありません")
    
    print()

conn.close()

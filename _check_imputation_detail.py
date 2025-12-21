#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完処理の詳細を確認するスクリプト
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

# 最新基準日の補完前データを確認
print("=== 最新基準日の補完前データ（fins_fy_raw）の欠損状況 ===\n")

latest_date = conn.execute("SELECT MAX(as_of_date) as d FROM fins_fy_raw").fetchone()["d"]
print(f"最新基準日: {latest_date}\n")

raw_data = pd.read_sql_query("""
    SELECT *
    FROM fins_fy_raw
    WHERE as_of_date = ?
""", conn, params=(latest_date,))

print(f"補完前データの総数: {len(raw_data):,}件\n")

# 各項目の欠損数を確認
print("各項目の欠損数（補完前）:")
print(f"  operating_profit: {raw_data['operating_profit'].isna().sum():,}件")
print(f"  profit: {raw_data['profit'].isna().sum():,}件")
print(f"  equity: {raw_data['equity'].isna().sum():,}件")
print(f"  eps: {raw_data['eps'].isna().sum():,}件")
print(f"  bvps: {raw_data['bvps'].isna().sum():,}件")

# 欠損があるレコードを確認
has_missing = raw_data[
    (raw_data["operating_profit"].isna()) |
    (raw_data["profit"].isna()) |
    (raw_data["equity"].isna()) |
    (raw_data["eps"].isna()) |
    (raw_data["bvps"].isna())
]
print(f"\n欠損があるレコード数: {len(has_missing):,}件")

# 実際に補完されたレコードと比較
print("\n=== 実際に補完されたレコード（fins_statements） ===\n")

imputed_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           imputed_op, imputed_profit, imputed_equity, imputed_eps, imputed_bvps
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
           OR imputed_eps = 1 OR imputed_bvps = 1)
""", conn)

print(f"補完されたレコード数: {len(imputed_data):,}件")

# 補完前データに欠損があるが、補完されなかったレコードを確認
print("\n=== 補完前データに欠損があるが補完されなかったレコード（サンプル） ===\n")

if not has_missing.empty:
    # 補完されたコードのセット
    imputed_codes = set(imputed_data["code"].astype(str))
    
    # 補完されなかったレコード
    not_imputed = has_missing[~has_missing["code"].astype(str).isin(imputed_codes)]
    
    if not not_imputed.empty:
        print(f"補完されなかったレコード数: {len(not_imputed):,}件")
        print("\nサンプル（最初の10件）:")
        for idx, row in not_imputed.head(10).iterrows():
            missing_items = []
            if pd.isna(row["operating_profit"]):
                missing_items.append("operating_profit")
            if pd.isna(row["profit"]):
                missing_items.append("profit")
            if pd.isna(row["equity"]):
                missing_items.append("equity")
            if pd.isna(row["eps"]):
                missing_items.append("eps")
            if pd.isna(row["bvps"]):
                missing_items.append("bvps")
            print(f"  コード: {row['code']}, 欠損項目: {', '.join(missing_items)}")
        
        # 四半期データがあるか確認（サンプル）
        if len(not_imputed) > 0:
            sample_code = not_imputed.iloc[0]["code"]
            quarterly_check = conn.execute("""
                SELECT COUNT(*) as cnt
                FROM fins_statements
                WHERE code = ?
                  AND type_of_current_period IN ('3Q', '2Q', '1Q')
                  AND disclosed_date <= ?
            """, (sample_code, latest_date)).fetchone()["cnt"]
            print(f"\n  サンプルコード {sample_code} の四半期データ件数: {quarterly_check}件")
    else:
        print("全ての欠損レコードが補完されています。")

conn.close()

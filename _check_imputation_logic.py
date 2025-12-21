#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完処理のロジックを詳細に確認するスクリプト
FYの開示日と四半期データの開示日の関係を確認
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

latest_date = "2025-12-19"

# 補完前データに欠損があるが、補完されなかったサンプル銘柄を確認
sample_code = "2282"

print(f"=== 補完処理のロジック確認（銘柄コード: {sample_code}） ===\n")

# FYデータを取得
fy_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_fy_raw
    WHERE as_of_date = ?
      AND code = ?
""", conn, params=(latest_date, sample_code))

if fy_data.empty:
    print("FYデータが見つかりません")
    conn.close()
    exit()

fy_row = fy_data.iloc[0]
fy_disclosed = fy_row["disclosed_date"]
fy_period_end = fy_row["current_period_end"]

print(f"FYデータ:")
print(f"  開示日: {fy_disclosed}")
print(f"  当期末: {fy_period_end}")
print(f"  欠損項目: ", end="")
missing = []
if pd.isna(fy_row["operating_profit"]):
    missing.append("operating_profit")
if pd.isna(fy_row["profit"]):
    missing.append("profit")
if pd.isna(fy_row["equity"]):
    missing.append("equity")
if pd.isna(fy_row["eps"]):
    missing.append("eps")
if pd.isna(fy_row["bvps"]):
    missing.append("bvps")
print(", ".join(missing) if missing else "なし")
print()

# 現在の補完ロジック（disclosed_date <= asof）で取得される四半期データ
quarterly_current = pd.read_sql_query("""
    SELECT disclosed_date, type_of_current_period, current_period_end,
           operating_profit, forecast_operating_profit,
           profit, forecast_profit,
           equity, eps, forecast_eps, bvps
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period IN ('3Q', '2Q', '1Q')
      AND disclosed_date <= ?
    ORDER BY disclosed_date DESC, type_of_current_period
""", conn, params=(sample_code, latest_date))

print(f"現在のロジック（disclosed_date <= {latest_date}）で取得される四半期データ: {len(quarterly_current)}件")
if not quarterly_current.empty:
    latest_q = quarterly_current.iloc[0]
    print(f"  最新: {latest_q['type_of_current_period']}, 開示日: {latest_q['disclosed_date']}, 当期末: {latest_q['current_period_end']}")
    if "operating_profit" in missing:
        print(f"    operating_profit 実績: {latest_q['operating_profit']} (isna: {pd.isna(latest_q['operating_profit'])})")
        print(f"    operating_profit 予想: {latest_q['forecast_operating_profit']} (isna: {pd.isna(latest_q['forecast_operating_profit'])})")
print()

# FY開示日より前の四半期データ（より適切な補完候補）
quarterly_before_fy = pd.read_sql_query("""
    SELECT disclosed_date, type_of_current_period, current_period_end,
           operating_profit, forecast_operating_profit,
           profit, forecast_profit,
           equity, eps, forecast_eps, bvps
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period IN ('3Q', '2Q', '1Q')
      AND disclosed_date <= ?
    ORDER BY disclosed_date DESC, type_of_current_period
""", conn, params=(sample_code, fy_disclosed))

print(f"FY開示日（{fy_disclosed}）より前の四半期データ: {len(quarterly_before_fy)}件")
if not quarterly_before_fy.empty:
    print(f"  最新5件:")
    for idx, row in quarterly_before_fy.head(5).iterrows():
        print(f"    [{idx}] {row['type_of_current_period']}, 開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
        if "operating_profit" in missing:
            print(f"       operating_profit 実績: {row['operating_profit']} (isna: {pd.isna(row['operating_profit'])})")
            print(f"       operating_profit 予想: {row['forecast_operating_profit']} (isna: {pd.isna(row['forecast_operating_profit'])})")
print()

# より広範囲に検索（当期末がFYの当期末より前の四半期データ）
quarterly_by_period = pd.read_sql_query("""
    SELECT disclosed_date, type_of_current_period, current_period_end,
           operating_profit, forecast_operating_profit,
           profit, forecast_profit,
           equity, eps, forecast_eps, bvps
    FROM fins_statements
    WHERE code = ?
      AND type_of_current_period IN ('3Q', '2Q', '1Q')
      AND current_period_end < ?
      AND disclosed_date <= ?
    ORDER BY current_period_end DESC, disclosed_date DESC
""", conn, params=(sample_code, fy_period_end, fy_disclosed))

print(f"FY当期末（{fy_period_end}）より前の四半期データで、FY開示日（{fy_disclosed}）以前に開示されたもの: {len(quarterly_by_period)}件")
if not quarterly_by_period.empty:
    print(f"  最新5件:")
    for idx, row in quarterly_by_period.head(5).iterrows():
        print(f"    [{idx}] {row['type_of_current_period']}, 開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
        if "operating_profit" in missing:
            print(f"       operating_profit 実績: {row['operating_profit']} (isna: {pd.isna(row['operating_profit'])})")
            print(f"       operating_profit 予想: {row['forecast_operating_profit']} (isna: {pd.isna(row['forecast_operating_profit'])})")

conn.close()

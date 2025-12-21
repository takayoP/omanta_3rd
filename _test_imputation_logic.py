#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完ロジックを実際にテストするスクリプト
"""

import sys
from pathlib import Path
import pandas as pd
import sqlite3

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db

# テスト対象の銘柄コード
test_code = "2130"  # equityが補完されるべきケース

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

# FYデータを取得
fy_data = pd.read_sql_query("""
    SELECT code, disclosed_date, current_period_end,
           operating_profit, profit, equity, eps, bvps
    FROM fins_fy_raw
    WHERE as_of_date = '2025-12-19'
      AND code = ?
""", conn, params=(test_code,))

if fy_data.empty:
    print(f"FYデータが見つかりません: {test_code}")
    sys.exit(1)

fy_row = fy_data.iloc[0]
fy_disclosed = fy_row["disclosed_date"]

print(f"=== テスト対象: 銘柄コード {test_code} ===")
print(f"FY開示日: {fy_disclosed}")
print(f"FY当期末: {fy_row['current_period_end']}")
print(f"欠損項目: ", end="")
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

# 四半期データを取得（monthly_run.pyと同じロジック）
asof = "2025-12-19"
quarterly = pd.read_sql_query("""
    SELECT code, disclosed_date, type_of_current_period, current_period_end,
           operating_profit, profit, equity, eps, bvps,
           forecast_operating_profit, forecast_profit, forecast_eps
    FROM fins_statements
    WHERE disclosed_date <= ?
      AND type_of_current_period IN ('3Q', '2Q', '1Q')
      AND code = ?
""", conn, params=(asof, test_code))

print(f"四半期データ総数（asof <= {asof}）: {len(quarterly)}件")

if quarterly.empty:
    print("四半期データが存在しません")
    sys.exit(1)

quarterly["disclosed_date"] = pd.to_datetime(quarterly["disclosed_date"], errors="coerce")
quarterly["period_priority"] = quarterly["type_of_current_period"].map({"3Q": 1, "2Q": 2, "1Q": 3})

# FY開示日より前のデータをフィルタ
fy_disclosed_dt = pd.to_datetime(fy_disclosed, errors="coerce")
q_data = quarterly[
    (quarterly["code"] == test_code) &
    (quarterly["disclosed_date"] < fy_disclosed_dt)
].copy()

print(f"FY開示日（{fy_disclosed}）より前の四半期データ: {len(q_data)}件")
print()

if q_data.empty:
    print("FY開示日より前の四半期データが存在しません")
    sys.exit(1)

# ソート
q_data = q_data.sort_values(["disclosed_date", "period_priority"], ascending=[False, True])

print("FY開示日より前の四半期データ（新しい順）:")
for idx, row in q_data.head(10).iterrows():
    print(f"  {row['type_of_current_period']}, 開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}")
    if "equity" in missing:
        print(f"    equity: {row['equity']} (isna: {pd.isna(row['equity'])})")
    if "operating_profit" in missing:
        print(f"    operating_profit 実績: {row['operating_profit']} (isna: {pd.isna(row['operating_profit'])})")
        print(f"    operating_profit 予想: {row['forecast_operating_profit']} (isna: {pd.isna(row['forecast_operating_profit'])})")
print()

# 補完ロジックをシミュレート
if "equity" in missing:
    print("equityの補完テスト:")
    for idx, q_row in q_data.iterrows():
        if pd.notna(q_row["equity"]):
            print(f"  → 補完可能: 四半期 {q_row['type_of_current_period']}, 開示日 {q_row['disclosed_date']}, 値: {q_row['equity']}")
            break
    else:
        print("  → 補完不可能（全て欠損）")

if "operating_profit" in missing:
    print("operating_profitの補完テスト:")
    for idx, q_row in q_data.iterrows():
        if pd.notna(q_row["operating_profit"]):
            print(f"  → 補完可能（実績）: 四半期 {q_row['type_of_current_period']}, 開示日 {q_row['disclosed_date']}, 値: {q_row['operating_profit']}")
            break
        elif pd.notna(q_row["forecast_operating_profit"]):
            print(f"  → 補完可能（予想）: 四半期 {q_row['type_of_current_period']}, 開示日 {q_row['disclosed_date']}, 値: {q_row['forecast_operating_profit']}")
            break
    else:
        print("  → 補完不可能（全て欠損）")

conn.close()

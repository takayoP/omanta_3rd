#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特定の銘柄コードについて補完処理をシミュレート
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
test_code = "2130"

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

# _load_latest_fyと同じ条件でFYデータを取得
asof = "2025-12-19"
df = pd.read_sql_query("""
    SELECT *
    FROM fins_statements
    WHERE disclosed_date <= ?
      AND type_of_current_period = 'FY'
      AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL)
      AND code = ?
""", conn, params=(asof, test_code))

if df.empty:
    print(f"FYデータが見つかりません: {test_code}")
    sys.exit(1)

df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
df = df.sort_values(["code", "disclosed_date", "current_period_end"])
latest = df.groupby("code", as_index=False).tail(1).copy()

print(f"=== テスト対象: 銘柄コード {test_code} ===")
print(f"最新FYデータ:")
for col in ["code", "disclosed_date", "current_period_end", "operating_profit", "profit", "equity", "eps", "bvps"]:
    print(f"  {col}: {latest.iloc[0][col]}")

row = latest.iloc[0]

# 補完処理をシミュレート
# 1. needs_fillの判定
needs_fill = latest[
    (latest["operating_profit"].isna()) |
    (latest["profit"].isna()) |
    (latest["equity"].isna()) |
    (latest["eps"].isna()) |
    (latest["bvps"].isna())
]["code"].unique()

print(f"\nneeds_fill: {needs_fill}")
print(f"code in needs_fill: {row['code'] in needs_fill}")

if len(needs_fill) == 0:
    print("補完が必要なコードがありません")
    sys.exit(0)

# 2. 四半期データを取得
quarterly = pd.read_sql_query("""
    SELECT code, disclosed_date, type_of_current_period, current_period_end,
           operating_profit, profit, equity, eps, bvps,
           forecast_operating_profit, forecast_profit, forecast_eps
    FROM fins_statements
    WHERE disclosed_date <= ?
      AND type_of_current_period IN ('3Q', '2Q', '1Q')
      AND code IN ({})
""".format(",".join("?" * len(needs_fill))),
    conn,
    params=(asof,) + tuple(needs_fill),
)

print(f"\n四半期データ総数: {len(quarterly)}件")

if quarterly.empty:
    print("四半期データが存在しません")
    sys.exit(0)

quarterly["disclosed_date"] = pd.to_datetime(quarterly["disclosed_date"], errors="coerce")
quarterly["period_priority"] = quarterly["type_of_current_period"].map({"3Q": 1, "2Q": 2, "1Q": 3})

# 3. FYデータをコピー
result = latest.copy()
result["disclosed_date"] = pd.to_datetime(result["disclosed_date"], errors="coerce")

# 補完フラグを初期化
result["imputed_op"] = 0
result["imputed_profit"] = 0
result["imputed_equity"] = 0
result["imputed_eps"] = 0
result["imputed_bvps"] = 0

# 4. 補完処理
code = row["code"]
if code not in needs_fill:
    print(f"\nコード {code} は needs_fill に含まれていません")
else:
    print(f"\nコード {code} は needs_fill に含まれています")
    
    fy_disclosed = row["disclosed_date"]
    print(f"FY開示日: {fy_disclosed} (type: {type(fy_disclosed)})")
    
    if pd.isna(fy_disclosed):
        print("FY開示日がNaNです")
    else:
        q_data = quarterly[
            (quarterly["code"] == code) &
            (quarterly["disclosed_date"] < fy_disclosed)
        ].copy()
        
        print(f"FY開示日より前の四半期データ: {len(q_data)}件")
        
        if q_data.empty:
            print("FY開示日より前の四半期データが存在しません")
        else:
            q_data = q_data.sort_values(["disclosed_date", "period_priority"], ascending=[False, True])
            print("\nFY開示日より前の四半期データ（新しい順、最初の5件）:")
            for idx, q_row in q_data.head(5).iterrows():
                print(f"  {q_row['type_of_current_period']}, 開示日: {q_row['disclosed_date']}, equity: {q_row['equity']} (isna: {pd.isna(q_row['equity'])})")
            
            # equityの補完をテスト
            if pd.isna(row["equity"]):
                print("\nequityの補完テスト:")
                found = False
                for idx, q_row in q_data.iterrows():
                    print(f"  チェック: 四半期 {q_row['type_of_current_period']}, 開示日 {q_row['disclosed_date']}, equity: {q_row['equity']} (isna: {pd.isna(q_row['equity'])})")
                    if pd.notna(q_row["equity"]):
                        print(f"  → 補完可能！値: {q_row['equity']}")
                        found = True
                        break
                if not found:
                    print("  → 補完不可能")
            else:
                print("\nequityは欠損していません")

conn.close()

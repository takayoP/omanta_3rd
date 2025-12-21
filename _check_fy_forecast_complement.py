#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
同じcurrent_period_endのFYデータで、operating_profitとforecast_operating_profitの
相互補完の可能性を調査
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect("data/db/jquants.sqlite")
conn.row_factory = sqlite3.Row

asof = "2025-12-19"

print("=== 同じcurrent_period_endのFYデータの相互補完可能性調査 ===\n")

# 同じcurrent_period_endで複数のFYレコードがあるケースを調査
print("【ケース1】同じcurrent_period_endで複数のFYレコードがある場合\n")

duplicate_periods = pd.read_sql_query("""
    SELECT code, current_period_end, COUNT(*) as cnt
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND disclosed_date <= ?
    GROUP BY code, current_period_end
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC, code, current_period_end
    LIMIT 10
""", conn, params=(asof,))

complement_candidates = []

for idx, dup_row in duplicate_periods.iterrows():
    code = dup_row["code"]
    period_end = dup_row["current_period_end"]
    
    fy_data = pd.read_sql_query("""
        SELECT disclosed_date, operating_profit, profit, 
               forecast_operating_profit, forecast_profit, forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND current_period_end = ?
          AND disclosed_date <= ?
        ORDER BY disclosed_date
    """, conn, params=(code, period_end, asof))
    
    # 相互補完の可能性をチェック
    has_op = fy_data["operating_profit"].notna().any()
    has_forecast_op = fy_data["forecast_operating_profit"].notna().any()
    has_profit = fy_data["profit"].notna().any()
    has_forecast_profit = fy_data["forecast_profit"].notna().any()
    has_forecast_eps = fy_data["forecast_eps"].notna().any()
    
    # 補完可能なケースを特定
    can_complement_op = has_op and has_forecast_op and not fy_data["operating_profit"].notna().all()
    can_complement_profit = has_profit and has_forecast_profit and not fy_data["profit"].notna().all()
    
    if can_complement_op or can_complement_profit:
        complement_candidates.append({
            "code": code,
            "current_period_end": period_end,
            "count": dup_row["cnt"],
            "can_complement_op": can_complement_op,
            "can_complement_profit": can_complement_profit,
        })
        
        print(f"銘柄コード: {code}, 当期末: {period_end} ({dup_row['cnt']}件)")
        for _, row in fy_data.iterrows():
            op_str = f"{row['operating_profit']:,.0f}" if pd.notna(row["operating_profit"]) else "NULL"
            forecast_op_str = f"{row['forecast_operating_profit']:,.0f}" if pd.notna(row["forecast_operating_profit"]) else "NULL"
            profit_str = f"{row['profit']:,.0f}" if pd.notna(row["profit"]) else "NULL"
            forecast_profit_str = f"{row['forecast_profit']:,.0f}" if pd.notna(row["forecast_profit"]) else "NULL"
            forecast_eps_str = f"{row['forecast_eps']:.2f}" if pd.notna(row["forecast_eps"]) else "NULL"
            
            print(f"  開示日: {row['disclosed_date']}")
            print(f"    operating_profit: {op_str}, forecast_operating_profit: {forecast_op_str}")
            print(f"    profit: {profit_str}, forecast_profit: {forecast_profit_str}")
            print(f"    forecast_eps: {forecast_eps_str}")
        print()

print("="*60)
print("【ケース2】現在の_load_latest_forecastで取得されるデータの範囲\n")

# _load_latest_forecastと同じクエリを実行
forecast_data = pd.read_sql_query("""
    SELECT code, disclosed_date, type_of_current_period,
           forecast_operating_profit, forecast_profit, forecast_eps
    FROM fins_statements
    WHERE disclosed_date <= ?
    ORDER BY code, disclosed_date DESC
    LIMIT 20
""", conn, params=(asof,))

print("取得されるデータのサンプル（最新20件）:")
for _, row in forecast_data.iterrows():
    print(f"  銘柄コード: {row['code']}, 開示日: {row['disclosed_date']}, "
          f"期間: {row['type_of_current_period']}, "
          f"forecast_operating_profit: {'あり' if pd.notna(row['forecast_operating_profit']) else 'NULL'}")

print("\n" + "="*60)
print("【ケース3】相互補完可能なケースの統計\n")

if complement_candidates:
    print(f"相互補完可能なケース: {len(complement_candidates)}件")
    op_complement = sum(1 for c in complement_candidates if c["can_complement_op"])
    profit_complement = sum(1 for c in complement_candidates if c["can_complement_profit"])
    print(f"  operating_profit補完可能: {op_complement}件")
    print(f"  profit補完可能: {profit_complement}件")
else:
    print("相互補完可能なケースは見つかりませんでした")

# 全体での統計
all_fy = pd.read_sql_query("""
    SELECT code, current_period_end, disclosed_date,
           operating_profit, forecast_operating_profit,
           profit, forecast_profit
    FROM fins_statements
    WHERE type_of_current_period = 'FY'
      AND disclosed_date <= ?
""", conn, params=(asof,))

# 同じcurrent_period_endで、operating_profitがあるものとforecast_operating_profitがあるものを集計
same_period = all_fy.groupby(["code", "current_period_end"]).agg({
    "operating_profit": lambda x: x.notna().any(),
    "forecast_operating_profit": lambda x: x.notna().any(),
    "profit": lambda x: x.notna().any(),
    "forecast_profit": lambda x: x.notna().any(),
}).reset_index()

same_period["has_both_op"] = same_period["operating_profit"] & same_period["forecast_operating_profit"]
same_period["has_both_profit"] = same_period["profit"] & same_period["forecast_profit"]

print(f"\n全体統計:")
print(f"  同じcurrent_period_endでoperating_profitとforecast_operating_profitの両方がある: {same_period['has_both_op'].sum()}件")
print(f"  同じcurrent_period_endでprofitとforecast_profitの両方がある: {same_period['has_both_profit'].sum()}件")

conn.close()

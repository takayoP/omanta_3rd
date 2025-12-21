#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
5年分の財務データを再取得してクリーンにする
補完フラグを削除した後のデータ再取得用
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.infra.jquants import JQuantsClient
from omanta_3rd.ingest.fins import ingest_financial_statements

# 5年前の日付を計算
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=5*365)).strftime("%Y-%m-%d")

print(f"5年分の財務データを再取得します")
print(f"期間: {start_date} ～ {end_date}")
print()

# データベースに接続して、既存のfins_statementsデータを確認
with connect_db() as conn:
    # 既存のデータ数を確認
    cursor = conn.execute("SELECT COUNT(*) FROM fins_statements")
    old_count = cursor.fetchone()[0]
    print(f"既存のデータ数: {old_count:,}件")
    
    # 日付範囲を確認
    cursor = conn.execute("SELECT MIN(disclosed_date), MAX(disclosed_date) FROM fins_statements")
    row = cursor.fetchone()
    if row[0]:
        print(f"既存のデータ範囲: {row[0]} ～ {row[1]}")
    print()

# データを再取得
print("データ取得を開始します...")
client = JQuantsClient()

try:
    ingest_financial_statements(
        date_from=start_date,
        date_to=end_date,
        client=client,
        sleep_sec=0.2,
        batch_size=2000,
    )
    print()
    print("✓ データ取得が完了しました")
except Exception as e:
    print(f"✗ エラーが発生しました: {e}")
    raise

# 再取得後のデータ数を確認
with connect_db() as conn:
    cursor = conn.execute("SELECT COUNT(*) FROM fins_statements")
    new_count = cursor.fetchone()[0]
    print(f"\n再取得後のデータ数: {new_count:,}件")
    
    cursor = conn.execute("SELECT MIN(disclosed_date), MAX(disclosed_date) FROM fins_statements")
    row = cursor.fetchone()
    if row[0]:
        print(f"データ範囲: {row[0]} ～ {row[1]}")
    
    # FYデータの数を確認
    cursor = conn.execute("SELECT COUNT(*) FROM fins_statements WHERE type_of_current_period = 'FY'")
    fy_count = cursor.fetchone()[0]
    print(f"FYデータ数: {fy_count:,}件")
    
    # 主要項目の欠損状況を確認
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN operating_profit IS NULL THEN 1 ELSE 0 END) as missing_op,
            SUM(CASE WHEN profit IS NULL THEN 1 ELSE 0 END) as missing_profit,
            SUM(CASE WHEN equity IS NULL THEN 1 ELSE 0 END) as missing_equity
        FROM fins_statements
        WHERE type_of_current_period = 'FY'
    """)
    row = cursor.fetchone()
    if row[0] > 0:
        print(f"\nFYデータの欠損状況:")
        print(f"  総数: {row[0]:,}件")
        print(f"  operating_profit欠損: {row[1]:,}件 ({row[1]/row[0]*100:.1f}%)")
        print(f"  profit欠損: {row[2]:,}件 ({row[2]/row[0]*100:.1f}%)")
        print(f"  equity欠損: {row[3]:,}件 ({row[3]/row[0]*100:.1f}%)")

print("\n✓ 完了しました")

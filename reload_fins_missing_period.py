#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
漏れた期間の財務データを取得
2019-01-04 ～ 2020-12-21
"""

import sys
from pathlib import Path
import sqlite3

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.infra.jquants import JQuantsClient
from omanta_3rd.ingest.fins import ingest_financial_statements

date_from = "2019-01-04"
date_to = "2020-12-21"

print(f"漏れた期間の財務データを取得します")
print(f"期間: {date_from} ～ {date_to}")
print()

# データベースに接続して、既存のデータ数を確認
with connect_db() as conn:
    # 既存のデータ数を確認
    cursor = conn.execute("SELECT COUNT(*) FROM fins_statements")
    old_count = cursor.fetchone()[0]
    print(f"既存のデータ数: {old_count:,}件")
    
    # この期間の既存データ数を確認
    cursor = conn.execute(
        "SELECT COUNT(*) FROM fins_statements WHERE disclosed_date >= ? AND disclosed_date <= ?",
        (date_from, date_to)
    )
    existing_count = cursor.fetchone()[0]
    print(f"この期間の既存データ数: {existing_count:,}件")
    print()

# データを取得
print("データ取得を開始します...")
client = JQuantsClient()

try:
    ingest_financial_statements(
        date_from=date_from,
        date_to=date_to,
        client=client,
        sleep_sec=0.2,
        batch_size=2000,
    )
    print()
    print("✓ データ取得が完了しました")
except Exception as e:
    print(f"✗ エラーが発生しました: {e}")
    raise

# 取得後のデータ数を確認
with connect_db() as conn:
    cursor = conn.execute("SELECT COUNT(*) FROM fins_statements")
    new_count = cursor.fetchone()[0]
    print(f"\n取得後の総データ数: {new_count:,}件 (追加: {new_count - old_count:,}件)")
    
    # この期間のデータ数を確認
    cursor = conn.execute(
        "SELECT COUNT(*) FROM fins_statements WHERE disclosed_date >= ? AND disclosed_date <= ?",
        (date_from, date_to)
    )
    period_count = cursor.fetchone()[0]
    print(f"この期間のデータ数: {period_count:,}件 (追加: {period_count - existing_count:,}件)")
    
    cursor = conn.execute("SELECT MIN(disclosed_date), MAX(disclosed_date) FROM fins_statements")
    row = cursor.fetchone()
    if row[0]:
        print(f"データ範囲: {row[0]} ～ {row[1]}")

print("\n✓ 完了しました")

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
strategy_params_monthly_rebalanceテーブルにjson_file_pathカラムを追加するスクリプト
"""

from omanta_3rd.infra.db import connect_db

def main():
    with connect_db() as conn:
        # カラムが既に存在するか確認
        cursor = conn.execute("PRAGMA table_info(strategy_params_monthly_rebalance)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "json_file_path" in columns:
            print("✓ json_file_pathカラムは既に存在します")
        else:
            # カラムを追加
            conn.execute("""
                ALTER TABLE strategy_params_monthly_rebalance
                ADD COLUMN json_file_path TEXT
            """)
            conn.commit()
            print("✓ json_file_pathカラムを追加しました")
        
        # インデックスを追加
        try:
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategy_params_monthly_rebalance_json_file
                ON strategy_params_monthly_rebalance(json_file_path)
            """)
            conn.commit()
            print("✓ インデックスを追加しました")
        except Exception as e:
            print(f"⚠️  インデックスの追加でエラー: {e}")
        
        # 現在のテーブル構造を確認
        print()
        print("=" * 80)
        print("現在のテーブル構造")
        print("=" * 80)
        cursor = conn.execute("PRAGMA table_info(strategy_params_monthly_rebalance)")
        for row in cursor.fetchall():
            col_id, col_name, col_type, not_null, default_val, pk = row
            print(f"  {col_name}: {col_type} {'NOT NULL' if not_null else 'NULL'} {'PRIMARY KEY' if pk else ''}")

if __name__ == "__main__":
    main()














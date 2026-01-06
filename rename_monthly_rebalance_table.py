#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
月次リバランス型のテーブル名をstrategy_paramsと整合させるスクリプト

monthly_rebalance_final_selected_candidates テーブルを
strategy_params_monthly_rebalance にリネームします。
"""

from omanta_3rd.infra.db import connect_db

def main():
    with connect_db() as conn:
        # テーブルが存在するか確認
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='monthly_rebalance_final_selected_candidates'
        """)
        if cursor.fetchone() is None:
            print("⚠️  monthly_rebalance_final_selected_candidates テーブルが見つかりません")
            return
        
        # 新しいテーブル名が既に存在するか確認
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='strategy_params_monthly_rebalance'
        """)
        if cursor.fetchone() is not None:
            print("⚠️  strategy_params_monthly_rebalance テーブルは既に存在します")
            return
        
        print("=" * 80)
        print("テーブル名の変更")
        print("=" * 80)
        print("monthly_rebalance_final_selected_candidates")
        print("  → strategy_params_monthly_rebalance")
        print()
        
        # テーブル名を変更
        conn.execute("""
            ALTER TABLE monthly_rebalance_final_selected_candidates
            RENAME TO strategy_params_monthly_rebalance
        """)
        conn.commit()
        print("✓ テーブル名を変更しました")
        
        # 外部キー参照を更新する必要があるテーブルを確認
        cursor = conn.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' 
            AND sql LIKE '%monthly_rebalance_final_selected_candidates%'
        """)
        dependent_tables = cursor.fetchall()
        
        if dependent_tables:
            print()
            print("⚠️  以下のテーブルが外部キー参照を持っている可能性があります:")
            for table_sql in dependent_tables:
                print(f"  - {table_sql[0][:100]}...")
            print()
            print("外部キー参照の更新が必要な場合は、手動で対応してください。")

if __name__ == "__main__":
    main()


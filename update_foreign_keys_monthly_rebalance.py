#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
月次リバランス型テーブルの外部キー参照を更新するスクリプト

SQLiteでは外部キー制約を直接変更できないため、
テーブルを再作成する必要があります。
ただし、データが既に存在する場合は注意が必要です。
"""

from omanta_3rd.infra.db import connect_db

def main():
    with connect_db() as conn:
        # 外部キー参照を持つテーブルを確認
        tables_with_fk = [
            'monthly_rebalance_candidate_performance',
            'monthly_rebalance_candidate_monthly_returns',
            'monthly_rebalance_candidate_detailed_metrics'
        ]
        
        print("=" * 80)
        print("外部キー参照の確認")
        print("=" * 80)
        
        for table_name in tables_with_fk:
            cursor = conn.execute(f"""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='{table_name}'
            """)
            result = cursor.fetchone()
            if result:
                sql = result[0]
                if 'strategy_params_monthly_rebalance' in sql:
                    print(f"✓ {table_name}: 既に更新済み")
                elif 'monthly_rebalance_final_selected_candidates' in sql:
                    print(f"⚠️  {table_name}: 更新が必要（ただし、SQLiteでは外部キー制約を直接変更できません）")
                    print(f"   実際の参照は動作する可能性がありますが、スキーマ定義は手動で更新してください")
                else:
                    print(f"  {table_name}: 外部キー参照なし")
        
        print()
        print("注意: SQLiteでは外部キー制約の定義を直接変更できません。")
        print("スキーマファイル（sql/schema.sql）は既に更新済みです。")
        print("実際のデータベースでは、テーブルを再作成する必要がある場合があります。")

if __name__ == "__main__":
    main()


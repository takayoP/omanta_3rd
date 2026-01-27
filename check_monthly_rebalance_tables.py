#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
月次リバランス型のテーブルを確認するスクリプト
"""

from omanta_3rd.infra.db import connect_db

def main():
    with connect_db() as conn:
        # テーブル一覧を確認
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND (name LIKE '%monthly_rebalance%' OR name LIKE '%strategy_params%')
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        print("=" * 80)
        print("月次リバランス型関連テーブル一覧")
        print("=" * 80)
        for table in tables:
            print(f"  - {table}")
        
        print()
        
        # monthly_rebalance_final_selected_candidates のデータを確認
        if 'monthly_rebalance_final_selected_candidates' in tables:
            cursor = conn.execute("""
                SELECT trial_number, ranking, recommendation_text, created_at
                FROM monthly_rebalance_final_selected_candidates
                ORDER BY trial_number
            """)
            rows = cursor.fetchall()
            print(f"monthly_rebalance_final_selected_candidates のレコード数: {len(rows)}")
            if rows:
                print("\nレコード一覧:")
                for row in rows:
                    print(f"  Trial #{row[0]}: ranking={row[1]}, recommendation={row[2][:50] if row[2] else 'N/A'}...")
        
        print()
        
        # strategy_params のデータを確認
        if 'strategy_params' in tables:
            cursor = conn.execute("""
                SELECT param_id, portfolio_type, strategy_type, horizon_months
                FROM strategy_params
                ORDER BY param_id
            """)
            rows = cursor.fetchall()
            print(f"strategy_params のレコード数: {len(rows)}")
            if rows:
                print("\nレコード一覧:")
                for row in rows:
                    print(f"  {row[0]}: portfolio_type={row[1]}, strategy_type={row[2]}, horizon={row[3]}M")

if __name__ == "__main__":
    main()














#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
追加したoperational_monthly_rebalanceレコードを削除するスクリプト
"""

from omanta_3rd.infra.db import connect_db

def main():
    with connect_db() as conn:
        # 削除前の確認
        cursor = conn.execute("""
            SELECT param_id, portfolio_type, description
            FROM strategy_params
            WHERE param_id = 'operational_monthly_rebalance'
        """)
        row = cursor.fetchone()
        
        if row:
            print(f"削除対象レコード:")
            print(f"  param_id: {row[0]}")
            print(f"  portfolio_type: {row[1]}")
            print(f"  description: {row[2][:60]}...")
            print()
            
            # 削除実行
            conn.execute("""
                DELETE FROM strategy_params
                WHERE param_id = 'operational_monthly_rebalance'
            """)
            conn.commit()
            print("✓ operational_monthly_rebalanceレコードを削除しました")
        else:
            print("⚠️  operational_monthly_rebalanceレコードが見つかりませんでした")
        
        # 削除後の確認
        cursor = conn.execute("""
            SELECT COUNT(*) FROM strategy_params
            WHERE param_id = 'operational_monthly_rebalance'
        """)
        count = cursor.fetchone()[0]
        if count == 0:
            print("✓ 削除が完了しました")
        else:
            print(f"⚠️  削除に失敗しました（残り: {count}件）")

if __name__ == "__main__":
    main()


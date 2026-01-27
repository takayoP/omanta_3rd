#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
strategy_params_monthly_rebalanceテーブルの既存レコードにJSONファイルのパスを設定するスクリプト
"""

from pathlib import Path
from omanta_3rd.infra.db import connect_db

def main():
    json_file_path = str(Path("final_selected_candidates.json").absolute())
    
    if not Path("final_selected_candidates.json").exists():
        print(f"⚠️  JSONファイルが見つかりません: {json_file_path}")
        return
    
    with connect_db() as conn:
        # 既存レコードを確認
        cursor = conn.execute("""
            SELECT trial_number, json_file_path
            FROM strategy_params_monthly_rebalance
            ORDER BY trial_number
        """)
        rows = cursor.fetchall()
        
        print("=" * 80)
        print("既存レコードの確認と更新")
        print("=" * 80)
        print(f"JSONファイルパス: {json_file_path}")
        print()
        
        for trial_number, current_path in rows:
            if current_path:
                print(f"Trial #{trial_number}: 既に設定済み ({current_path})")
            else:
                # JSONファイルのパスを設定
                conn.execute("""
                    UPDATE strategy_params_monthly_rebalance
                    SET json_file_path = ?
                    WHERE trial_number = ?
                """, (json_file_path, trial_number))
                print(f"Trial #{trial_number}: JSONファイルパスを設定しました")
        
        conn.commit()
        
        # 更新後の確認
        print()
        print("=" * 80)
        print("更新後の確認")
        print("=" * 80)
        cursor = conn.execute("""
            SELECT trial_number, json_file_path
            FROM strategy_params_monthly_rebalance
            ORDER BY trial_number
        """)
        for trial_number, json_path in cursor.fetchall():
            status = "✓" if json_path else "✗"
            print(f"{status} Trial #{trial_number}: {json_path if json_path else '未設定'}")

if __name__ == "__main__":
    main()














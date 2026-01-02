"""テーブル名のリネームを確認"""

import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("=== 月次リバランス関連テーブル ===")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE '%rebalance%' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
    
    print("\n=== 旧テーブル名が残っていないか確認 ===")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'final_%'
        ORDER BY name
    """)
    old_tables = cursor.fetchall()
    if old_tables:
        print("警告: 旧テーブル名が見つかりました:")
        for table in old_tables:
            print(f"  - {table[0]}")
    else:
        print("✓ 旧テーブル名は見つかりませんでした（正常）")
    
    conn.close()

if __name__ == "__main__":
    main()


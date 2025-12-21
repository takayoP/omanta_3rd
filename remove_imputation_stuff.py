#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完フラグカラムとfins_fy_rawテーブルを削除するマイグレーションスクリプト
"""

import sqlite3
from pathlib import Path

db_path = Path("data/db/jquants.sqlite")

if not db_path.exists():
    print(f"データベースが見つかりません: {db_path}")
    exit(1)

print(f"データベースに接続中: {db_path}")

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

try:
    # SQLiteではカラムの削除は直接できないため、テーブルの再作成が必要
    print("\n1. fins_statementsテーブルから補完フラグカラムを削除...")
    
    # 現在のテーブル構造を確認
    cursor = conn.execute("PRAGMA table_info(fins_statements)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"   現在のカラム数: {len(columns)}")
    
    # 補完フラグカラムを除いたカラムリストを作成
    imputed_cols = ["imputed_op", "imputed_profit", "imputed_equity", "imputed_eps", "imputed_bvps"]
    remaining_cols = [col for col in columns if col not in imputed_cols]
    print(f"   削除予定のカラム: {imputed_cols}")
    print(f"   残るカラム数: {len(remaining_cols)}")
    
    # テーブルの再作成（補完フラグカラムを除く）
    conn.execute("BEGIN TRANSACTION")
    
    # 一時テーブルを作成（補完フラグを除く）
    conn.execute("""
        CREATE TABLE fins_statements_new (
            disclosed_date TEXT NOT NULL,
            disclosed_time TEXT,
            code TEXT NOT NULL,
            type_of_current_period TEXT,
            current_period_end TEXT,
            operating_profit REAL,
            profit REAL,
            equity REAL,
            eps REAL,
            bvps REAL,
            forecast_operating_profit REAL,
            forecast_profit REAL,
            forecast_eps REAL,
            next_year_forecast_operating_profit REAL,
            next_year_forecast_profit REAL,
            next_year_forecast_eps REAL,
            shares_outstanding REAL,
            treasury_shares REAL,
            PRIMARY KEY (
                disclosed_date,
                code,
                type_of_current_period,
                current_period_end
            )
        )
    """)
    
    # データをコピー（補完フラグを除く）
    cols_str = ", ".join(remaining_cols)
    conn.execute(f"""
        INSERT INTO fins_statements_new ({cols_str})
        SELECT {cols_str}
        FROM fins_statements
    """)
    
    # 元のテーブルを削除
    conn.execute("DROP TABLE fins_statements")
    
    # 新しいテーブルをリネーム
    conn.execute("ALTER TABLE fins_statements_new RENAME TO fins_statements")
    
    # インデックスを再作成
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fins_code_date ON fins_statements (code, disclosed_date)")
    
    print("   ✓ fins_statementsテーブルの更新が完了しました")
    
    # fins_fy_rawテーブルを削除
    print("\n2. fins_fy_rawテーブルを削除...")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fins_fy_raw'")
    if cursor.fetchone():
        conn.execute("DROP TABLE fins_fy_raw")
        print("   ✓ fins_fy_rawテーブルを削除しました")
    else:
        print("   ✓ fins_fy_rawテーブルは存在しませんでした")
    
    # インデックスも削除
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_fins_fy_raw_date_code'")
    if cursor.fetchone():
        conn.execute("DROP INDEX idx_fins_fy_raw_date_code")
        print("   ✓ fins_fy_rawのインデックスを削除しました")
    
    conn.execute("COMMIT")
    print("\n✓ マイグレーションが正常に完了しました")
    
    # 最終確認
    cursor = conn.execute("PRAGMA table_info(fins_statements)")
    final_columns = [row[1] for row in cursor.fetchall()]
    print(f"\n最終的なfins_statementsテーブルのカラム数: {len(final_columns)}")
    for col in final_columns:
        if col in imputed_cols:
            print(f"  ⚠ {col} がまだ存在します！")
    
    # fins_fy_rawの存在確認
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fins_fy_raw'")
    if cursor.fetchone():
        print("  ⚠ fins_fy_rawテーブルがまだ存在します！")
    else:
        print("  ✓ fins_fy_rawテーブルは正常に削除されました")

except Exception as e:
    conn.execute("ROLLBACK")
    print(f"\n✗ エラーが発生しました: {e}")
    raise
finally:
    conn.close()

"""最終選定候補テーブルを月次リバランス型にリネーム"""

import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

# テーブル名のマッピング（旧名 -> 新名）
TABLE_RENAMES = {
    'final_selected_candidates': 'monthly_rebalance_final_selected_candidates',
    'final_candidate_performance': 'monthly_rebalance_candidate_performance',
    'final_candidate_monthly_returns': 'monthly_rebalance_candidate_monthly_returns',
    'final_candidate_detailed_metrics': 'monthly_rebalance_candidate_detailed_metrics',
}

# インデックス名のマッピング（旧名 -> 新名）
INDEX_RENAMES = {
    'idx_final_candidate_performance_trial': 'idx_monthly_rebalance_performance_trial',
    'idx_final_monthly_returns_trial_period': 'idx_monthly_rebalance_returns_trial_period',
    'idx_final_detailed_metrics_trial_period': 'idx_monthly_rebalance_detailed_metrics_trial_period',
}


def main():
    """メイン処理"""
    print(f"データベースパス: {DB_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # 既存のテーブルを確認
        print("\n=== 既存テーブルの確認 ===")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'final_%'
            ORDER BY name
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"見つかったテーブル: {existing_tables}")
        
        # リネーム対象のテーブルが存在するか確認
        tables_to_rename = [old_name for old_name in TABLE_RENAMES.keys() if old_name in existing_tables]
        if not tables_to_rename:
            print("リネーム対象のテーブルが見つかりませんでした。")
            return
        
        print(f"\nリネーム対象テーブル: {tables_to_rename}")
        
        # トランザクション開始
        conn.execute("BEGIN TRANSACTION")
        
        # テーブルをリネーム
        for old_name, new_name in TABLE_RENAMES.items():
            if old_name in tables_to_rename:
                print(f"  {old_name} -> {new_name}")
                cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')
        
        # インデックスをリネーム（SQLiteではインデックスを直接リネームできないため、再作成）
        print("\n=== インデックスの再作成 ===")
        
        # idx_monthly_rebalance_performance_trial
        cursor.execute("DROP INDEX IF EXISTS idx_final_candidate_performance_trial")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_rebalance_performance_trial 
            ON monthly_rebalance_candidate_performance(trial_number)
        """)
        
        # idx_monthly_rebalance_returns_trial_period
        cursor.execute("DROP INDEX IF EXISTS idx_final_monthly_returns_trial_period")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_rebalance_returns_trial_period 
            ON monthly_rebalance_candidate_monthly_returns(trial_number, evaluation_period)
        """)
        
        # idx_monthly_rebalance_detailed_metrics_trial_period
        cursor.execute("DROP INDEX IF EXISTS idx_final_detailed_metrics_trial_period")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_rebalance_detailed_metrics_trial_period 
            ON monthly_rebalance_candidate_detailed_metrics(trial_number, evaluation_period)
        """)
        
        # 外部キー制約の確認（SQLiteでは外部キー制約の名前は変更できないが、テーブル名の変更で自動的に更新される）
        
        # コミット
        conn.commit()
        print("\nリネームが完了しました！")
        
        # 確認: 新しいテーブル名を表示
        print("\n=== リネーム後のテーブル確認 ===")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'monthly_rebalance_%'
            ORDER BY name
        """)
        new_tables = [row[0] for row in cursor.fetchall()]
        for table in new_tables:
            print(f"  - {table}")
        
        # データ数の確認
        print("\n=== データ数の確認 ===")
        for new_name in TABLE_RENAMES.values():
            cursor.execute(f'SELECT COUNT(*) FROM "{new_name}"')
            count = cursor.fetchone()[0]
            print(f"  {new_name}: {count}件")
        
    except Exception as e:
        conn.rollback()
        print(f"\nエラーが発生しました: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()


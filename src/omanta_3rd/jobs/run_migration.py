"""データベースマイグレーション実行スクリプト"""

import sqlite3
from pathlib import Path
from ..infra.db import connect_db


def run_migration(migration_file: Path):
    """
    マイグレーションファイルを実行
    
    Args:
        migration_file: マイグレーションSQLファイルのパス
    """
    if not migration_file.exists():
        raise FileNotFoundError(f"マイグレーションファイルが見つかりません: {migration_file}")
    
    print(f"マイグレーションを実行しています: {migration_file.name}")
    
    with connect_db() as conn:
        # SQLiteのエラー処理: ALTER TABLEでカラムが既に存在する場合はエラーになるが、続行
        with open(migration_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        
        # SQL文を分割して個別に実行（エラーハンドリングのため）
        # コメント行と空行を除外
        lines = sql_script.split("\n")
        current_statement = []
        statements = []
        
        for line in lines:
            stripped = line.strip()
            # コメント行をスキップ
            if stripped.startswith("--") or not stripped:
                continue
            # SQL文を構築
            current_statement.append(stripped)
            # セミコロンで終わる場合は文を完了
            if stripped.endswith(";"):
                stmt = " ".join(current_statement).rstrip(";")
                if stmt:
                    statements.append(stmt)
                current_statement = []
        
        # 残りの文がある場合
        if current_statement:
            stmt = " ".join(current_statement)
            if stmt:
                statements.append(stmt)
        
        for statement in statements:
            try:
                conn.execute(statement)
                print(f"  ✓ 実行完了")
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                # テーブル/カラム/インデックスが既に存在する場合などはスキップ
                if (
                    "duplicate column name" in error_msg 
                    or "already exists" in error_msg 
                    or "table" in error_msg and "already exists" in error_msg
                    or "index" in error_msg and "already exists" in error_msg
                ):
                    print(f"  - スキップ（既に存在）")
                else:
                    print(f"  ✗ エラー: {e}")
                    raise
    
    print("マイグレーションが完了しました。")


def main():
    """メイン処理"""
    import sys
    from pathlib import Path
    
    # デフォルトのマイグレーションファイル
    default_migration = Path(__file__).parent.parent.parent.parent / "sql" / "migration_add_imputation_flags.sql"
    
    if len(sys.argv) > 1:
        migration_file = Path(sys.argv[1])
    else:
        migration_file = default_migration
    
    run_migration(migration_file)


if __name__ == "__main__":
    main()

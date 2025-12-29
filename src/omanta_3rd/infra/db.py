"""データベース接続・操作ユーティリティ"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from ..config.settings import DB_PATH, SQL_SCHEMA_PATH, SQL_INDEXES_PATH


@contextmanager
def connect_db(read_only: bool = False):
    """
    SQLiteデータベース接続コンテキストマネージャー
    
    Args:
        read_only: 読み取り専用モード
    """
    mode = "ro" if read_only else "rwc"
    uri = f"file:{DB_PATH}?mode={mode}"
    
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)  # タイムアウトを30秒に設定
    conn.row_factory = sqlite3.Row
    
    try:
        # WALモードとPRAGMA設定（並列読み取り性能向上）
        if not read_only:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
        else:
            # 読み取り専用接続でも最適化設定
            conn.execute("PRAGMA journal_mode=WAL")  # WALモードは読み取り専用でも有効
        
        # 並列読み取り性能向上のための設定
        conn.execute("PRAGMA cache_size=-64000")  # 64MBキャッシュ（負の値はKB単位）
        conn.execute("PRAGMA temp_store=MEMORY")  # 一時データをメモリに保存
        conn.execute("PRAGMA mmap_size=268435456")  # 256MBのメモリマッピング
        
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """データベースを初期化（スキーマとインデックスを作成）"""
    with connect_db() as conn:
        # スキーマ作成
        if SQL_SCHEMA_PATH.exists():
            with open(SQL_SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        
        # インデックス作成
        if SQL_INDEXES_PATH.exists():
            with open(SQL_INDEXES_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())


def upsert(
    conn: sqlite3.Connection,
    table: str,
    data: List[Dict[str, Any]],
    conflict_columns: List[str],
):
    """
    バルクUPSERT（INSERT OR REPLACE）
    
    Args:
        conn: データベース接続
        table: テーブル名
        data: 挿入データのリスト
        conflict_columns: 競合判定カラム（PRIMARY KEY）
    """
    if not data:
        return
    
    columns = list(data[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_names = ", ".join(columns)
    conflict_clause = ", ".join(conflict_columns)
    
    sql = f"""
        INSERT OR REPLACE INTO {table} ({column_names})
        VALUES ({placeholders})
    """
    
    values = [tuple(row[col] for col in columns) for row in data]
    conn.executemany(sql, values)


def delete_by_date(
    conn: sqlite3.Connection,
    table: str,
    date_column: str,
    date: str,
):
    """
    指定日付のデータを削除
    
    Args:
        conn: データベース接続
        table: テーブル名
        date_column: 日付カラム名
        date: 削除する日付（YYYY-MM-DD）
    """
    sql = f"DELETE FROM {table} WHERE {date_column} = ?"
    conn.execute(sql, (date,))



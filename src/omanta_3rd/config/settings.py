"""アプリケーション設定（DBパス、API設定、実行日付、閾値など）"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# データベース設定
DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "data" / "db" / "jquants.sqlite"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# J-Quants API設定
JQUANTS_REFRESH_TOKEN = os.getenv("JQUANTS_REFRESH_TOKEN", "")
JQUANTS_MAILADDRESS = os.getenv("JQUANTS_MAILADDRESS", "")
JQUANTS_PASSWORD = os.getenv("JQUANTS_PASSWORD", "")
JQUANTS_API_BASE_URL = os.getenv("JQUANTS_API_BASE_URL", "https://api.jquants.com/v1")

# ログ設定
LOG_DIR = Path(os.getenv("LOG_DIR", PROJECT_ROOT / "data" / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 実行日付（デフォルトは今日、バックテスト時は指定可能）
EXECUTION_DATE: Optional[str] = os.getenv("EXECUTION_DATE", None)

# SQLファイルパス
SQL_SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
SQL_INDEXES_PATH = PROJECT_ROOT / "sql" / "indexes.sql"


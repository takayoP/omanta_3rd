"""データベース初期化ジョブ"""

from ..infra.db import init_db


def main():
    """データベースを初期化"""
    print("データベースを初期化しています...")
    init_db()
    print("データベースの初期化が完了しました。")


if __name__ == "__main__":
    main()



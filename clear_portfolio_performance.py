"""ポートフォリオとパフォーマンステーブルをクリアするスクリプト"""

from omanta_3rd.infra.db import connect_db

def clear_tables():
    """ポートフォリオとパフォーマンステーブルをクリア"""
    with connect_db() as conn:
        # ポートフォリオテーブルをクリア
        conn.execute("DELETE FROM portfolio_monthly")
        print("✅ portfolio_monthly テーブルをクリアしました")
        
        # パフォーマンステーブルをクリア
        conn.execute("DELETE FROM backtest_performance")
        print("✅ backtest_performance テーブルをクリアしました")
        
        # 銘柄別パフォーマンステーブルをクリア
        conn.execute("DELETE FROM backtest_stock_performance")
        print("✅ backtest_stock_performance テーブルをクリアしました")
        
        conn.commit()
        print("\n✅ すべてのテーブルをクリアしました")

if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("ポートフォリオとパフォーマンステーブルのクリア")
    print("=" * 80)
    print()
    
    # コマンドライン引数で確認をスキップ
    if len(sys.argv) > 1 and sys.argv[1] == "--yes":
        clear_tables()
    else:
        try:
            confirm = input("ポートフォリオとパフォーマンステーブルをクリアしますか？ (yes/no): ")
            if confirm.lower() in ['yes', 'y']:
                clear_tables()
            else:
                print("キャンセルしました")
        except EOFError:
            # 対話的でない環境（スクリプト実行時など）の場合は確認なしで実行
            print("対話的入力ができないため、確認なしで実行します...")
            clear_tables()


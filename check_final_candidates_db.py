"""データベースに保存された最終選定候補データを確認"""

import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # テーブル一覧
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'final_%'")
    tables = cursor.fetchall()
    print("=== 作成されたテーブル ===")
    for table in tables:
        print(f"  - {table[0]}")
    
    # 基本情報
    print("\n=== 基本情報とパラメータ ===")
    cursor.execute("""
        SELECT trial_number, ranking, recommendation_text, 
               w_quality, w_growth, w_value, roe_min
        FROM monthly_rebalance_final_selected_candidates 
        ORDER BY ranking
    """)
    for row in cursor.fetchall():
        print(f"\n#{row[0]} (ランキング{row[1]}位)")
        print(f"  推奨: {row[2]}")
        print(f"  パラメータ: w_quality={row[3]:.4f}, w_growth={row[4]:.4f}, w_value={row[5]:.4f}, roe_min={row[6]:.4f}")
    
    # パフォーマンス指標
    print("\n=== パフォーマンス指標 ===")
    cursor.execute("""
        SELECT trial_number, 
               sharpe_excess_0bps, sharpe_excess_10bps, sharpe_excess_20bps,
               sharpe_excess_2023, sharpe_excess_2024,
               sharpe_excess_2025_10bps,
               max_drawdown, max_drawdown_2025
        FROM monthly_rebalance_candidate_performance 
        ORDER BY trial_number
    """)
    for row in cursor.fetchall():
        print(f"\n#{row[0]}:")
        print(f"  Holdout 0bps: {row[1]:.4f}, 10bps: {row[2]:.4f}, 20bps: {row[3]:.4f}")
        print(f"  2023: {row[4]:.4f}, 2024: {row[5]:.4f}")
        print(f"  2025 (10bps): {row[6]:.4f}")
        print(f"  MaxDD (Holdout): {row[7]:.2f}%, 2025: {row[8]:.2f}%")
    
    conn.close()
    print("\n確認完了")

if __name__ == "__main__":
    main()


"""保存されたテスト結果データを確認"""

import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 月次超過リターンの確認
    print("=== 月次超過リターン時系列データ ===")
    cursor.execute("""
        SELECT trial_number, evaluation_period, COUNT(*) as count,
               MIN(period_date) as min_date, MAX(period_date) as max_date
        FROM monthly_rebalance_candidate_monthly_returns
        GROUP BY trial_number, evaluation_period
        ORDER BY trial_number, evaluation_period
    """)
    for row in cursor.fetchall():
        print(f"Trial #{row[0]} ({row[1]}): {row[2]}件 ({row[3]} ～ {row[4]})")
    
    # 詳細パフォーマンス指標の確認
    print("\n=== 詳細パフォーマンス指標 ===")
    cursor.execute("""
        SELECT trial_number, evaluation_period, cost_bps,
               sharpe_ratio, cagr, turnover_annual, num_periods
        FROM monthly_rebalance_candidate_detailed_metrics
        ORDER BY trial_number, evaluation_period, cost_bps
    """)
    for row in cursor.fetchall():
        print(f"\nTrial #{row[0]} ({row[1]}, {row[2]}bps):")
        sharpe_str = f"{row[3]:.4f}" if row[3] is not None else "N/A"
        cagr_str = f"{row[4]:.2f}%" if row[4] is not None else "N/A"
        turnover_str = f"{row[5]:.1f}" if row[5] is not None else "N/A"
        periods_str = f"{row[6]}" if row[6] is not None else "N/A"
        print(f"  Sharpe: {sharpe_str}, CAGR: {cagr_str}, Turnover: {turnover_str}, Periods: {periods_str}")
    
    # サンプルデータ（月次超過リターンの最初の5件）
    print("\n=== 月次超過リターン サンプル（Trial #96, holdout_2023_2024 最初の5件）===")
    cursor.execute("""
        SELECT period_date, excess_return
        FROM monthly_rebalance_candidate_monthly_returns
        WHERE trial_number = 96 AND evaluation_period = 'holdout_2023_2024'
        ORDER BY period_date
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]:.4f} ({row[1]*100:.2f}%)")
    
    conn.close()
    print("\n確認完了")

if __name__ == "__main__":
    main()


"""_get_next_trading_dayの動作を確認

2020-2022年のリバランス日で、翌営業日が正しく取得できるか確認します。

Usage:
    python test_next_trading_day.py
"""

from __future__ import annotations

import sys
import pandas as pd
from datetime import datetime

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
from src.omanta_3rd.backtest.performance import _get_next_trading_day


def test_next_trading_days(start_date: str, end_date: str):
    """
    リバランス日の翌営業日を確認
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    """
    print("=" * 80)
    print(f"リバランス日の翌営業日を確認")
    print(f"期間: {start_date} ～ {end_date}")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print()
    
    with connect_db() as conn:
        # 最新の価格データ日を確認
        latest_date_df = pd.read_sql_query(
            "SELECT MAX(date) as max_date FROM prices_daily",
            conn
        )
        latest_date = latest_date_df["max_date"].iloc[0] if not latest_date_df.empty else None
        print(f"最新の価格データ日: {latest_date}")
        print()
        
        # 各リバランス日の翌営業日を確認
        problem_dates = []
        
        for rebalance_date in rebalance_dates:
            # 翌営業日を取得
            next_trading_day = _get_next_trading_day(conn, rebalance_date)
            
            if next_trading_day is None:
                print(f"❌ {rebalance_date}: 翌営業日が見つかりません")
                problem_dates.append(rebalance_date)
                continue
            
            # 翌営業日に価格データがある銘柄の数を確認
            all_codes_count = pd.read_sql_query(
                """
                SELECT COUNT(DISTINCT code) as count
                FROM prices_daily
                WHERE date = ?
                """,
                conn,
                params=(next_trading_day,),
            )
            
            count = all_codes_count['count'].iloc[0] if not all_codes_count.empty else 0
            
            if count == 0:
                print(f"❌ {rebalance_date}: 翌営業日 {next_trading_day} に価格データが存在しません")
                problem_dates.append(rebalance_date)
            else:
                # 日数差を計算
                rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                next_dt = datetime.strptime(next_trading_day, "%Y-%m-%d")
                days_diff = (next_dt - rebalance_dt).days
                
                if days_diff > 5:
                    print(f"⚠️  {rebalance_date}: 翌営業日 {next_trading_day} (日数差: {days_diff}日, 銘柄数: {count})")
                else:
                    print(f"✅ {rebalance_date}: 翌営業日 {next_trading_day} (日数差: {days_diff}日, 銘柄数: {count})")
        
        print()
        print("=" * 80)
        print("調査結果")
        print("=" * 80)
        print(f"問題のあるリバランス日: {len(problem_dates)}日")
        if problem_dates:
            for date in problem_dates:
                print(f"  - {date}")
        print()


def main():
    # 2020-2022年の期間で調査
    test_next_trading_days("2020-01-01", "2022-12-31")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())




"""リバランス日の購入価格取得問題を調査

2020-2022年の期間で、特定のリバランス日で12銘柄すべてで購入価格が取得できない問題を調査します。

Usage:
    python investigate_rebalance_issue.py
"""

from __future__ import annotations

import sys
import pandas as pd
from datetime import datetime

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
from src.omanta_3rd.backtest.performance import _get_next_trading_day


def investigate_rebalance_dates(start_date: str, end_date: str):
    """
    リバランス日の購入価格取得問題を調査
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    """
    print("=" * 80)
    print(f"リバランス日の購入価格取得問題を調査")
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
        
        # 各リバランス日を調査
        problem_dates = []
        
        for rebalance_date in rebalance_dates:
            # 翌営業日を取得
            next_trading_day = _get_next_trading_day(conn, rebalance_date)
            
            if next_trading_day is None:
                print(f"❌ {rebalance_date}: 翌営業日が見つかりません")
                problem_dates.append(rebalance_date)
                continue
            
            # そのリバランス日のポートフォリオを取得
            portfolio = pd.read_sql_query(
                """
                SELECT code, weight
                FROM portfolio_monthly
                WHERE rebalance_date = ?
                """,
                conn,
                params=(rebalance_date,),
            )
            
            if portfolio.empty:
                # ポートフォリオが存在しない場合はスキップ
                continue
            
            # 各銘柄の翌営業日の始値を確認
            missing_count = 0
            for code in portfolio["code"]:
                price_row = pd.read_sql_query(
                    """
                    SELECT open
                    FROM prices_daily
                    WHERE code = ? AND date = ?
                    """,
                    conn,
                    params=(code, next_trading_day),
                )
                
                if price_row.empty or price_row["open"].iloc[0] is None:
                    missing_count += 1
            
            # 全銘柄で購入価格が取得できない場合
            if missing_count == len(portfolio):
                print(f"❌ {rebalance_date}: 全{len(portfolio)}銘柄で購入価格が取得できません")
                print(f"   翌営業日: {next_trading_day}")
                print(f"   銘柄コード: {portfolio['code'].tolist()}")
                
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
                print(f"   翌営業日 {next_trading_day} に価格データがある銘柄数: {all_codes_count['count'].iloc[0]}")
                
                # ポートフォリオの銘柄が翌営業日に存在するか確認
                portfolio_codes_str = "','".join(portfolio["code"].tolist())
                portfolio_codes_count = pd.read_sql_query(
                    f"""
                    SELECT COUNT(DISTINCT code) as count
                    FROM prices_daily
                    WHERE date = ?
                      AND code IN ('{portfolio_codes_str}')
                    """,
                    conn,
                    params=(next_trading_day,),
                )
                print(f"   ポートフォリオの銘柄のうち、翌営業日に価格データがある銘柄数: {portfolio_codes_count['count'].iloc[0]}")
                print()
                
                problem_dates.append(rebalance_date)
        
        print("=" * 80)
        print("調査結果")
        print("=" * 80)
        print(f"問題のあるリバランス日: {len(problem_dates)}日")
        if problem_dates:
            for date in problem_dates:
                print(f"  - {date}")
        print()
        
        # 問題のあるリバランス日の詳細を調査
        if problem_dates:
            print("=" * 80)
            print("問題のあるリバランス日の詳細調査")
            print("=" * 80)
            
            for rebalance_date in problem_dates[:3]:  # 最初の3日のみ詳細調査
                print()
                print(f"【{rebalance_date}】")
                
                next_trading_day = _get_next_trading_day(conn, rebalance_date)
                if next_trading_day is None:
                    print("  翌営業日が見つかりません")
                    continue
                
                print(f"  翌営業日: {next_trading_day}")
                
                # リバランス日と翌営業日の関係を確認
                rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                next_dt = datetime.strptime(next_trading_day, "%Y-%m-%d")
                days_diff = (next_dt - rebalance_dt).days
                print(f"  日数差: {days_diff}日")
                
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
                print(f"  翌営業日に価格データがある全銘柄数: {all_codes_count['count'].iloc[0]}")
                
                # ポートフォリオを取得
                portfolio = pd.read_sql_query(
                    """
                    SELECT code, weight
                    FROM portfolio_monthly
                    WHERE rebalance_date = ?
                    """,
                    conn,
                    params=(rebalance_date,),
                )
                
                if not portfolio.empty:
                    print(f"  ポートフォリオ銘柄数: {len(portfolio)}")
                    print(f"  銘柄コード: {portfolio['code'].tolist()}")
                    
                    # 各銘柄の詳細を確認
                    print("  各銘柄の詳細:")
                    for code in portfolio["code"][:5]:  # 最初の5銘柄のみ
                        # 翌営業日のデータ
                        price_row = pd.read_sql_query(
                            """
                            SELECT open, close, adj_close
                            FROM prices_daily
                            WHERE code = ? AND date = ?
                            """,
                            conn,
                            params=(code, next_trading_day),
                        )
                        
                        if price_row.empty:
                            print(f"    ❌ {code}: 翌営業日 {next_trading_day} のデータが存在しません")
                        elif price_row["open"].iloc[0] is None:
                            print(f"    ⚠️  {code}: 始値がNULL（終値: {price_row['close'].iloc[0]}, 調整後終値: {price_row['adj_close'].iloc[0]}）")
                        else:
                            print(f"    ✅ {code}: 始値={price_row['open'].iloc[0]:.2f}")
                        
                        # リバランス日前後のデータを確認
                        price_data = pd.read_sql_query(
                            """
                            SELECT date, open, close
                            FROM prices_daily
                            WHERE code = ?
                              AND date >= date(?, '-3 days')
                              AND date <= date(?, '+3 days')
                            ORDER BY date
                            """,
                            conn,
                            params=(code, rebalance_date, rebalance_date),
                        )
                        
                        if not price_data.empty:
                            print(f"      前後3日間のデータ: {len(price_data)}件")
                            # 翌営業日のデータがあるか確認
                            if next_trading_day in price_data["date"].values:
                                print(f"      ✅ 翌営業日 {next_trading_day} のデータが存在します")
                            else:
                                print(f"      ❌ 翌営業日 {next_trading_day} のデータが存在しません")


def main():
    # 2020-2022年の期間で調査
    investigate_rebalance_dates("2020-01-01", "2022-12-31")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())




"""リバランス日の購入価格取得問題を診断

特定のリバランス日で購入価格が取得できない問題を診断します。

Usage:
    python diagnose_rebalance_date_issue.py --rebalance-date 2020-01-31
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
import pandas as pd

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.backtest.performance import _get_next_trading_day


def diagnose_rebalance_date(rebalance_date: str):
    """
    リバランス日の購入価格取得問題を診断
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
    """
    print("=" * 80)
    print(f"リバランス日の購入価格取得問題を診断: {rebalance_date}")
    print("=" * 80)
    print()
    
    with connect_db() as conn:
        # 1. リバランス日の翌営業日を取得
        next_trading_day = _get_next_trading_day(conn, rebalance_date)
        
        if next_trading_day is None:
            print(f"❌ 問題: リバランス日 {rebalance_date} の翌営業日が見つかりません")
            print()
            print("考えられる原因:")
            print("  1. リバランス日が最新日付で、それより後のデータが存在しない")
            print("  2. 価格データが存在しない")
            return
        
        print(f"✅ 翌営業日: {next_trading_day}")
        print()
        
        # 2. そのリバランス日のポートフォリオを取得
        portfolio = pd.read_sql_query(
            """
            SELECT code, weight, core_score, entry_score
            FROM portfolio_monthly
            WHERE rebalance_date = ?
            """,
            conn,
            params=(rebalance_date,),
        )
        
        if portfolio.empty:
            print(f"❌ 問題: リバランス日 {rebalance_date} のポートフォリオが見つかりません")
            print()
            print("考えられる原因:")
            print("  1. ポートフォリオが作成されていない")
            print("  2. データベースに保存されていない")
            return
        
        print(f"✅ ポートフォリオ: {len(portfolio)}銘柄")
        print(f"   銘柄コード: {portfolio['code'].tolist()}")
        print()
        
        # 3. 各銘柄の翌営業日の始値を確認
        print("=" * 80)
        print("各銘柄の翌営業日の始値を確認")
        print("=" * 80)
        
        missing_codes = []
        available_codes = []
        
        for code in portfolio["code"]:
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
                print(f"❌ {code}: 翌営業日 {next_trading_day} の価格データが存在しません")
                missing_codes.append(code)
            elif price_row["open"].iloc[0] is None:
                print(f"⚠️  {code}: 翌営業日 {next_trading_day} の始値（open）がNULL")
                print(f"    終値（close）: {price_row['close'].iloc[0]}")
                print(f"    調整後終値（adj_close）: {price_row['adj_close'].iloc[0]}")
                missing_codes.append(code)
            else:
                print(f"✅ {code}: 始値={price_row['open'].iloc[0]:.2f}")
                available_codes.append(code)
        
        print()
        print("=" * 80)
        print("診断結果")
        print("=" * 80)
        print(f"リバランス日: {rebalance_date}")
        print(f"翌営業日: {next_trading_day}")
        print(f"ポートフォリオ銘柄数: {len(portfolio)}")
        print(f"購入価格が取得できる銘柄: {len(available_codes)}")
        print(f"購入価格が取得できない銘柄: {len(missing_codes)}")
        
        if missing_codes:
            print()
            print(f"❌ 問題のある銘柄: {missing_codes}")
            print()
            print("考えられる原因:")
            print("  1. その銘柄が翌営業日に取引停止になっている")
            print("  2. その銘柄の価格データが欠損している")
            print("  3. その銘柄が上場廃止・合併などでデータが存在しない")
            print()
            
            # 4. その銘柄の価格データの存在を確認
            print("=" * 80)
            print("問題のある銘柄の価格データの存在を確認")
            print("=" * 80)
            
            for code in missing_codes[:5]:  # 最初の5銘柄のみ確認
                # リバランス日前後の価格データを確認
                price_data = pd.read_sql_query(
                    """
                    SELECT date, open, close, adj_close
                    FROM prices_daily
                    WHERE code = ?
                      AND date >= date(?, '-7 days')
                      AND date <= date(?, '+7 days')
                    ORDER BY date
                    """,
                    conn,
                    params=(code, rebalance_date, rebalance_date),
                )
                
                if price_data.empty:
                    print(f"❌ {code}: リバランス日前後7日間の価格データが存在しません")
                else:
                    print(f"📊 {code}: リバランス日前後7日間の価格データ")
                    print(price_data.to_string(index=False))
                    print()
        
        # 5. 翌営業日に価格データがある銘柄の数を確認
        print("=" * 80)
        print("翌営業日に価格データがある銘柄の数を確認")
        print("=" * 80)
        
        all_codes_count = pd.read_sql_query(
            """
            SELECT COUNT(DISTINCT code) as count
            FROM prices_daily
            WHERE date = ?
            """,
            conn,
            params=(next_trading_day,),
        )
        
        print(f"翌営業日 {next_trading_day} に価格データがある銘柄数: {all_codes_count['count'].iloc[0]}")
        print()
        
        # 6. ポートフォリオの銘柄が翌営業日に存在するか確認
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
        
        print(f"ポートフォリオの銘柄のうち、翌営業日に価格データがある銘柄数: {portfolio_codes_count['count'].iloc[0]}")
        print()
        
        if len(missing_codes) == len(portfolio):
            print("=" * 80)
            print("⚠️  重大な問題: ポートフォリオの全銘柄で購入価格が取得できません")
            print("=" * 80)
            print()
            print("考えられる原因:")
            print("  1. リバランス日が最新日付で、それより後のデータが存在しない")
            print("  2. 選定された銘柄がすべて上場廃止・合併などでデータが存在しない")
            print("  3. データベースの価格データが更新されていない")
            print()
            print("確認事項:")
            print(f"  - リバランス日: {rebalance_date}")
            print(f"  - 翌営業日: {next_trading_day}")
            print(f"  - 最新の価格データ日: 確認が必要")
            print(f"  - 選定された銘柄: {portfolio['code'].tolist()}")


def main():
    parser = argparse.ArgumentParser(
        description="リバランス日の購入価格取得問題を診断",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--rebalance-date",
        type=str,
        required=True,
        help="リバランス日（YYYY-MM-DD）",
    )
    
    args = parser.parse_args()
    
    diagnose_rebalance_date(args.rebalance_date)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())












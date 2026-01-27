"""バックテストパフォーマンス検証用のサンプルデータ抽出スクリプト"""

import pandas as pd
from omanta_3rd.infra.db import connect_db

def extract_sample_data(rebalance_date: str = "2022-01-31", as_of_date: str = "2025-12-26"):
    """
    検証用のサンプルデータを抽出
    
    Args:
        rebalance_date: リバランス日
        as_of_date: 評価日
    """
    with connect_db() as conn:
        print("=" * 80)
        print("バックテストパフォーマンス検証用サンプルデータ抽出")
        print("=" * 80)
        print(f"リバランス日: {rebalance_date}")
        print(f"評価日: {as_of_date}")
        print()
        
        # 1. ポートフォリオ全体のパフォーマンス
        print("【1. ポートフォリオ全体のパフォーマンス】")
        print("-" * 80)
        perf_df = pd.read_sql_query(
            """
            SELECT 
                rebalance_date,
                as_of_date,
                total_return_pct,
                topix_return_pct,
                excess_return_pct,
                num_stocks,
                num_stocks_with_price,
                avg_return_pct,
                min_return_pct,
                max_return_pct
            FROM backtest_performance
            WHERE rebalance_date = ? AND as_of_date = ?
            """,
            conn,
            params=(rebalance_date, as_of_date),
        )
        
        if not perf_df.empty:
            print(perf_df.to_string(index=False))
        else:
            print("データが見つかりませんでした")
        print()
        
        # 2. 銘柄別のパフォーマンス（上位5件と下位5件）
        print("【2. 銘柄別のパフォーマンス（上位5件）】")
        print("-" * 80)
        stock_top_df = pd.read_sql_query(
            """
            SELECT 
                code,
                weight,
                rebalance_price,
                current_price,
                split_multiplier,
                adjusted_current_price,
                return_pct,
                topix_return_pct,
                excess_return_pct
            FROM backtest_stock_performance
            WHERE rebalance_date = ? AND as_of_date = ?
            ORDER BY return_pct DESC
            LIMIT 5
            """,
            conn,
            params=(rebalance_date, as_of_date),
        )
        
        if not stock_top_df.empty:
            print(stock_top_df.to_string(index=False))
        else:
            print("データが見つかりませんでした")
        print()
        
        print("【3. 銘柄別のパフォーマンス（下位5件）】")
        print("-" * 80)
        stock_bottom_df = pd.read_sql_query(
            """
            SELECT 
                code,
                weight,
                rebalance_price,
                current_price,
                split_multiplier,
                adjusted_current_price,
                return_pct,
                topix_return_pct,
                excess_return_pct
            FROM backtest_stock_performance
            WHERE rebalance_date = ? AND as_of_date = ?
            ORDER BY return_pct ASC
            LIMIT 5
            """,
            conn,
            params=(rebalance_date, as_of_date),
        )
        
        if not stock_bottom_df.empty:
            print(stock_bottom_df.to_string(index=False))
        else:
            print("データが見つかりませんでした")
        print()
        
        # 3. 分割が発生した銘柄
        print("【4. 分割が発生した銘柄（split_multiplier != 1.0）】")
        print("-" * 80)
        split_df = pd.read_sql_query(
            """
            SELECT 
                code,
                weight,
                rebalance_price,
                current_price,
                split_multiplier,
                adjusted_current_price,
                return_pct
            FROM backtest_stock_performance
            WHERE rebalance_date = ? 
              AND as_of_date = ?
              AND split_multiplier != 1.0
            ORDER BY split_multiplier DESC
            """,
            conn,
            params=(rebalance_date, as_of_date),
        )
        
        if not split_df.empty:
            print(f"分割が発生した銘柄数: {len(split_df)}")
            print(split_df.to_string(index=False))
        else:
            print("分割が発生した銘柄はありませんでした")
        print()
        
        # 4. weightの合計を確認
        print("【5. ポートフォリオ内のweight合計】")
        print("-" * 80)
        weight_df = pd.read_sql_query(
            """
            SELECT 
                SUM(weight) as total_weight,
                COUNT(*) as num_stocks,
                MIN(weight) as min_weight,
                MAX(weight) as max_weight
            FROM backtest_stock_performance
            WHERE rebalance_date = ? AND as_of_date = ?
            """,
            conn,
            params=(rebalance_date, as_of_date),
        )
        
        if not weight_df.empty:
            print(weight_df.to_string(index=False))
        else:
            print("データが見つかりませんでした")
        print()
        
        # 5. 検証用の詳細データ（特定の銘柄1つ）
        if not stock_top_df.empty:
            sample_code = stock_top_df.iloc[0]["code"]
            print(f"【6. 検証用詳細データ（銘柄コード: {sample_code}）】")
            print("-" * 80)
            
            # 価格データを取得
            next_trading_day_df = pd.read_sql_query(
                """
                SELECT MIN(date) AS next_date
                FROM prices_daily
                WHERE date > ?
                """,
                conn,
                params=(rebalance_date,),
            )
            
            if not next_trading_day_df.empty:
                next_trading_day = next_trading_day_df.iloc[0]["next_date"]
                print(f"リバランス日の翌営業日: {next_trading_day}")
                
                # 購入価格（翌営業日の始値）
                buy_price_df = pd.read_sql_query(
                    """
                    SELECT open, close
                    FROM prices_daily
                    WHERE code = ? AND date = ?
                    """,
                    conn,
                    params=(sample_code, next_trading_day),
                )
                
                if not buy_price_df.empty:
                    print(f"購入価格（翌営業日の始値）: {buy_price_df.iloc[0]['open']}")
                    print(f"購入日の終値: {buy_price_df.iloc[0]['close']}")
                
                # 評価価格（評価日の終値）
                sell_price_df = pd.read_sql_query(
                    """
                    SELECT close, date
                    FROM prices_daily
                    WHERE code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT 1
                    """,
                    conn,
                    params=(sample_code, as_of_date),
                )
                
                if not sell_price_df.empty:
                    print(f"評価価格（評価日の終値）: {sell_price_df.iloc[0]['close']}")
                    print(f"評価日（実際の価格データの日付）: {sell_price_df.iloc[0]['date']}")
                
                # 分割履歴
                split_history_df = pd.read_sql_query(
                    """
                    SELECT date, adjustment_factor
                    FROM prices_daily
                    WHERE code = ?
                      AND date > ?
                      AND date <= ?
                      AND adjustment_factor IS NOT NULL
                      AND adjustment_factor != 1.0
                    ORDER BY date ASC
                    """,
                    conn,
                    params=(sample_code, next_trading_day, as_of_date),
                )
                
                if not split_history_df.empty:
                    print(f"\n分割履歴:")
                    print(split_history_df.to_string(index=False))
                    
                    # 手動計算
                    split_mult = 1.0
                    for _, row in split_history_df.iterrows():
                        split_mult *= (1.0 / row["adjustment_factor"])
                    print(f"\n手動計算による分割倍率: {split_mult}")
                else:
                    print("\n分割履歴: なし（split_multiplier = 1.0）")
                
                # データベースの値と比較
                db_row = stock_top_df[stock_top_df["code"] == sample_code].iloc[0]
                print(f"\nデータベースの値:")
                print(f"  rebalance_price: {db_row['rebalance_price']}")
                print(f"  current_price: {db_row['current_price']}")
                print(f"  split_multiplier: {db_row['split_multiplier']}")
                print(f"  adjusted_current_price: {db_row['adjusted_current_price']}")
                print(f"  return_pct: {db_row['return_pct']}")
                
                # 手動計算で検証
                if not buy_price_df.empty and not sell_price_df.empty:
                    manual_rebalance_price = buy_price_df.iloc[0]['open']
                    manual_current_price = sell_price_df.iloc[0]['close']
                    manual_split_mult = split_mult if not split_history_df.empty else 1.0
                    manual_adjusted_price = manual_current_price * manual_split_mult
                    manual_return = (manual_adjusted_price - manual_rebalance_price) / manual_rebalance_price * 100.0
                    
                    print(f"\n手動計算による検証:")
                    print(f"  購入価格: {manual_rebalance_price}")
                    print(f"  評価価格: {manual_current_price}")
                    print(f"  分割倍率: {manual_split_mult}")
                    print(f"  調整後評価価格: {manual_adjusted_price}")
                    print(f"  リターン: {manual_return:.2f}%")
                    print(f"  データベースのリターン: {db_row['return_pct']:.2f}%")
                    print(f"  差分: {abs(manual_return - db_row['return_pct']):.4f}%")
        
        print()
        print("=" * 80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) >= 3:
        rebalance_date = sys.argv[1]
        as_of_date = sys.argv[2]
    else:
        rebalance_date = "2022-01-31"
        as_of_date = "2025-12-26"
    
    extract_sample_data(rebalance_date, as_of_date)




















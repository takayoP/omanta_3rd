"""
バックテスト可能な期間を確認

各テーブルのデータ範囲を確認し、バックテストに必要なデータが
揃っている期間を特定します。
"""

from omanta_3rd.infra.db import connect_db
import pandas as pd


def check_table_date_range(conn, table_name: str, date_column: str) -> dict:
    """テーブルの日付範囲を確認"""
    try:
        query = f"""
        SELECT 
            MIN({date_column}) as min_date,
            MAX({date_column}) as max_date,
            COUNT(DISTINCT {date_column}) as date_count
        FROM {table_name}
        WHERE {date_column} IS NOT NULL
        """
        result = pd.read_sql_query(query, conn)
        if not result.empty and result["min_date"].iloc[0] is not None:
            return {
                "min_date": result["min_date"].iloc[0],
                "max_date": result["max_date"].iloc[0],
                "date_count": result["date_count"].iloc[0],
            }
    except Exception as e:
        print(f"  ⚠️  エラー: {e}")
    return None


def check_code_count(conn, table_name: str, date_column: str) -> dict:
    """各日付の銘柄数を確認"""
    try:
        query = f"""
        SELECT 
            {date_column} as date,
            COUNT(DISTINCT code) as code_count
        FROM {table_name}
        WHERE {date_column} IS NOT NULL
        GROUP BY {date_column}
        ORDER BY {date_column}
        """
        result = pd.read_sql_query(query, conn)
        if not result.empty:
            return {
                "first_date": result["date"].iloc[0],
                "last_date": result["date"].iloc[-1],
                "first_count": result["code_count"].iloc[0],
                "last_count": result["code_count"].iloc[-1],
            }
    except Exception as e:
        print(f"  ⚠️  エラー: {e}")
    return None


def main():
    print("=" * 80)
    print("バックテスト可能な期間の確認")
    print("=" * 80)
    print()
    
    with connect_db() as conn:
        # 1. prices_daily（価格データ）
        print("【1. 価格データ (prices_daily)】")
        price_range = check_table_date_range(conn, "prices_daily", "date")
        if price_range:
            print(f"  期間: {price_range['min_date']} ～ {price_range['max_date']}")
            print(f"  日付数: {price_range['date_count']:,}日")
        price_codes = check_code_count(conn, "prices_daily", "date")
        if price_codes:
            print(f"  最初の日付の銘柄数: {price_codes['first_count']:,}銘柄")
            print(f"  最後の日付の銘柄数: {price_codes['last_count']:,}銘柄")
        print()
        
        # 2. fins_statements（財務データ）
        print("【2. 財務データ (fins_statements)】")
        fins_range = check_table_date_range(conn, "fins_statements", "disclosed_date")
        if fins_range:
            print(f"  開示日範囲: {fins_range['min_date']} ～ {fins_range['max_date']}")
            print(f"  開示日数: {fins_range['date_count']:,}日")
        
        # 財務データの期末日も確認
        fins_period_range = check_table_date_range(conn, "fins_statements", "current_period_end")
        if fins_period_range:
            print(f"  期末日範囲: {fins_period_range['min_date']} ～ {fins_period_range['max_date']}")
        
        # 予想データの有無を確認
        query_forecast = """
        SELECT 
            MIN(disclosed_date) as min_date,
            MAX(disclosed_date) as max_date,
            COUNT(*) as count
        FROM fins_statements
        WHERE disclosed_date IS NOT NULL
          AND (forecast_operating_profit IS NOT NULL 
               OR forecast_profit IS NOT NULL 
               OR forecast_eps IS NOT NULL)
        """
        forecast_result = pd.read_sql_query(query_forecast, conn)
        if not forecast_result.empty and forecast_result["min_date"].iloc[0] is not None:
            print(f"  予想データ範囲: {forecast_result['min_date'].iloc[0]} ～ {forecast_result['max_date'].iloc[0]}")
            print(f"  予想データ件数: {forecast_result['count'].iloc[0]:,}件")
        print()
        
        # 3. listed_info（銘柄情報）
        print("【3. 銘柄情報 (listed_info)】")
        listed_range = check_table_date_range(conn, "listed_info", "date")
        if listed_range:
            print(f"  期間: {listed_range['min_date']} ～ {listed_range['max_date']}")
            print(f"  日付数: {listed_range['date_count']:,}日")
        listed_codes = check_code_count(conn, "listed_info", "date")
        if listed_codes:
            print(f"  最初の日付の銘柄数: {listed_codes['first_count']:,}銘柄")
            print(f"  最後の日付の銘柄数: {listed_codes['last_count']:,}銘柄")
        print()
        
        # 4. index_daily（TOPIXデータ）
        print("【4. インデックスデータ (index_daily)】")
        try:
            index_range = check_table_date_range(conn, "index_daily", "date")
            if index_range:
                print(f"  期間: {index_range['min_date']} ～ {index_range['max_date']}")
                print(f"  日付数: {index_range['date_count']:,}日")
            
            # TOPIXのデータを確認
            query_topix = """
            SELECT 
                MIN(date) as min_date,
                MAX(date) as max_date,
                COUNT(*) as count
            FROM index_daily
            WHERE index_code = '0000' AND date IS NOT NULL
            """
            topix_result = pd.read_sql_query(query_topix, conn)
            if not topix_result.empty and topix_result["min_date"].iloc[0] is not None:
                print(f"  TOPIX期間: {topix_result['min_date'].iloc[0]} ～ {topix_result['max_date'].iloc[0]}")
                print(f"  TOPIXデータ件数: {topix_result['count'].iloc[0]:,}件")
        except Exception as e:
            print(f"  ⚠️  インデックスデータの確認でエラー: {e}")
        print()
        
        # 5. バックテストに必要なデータの整合性確認
        print("=" * 80)
        print("【バックテスト可能な期間の推定】")
        print("=" * 80)
        
        # listed_infoの扱いについて
        print("\n【銘柄情報（listed_info）について】")
        print("listed_infoは過去のデータがなくても、最新のデータを使用してバックテスト可能です。")
        print("（_snap_listed_date関数が、過去の日付が指定された場合、")
        print(" その日付以前の最新のlisted_infoを取得し、なければ最新のデータを使用します）")
        print("ただし、過去のセクター情報などが正確でない可能性があります。")
        print()
        
        # 必要なデータの最小日付を確認（listed_infoは除外）
        required_dates = []
        
        if price_range:
            required_dates.append(("価格データ", price_range["min_date"]))
        if fins_range:
            required_dates.append(("財務データ", fins_range["min_date"]))
        if index_range:
            required_dates.append(("インデックスデータ", index_range["min_date"]))
        
        if required_dates:
            # 最も新しい開始日を採用（すべてのデータが揃っている期間）
            latest_start = max([d[1] for d in required_dates])
            print(f"データが揃っている開始日: {latest_start}")
            print("  （価格データ、財務データ、インデックスデータが揃っている期間の開始日）")
            
            # 各データの開始日を表示
            print("\n各データの開始日:")
            for name, date in sorted(required_dates, key=lambda x: x[1], reverse=True):
                marker = " ← ボトルネック" if date == latest_start else ""
                print(f"  {name}: {date}{marker}")
            if listed_range:
                print(f"  銘柄情報: {listed_range['min_date']} （過去データなし、最新データを使用可能）")
        
        # 財務データの利用可能性を確認（過去5年の財務データが必要）
        print("\n【財務データの利用可能性】")
        print("バックテストには、リバランス日時点で過去5年の財務データが必要です。")
        if fins_range:
            # 過去5年の財務データが利用可能になる日付を計算
            from datetime import datetime, timedelta
            try:
                fins_min = datetime.strptime(fins_range["min_date"], "%Y-%m-%d")
                # 過去5年分のデータが必要なので、開始日から5年後が実質的な開始日
                effective_start = (fins_min + timedelta(days=5*365)).strftime("%Y-%m-%d")
                print(f"  財務データ開始日: {fins_range['min_date']}")
                print(f"  実質的なバックテスト開始日（過去5年データが必要）: {effective_start}")
                
                # 実際に過去5年の財務データがあるか確認
                query_5years = """
                SELECT 
                    COUNT(DISTINCT code) as code_count,
                    COUNT(*) as record_count
                FROM fins_statements
                WHERE disclosed_date <= ?
                  AND disclosed_date >= date(?, '-5 years')
                  AND (operating_profit IS NOT NULL 
                       OR profit IS NOT NULL 
                       OR equity IS NOT NULL)
                """
                test_date = effective_start
                result_5years = pd.read_sql_query(query_5years, conn, params=(test_date, test_date))
                if not result_5years.empty:
                    print(f"  {test_date}時点での過去5年財務データ:")
                    print(f"    銘柄数: {result_5years['code_count'].iloc[0]:,}銘柄")
                    print(f"    レコード数: {result_5years['record_count'].iloc[0]:,}件")
            except Exception as e:
                print(f"  ⚠️  エラー: {e}")
        
        print("\n" + "=" * 80)
        print("【推奨バックテスト期間】")
        print("=" * 80)
        
        if price_range and index_range:
            # 価格データとインデックスデータが揃っている期間
            start_date = max(
                price_range["min_date"],
                index_range["min_date"]
            )
            end_date = min(
                price_range["max_date"],
                index_range["max_date"]
            )
            
            print(f"理論的な開始日: {start_date}")
            print(f"  （価格データとインデックスデータが揃っている期間）")
            
            if fins_range:
                from datetime import datetime, timedelta
                try:
                    fins_min = datetime.strptime(fins_range["min_date"], "%Y-%m-%d")
                    effective_start = (fins_min + timedelta(days=5*365)).strftime("%Y-%m-%d")
                    print(f"\n実質的な開始日: {effective_start}")
                    print(f"  （過去5年の財務データが必要なため）")
                except:
                    pass
            
            print(f"\n終了日: {end_date}")
            print()
            print("注意事項:")
            print("  - listed_infoは過去のデータがなくても、最新のデータを使用してバックテスト可能")
            print("  - ただし、過去のセクター情報などが正確でない可能性がある")
            print("  - 財務データは過去5年分が必要なため、実質的な開始日は上記より遅くなる")


if __name__ == "__main__":
    main()


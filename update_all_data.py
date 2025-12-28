"""
APIから取得している各種テーブル情報を最新の情報に一括で更新するスクリプト

使用方法:
    python update_all_data.py                    # すべてのテーブルを最新まで更新
    python update_all_data.py --target prices    # 価格データのみ更新
    python update_all_data.py --target fins      # 財務データのみ更新
    python update_all_data.py --target listed    # 銘柄情報のみ更新
    python update_all_data.py --start 2024-01-01 --end 2024-12-31  # 指定期間を更新
"""

import argparse
import sys
from datetime import datetime, timedelta
from typing import Optional

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.infra.jquants import JQuantsClient
from src.omanta_3rd.ingest.listed import ingest_listed_info
from src.omanta_3rd.ingest.prices import ingest_prices
from src.omanta_3rd.ingest.fins import ingest_financial_statements
from src.omanta_3rd.ingest.indices import ingest_index_data, TOPIX_CODE
from src.omanta_3rd.portfolio.holdings import update_holding_performance, update_holdings_summary


def get_latest_date_from_table(table_name: str, date_column: str = "date") -> Optional[str]:
    """
    DBテーブルから最新の日付を取得
    
    Args:
        table_name: テーブル名
        date_column: 日付カラム名
        
    Returns:
        最新の日付（YYYY-MM-DD形式）、データがない場合はNone
    """
    with connect_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT MAX({date_column}) FROM {table_name}")
            result = cursor.fetchone()
            if result and result[0]:
                if isinstance(result[0], str):
                    return result[0]
                elif hasattr(result[0], 'strftime'):
                    return result[0].strftime("%Y-%m-%d")
                else:
                    return str(result[0])
            return None
        except Exception as e:
            print(f"警告: {table_name}テーブルから最新日付を取得できませんでした: {e}")
            return None


def calculate_date_range(
    table_name: str,
    date_column: str = "date",
    default_days: int = 30,
    end_date: Optional[str] = None
) -> tuple[str, str]:
    """
    更新に必要な日付範囲を計算
    
    Args:
        table_name: テーブル名
        date_column: 日付カラム名
        default_days: デフォルトの更新日数
        end_date: 終了日（Noneの場合は今日）
        
    Returns:
        (start_date, end_date) のタプル
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    latest_date = get_latest_date_from_table(table_name, date_column)
    
    if latest_date:
        # 最新日付の翌日から開始
        latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
        start_dt = latest_dt + timedelta(days=1)
        start_date = start_dt.strftime("%Y-%m-%d")
        
        # 開始日が終了日より後なら、デフォルト日数分を取得
        if start_dt.date() > datetime.strptime(end_date, "%Y-%m-%d").date():
            start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=default_days)
            start_date = start_dt.strftime("%Y-%m-%d")
    else:
        # データがない場合は、デフォルト日数分を取得
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=default_days)
        start_date = start_dt.strftime("%Y-%m-%d")
    
    return start_date, end_date


def update_listed_info(date: Optional[str] = None, client: Optional[JQuantsClient] = None):
    """銘柄情報を更新"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    if client is None:
        client = JQuantsClient()
    
    print("=" * 80)
    print("【銘柄情報の更新】")
    print(f"更新日: {date}")
    print("=" * 80)
    
    try:
        ingest_listed_info(date, client)
        print("✅ 銘柄情報の更新が完了しました。")
        return True
    except Exception as e:
        print(f"❌ 銘柄情報の更新中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_prices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    client: Optional[JQuantsClient] = None,
    auto_calculate: bool = True
):
    """価格データを更新"""
    if client is None:
        client = JQuantsClient()
    
    if start_date is None or end_date is None:
        if auto_calculate:
            start_date, end_date = calculate_date_range("prices_daily", "date", default_days=30, end_date=end_date)
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print("=" * 80)
    print("【価格データの更新】")
    print(f"期間: {start_date} ～ {end_date}")
    
    # 日数計算
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end_dt - start_dt).days + 1
    print(f"更新日数: {days}日")
    print("=" * 80)
    
    try:
        ingest_prices(start_date, end_date, client=client)
        print("✅ 価格データの更新が完了しました。")
        return True
    except Exception as e:
        print(f"❌ 価格データの更新中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_financials(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    client: Optional[JQuantsClient] = None,
    auto_calculate: bool = True
):
    """財務データを更新"""
    if client is None:
        client = JQuantsClient()
    
    if start_date is None or end_date is None:
        if auto_calculate:
            start_date, end_date = calculate_date_range("fins_statements", "disclosed_date", default_days=90, end_date=end_date)
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
    
    print("=" * 80)
    print("【財務データの更新】")
    print(f"期間: {start_date} ～ {end_date}")
    
    # 日数計算
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end_dt - start_dt).days + 1
    print(f"更新日数: {days}日")
    print("=" * 80)
    
    try:
        ingest_financial_statements(date_from=start_date, date_to=end_date, client=client)
        print("✅ 財務データの更新が完了しました。")
        return True
    except Exception as e:
        print(f"❌ 財務データの更新中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_indices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    client: Optional[JQuantsClient] = None,
    auto_calculate: bool = True,
    index_code: str = TOPIX_CODE,
):
    """指数データ（TOPIXなど）を更新"""
    if client is None:
        client = JQuantsClient()
    
    if start_date is None or end_date is None:
        if auto_calculate:
            start_date, end_date = calculate_date_range("index_daily", "date", default_days=30, end_date=end_date)
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print("=" * 80)
    print(f"【指数データの更新】 ({index_code})")
    print(f"期間: {start_date} ～ {end_date}")
    
    # 日数計算
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end_dt - start_dt).days + 1
    print(f"更新日数: {days}日")
    print("=" * 80)
    
    try:
        ingest_index_data(index_code, start_date, end_date, client=client)
        print(f"✅ 指数データ ({index_code}) の更新が完了しました。")
        return True
    except Exception as e:
        print(f"❌ 指数データ ({index_code}) の更新中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def main(
    target: str = "all",
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    auto_calculate: bool = True,
):
    """
    一括更新を実行
    
    Args:
        target: 更新対象（"all", "listed", "prices", "fins", "indices"）
        date: 更新日（銘柄情報用、YYYY-MM-DD）
        start_date: 開始日（価格・財務・指数データ用、YYYY-MM-DD）
        end_date: 終了日（価格・財務・指数データ用、YYYY-MM-DD）
        auto_calculate: 自動で日付範囲を計算するか
    """
    print("=" * 80)
    print("APIデータ一括更新スクリプト")
    print("=" * 80)
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"更新対象: {target}")
    print("=" * 80)
    print()
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    client = JQuantsClient()
    
    results = {}
    
    # 銘柄情報の更新
    if target in ["all", "listed"]:
        results["listed"] = update_listed_info(date, client)
        print()
    
    # 価格データの更新
    if target in ["all", "prices"]:
        results["prices"] = update_prices(start_date, end_date, client, auto_calculate)
        print()
    
    # 財務データの更新
    if target in ["all", "fins"]:
        results["fins"] = update_financials(start_date, end_date, client, auto_calculate)
        print()
    
    # 指数データの更新（TOPIX）
    if target in ["all", "indices"]:
        results["indices"] = update_indices(start_date, end_date, client, auto_calculate, TOPIX_CODE)
        print()
    
    # 保有銘柄のパフォーマンス更新（価格データ更新後に実行）
    if target in ["all", "prices", "holdings"]:
        try:
            from src.omanta_3rd.portfolio.holdings import update_holding_performance, update_holdings_summary
            
            update_holding_performance()
            update_holdings_summary()
            results["holdings"] = True
            print("✅ 保有銘柄のパフォーマンスを更新しました")
            print()
        except Exception as e:
            print(f"❌ 保有銘柄のパフォーマンス更新中にエラーが発生しました: {e}")
            results["holdings"] = False
            print()
    
    # 結果サマリー
    print("=" * 80)
    print("【更新結果サマリー】")
    print("=" * 80)
    for key, success in results.items():
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"{key}: {status}")
    print("=" * 80)
    
    # すべて成功した場合のみ正常終了
    if all(results.values()):
        print("すべての更新が正常に完了しました。")
        return 0
    else:
        print("一部の更新でエラーが発生しました。")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="APIから取得している各種テーブル情報を最新の情報に一括で更新",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # すべてのテーブルを最新まで更新（自動で日付範囲を計算）
  python update_all_data.py

  # 価格データのみ更新
  python update_all_data.py --target prices

  # 財務データのみ更新
  python update_all_data.py --target fins

  # 指数データ（TOPIX）のみ更新
  python update_all_data.py --target indices

  # 指定期間を更新
  python update_all_data.py --start 2024-01-01 --end 2024-12-31

  # 自動計算を無効にして、過去30日分を取得
  python update_all_data.py --no-auto-calculate
        """
    )
    
    parser.add_argument(
        "--target",
        type=str,
        choices=["all", "listed", "prices", "fins", "indices", "holdings"],
        default="all",
        help="更新対象（デフォルト: all）",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="更新日（銘柄情報用、YYYY-MM-DD、デフォルトは今日）",
    )
    parser.add_argument(
        "--start",
        type=str,
        dest="start_date",
        help="開始日（価格・財務データ用、YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        dest="end_date",
        help="終了日（価格・財務データ用、YYYY-MM-DD、デフォルトは今日）",
    )
    parser.add_argument(
        "--no-auto-calculate",
        action="store_true",
        help="自動で日付範囲を計算しない（デフォルトの日数分を取得）",
    )
    
    args = parser.parse_args()
    
    sys.exit(main(
        target=args.target,
        date=args.date,
        start_date=args.start_date,
        end_date=args.end_date,
        auto_calculate=not args.no_auto_calculate,
    ))








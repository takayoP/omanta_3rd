"""ETL更新ジョブ（API → DB）"""

import argparse
from datetime import datetime, timedelta
from typing import Optional

from ..infra.jquants import JQuantsClient
from ..ingest.listed import ingest_listed_info
from ..ingest.prices import ingest_prices
from ..ingest.fins import ingest_financial_statements
from ..config.settings import EXECUTION_DATE


def main(
    date: Optional[str] = None,
    update_listed: bool = True,
    update_prices: bool = True,
    update_financials: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    ETL更新を実行
    
    Args:
        date: 更新日（YYYY-MM-DD、Noneの場合は今日）
        update_listed: 銘柄情報を更新するか
        update_prices: 価格データを更新するか
        update_financials: 財務データを更新するか
        start_date: 開始日（YYYY-MM-DD、価格データ取得時に使用）
        end_date: 終了日（YYYY-MM-DD、価格データ取得時に使用）
    """
    if date is None:
        date = EXECUTION_DATE or datetime.now().strftime("%Y-%m-%d")
    
    print(f"ETL更新を開始します（日付: {date}）")
    
    client = JQuantsClient()
    
    if update_listed:
        print("銘柄情報を取得中...")
        ingest_listed_info(date, client)
        print("銘柄情報の取得が完了しました。")
    
    if update_prices:
        print("価格データを取得中...")
        if start_date and end_date:
            # 指定された日付範囲を使用
            ingest_prices(start_date, end_date, client=client)
        else:
            # 過去30日分を取得
            prices_start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
            ingest_prices(prices_start, date, client=client)
        print("価格データの取得が完了しました。")
    
    if update_financials:
        print("財務データを取得中...")
        # 過去90日分を取得
        date_from = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
        ingest_financial_statements(date_from, date, client=client)
        print("財務データの取得が完了しました。")
    
    print("ETL更新が完了しました。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL更新ジョブ（API → DB）")
    parser.add_argument(
        "--date",
        type=str,
        help="更新日（YYYY-MM-DD、デフォルトは今日）",
    )
    parser.add_argument(
        "--target",
        type=str,
        choices=["listed", "prices", "fins", "all"],
        default="all",
        help="更新対象（listed: 銘柄情報, prices: 価格データ, fins: 財務データ, all: すべて）",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="開始日（YYYY-MM-DD、価格データ取得時に使用）",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="終了日（YYYY-MM-DD、価格データ取得時に使用）",
    )
    
    args = parser.parse_args()
    
    update_listed = args.target in ["listed", "all"]
    update_prices = args.target in ["prices", "all"]
    update_financials = args.target in ["fins", "all"]
    
    main(
        date=args.date,
        update_listed=update_listed,
        update_prices=update_prices,
        update_financials=update_financials,
        start_date=args.start,
        end_date=args.end,
    )


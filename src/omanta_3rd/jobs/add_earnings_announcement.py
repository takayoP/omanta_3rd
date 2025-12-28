"""決算発表予定日を追加するジョブ"""

from __future__ import annotations

import argparse
from ..ingest.earnings_calendar import add_earnings_announcement


def main(
    code: str,
    announcement_date: str,
    period_type: str | None = None,
    period_end: str | None = None,
):
    """
    決算発表予定日を追加
    
    Args:
        code: 銘柄コード
        announcement_date: 決算発表予定日（YYYY-MM-DD）
        period_type: 期間種別（FY / 1Q / 2Q / 3Q）
        period_end: 当期末日（YYYY-MM-DD）
    """
    try:
        earnings = add_earnings_announcement(
            code=code,
            announcement_date=announcement_date,
            period_type=period_type,
            period_end=period_end,
        )
        print(f"決算発表予定日を追加しました:")
        print(f"  銘柄コード: {earnings['code']}")
        print(f"  発表予定日: {earnings['announcement_date']}")
        if earnings.get('period_type'):
            print(f"  期間種別: {earnings['period_type']}")
        if earnings.get('period_end'):
            print(f"  当期末日: {earnings['period_end']}")
    except Exception as e:
        print(f"エラー: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="決算発表予定日を追加するジョブ")
    parser.add_argument(
        "--code",
        type=str,
        required=True,
        help="銘柄コード",
    )
    parser.add_argument(
        "--announcement-date",
        type=str,
        required=True,
        help="決算発表予定日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--period-type",
        type=str,
        choices=["FY", "1Q", "2Q", "3Q"],
        help="期間種別（FY / 1Q / 2Q / 3Q）",
    )
    parser.add_argument(
        "--period-end",
        type=str,
        help="当期末日（YYYY-MM-DD）",
    )
    
    args = parser.parse_args()
    
    main(
        code=args.code,
        announcement_date=args.announcement_date,
        period_type=args.period_type,
        period_end=args.period_end,
    )


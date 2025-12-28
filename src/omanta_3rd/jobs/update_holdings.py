"""保有銘柄のパフォーマンス更新ジョブ"""

from __future__ import annotations

import argparse
from ..portfolio.holdings import update_holding_performance


def main(
    holding_id: int | None = None,
    as_of_date: str | None = None,
):
    """
    保有銘柄のパフォーマンスを更新
    
    Args:
        holding_id: 更新する保有銘柄のID（Noneの場合はすべての保有中の銘柄を更新）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
    """
    try:
        update_holding_performance(holding_id=holding_id, as_of_date=as_of_date)
        if holding_id:
            print(f"保有銘柄ID {holding_id} のパフォーマンスを更新しました")
        else:
            print("すべての保有中銘柄のパフォーマンスを更新しました")
    except Exception as e:
        print(f"エラー: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="保有銘柄のパフォーマンス更新ジョブ")
    parser.add_argument(
        "--holding-id",
        type=int,
        help="更新する保有銘柄のID（指定しない場合はすべての保有中の銘柄を更新）",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        help="評価日（YYYY-MM-DD、指定しない場合は最新の価格データを使用）",
    )
    
    args = parser.parse_args()
    
    main(
        holding_id=args.holding_id,
        as_of_date=args.as_of_date,
    )


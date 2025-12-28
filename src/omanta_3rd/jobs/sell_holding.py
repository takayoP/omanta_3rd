"""保有銘柄を売却するジョブ"""

from __future__ import annotations

import argparse
from ..portfolio.holdings import sell_holding


def main(
    holding_id: int,
    sell_date: str,
    sell_price: float | None = None,
):
    """
    保有銘柄を売却
    
    Args:
        holding_id: 保有銘柄のID
        sell_date: 売却日（YYYY-MM-DD）
        sell_price: 売却単価（Noneの場合は売却日の終値を使用）
    """
    try:
        sell_holding(
            holding_id=holding_id,
            sell_date=sell_date,
            sell_price=sell_price,
        )
        print(f"保有銘柄ID {holding_id} を売却しました")
        print(f"  売却日: {sell_date}")
        if sell_price:
            print(f"  売却単価: {sell_price}")
        else:
            print(f"  売却単価: 売却日の終値を使用")
    except Exception as e:
        print(f"エラー: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="保有銘柄を売却するジョブ")
    parser.add_argument(
        "--holding-id",
        type=int,
        required=True,
        help="保有銘柄のID",
    )
    parser.add_argument(
        "--sell-date",
        type=str,
        required=True,
        help="売却日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--sell-price",
        type=float,
        help="売却単価（指定しない場合は売却日の終値を使用）",
    )
    
    args = parser.parse_args()
    
    main(
        holding_id=args.holding_id,
        sell_date=args.sell_date,
        sell_price=args.sell_price,
    )


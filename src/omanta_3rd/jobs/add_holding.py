"""保有銘柄を追加するジョブ"""

from __future__ import annotations

import argparse
from ..portfolio.holdings import add_holding


def main(
    purchase_date: str,
    code: str,
    shares: float,
    purchase_price: float,
    broker: str | None = None,
):
    """
    保有銘柄を追加
    
    Args:
        purchase_date: 購入日（YYYY-MM-DD）
        code: 銘柄コード
        shares: 株数
        purchase_price: 購入単価
        broker: 証券会社名（例: "SBI証券", "大和証券"）
    """
    try:
        holding = add_holding(
            purchase_date=purchase_date,
            code=code,
            shares=shares,
            purchase_price=purchase_price,
            broker=broker,
        )
        print(f"保有銘柄を追加しました:")
        print(f"  購入日: {holding['purchase_date']}")
        print(f"  銘柄コード: {holding['code']}")
        print(f"  株数: {holding['shares']}")
        print(f"  購入単価: {holding['purchase_price']}")
        if holding.get('broker'):
            print(f"  証券会社: {holding['broker']}")
        print()
        print("パフォーマンスを更新するには以下のコマンドを実行してください:")
        print(f"  python -m src.omanta_3rd.jobs.update_holdings")
    except Exception as e:
        print(f"エラー: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="保有銘柄を追加するジョブ")
    parser.add_argument(
        "--purchase-date",
        type=str,
        required=True,
        help="購入日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--code",
        type=str,
        required=True,
        help="銘柄コード",
    )
    parser.add_argument(
        "--shares",
        type=float,
        required=True,
        help="株数",
    )
    parser.add_argument(
        "--purchase-price",
        type=float,
        required=True,
        help="購入単価",
    )
    parser.add_argument(
        "--broker",
        type=str,
        help="証券会社名（例: SBI証券, 大和証券）",
    )
    
    args = parser.parse_args()
    
    main(
        purchase_date=args.purchase_date,
        code=args.code,
        shares=args.shares,
        purchase_price=args.purchase_price,
        broker=args.broker,
    )

